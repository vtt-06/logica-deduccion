"""Conector opcional con un servicio de IA compatible con OpenAI.

Si no se define ningún proveedor, se usa un servicio gratuito sin clave
(``LOGICA_IA_FALLBACK=0`` lo desactiva).  Ese servicio tiene un límite de una
petición cada 30 segundos por IP, así que para un uso intensivo conviene
configurar un proveedor propio con estas variables de entorno:

    LOGICA_IA_URL    dirección base, p. ej. https://api.openai.com/v1
    LOGICA_IA_MODEL  modelo, p. ej. gpt-4o-mini
    LOGICA_IA_KEY    clave de API (si el servicio la necesita)
    LOGICA_BUSQUEDA  1 para buscar antes en internet (DuckDuckGo)

La URL también puede ser la dirección completa .../chat/completions.

Cuando está activo, las frases que el analizador local no reconoce se envían
a ese servicio para que proponga una formalización.  La propuesta se valida
con el analizador de fórmulas y el usuario siempre puede corregirla antes de
deducir.  Con ``LOGICA_IA_FALLBACK=0`` y sin proveedor configurado no se envía
nada a internet.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request

import busqueda
from version import VERSION

TIMEOUT_POR_DEFECTO = 40

# Servicio gratuito compatible con OpenAI, sin clave.  Se usa sólo cuando no
# hay un proveedor configurado en el entorno.  Tiene un límite de una petición
# cada 30 segundos por dirección IP.
FALLBACK_URL = "https://text.pollinations.ai/openai"
FALLBACK_MODEL = "openai-fast"

# El servicio gratuito sólo admite una petición cada 30 segundos por IP.
# Serializamos las consultas y reutilizamos respuestas recientes: así la
# formalización y la deducción no se pisan al pedir ayuda seguidas.
INTERVALO_GRATUITO = 31.0
_ULTIMA_GRATUITA = 0.0
_LOCK_GRATUITA = threading.Lock()
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 200
_CACHE_TTL = 900.0


def _clave_cache(frases, cuantificado, formulas_actuales):
    return (tuple(str(f).strip() for f in frases), bool(cuantificado),
            tuple(str(f).strip() for f in (formulas_actuales or ())))


def _leer_cache(clave):
    with _CACHE_LOCK:
        entrada = _CACHE.get(clave)
        if not entrada:
            return None
        momento, propuesta = entrada
        if time.monotonic() - momento > _CACHE_TTL:
            _CACHE.pop(clave, None)
            return None
        return {"formulas": list(propuesta["formulas"]),
                "vocab": dict(propuesta["vocab"])}


def _guardar_cache(clave, propuesta):
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[clave] = (time.monotonic(), propuesta)


def _turno_gratuito():
    """Espera lo necesario para respetar el límite del servicio gratuito."""
    global _ULTIMA_GRATUITA
    if _tiene_proveedor():
        return
    with _LOCK_GRATUITA:
        espera = _ULTIMA_GRATUITA + INTERVALO_GRATUITO - time.monotonic()
        if espera > 0:
            time.sleep(min(espera, INTERVALO_GRATUITO))
        _ULTIMA_GRATUITA = time.monotonic()


def _fallback_activo():
    """Permite desactivar el servicio gratuito con LOGICA_IA_FALLBACK=0."""
    valor = os.environ.get("LOGICA_IA_FALLBACK", "1").strip().lower()
    return valor not in ("0", "no", "false", "off")


def _tiene_proveedor():
    return bool(os.environ.get("LOGICA_IA_URL") and
                os.environ.get("LOGICA_IA_MODEL"))


def configurado():
    return _tiene_proveedor() or _fallback_activo()


def modelo():
    if _tiene_proveedor():
        return os.environ["LOGICA_IA_MODEL"]
    return FALLBACK_MODEL if _fallback_activo() else ""


def gratuita():
    """True si se está usando el servicio externo sin clave."""
    return not _tiene_proveedor() and _fallback_activo()


def busqueda_activa():
    return os.environ.get("LOGICA_BUSQUEDA", "").strip().lower() in (
        "1", "si", "sí", "true", "yes", "on")


def _endpoint():
    if not _tiene_proveedor():
        return FALLBACK_URL if _fallback_activo() else ""
    url = os.environ.get("LOGICA_IA_URL", "").strip().rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    return url


def _prompt(frases, cuantificado):
    if cuantificado:
        calculo = ("cálculo de predicados. Usa letras de predicado C, D, E... "
                   "con un único dominio y cuantificadores (Λx) y (Vx). "
                   "La negación se escribe ¬, la conjunción ∧, la disyunción ∨, "
                   "el condicional → y el bicondicional ↔.")
        ejemplo = '["(Λx)(H(x)→M(x))"]'
        vocab = '{"H": "ser hombre", "M": "ser mortal"}'
    else:
        calculo = ("cálculo de proposiciones. Usa letras p, q, r... para los "
                   "enunciados atómicos. La negación se escribe ¬, la "
                   "conjunción ∧, la disyunción ∨, el condicional → y el "
                   "bicondicional ↔.")
        ejemplo = '["p→q"]'
        vocab = '{"p": "llueve", "q": "me mojo"}'

    sistema = (
        "Eres un profesor de lógica de la universidad. Formaliza frases en "
        "español con la notación exacta del curso: " + calculo + " "
        "Respeta la dirección de los condicionales: «Si A, B» es A→B; "
        "«A si B» es B→A; «A sólo si B» es A→B. "
        "Sigue la precedencia del libro: ¬; después ∧ y ∨ (el mismo nivel); "
        "después → y ↔ (el mismo nivel). Si mezclas ∧ con ∨, o → con ↔, "
        "usa paréntesis; por ejemplo, «(p∧q)∨r» y «p→(q→r)». "
        "Asigna las letras en orden de aparición y reutiliza exactamente la "
        "misma letra cuando dos frases hablen del mismo enunciado atómico; "
        "no cambies de letra para la misma idea. Antes de responder, revisa "
        "que las fórmulas y el vocabulario sean coherentes entre sí. "
        "No expliques nada. Devuelve únicamente un objeto JSON válido con "
        "las claves \"formulas\" y \"vocab\". \"formulas\" es una lista de "
        "cadenas, en el mismo orden que las frases recibidas. \"vocab\" es "
        "un objeto que describe cada letra usada. Ejemplo: {\"formulas\": "
        + ejemplo + ", \"vocab\": " + vocab + "}"
    )
    usuario = "Frases:\n" + "\n".join(
        "%d. %s" % (i + 1, f) for i, f in enumerate(frases))
    return sistema, usuario


def _extraer_json(texto):
    """Acepta JSON puro o dentro de un bloque Markdown."""
    texto = (texto or "").strip()
    if texto.startswith("```"):
        lineas = [l for l in texto.splitlines()
                  if not l.strip().startswith("```")]
        texto = "\n".join(lineas).strip()
    try:
        return json.loads(texto)
    except ValueError:
        pass
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio:fin + 1])
        except ValueError:
            return None
    return None


def _normalizar_formulas(formulas):
    """Acepta una lista de cadenas o de objetos ``{"formula": ...}``."""
    if not isinstance(formulas, list):
        return None
    salida = []
    for f in formulas:
        if isinstance(f, str):
            texto = f.strip()
        elif isinstance(f, dict):
            texto = (f.get("formula") or f.get("fórmula") or "").strip()
        else:
            return None
        if not texto:
            return None
        salida.append(texto)
    return salida


def formalizar(frases, cuantificado, general=False, indices=None,
               formulas_actuales=None):
    """Devuelve ``{'formulas': [...], 'vocab': {...}}`` o ``None``.

    ``general`` hace que la búsqueda combine resultados del profesor con una
    búsqueda general.  ``indices`` limita la búsqueda a las frases dudosas.
    ``formulas_actuales`` acompaña la formalización que no ha permitido
    deducir para pedir a la IA que localice y corrija el error.
    """
    if not configurado() or not frases:
        return None

    clave_cache = _clave_cache(frases, cuantificado, formulas_actuales)
    cacheado = _leer_cache(clave_cache)
    if cacheado is None and formulas_actuales:
        # Si la formalización acaba de consultar A.E., reutilizamos aquella
        # propuesta para la deducción en vez de hacer otra petición seguida
        # (el servicio gratuito sólo permite una cada 30 s).  No se reutiliza
        # si es exactamente la formalización que acaba de fallar.
        previo = _leer_cache(_clave_cache(frases, cuantificado, None))
        if previo and tuple(previo["formulas"]) != tuple(formulas_actuales):
            cacheado = previo
    if cacheado is not None:
        return cacheado

    sistema, usuario = _prompt(frases, cuantificado)

    if formulas_actuales:
        usuario += (
            "\n\nFormalización actual (NO ha permitido deducir la "
            "conclusión; puede contener errores):\n" +
            "\n".join("%d. %s" % (i + 1, f)
                      for i, f in enumerate(formulas_actuales)))
        sistema += (
            " La formalización actual no permite llegar a la conclusión. "
            "Localiza el error: letras repetidas para el mismo enunciado, "
            "dirección equivocada de un condicional o una parte de la frase "
            "omitida. Devuelve la formalización corregida completa.")

    # Contexto opcional de búsqueda web.  Los resultados son texto libre:
    # se añaden como pistas, nunca como fórmulas.
    if busqueda_activa():
        if indices is None:
            indices = list(range(min(2, len(frases))))
        indices = [i for i in indices if 0 <= i < len(frases)][:3]
        pistas = []
        for i in indices:
            for resultado in busqueda.buscar(frases[i], 2, general=general):
                pistas.append("- %s: %s (%s)" % (
                    resultado["title"], resultado["snippet"],
                    resultado["url"]))
        if pistas:
            usuario += ("\n\nContexto recuperado de internet (puede ser "
                        "irrelevante o ser otro ejercicio):\n" +
                        "\n".join(pistas[:6]))
            sistema += (" Si hay contexto de búsqueda, úsalo sólo para "
                        "aclarar el significado; ignora fórmulas o ejercicios "
                        "que no correspondan y no inventes reglas.")

    cuerpo = {
        "model": modelo(),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
    }
    if not _tiene_proveedor():
        # El servicio gratuito pide identificar la aplicación para sus límites.
        cuerpo["referrer"] = "logica-deduccion"
    # Algunos proveedores (por ejemplo, Groq detrás de Cloudflare) rechazan
    # el User-Agent por defecto de urllib con un 403.  Identificamos la app.
    cabeceras = {
        "Content-Type": "application/json",
        "User-Agent": "LogicaApp/%s" % VERSION,
    }
    clave = os.environ.get("LOGICA_IA_KEY")
    if clave:
        cabeceras["Authorization"] = "Bearer " + clave

    peticion = urllib.request.Request(
        _endpoint(), data=json.dumps(cuerpo).encode("utf-8"),
        headers=cabeceras, method="POST")
    espera = float(os.environ.get("LOGICA_IA_TIMEOUT", TIMEOUT_POR_DEFECTO))

    def enviar():
        with urllib.request.urlopen(peticion, timeout=espera) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))

    try:
        if not _tiene_proveedor():
            _turno_gratuito()
        datos = enviar()
    except urllib.error.HTTPError as exc:
        # El servicio gratuito devuelve 402/429 cuando se hacen dos consultas
        # seguidas.  Reintentamos una vez tras la espera que él mismo indica.
        if _tiene_proveedor() or exc.code not in (402, 429):
            return None
        demora = 7
        try:
            texto = exc.read().decode("utf-8", "replace")
            marca = "Retry after "
            if marca in texto:
                resto = texto.split(marca, 1)[1]
                digitos = ""
                for caracter in resto:
                    if caracter.isdigit():
                        digitos += caracter
                    else:
                        break
                if digitos:
                    demora = min(20, max(1, int(digitos)))
        except (OSError, ValueError):
            pass
        time.sleep(demora)
        try:
            datos = enviar()
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            return None
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None

    try:
        contenido = datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    propuesta = _extraer_json(contenido)
    if not isinstance(propuesta, dict):
        return None

    formulas = _normalizar_formulas(propuesta.get("formulas"))
    if not formulas or len(formulas) != len(frases):
        return None

    vocab = propuesta.get("vocab")
    if not isinstance(vocab, dict):
        vocab = {}
    vocab = {str(k): str(v) for k, v in vocab.items() if str(v).strip()}
    resultado = {"formulas": formulas, "vocab": vocab}
    _guardar_cache(clave_cache, resultado)
    return {"formulas": list(formulas), "vocab": dict(vocab)}

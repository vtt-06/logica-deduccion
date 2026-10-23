"""Conector opcional con un servicio de IA compatible con OpenAI.

Está desactivado por defecto: sólo se usa si se han definido estas variables
de entorno al arrancar la aplicación:

    LOGICA_IA_URL    dirección base, p. ej. https://api.openai.com/v1
    LOGICA_IA_MODEL  modelo, p. ej. gpt-4o-mini
    LOGICA_IA_KEY    clave de API (si el servicio la necesita)
    LOGICA_BUSQUEDA  1 para buscar antes en internet (DuckDuckGo)

La URL también puede ser la dirección completa .../chat/completions.

Cuando está activo, las frases que el analizador local no reconoce se envían
a ese servicio para que proponga una formalización.  La propuesta se valida
con el analizador de fórmulas y el usuario siempre puede corregirla antes de
deducir.  Si no hay variables de entorno, no se envía nada a internet.
"""

import json
import os
import urllib.error
import urllib.request

import busqueda
from version import VERSION

TIMEOUT_POR_DEFECTO = 20


def configurado():
    return bool(os.environ.get("LOGICA_IA_URL") and
                os.environ.get("LOGICA_IA_MODEL"))


def busqueda_activa():
    return os.environ.get("LOGICA_BUSQUEDA", "").strip().lower() in (
        "1", "si", "sí", "true", "yes", "on")


def _endpoint():
    url = os.environ.get("LOGICA_IA_URL", "").strip().rstrip("/")
    if not url:
        return ""
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


def formalizar(frases, cuantificado, general=False, indices=None):
    """Devuelve ``{'formulas': [...], 'vocab': {...}}`` o ``None``.

    ``general`` hace que la búsqueda combine resultados del profesor con una
    búsqueda general.  ``indices`` limita la búsqueda a las frases dudosas.
    """
    if not configurado() or not frases:
        return None

    sistema, usuario = _prompt(frases, cuantificado)

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
        "model": os.environ["LOGICA_IA_MODEL"],
        "temperature": 0,
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
    }
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
    try:
        with urllib.request.urlopen(
                peticion, timeout=float(os.environ.get(
                    "LOGICA_IA_TIMEOUT", TIMEOUT_POR_DEFECTO))) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
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
    return {"formulas": formulas, "vocab": vocab}

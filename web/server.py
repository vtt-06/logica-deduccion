"""Servidor web de la aplicación de lógica.

Uso:
    python3 web/server.py            # http://localhost:8000
    python3 web/server.py --port 9000

El servidor escucha en 0.0.0.0, así que también se puede abrir desde el móvil
o la tablet usando la dirección IP del ordenador en la misma red WiFi.
"""

import argparse
import errno
import hashlib
import json
import mimetypes
import os
import re
import socket
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

from formulas import F, parse_formula, render, atoms       # noqa: E402
from prover import prove                                  # noqa: E402
from tablas_verdad import generar_tabla                   # noqa: E402
import formalize as fz                                    # noqa: E402
from aprendizaje import Aprendizaje                       # noqa: E402
from version import VERSION                               # noqa: E402
import asistente_ia                                       # noqa: E402
from main import NOMBRE_LIBRO, _cita, formato_libro       # noqa: E402

ESTATICOS = RAIZ / "static"
MAX_CUERPO = 1_000_000


def _cargar_config_ia():
    """Carga web/config_ia.env sin sobrescribir el entorno del sistema."""
    ruta = os.environ.get("LOGICA_IA_CONFIG") or str(RAIZ / "config_ia.env")
    try:
        with open(ruta, encoding="utf-8") as fh:
            lineas = fh.readlines()
    except OSError:
        return
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        if clave.startswith("export "):
            clave = clave[7:].strip()
        if not clave.startswith("LOGICA_"):
            continue
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(clave, valor)


_cargar_config_ia()


# Almacén compartido por todas las peticiones.  Guarda el banco de frases y
# los ejercicios.
MEMORIA = Aprendizaje()
# El aprendizaje está siempre activo: los ejercicios deducidos alimentan el
# banco y las plantillas que se reutilizan en ejercicios parecidos.
APRENDIZAJE = MEMORIA


def _sembrar_banco():
    """Añade al banco los ejemplos que falten.

    El almacenamiento de Render es efímero: al reiniciar el servicio se pierde
    ``aprendizaje.json``.  Sin esta semilla, el banco aparecería vacío en cada
    arranque y parecería que no se guarda nada.  Las frases que ya existen no
    se tocan: sólo se añaden las que falten, sin pisar correcciones del usuario.
    """
    ruta = RAIZ.parent / "banco_ejemplos.json"
    try:
        with ruta.open(encoding="utf-8") as fh:
            ejemplos = json.load(fh)
    except (OSError, ValueError):
        return 0
    if not isinstance(ejemplos, list):
        return 0
    sembradas = 0
    for ejemplo in ejemplos:
        if not isinstance(ejemplo, dict):
            continue
        try:
            cuantificado = ejemplo.get("calculus") == "pred"
            if MEMORIA.tiene_frase(ejemplo.get("texto", ""), cuantificado):
                continue
            if MEMORIA.registrar_frase(
                    ejemplo.get("texto", ""), ejemplo.get("formula", ""),
                    ejemplo.get("vocab") or {},
                    ejemplo.get("calculus") == "pred",
                    ejemplo.get("fuente") or "ejemplo",
                    confirmada=True):
                sembradas += 1
        except Exception:
            continue
    return sembradas


_sembrar_banco()
# Recupera patrones de los ejercicios y ejemplos guardados en arranques
# anteriores, para que la memoria no empiece de cero.
MEMORIA.aprender_de_banco()
MEMORIA.aprender_de_ejercicios()


# ==========================================================================
# Formalización
# ==========================================================================
def _frases(data):
    crudas = data.get("sentences", [])
    if not isinstance(crudas, list):
        return []
    return [str(x).strip() for x in crudas if str(x).strip()]


_TIEMPO_INICIAL = {"hoy", "ayer", "manana", "ahora", "actualmente"}


def _raiz_infinitivo(palabra):
    """Une la raíz verbal con su infinitivo («moj» / «mojar»)."""
    if len(palabra) >= 5 and palabra.endswith(("ar", "er", "ir")):
        return palabra[:-2]
    return palabra


def _clave_atomo(texto):
    """Clave para reconocer el mismo enunciado escrito de otra forma.

    Usa la normalización del analizador, que reduce los verbos a su raíz: así
    «Llovió mucho en el pueblo» y «Lloverá mucho en el pueblo» son el mismo
    átomo.  Además ignora mayúsculas, acentos, el orden de las palabras y los
    adverbios de tiempo iniciales («Hoy es viernes» / «es viernes»).
    """
    normal = fz._norm(str(texto))
    palabras = re.findall(r"[a-z0-9]+", normal)
    while palabras and palabras[0] in _TIEMPO_INICIAL:
        palabras.pop(0)
    if palabras[:3] == ["en", "este", "momento"]:
        palabras = palabras[3:]
    palabras = [_raiz_infinitivo(p) for p in palabras]
    return " ".join(sorted(palabras))


def _remapa_atomos(formula, mapa):
    """Sustituye letras de átomo manteniendo la estructura de la fórmula."""
    if not mapa:
        return formula
    if formula.kind == "var":
        return F.var(mapa.get(formula.data, formula.data))
    if formula.kind == "pred":
        return F.pred(mapa.get(formula.data, formula.data), formula.term)
    if formula.kind in ("forall", "exists"):
        return F(formula.kind, formula.data,
                 (_remapa_atomos(formula.children[0], mapa),))
    return F(formula.kind, formula.data,
             tuple(_remapa_atomos(c, mapa) for c in formula.children))


def _unificar_atomos(items, formulas, form, quantified):
    """Da la misma letra a descripciones equivalentes del mismo ejercicio.

    El analizador trabaja frase a frase, así que a veces usa letras distintas
    para el mismo enunciado.  Sin esta unificación, la deducción falla aunque
    el razonamiento sea correcto.
    """
    textos = {t.letter: t.text.strip(" ,.") for t in form.vocab}
    grupos = {}
    orden = []
    for formula in formulas:
        for atomo in atoms(formula):
            letra = atomo.data
            if letra in grupos or letra not in textos:
                continue
            clave = _clave_atomo(textos[letra])
            if not clave:
                continue
            orden.append(letra)
            grupos.setdefault(clave, []).append(letra)

    mapa = {}
    for clave in grupos:
        letras = grupos[clave]
        if len(letras) < 2:
            continue
        destino = letras[0]
        for letra in letras[1:]:
            mapa[letra] = destino
        # Conservamos la descripción más completa como texto del grupo.
        mejor = max((textos[l] for l in letras), key=len)
        textos[destino] = mejor

    if not mapa:
        return formulas, _sugerencias_vocabulario(form, formulas, quantified)

    nuevas = [_remapa_atomos(f, mapa) for f in formulas]
    for item, formula in zip(items, nuevas):
        item["formula"] = render(formula)
    return nuevas, _vocab_con_textos(nuevas, textos, None, quantified)


def _sugerencias_vocabulario(form, formulas, quantified):
    usadas = set()
    for f in formulas:
        for a in atoms(f):
            usadas.add(a.data)

    orden, vistos = [], set()
    for t in form.vocab:
        if t.letter in usadas and t.letter not in vistos:
            vistos.add(t.letter)
            orden.append(t.letter)
    for f in formulas:
        for a in atoms(f):
            if a.data not in vistos:
                vistos.add(a.data)
                orden.append(a.data)

    vocab = []
    for t in form.vocab:
        if t.letter in usadas:
            texto = t.text.strip(" ,.")
            if texto:
                vocab.append({"letter": t.letter, "text": texto})
    for letter in orden:
        if not any(v["letter"] == letter for v in vocab):
            vocab.append({"letter": letter, "text": ""})
    return vocab


def _vocab_con_textos(formulas, textos, form, quantified):
    """Vocabulario ordenado por aparición, mezclando textos de la IA y locales."""
    locales = ({t.letter: t.text.strip(" ,.") for t in form.vocab}
               if form is not None else {})
    orden, vistos = [], set()
    for f in formulas:
        for a in atoms(f):
            if a.data not in vistos:
                vistos.add(a.data)
                orden.append(a.data)
    vocab = []
    for letra in orden:
        texto = (textos.get(letra) or locales.get(letra) or "").strip()
        if quantified and texto and not texto.lower().startswith(
                ("ser ", "estar ")):
            texto = "ser " + texto
        vocab.append({"letter": letra, "text": texto})
    return vocab


def api_formalizar(data):
    frases = _frases(data)
    if len(frases) < 2:
        return {"ok": False,
                "error": "Escribe al menos una premisa y la conclusión."}

    # La conclusión puede venir marcada con «Por tanto», «Por consiguiente»…
    # aunque el usuario no haya escrito «=>».  Se coloca al final para que la
    # deducción la use como meta, sin depender del orden de las líneas.
    indices = [i for i, frase in enumerate(frases)
               if fz.tiene_marcador_conclusion(frase)]
    if indices:
        elegida = indices[-1]
        if elegida != len(frases) - 1:
            frases = (frases[:elegida] + frases[elegida + 1:] +
                      [frases[elegida]])

    quantified = data.get("calculus") == "pred"
    forzar_ia = bool(data.get("force_ai"))
    form = fz.Formalyzer(quantified, APRENDIZAJE)
    items, formulas = [], []
    for i, frase in enumerate(frases):
        formula = None
        confianza, motivo_confianza = "alta", ""
        try:
            formula = form.formalize(frase)
            confianza = form.confianza
            motivo_confianza = form.motivo_confianza
        except Exception:
            traceback.print_exc()
            confianza = "baja"
            motivo_confianza = "No se ha podido analizar la frase."
        fuente = form.fuente
        rol = "premisa" if i < len(frases) - 1 else "conclusion"
        # (la conclusión marcada ya se ha movido al final)
        items.append({
            "text": frase,
            "role": rol,
            "formula": render(formula) if formula is not None else "",
            "ok": formula is not None,
            "source": fuente,
            "confianza": confianza,
            "motivo_confianza": motivo_confianza,
        })
        if formula is not None:
            formulas.append(formula)

    if len(formulas) == len(frases):
        formulas, vocab = _unificar_atomos(
            items, formulas, form, quantified)
    else:
        vocab = []

    # Si el analizador local no ha reconocido alguna frase (o el usuario pide
    # expresamente una segunda opinión), se pide una propuesta completa a la
    # IA.  La decisión de enviar las frases es del usuario: hay que definir
    # las variables de entorno LOGICA_IA_* expresamente.
    ia_aplicada = False
    aviso_ia = ""
    # Una frase puede ser un átomo legítimo («Llueve») o puede haber quedado
    # como átomo porque el analizador no ha entendido su estructura.  En el
    # segundo caso se consulta la IA aunque la fórmula local sea válida.
    def necesita_ia(item):
        if not item["ok"]:
            return True
        if item["confianza"] != "baja":
            return False
        # Una variante verbal («podrás» / «puedes») es una duda léxica, no
        # una estructura que el analizador haya dejado sin interpretar.  No
        # se consulta la IA por eso: se mantiene la fórmula local y se avisa
        # para que el usuario la revise.
        motivo = (item.get("motivo_confianza") or "").lower()
        return "estructura" in motivo or "analizar" in motivo

    indices_ia = [i for i, item in enumerate(items) if necesita_ia(item)]
    motivo_ia = "manual" if forzar_ia else ("baja_confianza" if indices_ia else "")
    if (forzar_ia or indices_ia) and asistente_ia.configurado():
        indices_busqueda = (list(range(min(3, len(frases)))) if forzar_ia
                            else indices_ia[:3])
        propuesta = asistente_ia.formalizar(
            frases, quantified,
            general=forzar_ia or bool(indices_ia),
            indices=indices_busqueda)
        if propuesta:
            nuevas, validas = [], True
            for texto in propuesta["formulas"]:
                try:
                    nuevas.append(parse_formula(texto))
                except Exception:
                    validas = False
                    break
            if validas and len(nuevas) == len(frases):
                formulas = nuevas
                ia_aplicada = True
                if forzar_ia:
                    aviso_ia = (
                        "La ayuda exterior (A.E.) ha revisado las frases y ha "
                        "propuesto esta formalización. Compruébala antes de "
                        "deducir.")
                for i, item in enumerate(items):
                    item["formula"] = render(nuevas[i])
                    item["ok"] = True
                    item["source"] = "ia"
                    item["confianza"] = "alta"
                    item["motivo_confianza"] = ""
                vocab = _vocab_con_textos(nuevas, propuesta.get("vocab") or {},
                                          form, quantified)
            elif forzar_ia:
                aviso_ia = ("La ayuda exterior (A.E.) no ha devuelto fórmulas "
                            "válidas; se mantiene la formalización local. "
                            "Revísala o corrígela a mano.")
            elif indices_ia:
                aviso_ia = ("La ayuda exterior (A.E.) no ha devuelto fórmulas "
                            "válidas para las frases marcadas; se mantiene la "
                            "formalización local.")
        elif forzar_ia:
            aviso_ia = ("No se ha podido consultar la ayuda exterior (A.E.). "
                        "Se mantiene la formalización local; revisa la conexión "
                        "o la clave.")
        elif indices_ia:
            aviso_ia = ("No se ha podido consultar la ayuda exterior (A.E.) "
                        "para las frases marcadas; se mantiene la formalización "
                        "local. Puedes corregirlas a mano.")

    banco_guardadas = _registrar_banco_frases(items, vocab, quantified)

    return {"ok": True, "items": items, "vocab": vocab,
            "ia_aplicada": ia_aplicada, "aviso_ia": aviso_ia,
            "motivo_ia": motivo_ia, "banco_guardadas": banco_guardadas,
            "calculus": "pred" if quantified else "prop"}


# ==========================================================================
# Prueba y explicaciones
# ==========================================================================
def _lista_nums(nums):
    nums = list(nums)
    if not nums:
        return ""
    if len(nums) == 1:
        return "la línea %d" % nums[0]
    return "las líneas %s" % ", ".join(str(n) for n in nums[:-1]) + \
        " y %d" % nums[-1]


def _t(n, refs):
    """Texto de la fórmula de la línea `n` (si está entre las citadas)."""
    return refs.get(n, "")


def explicar(ln, nombre, refs, total):
    """Explicación didáctica de una línea de la deducción."""
    f = render(ln.formula)
    j = list(ln.just)

    if ln.rule == "PREM":
        return "Es una de las premisas del ejercicio; se toma tal cual."

    if ln.hyp:
        return ("Se abre una subdemostración suponiendo «%s». Al final se "
                "cerrará con TD (si se demuestra una implicación) o con Abs "
                "(si se llega a una contradicción)." % f)

    if nombre == "MP" and len(j) >= 2:
        return ("En %s tenemos «%s» y en %s tenemos «%s». El modus ponens "
                "(MP) dice que de A→B y A se sigue B; aquí B es «%s»."
                % (_lista_nums(j[:1]), _t(j[0], refs),
                   _lista_nums(j[1:2]), _t(j[1], refs), f))

    if nombre == "MT" and len(j) >= 2:
        return ("En %s tenemos «%s» y en %s tenemos «%s». El modus tollens "
                "(MT) dice que de A→B y ¬B se sigue ¬A; aquí se concluye "
                "«%s»." % (_lista_nums(j[:1]), _t(j[0], refs),
                           _lista_nums(j[1:2]), _t(j[1], refs), f))

    if nombre == "SH" and len(j) >= 2:
        return ("El silogismo hipotético (SH) encadena las implicaciones de "
                "%s y %s: si A→B y B→C, entonces A→C. Se obtiene «%s»."
                % (_lista_nums(j[:1]), _lista_nums(j[1:2]), f))

    if ln.rule.startswith("Simp") and j:
        return ("La conjunción de %s («%s») permite quedarse con uno de sus "
                "componentes mediante simplificación: «%s»."
                % (_lista_nums(j), _t(j[0], refs), f))

    if ln.rule == "DC" and j:
        return ("De la conjunción «%s» (%s) se sigue la disyunción de dos de "
                "sus componentes: «%s». Es un paso abreviado de "
                "simplificación más adición." % (_t(j[0], refs),
                                                 _lista_nums(j), f))

    if nombre == "IC" and len(j) >= 2:
        return ("Con «%s» (%s) y «%s» (%s) se forma su conjunción: «%s»."
                % (_t(j[0], refs), _lista_nums(j[:1]), _t(j[1], refs),
                   _lista_nums(j[1:2]), f))

    if nombre == "Ad" and j:
        return ("Por adición, de «%s» (%s) se sigue la disyunción «%s»: "
                "basta con que se cumpla uno de los dos términos."
                % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "SD" and len(j) >= 2:
        return ("Tenemos la disyunción «%s» en %s y la negación de uno de sus "
                "términos en %s. El silogismo disyuntivo (SD) concluye el "
                "otro término: «%s»."
                % (_t(j[0], refs), _lista_nums(j[:1]), _lista_nums(j[1:]),
                   f))

    if nombre == "Dil" and len(j) >= 3:
        return ("Análisis de casos (dilema): la disyunción «%s» de la línea %d "
                "cubre dos posibilidades; en %s se prueba que la primera lleva "
                "a «%s» y en %s que la segunda lleva a «%s». En ambos casos "
                "se llega a «%s»."
                % (_t(j[0], refs), j[0], _lista_nums(j[1:2]),
                   _t(j[1], refs), _lista_nums(j[3:4]) if len(j) > 3 else "",
                   _t(j[3], refs) if len(j) > 3 else "", f))

    if nombre == "DI1" and j:
        return ("Por la primera definición del implicador, «%s» (%s) equivale "
                "a decir que no se da a la vez el antecedente y la negación "
                "del consecuente: «%s»." % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "DI2" and j:
        return ("Por la segunda definición del implicador, «%s» (%s) equivale "
                "a «%s»: o no se cumple el antecedente, o se cumple el "
                "consecuente." % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "DM1" and j:
        return ("Ley de De Morgan: la negación de la conjunción «%s» (%s) "
                "equivale a la disyunción de las negaciones: «%s»."
                % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "DM2" and j:
        return ("Ley de De Morgan: la negación de la disyunción «%s» (%s) "
                "equivale a la conjunción de las negaciones: «%s»."
                % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "DN" and j:
        return ("Doble negación: de «%s» (%s) se sigue «%s»; dos negaciones "
                "se anulan." % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "IDN" and j:
        return ("Introducción de la doble negación: de «%s» (%s) se sigue "
                "«%s»." % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "Cp" and j:
        return ("Contraposición: «%s» (%s) equivale a «%s» (se niegan "
                "antecedente y consecuente y se invierte la implicación)."
                % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "Abs" and len(j) >= 2:
        return ("Dentro del supuesto de la línea %d se llega a una "
                "contradicción en la línea %d: «%s». Por absorción (Abs) se "
                "cierra la subdemostración y se concluye «%s»."
                % (j[0], j[1], _t(j[1], refs), f))

    if nombre == "TD" and len(j) >= 2:
        return ("Teorema de deducción: en la subdemostración %d-%d se parte "
                "del supuesto «%s» y se llega a «%s». Por tanto, queda "
                "demostrada la implicación «%s»."
                % (j[0], j[1], _t(j[0], refs), _t(j[1], refs), f))

    if nombre == "EG" and j:
        return ("Eliminación del generalizador: de «%s» (%s) se sigue «%s» "
                "para un término cualquiera. Si vale para todos, vale para "
                "uno cualquiera." % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "IG" and j:
        return ("Introducción del generalizador: como «%s» (%s) se ha "
                "obtenido para un término arbitrario, vale para todos: «%s»."
                % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "EP" and j:
        return ("Eliminación del particularizador: de «%s» (%s) se sigue "
                "«%s» para un término nuevo. Si existe alguno que cumple P, "
                "podemos darle un nombre." % (_t(j[0], refs), _lista_nums(j), f))

    if nombre == "IP" and j:
        return ("Introducción del particularizador: de «%s» (%s) se sigue "
                "«%s»: si hay un caso concreto, entonces existe alguno."
                % (_t(j[0], refs), _lista_nums(j), f))

    if ln.rule in ("EI1", "EI2") and j:
        return ("Eliminación del coimplicador: de «%s» (%s) se sigue una de "
                "las dos implicaciones que contiene: «%s»."
                % (_t(j[0], refs), _lista_nums(j), f))

    if ln.rule == "Dil1" and j:
        return ("Paso abreviado de dilema a partir de «%s» (%s): «%s»."
                % (_t(j[0], refs), _lista_nums(j), f))

    # último recurso, pero siempre explicativo
    if j:
        return ("Se aplica la regla %s a %s y se obtiene «%s»."
                % (nombre, _lista_nums(j), f))
    return "Se obtiene «%s» aplicando la regla %s." % (f, nombre)


def _registrar_confirmadas(data, formulas):
    """Guarda las frases de un ejercicio que acaba de deducirse bien."""
    if APRENDIZAJE is None:
        return 0
    frases = data.get("sentences")
    vocab = data.get("vocab")
    if not isinstance(frases, list) or len(frases) != len(formulas):
        return 0
    if not isinstance(vocab, dict):
        return 0
    cuantificado = any(a.kind == "pred" for f in formulas for a in atoms(f))
    guardadas = 0
    for frase, formula in zip(frases, formulas):
        letras = {a.data for a in atoms(formula)}
        textos = {}
        for letra in letras:
            texto = str(vocab.get(letra, "")).strip()
            if texto:
                textos[letra] = texto
        # Sin descripción de todos los enunciados no se puede reutilizar bien
        # la fórmula en otro ejercicio.
        if len(textos) != len(letras):
            continue
        if APRENDIZAJE.guardar(str(frase), render(formula), textos,
                               cuantificado):
            guardadas += 1
    return guardadas


def _registrar_banco_frases(items, vocab, cuantificado):
    """Guarda en el banco cada frase que tenga una fórmula válida.

    No exige que la deducción se complete ni que el vocabulario sea perfecto:
    el banco es un registro de consulta, no la memoria que reutiliza fórmulas.
    """
    if MEMORIA is None:
        return 0
    textos = {}
    if isinstance(vocab, list):
        for entrada in vocab:
            if not isinstance(entrada, dict):
                continue
            letra = str(entrada.get("letter", "")).strip()
            descripcion = str(entrada.get("text", "")).strip()
            if letra and descripcion:
                textos[letra] = descripcion
    guardadas = 0
    for item in items:
        if not item.get("ok") or not item.get("formula"):
            continue
        try:
            formula = parse_formula(item["formula"])
        except Exception:
            continue
        letras = {a.data for a in atoms(formula)}
        vocabulario = {letra: textos[letra] for letra in letras
                       if letra in textos}
        if MEMORIA.registrar_frase(
                item.get("text", ""), item["formula"], vocabulario,
                cuantificado, item.get("source", "")):
            guardadas += 1
    return guardadas


def _registrar_ejercicio(data, premisas, meta, vistas, plain,
                         correcciones=None, aviso_variante=""):
    """Guarda el ejercicio completo para poder revisarlo desde la memoria."""
    if MEMORIA is None:
        return None
    frases = data.get("sentences")
    total = len(premisas) + 1
    if not isinstance(frases, list) or len(frases) != total:
        frases = [render(p) for p in premisas] + [render(meta)]
    vocab = data.get("vocab")
    if not isinstance(vocab, dict):
        vocab = {}
    cuantificado = any(a.kind == "pred"
                       for f in list(premisas) + [meta] for a in atoms(f))
    items = []
    for i, texto in enumerate(frases):
        items.append({
            "text": str(texto),
            "formula": render(premisas[i]) if i < len(premisas)
                       else render(meta),
            "role": "premisa" if i < len(premisas) else "conclusion",
        })
    try:
        return MEMORIA.guardar_ejercicio({
            "frases": items,
            "vocab": {str(k): str(v) for k, v in vocab.items()},
            "meta": render(meta),
            "premisas": [render(p) for p in premisas],
            "lineas": vistas,
            "plain": plain,
            "calculus": "pred" if cuantificado else "prop",
            "correcciones": correcciones or {},
            "aviso": aviso_variante,
        })
    except Exception:
        traceback.print_exc()
        return None


def _variante_docente(premisas, meta):
    """Prueba una corrección mínima si la formalización literal no deduce.

    En clase es frecuente que una premisa como «Si no te matriculas…» se
    formalice con el antecedente afirmativo (``s → ¬t``) aunque la lectura
    literal sea ``¬s → ¬t``.  Cuando la deducción literal falla, se prueba a
    quitar la negación del antecedente de una sola implicación.  Sólo se
    acepta si la variante permite una deducción completa; el usuario recibe
    un aviso para que sepa qué premisa se ha ajustado.
    """
    for i, premisa in enumerate(premisas):
        if premisa.kind != "imp" or premisa.children[0].kind != "not":
            continue
        corregida = F("imp", None, (premisa.children[0].children[0],
                                    premisa.children[1]))
        variante = list(premisas)
        variante[i] = corregida
        try:
            lineas = prove(variante, meta)
        except Exception:
            continue
        if lineas is not None:
            return i, corregida, variante, lineas
    return None


def _vistas_de_prueba(lines):
    """Convierte las líneas del motor en los datos que pinta la web."""
    refs = {ln.n: render(ln.formula) for ln in lines}
    vistas = []
    for i, ln in enumerate(lines):
        prof = ln.depth
        if prof == 0:
            marca = "\u2212" if ln.rule == "PREM" else " "
        elif ln.hyp:
            marca = "\u2308"
        else:
            siguiente = lines[i + 1] if i + 1 < len(lines) else None
            if siguiente is None or siguiente.depth < prof or siguiente.hyp:
                marca = "\u230a"
            else:
                marca = "|"
        if ln.rule == "PREM":
            nombre, just = "Premisa", ""
        elif ln.hyp:
            nombre, just = "Supuesto", ""
        else:
            nombre = NOMBRE_LIBRO.get(ln.rule, ln.rule)
            just = _cita(ln, nombre)
        vistas.append({
            "n": ln.n,
            "depth": prof,
            "hyp": ln.hyp,
            "marker": marca,
            "label": nombre,
            "rawRule": ln.rule,
            "formula": refs[ln.n],
            "citation": just,
            "explanation": explicar(ln, nombre, refs, len(lines)),
        })
    return vistas


def _id_legado(fecha, frases):
    base = fecha + "|" + "|".join(str(f.get("texto", "")) for f in frases)
    return "legacy-" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _conclusion_legado(frases, formulas):
    """Elige la conclusión de un grupo antiguo y, si puede, rehace la prueba."""
    marcadas = [i for i, f in enumerate(frases)
                if fz.tiene_marcador_conclusion(str(f.get("texto", "")))]
    candidatos = marcadas + [i for i in range(len(frases)) if i not in marcadas]
    if formulas:
        for indice in candidatos:
            premisas = [formulas[i] for i in range(len(formulas))
                        if i != indice]
            try:
                lineas = prove(premisas, formulas[indice])
            except Exception:
                lineas = None
            if lineas is not None:
                return indice, lineas
    if marcadas:
        return marcadas[-1], None
    return len(frases) - 1, None


def _resumen_legado(fecha, frases):
    if len(frases) < 2:
        return None
    formulas = None
    try:
        formulas = [parse_formula(str(f.get("formula", "")).strip())
                    for f in frases]
    except Exception:
        pass
    indice, _ = _conclusion_legado(frases, formulas)
    conclusion = frases[indice]
    cuantificado = False
    if formulas:
        cuantificado = any(a.kind == "pred" for f in formulas for a in atoms(f))
    return {
        "id": _id_legado(fecha, frases),
        "titulo": conclusion.get("texto", ""),
        "meta": conclusion.get("formula", ""),
        "frases": len(frases),
        "usos": max(int(f.get("usos", 0)) for f in frases),
        "actualizado": fecha,
        "calculus": "pred" if cuantificado else "prop",
        "recuperado": True,
    }


def _detalle_legado(fecha, frases):
    if len(frases) < 2:
        return None
    formulas = None
    try:
        formulas = [parse_formula(str(f.get("formula", "")).strip())
                    for f in frases]
    except Exception:
        pass
    indice, lineas = _conclusion_legado(frases, formulas)
    conclusion = frases[indice]
    orden = [i for i in range(len(frases)) if i != indice] + [indice]
    items = []
    for i in orden:
        items.append({
            "text": frases[i].get("texto", ""),
            "formula": frases[i].get("formula", ""),
            "role": "conclusion" if i == indice else "premisa",
        })
    vocab = {}
    for frase in frases:
        for letra, texto in (frase.get("vocab") or {}).items():
            if texto:
                vocab.setdefault(str(letra), str(texto))
    vistas = _vistas_de_prueba(lineas) if lineas else []
    plain = formato_libro(lineas) if lineas else ""
    if lineas:
        aviso = ("Ejercicio recuperado de la memoria antigua de frases. "
                 "La deducción se ha reconstruido a partir de las fórmulas "
                 "guardadas.")
    else:
        aviso = ("Ejercicio recuperado de la memoria antigua de frases. No "
                 "se ha podido reconstruir la deducción con las fórmulas "
                 "guardadas; se muestran la formalización y el vocabulario.")
    return {
        "id": _id_legado(fecha, frases),
        "frases": items,
        "vocab": vocab,
        "meta": conclusion.get("formula", ""),
        "premisas": [frases[i].get("formula", "") for i in orden[:-1]],
        "lineas": vistas,
        "plain": plain,
        "calculus": ("pred" if formulas and any(
            a.kind == "pred" for f in formulas for a in atoms(f)) else "prop"),
        "usos": max(int(f.get("usos", 0)) for f in frases),
        "actualizado": fecha,
        "recuperado": True,
        "aviso": aviso,
    }


def _legado_agrupado(datos):
    grupos = {}
    for frase in datos.get("frases", []):
        fecha = frase.get("actualizado", "")
        if fecha:
            grupos.setdefault(fecha, []).append(frase)
    return sorted(grupos.items(), reverse=True)


def _legado_sin_duplicar(datos):
    """Grupos antiguos que no forman ya parte de un ejercicio completo."""
    guardados = set()
    for resumen in datos.get("ejercicios", []):
        ejercicio = MEMORIA.obtener_ejercicio(resumen.get("id"))
        if not ejercicio:
            continue
        for frase in ejercicio.get("frases", []):
            guardados.add(str(frase.get("text", "")).strip().casefold())
    resultado = []
    for fecha, frases in _legado_agrupado(datos):
        if len(frases) < 2:
            continue
        if all(str(f.get("texto", "")).strip().casefold() in guardados
               for f in frases):
            continue
        resultado.append((fecha, frases))
    return resultado


def _ayuda_exterior_deduccion(data, formulas, cuantificado, forzar=False):
    """Pide a la IA una formalización alternativa cuando no hay deducción.

    La propuesta se comprueba siempre con el motor local: si la IA cambia una
    fórmula y con ella sí se deduce la conclusión, se devuelve esa prueba.
    Nunca se acepta una deducción sin verificarla.
    """
    if not asistente_ia.configurado():
        return None
    frases = data.get("sentences")
    if not isinstance(frases, list) or len(frases) != len(formulas):
        return None
    frases = [str(f).strip() for f in frases]
    if any(not f for f in frases):
        return None

    propuesta = asistente_ia.formalizar(
        frases, cuantificado, general=True,
        formulas_actuales=[render(f) for f in formulas])
    if not propuesta:
        return {"lines": None,
                "aviso": ("No se ha podido consultar la ayuda exterior (A.E.) "
                          "o no ha devuelto una propuesta válida. Revisa las "
                          "fórmulas a mano.")}
    nuevas = []
    for texto in propuesta.get("formulas") or []:
        try:
            nuevas.append(parse_formula(str(texto).strip()))
        except Exception:
            return {"lines": None,
                    "aviso": ("La ayuda exterior (A.E.) ha devuelto fórmulas "
                              "que no se pueden leer. Revisa las fórmulas a "
                              "mano.")}
    if len(nuevas) != len(formulas):
        return {"lines": None,
                "aviso": ("La ayuda exterior (A.E.) no ha devuelto una "
                          "fórmula por frase. Revisa las fórmulas a mano.")}

    premisas, meta = nuevas[:-1], nuevas[-1]
    try:
        lines = prove(premisas, meta)
    except Exception:
        traceback.print_exc()
        lines = None
    if lines is None:
        return {"lines": None,
                "aviso": ("La ayuda exterior (A.E.) tampoco ha encontrado "
                          "una deducción válida con estas frases. Comprueba "
                          "si falta alguna premisa o corrige las fórmulas.")}

    correcciones = {}
    for i, (antes, despues) in enumerate(zip(formulas, nuevas)):
        if render(antes) != render(despues):
            correcciones[str(i)] = render(despues)

    textos = {}
    if isinstance(data.get("vocab"), dict):
        for letra, descripcion in data["vocab"].items():
            descripcion = str(descripcion or "").strip()
            if letra and descripcion:
                textos[str(letra)] = descripcion
    for letra, descripcion in (propuesta.get("vocab") or {}).items():
        descripcion = str(descripcion or "").strip()
        if descripcion:
            textos[str(letra)] = descripcion

    return {
        "lines": lines,
        "premisas": premisas,
        "meta": meta,
        "correcciones": correcciones,
        "vocab": _vocab_con_textos(nuevas, textos, None, cuantificado),
    }


def api_deducir(data):
    crudas = data.get("formulas", [])
    if not isinstance(crudas, list) or len(crudas) < 2:
        return {"ok": False,
                "error": "Faltan la premisa o la conclusión."}

    formulas, errores = [], {}
    for i, txt in enumerate(crudas):
        try:
            formulas.append(parse_formula(str(txt).strip()))
        except Exception as exc:
            errores[str(i)] = "No se puede leer la fórmula: %s" % exc
    if errores:
        return {"ok": False, "error": "Hay fórmulas que no se pueden leer.",
                "errores": errores}

    premisas, meta = formulas[:-1], formulas[-1]
    cuantificado = any(a.kind == "pred" for f in formulas for a in atoms(f))
    forzar_ia = bool(data.get("force_ai"))
    try:
        lines = prove(premisas, meta)
    except Exception:
        traceback.print_exc()
        return {"ok": False, "error": "El motor ha fallado al buscar la "
                                      "deducción. Revisa las fórmulas."}

    correcciones = {}
    aviso_variante = ""
    aviso_ia = ""
    ia_aplicada = False
    vocab = None
    if lines is None:
        variante = None if forzar_ia else _variante_docente(premisas, meta)
        ayuda = None
        if variante is not None:
            indice, corregida, premisas, lines = variante
            correcciones[str(indice)] = render(corregida)
            aviso_variante = (
                "La formalización literal no permitía la deducción. Se ha "
                "ajustado la premisa %d a «%s», que es la variante usada en "
                "la solución de clase; revisa si esa era la intención."
                % (indice + 1, render(corregida)))
        else:
            ayuda = _ayuda_exterior_deduccion(
                data, formulas, cuantificado, forzar=forzar_ia)
            if ayuda is not None and ayuda.get("lines") is not None:
                premisas = ayuda["premisas"]
                meta = ayuda["meta"]
                lines = ayuda["lines"]
                correcciones = ayuda["correcciones"]
                vocab = ayuda["vocab"]
                ia_aplicada = True
                aviso_ia = (
                    "La formalización no permitía la deducción. La ayuda "
                    "exterior (A.E.) ha propuesto fórmulas nuevas y la "
                    "deducción se ha comprobado con las reglas del curso. "
                    "Revisa las fórmulas marcadas como «A.E.» antes de usarlas.")
            else:
                error = ("No se ha encontrado una deducción con estas "
                         "reglas. Puede que la conclusión no se siga de las "
                         "premisas (revisa si falta alguna premisa, como el "
                         "antecedente de un condicional) o que haya que "
                         "corregir alguna fórmula.")
                if not asistente_ia.configurado():
                    error += (" La ayuda exterior (A.E.) no está configurada "
                              "en este servidor.")
                elif ayuda is None:
                    error += (" No se han recibido las frases originales para "
                              "consultar la ayuda exterior (A.E.).")
                elif ayuda.get("aviso"):
                    error += " " + ayuda["aviso"]
                return {"ok": False, "error": error,
                        "ia_aplicada": False,
                        "ia": asistente_ia.configurado(),
                        "puede_ae": asistente_ia.configurado()}

    vistas = _vistas_de_prueba(lines)
    plain = formato_libro(lines)
    if vocab is not None:
        # La memoria debe guardar el vocabulario nuevo, no el de la propuesta
        # que no permitía deducir.
        data["vocab"] = {v["letter"]: v["text"] for v in vocab
                         if v.get("text")}
    aprendido = _registrar_confirmadas(data, list(premisas) + [meta])
    _registrar_ejercicio(data, premisas, meta, vistas, plain,
                         correcciones, aviso_variante)
    respuesta = {
        "ok": True,
        "lines": vistas,
        "premises": [render(p) for p in premisas],
        "goal": render(meta),
        "plain": plain,
        "aprendido": aprendido,
        "correcciones": correcciones,
        "aviso_variante": aviso_variante,
        "ia_aplicada": ia_aplicada,
        "aviso_ia": aviso_ia,
    }
    if vocab is not None:
        respuesta["vocab"] = vocab
    return respuesta


def api_memoria(consulta):
    """Lista o devuelve un ejercicio guardado en la memoria local."""
    identificador = (consulta.get("id") or [""])[0]
    if identificador.startswith("legacy-"):
        datos = MEMORIA.listar_memoria()
        for fecha, frases in _legado_agrupado(datos):
            ejercicio = _detalle_legado(fecha, frases)
            if ejercicio and ejercicio["id"] == identificador:
                return {"ok": True, "ejercicio": ejercicio}
        return {"ok": False, "error": "Ese ejercicio ya no está guardado."}
    if identificador:
        ejercicio = MEMORIA.obtener_ejercicio(identificador)
        if ejercicio is None:
            return {"ok": False, "error": "Ese ejercicio ya no está guardado."}
        return {"ok": True, "ejercicio": ejercicio}
    datos = MEMORIA.listar_memoria()
    for fecha, frases in _legado_sin_duplicar(datos):
        resumen = _resumen_legado(fecha, frases)
        if resumen:
            datos["ejercicios"].append(resumen)
    datos["ejercicios"].sort(
        key=lambda e: str(e.get("actualizado", "")), reverse=True)
    return {"ok": True, "activo": True,
            "aprendizaje": APRENDIZAJE is not None, **datos}


def api_tabla_verdad(data):
    """Calcula la tabla de verdad de una fórmula de enunciados."""
    try:
        return {"ok": True, **generar_tabla(data.get("formula", ""))}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        traceback.print_exc()
        return {"ok": False,
                "error": "No se ha podido generar la tabla de verdad."}


# ==========================================================================
# Servidor HTTP
# ==========================================================================
class Handler(BaseHTTPRequestHandler):
    server_version = "LogicaWeb/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))

    # -- utilidades --------------------------------------------------------
    def _json(self, payload, status=200):
        cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _leer_json(self):
        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            largo = 0
        if largo <= 0 or largo > MAX_CUERPO:
            raise ValueError("cuerpo vacío o demasiado grande")
        return json.loads(self.rfile.read(largo).decode("utf-8"))

    def _estatico(self, ruta):
        if ruta in ("", "/"):
            ruta = "/index.html"
        destino = (ESTATICOS / unquote(ruta.lstrip("/"))).resolve()
        if ESTATICOS.resolve() not in destino.parents or not destino.is_file():
            self.send_error(404, "No encontrado")
            return
        tipo, _ = mimetypes.guess_type(str(destino))
        datos = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         (tipo or "application/octet-stream") +
                         ("; charset=utf-8" if tipo and tipo.startswith("text/")
                          else ""))
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(datos)

    # -- rutas -------------------------------------------------------------
    def do_HEAD(self):
        """Render y otros servicios usan HEAD para comprobar la salud."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta == "/api/salud":
            self._json({"ok": True})
            return
        if ruta == "/api/memoria":
            self._json(api_memoria(parse_qs(urlparse(self.path).query)))
            return
        if ruta == "/api/aprendizaje":
            datos = MEMORIA.estadisticas()
            self._json({"ok": True, "activo": True,
                        "aprendizaje": APRENDIZAJE is not None, **datos,
                        "version": VERSION,
                        "ia": asistente_ia.configurado(),
                        "busqueda": asistente_ia.busqueda_activa(),
                        "modelo": asistente_ia.modelo(),
                        "gratuita": asistente_ia.gratuita()})
            return
        self._estatico(ruta)

    def do_POST(self):
        ruta = urlparse(self.path).path
        try:
            data = self._leer_json()
        except Exception as exc:
            self._json({"ok": False, "error": "Petición no válida: %s" % exc},
                       400)
            return

        if ruta == "/api/formalizar":
            self._json(api_formalizar(data))
        elif ruta == "/api/deducir":
            self._json(api_deducir(data))
        elif ruta == "/api/tabla-verdad":
            self._json(api_tabla_verdad(data))
        else:
            self._json({"ok": False, "error": "Ruta desconocida."}, 404)


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Web de lógica")
    parser.add_argument("--port", type=int, default=int(os.environ.get(
        "PORT", "8000")))
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args(argv)

    try:
        servidor = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print()
            print("  El puerto %d ya está ocupado." % args.port)
            print("  Lo más probable es que la aplicación ya esté abierta:")
            print("      http://localhost:%d" % args.port)
            print()
            print("  Si quieres pararla y volver a arrancarla:")
            print("      pkill -f 'web/server.py'")
            print("  O usa otro puerto:")
            print("      python3 web/server.py --port 8001")
            print()
            return 0
        raise
    print()
    print("  Lógica — servidor web")
    print("  " + "-" * 44)
    print("  En este ordenador:  http://localhost:%d" % args.port)
    print("  Desde otro equipo:  http://%s:%d" % (ip_local(), args.port))
    print("  (misma red WiFi; Ctrl+C para parar)")
    if asistente_ia.configurado():
        print("  IA conectada:       %s" % asistente_ia.modelo())
    print()
    sys.stdout.flush()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor parado.")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

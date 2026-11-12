"""Generación de tablas de verdad para fórmulas de enunciados.

La entrada admite la notación del curso (¬, ∧, ∨, →, ↔) y también la
notación habitual de programación (!, &, |, ->, <->).  Devuelve una tabla
lista para representar en la web y una clasificación semántica de la fórmula.
"""

import itertools
import re

from formulas import atoms, parse_formula, render

MAX_VARIABLES = 10

_SUSTITUCIONES = (
    ("<=>", "↔"),
    ("<->", "↔"),
    ("=>", "→"),
    ("->", "→"),
    ("&&", "∧"),
    ("||", "∨"),
    ("~", "¬"),
    ("!", "¬"),
    ("&", "∧"),
    ("^", "∧"),
    ("|", "∨"),
    ("⊃", "→"),
    ("⊂", "→"),
    ("≡", "↔"),
    # El guion se admite como negador.  Debe ir después de «->» para no
    # romper la flecha escrita en ASCII.
    ("-", "¬"),
    ("−", "¬"),
)


def normalizar_formula(texto):
    """Pasa la notación ASCII a los símbolos usados en la aplicación."""
    limpio = str(texto or "").strip().rstrip(".;")
    for origen, destino in _SUSTITUCIONES:
        limpio = limpio.replace(origen, destino)
    limpio = re.sub(r"\bnot\b", "¬", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\band\b", "∧", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\bor\b", "∨", limpio, flags=re.IGNORECASE)
    # Las variables de una sola letra pueden venir en mayúscula.
    limpio = re.sub(
        r"(?<![A-Za-z0-9_])([A-Z])(?![A-Za-z0-9_])",
        lambda m: m.group(1).lower(), limpio)
    return limpio.strip()


def evaluar(nodo, asignacion):
    """Valora una fórmula para una asignación de verdad."""
    if nodo.kind == "var":
        return bool(asignacion[nodo.data])
    if nodo.kind == "not":
        return not evaluar(nodo.children[0], asignacion)
    if nodo.kind == "and":
        return all(evaluar(c, asignacion) for c in nodo.children)
    if nodo.kind == "or":
        return any(evaluar(c, asignacion) for c in nodo.children)
    if nodo.kind == "imp":
        return (not evaluar(nodo.children[0], asignacion) or
                evaluar(nodo.children[1], asignacion))
    if nodo.kind == "iff":
        return (evaluar(nodo.children[0], asignacion) ==
                evaluar(nodo.children[1], asignacion))
    raise ValueError("La fórmula contiene cuantificadores o predicados; "
                     "las tablas de verdad son para enunciados.")


def _leer_formula(texto):
    """Interpreta una fórmula de enunciados o lanza ``ValueError``."""
    if not str(texto or "").strip():
        raise ValueError("Escribe una fórmula para generar su tabla de verdad.")
    try:
        formula = parse_formula(normalizar_formula(texto))
    except RecursionError:
        raise ValueError("La fórmula está incompleta: falta un operando o un "
                         "paréntesis.") from None
    lista_atomos = atoms(formula)
    if any(a.kind != "var" for a in lista_atomos):
        raise ValueError("Las tablas de verdad son para fórmulas de "
                         "enunciados; no uses predicados ni cuantificadores.")
    variables = sorted({a.data for a in lista_atomos})
    if not variables:
        raise ValueError("La fórmula no contiene ninguna variable.")
    if len(variables) > MAX_VARIABLES:
        raise ValueError("La fórmula tiene demasiadas variables (%d). El "
                         "máximo es %d." % (len(variables), MAX_VARIABLES))
    return formula, variables


def _clasificar(resultados):
    if all(resultados):
        return ("tautologia",
                "Es una tautología: siempre es verdadera.")
    if not any(resultados):
        return ("contradiccion",
                "Es una contradicción: siempre es falsa.")
    return ("contingente",
            "Es contingente: es verdadera en algunas filas y falsa en otras.")


def _subformulas(formula):
    """Subfórmulas compuestas, en orden de evaluación (sin la fórmula raíz)."""
    salida, vistas = [], set()

    def recorrer(nodo, raiz=False):
        for hijo in nodo.children:
            recorrer(hijo)
        if raiz or nodo.kind == "var" or nodo.kind == "pred":
            return
        clave = nodo.key()
        if clave in vistas:
            return
        vistas.add(clave)
        salida.append(nodo)

    recorrer(formula, raiz=True)
    return salida


def generar_tabla(texto):
    """Devuelve la tabla de verdad de una fórmula.

    El resultado tiene esta forma::

        {
          "formula": "p→q",
          "variables": ["p", "q"],
          "filas": [{"valores": [true, true], "resultado": true}, ...],
          "subformulas": [{"formula": "p→q", "valores": [...]}, ...],
          "clasificacion": "contingente",
          "resumen": "La fórmula es contingente: ..."
        }
    """
    formula, variables = _leer_formula(texto)
    compuestas = _subformulas(formula)

    filas = []
    for combinacion in itertools.product((True, False), repeat=len(variables)):
        asignacion = dict(zip(variables, combinacion))
        filas.append({
            "valores": list(combinacion),
            "resultado": evaluar(formula, asignacion),
            "parciales": [evaluar(nodo, asignacion) for nodo in compuestas],
        })

    clasificacion, resumen = _clasificar(
        [fila["resultado"] for fila in filas])
    return {
        "formula": render(formula),
        "variables": variables,
        "filas": filas,
        "subformulas": [
            {"formula": render(nodo),
             "valores": [fila["parciales"][i] for fila in filas]}
            for i, nodo in enumerate(compuestas)
        ],
        "clasificacion": clasificacion,
        "resumen": resumen,
    }


def comparar_formulas(texto_a, texto_b):
    """Compara dos fórmulas y determina si son semánticamente equivalentes."""
    formula_a, variables_a = _leer_formula(texto_a)
    formula_b, variables_b = _leer_formula(texto_b)
    variables = sorted(set(variables_a) | set(variables_b))
    if len(variables) > MAX_VARIABLES:
        raise ValueError("Entre las dos fórmulas hay demasiadas variables "
                         "(%d). El máximo es %d." %
                         (len(variables), MAX_VARIABLES))

    filas = []
    for combinacion in itertools.product((True, False), repeat=len(variables)):
        asignacion = dict(zip(variables, combinacion))
        filas.append({
            "valores": list(combinacion),
            "resultado": evaluar(formula_a, asignacion),
            "resultado_b": evaluar(formula_b, asignacion),
        })
    equivalente = all(f["resultado"] == f["resultado_b"] for f in filas)
    clasificacion, resumen = _clasificar(
        [fila["resultado"] for fila in filas])
    clasificacion_b, resumen_b = _clasificar(
        [fila["resultado_b"] for fila in filas])
    return {
        "formula": render(formula_a),
        "formula_b": render(formula_b),
        "variables": variables,
        "filas": filas,
        "equivalente": equivalente,
        "clasificacion": clasificacion,
        "clasificacion_b": clasificacion_b,
        "resumen": resumen,
        "resumen_b": resumen_b,
    }

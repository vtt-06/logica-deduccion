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


def generar_tabla(texto):
    """Devuelve la tabla de verdad de una fórmula.

    El resultado tiene esta forma::

        {
          "formula": "p→q",
          "variables": ["p", "q"],
          "filas": [{"valores": [true, true], "resultado": true}, ...],
          "clasificacion": "contingente",
          "resumen": "La fórmula es contingente: ..."
        }
    """
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

    filas = []
    for combinacion in itertools.product((True, False), repeat=len(variables)):
        asignacion = dict(zip(variables, combinacion))
        filas.append({
            "valores": list(combinacion),
            "resultado": evaluar(formula, asignacion),
        })

    resultados = [fila["resultado"] for fila in filas]
    if all(resultados):
        clasificacion = "tautologia"
        resumen = "Es una tautología: siempre es verdadera."
    elif not any(resultados):
        clasificacion = "contradiccion"
        resumen = "Es una contradicción: siempre es falsa."
    else:
        clasificacion = "contingente"
        resumen = ("Es contingente: es verdadera en algunas filas y falsa "
                   "en otras.")
    return {
        "formula": render(formula),
        "variables": variables,
        "filas": filas,
        "clasificacion": clasificacion,
        "resumen": resumen,
    }

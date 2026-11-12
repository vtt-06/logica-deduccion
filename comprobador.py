"""Comprobador de deducciones escritas por el alumno.

Cada línea de la deducción se escribe con el formato::

    fórmula ; regla ; referencias

Por ejemplo::

    p→q ; Premisa
    p ; Premisa
    q ; MP ; 1,2

El comprobador valida, línea a línea, que la fórmula se sigue de las líneas
citadas aplicando la regla indicada.  Para las reglas del cálculo de
enunciados se apoya en el mismo motor que genera las deducciones y, además,
comprueba semánticamente el paso con una tabla de verdad.
"""

import re
import unicodedata

from formulas import F, atoms, parse_formula, render
from prover import _semanticamente_valido, conj, disj, neg, nf, rules_one_step

PREMISA = "PREM"
SUPUESTO = "HIP"

# Nombres que puede escribir el alumno -> familia interna.
_ALIAS = {
    "PREMISA": "PREM", "PREMISAS": "PREM", "PREM": "PREM", "P": "PREM",
    "SUPUESTO": "HIP", "SUPUESTOS": "HIP", "HIPOTESIS": "HIP", "HIP": "HIP",
    "SUP": "HIP",
    "MP": "MP", "MODUSPONENS": "MP", "MODUSPONENDO": "MP",
    "MT": "MT", "MODUSTOLLENS": "MT",
    "IC": "IC", "CONJUNCION": "IC", "INTRODUCCIONCONJUNCION": "IC",
    "SIMP": "SIMP", "SIMP1": "SIMP", "SIMP2": "SIMP", "SIMPLIFICACION": "SIMP",
    "AD": "AD", "ADICION": "AD", "ID": "AD",
    "SD": "SD", "SILOGISMODISYUNTIVO": "SD",
    "SH": "SH", "SIL": "SH", "SILOGISMO": "SH",
    "SILOGISMOHIPOTETICO": "SH",
    "DN": "DN", "DOBLENEGACION": "DN",
    "DM1": "DM", "DM2": "DM", "DM": "DM", "DEMORGAN": "DM",
    "CP": "CP", "CONTRAPOSICION": "CP", "CONTRAPOSITIVA": "CP",
    "DI1": "DI1", "DI2": "DI2",
    "EI1": "EI1", "EI2": "EI2",
    "TD": "TD", "II": "TD", "TEOREMADEDUCCION": "TD",
    "IMPORTACION": "TD",
    "ABS": "ABS", "ABSURDO": "ABS", "REDUCCIONALABSURDO": "ABS",
    "IDN": "IDN",
    "REIT": "REIT", "REITERACION": "REIT",
    "EG": "EG", "EG1": "EG", "EG2": "EG", "GENERALIZACION": "EG",
    "EP": "EP", "EP1": "EP", "EP2": "EP", "PARTICULARIZACION": "EP",
    "IG": "IG", "INSTANCIACION": "IG",
}

# Familia que produce el motor para cada regla interna.
_FAMILIA_MOTOR = {
    "MP": "MP", "MT": "MT", "IC": "IC", "Ad": "AD", "Ad1": "AD",
    "Ad2": "AD", "Simp": "SIMP", "Simp1": "SIMP", "Simp2": "SIMP",
    "IDD": "SIMP", "SD": "SD", "DC": "SD", "Sil": "SH", "SH": "SH",
    "Dn": "DN", "DM1": "DM", "DM2": "DM", "Cp": "CP", "DI1": "DI1",
    "DI2": "DI2", "EI1": "EI1", "EI2": "EI2", "Abs": "ABS",
    "EG1": "EG", "EG2": "EG", "EP1": "EP", "EP2": "EP",
    "IG": "IG", "IDN": "IDN",
}

_SIN_ACENTOS = str.maketrans(
    "áéíóúÁÉÍÓÚüÜñÑ", "aeiouAEIOUuUnN")


def _limpia(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[\s._-]+", "", texto.translate(_SIN_ACENTOS)).upper()


def _familia(regla):
    clave = _limpia(regla)
    if not clave:
        return ""
    if clave in _ALIAS:
        return _ALIAS[clave]
    # «Simp 1» o «MP 1,2» escritos dentro del campo de la regla.
    cabeza = re.split(r"[0-9,]", clave, maxsplit=1)[0]
    return _ALIAS.get(cabeza, clave)


def _parsear_refs(texto, total):
    """Convierte «1,2,4-6» en [1, 2, 4, 5, 6] (índices ya validados)."""
    refs = []
    for trozo in re.split(r"[,;]", str(texto or "")):
        trozo = trozo.strip()
        if not trozo:
            continue
        rango = re.match(r"^(\d+)\s*[-\u2013]\s*(\d+)$", trozo)
        if rango:
            inicio, fin = int(rango.group(1)), int(rango.group(2))
            if inicio > fin:
                inicio, fin = fin, inicio
            refs.extend(range(inicio, fin + 1))
            continue
        if trozo.isdigit():
            refs.append(int(trozo))
            continue
        raise ValueError("No entiendo la referencia «%s»." % trozo)
    vistos = []
    for ref in refs:
        if ref < 1 or ref > total:
            raise ValueError("La línea %d no existe." % ref)
        if ref not in vistos:
            vistos.append(ref)
    return vistos


def _parsear_lineas(texto):
    """Divide el texto del alumno en líneas con fórmula, regla y referencias."""
    salida = []
    for numero, cruda in enumerate(str(texto or "").splitlines(), 1):
        linea = cruda.strip()
        if not linea or linea.startswith("#") or linea.startswith("//"):
            continue
        partes = [p.strip() for p in linea.split(";")]
        formula = partes[0] if partes else ""
        regla = partes[1] if len(partes) > 1 else ""
        refs = partes[2] if len(partes) > 2 else ""
        formula = re.sub(r"^\s*\d+\s*[.)]\s*", "", formula)
        if not formula:
            raise ValueError("La línea %d no tiene fórmula." % numero)
        salida.append({
            "n": len(salida) + 1,
            "texto": linea,
            "formula_texto": formula,
            "regla_texto": regla,
            "refs_texto": refs,
        })
    return salida


def _derivadas(pool):
    """Consecuencias de un paso obtenidas con el motor del curso."""
    out, vistos = [], set()
    pool = list(pool)
    pool_set = set(pool)

    def add(formula, regla):
        formula = nf(formula)
        if formula in pool_set or formula in vistos:
            return
        vistos.add(formula)
        out.append((formula, regla))

    for a in pool:
        tmp = []
        try:
            rules_one_step(a, pool, pool_set, tmp)
        except Exception:
            tmp = []
        for elemento in tmp:
            add(elemento[0], elemento[1])

    # Reglas que necesitan combinar dos líneas y que el motor reparte entre
    # varias llamadas.
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            add(conj(a, b), "IC")
            add(disj(a, b), "Ad")
    for a in pool:
        add(disj(a, neg(a)), "Ad")
        if a.kind == "imp":
            ant, cons = a.children[0], a.children[1]
            add(disj(neg(ant), cons), "DI2")
            add(neg(conj(ant, neg(cons))), "DI1")
            add(F("imp", None, (neg(cons), neg(ant))), "Cp")
        if a.kind == "iff":
            x, y = a.children[0], a.children[1]
            add(F("imp", None, (x, y)), "EI1")
            add(F("imp", None, (y, x)), "EI2")
    return out


def _es_proposicional(formulas):
    for formula in formulas:
        for atomo in atoms(formula):
            if atomo.kind != "var":
                return False
    return True


def _comprueba_td(pool, refs, claimed):
    """TD/II: la conclusión es H→C y el rango empieza en el supuesto H."""
    if not refs:
        return False, "TD necesita el rango del supuesto: por ejemplo «TD 1-3»."
    if claimed.kind != "imp":
        return False, "Con TD la fórmula debe ser un condicional H→C."
    primera = pool[0] if pool else None
    if primera is None:
        return False, "El rango de TD está vacío."
    ultima = pool[-1] if pool else None
    if ultima is None:
        return False, "El rango de TD está vacío."
    if not (primera == claimed.children[0] or
            nf(primera) == nf(claimed.children[0])):
        return False, ("El rango de TD debe empezar en el supuesto %s."
                       % render(claimed.children[0]))
    if not (ultima == claimed.children[1] or
            nf(ultima) == nf(claimed.children[1])):
        return False, ("El rango de TD debe terminar en el consecuente %s."
                       % render(claimed.children[1]))
    return True, ""


def _comprueba_abs(pool, claimed):
    """Abs: en el rango hay una contradicción H y ¬H."""
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if nf(a) == nf(neg(b)) or nf(b) == nf(neg(a)):
                return True, ""
    return False, ("Para usar Abs el rango debe contener una contradicción "
                   "(una fórmula y su negación).")


def comprobar(premisas_texto, meta_texto, texto):
    """Valida una deducción y devuelve el resultado línea a línea."""
    try:
        premisas = [parse_formula(str(p).strip()) for p in premisas_texto]
        meta = parse_formula(str(meta_texto).strip())
    except Exception as exc:
        return {"ok": False,
                "error": "No se pueden leer las premisas o la conclusión: %s"
                         % exc}

    try:
        crudas = _parsear_lineas(texto)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not crudas:
        return {"ok": False, "error": "Escribe al menos una línea."}

    lineas = []
    disponibles = {}          # n -> fórmula
    abiertos = []             # índices (n) de supuestos sin cerrar
    errores = 0

    for cruda in crudas:
        n = cruda["n"]
        try:
            formula = parse_formula(cruda["formula_texto"])
        except Exception as exc:
            lineas.append({
                "n": n, "formula": cruda["formula_texto"], "rule": "",
                "ok": False, "error": "No se puede leer la fórmula: %s" % exc,
                "depth": len(abiertos),
            })
            errores += 1
            disponibles[n] = None
            continue

        regla = _familia(cruda["regla_texto"])
        if not regla:
            if any(nf(formula) == nf(p) for p in premisas):
                regla = PREMISA
            else:
                lineas.append({
                    "n": n, "formula": render(formula), "rule": "",
                    "ok": False,
                    "error": "Indica la regla. Si es una premisa, escribe "
                             "«Premisa»; si abres un supuesto, «Supuesto».",
                    "depth": len(abiertos),
                })
                errores += 1
                disponibles[n] = formula
                continue

        try:
            refs = _parsear_refs(cruda["refs_texto"], n)
        except ValueError as exc:
            lineas.append({
                "n": n, "formula": render(formula), "rule": regla,
                "ok": False, "error": str(exc), "depth": len(abiertos),
            })
            errores += 1
            disponibles[n] = formula
            continue

        ok, mensaje = True, ""
        if regla == PREMISA:
            if not any(nf(formula) == nf(p) for p in premisas):
                ok = False
                mensaje = "Esta fórmula no es una de las premisas del ejercicio."
        elif regla == SUPUESTO:
            abiertos.append(n)
        elif regla == "REIT":
            refs = refs or [n - 1]
            citadas = [disponibles.get(r) for r in refs if disponibles.get(r)]
            if not any(nf(formula) == nf(c) for c in citadas):
                ok = False
                mensaje = "La reiteración debe repetir una línea anterior."
        elif regla in ("TD", "ABS"):
            citadas = [disponibles.get(r) for r in refs]
            if any(c is None for c in citadas):
                ok = False
                mensaje = "Alguna referencia del rango no es una línea válida."
            elif regla == "TD":
                ok, mensaje = _comprueba_td(citadas, refs, formula)
                if ok and abiertos:
                    abiertos.pop()
            else:
                ok, mensaje = _comprueba_abs(citadas, formula)
                if ok and abiertos:
                    abiertos.pop()
        else:
            if not refs:
                # Sin referencias se prueban todas las líneas anteriores.
                refs = [r for r in disponibles if disponibles.get(r)]
            citadas = [disponibles.get(r) for r in refs]
            if any(c is None for c in citadas):
                ok = False
                mensaje = "Alguna línea citada no es válida."
            else:
                objetivo = _familia(regla)
                candidatos = _derivadas(citadas)
                elegibles = [
                    (f, r) for f, r in candidatos
                    if _FAMILIA_MOTOR.get(r, _familia(r)) == objetivo
                ]
                coincide = any(nf(f) == nf(formula) for f, _ in elegibles)
                if not coincide:
                    opciones = sorted({r for _, r in candidatos})
                    detalle = ""
                    if opciones:
                        detalle = (" Con las líneas citadas se puede obtener: "
                                   "%s." % ", ".join(opciones[:8]))
                    ok = False
                    mensaje = ("La regla %s no permite pasar de las líneas %s "
                               "a «%s».%s"
                               % (regla, ",".join(str(r) for r in refs),
                                  render(formula), detalle))
                if ok and _es_proposicional(citadas + [formula]):
                    valido = _semanticamente_valido(citadas, formula)
                    if valido is False:
                        ok = False
                        mensaje = ("Semánticamente, «%s» no se sigue de las "
                                   "líneas citadas." % render(formula))

        lineas.append({
            "n": n,
            "formula": render(formula),
            "rule": regla,
            "refs": refs,
            "ok": ok,
            "error": mensaje,
            "depth": max(0, len(abiertos) - (1 if regla == SUPUESTO else 0)),
        })
        if not ok:
            errores += 1
        disponibles[n] = formula

    if not abiertos:
        cerrada = True
    else:
        cerrada = False
    ultima = disponibles.get(crudas[-1]["n"])
    conclusion_ok = ultima is not None and nf(ultima) == nf(meta)

    avisos = []
    if abiertos:
        avisos.append("Quedan supuestos sin cerrar: usa TD o Abs para "
                      "cerrarlos.")
    if not conclusion_ok:
        avisos.append("La última línea debe ser la conclusión «%s»."
                      % render(meta))

    return {
        "ok": errores == 0 and cerrada and conclusion_ok,
        "lineas": lineas,
        "meta": render(meta),
        "premisas": [render(p) for p in premisas],
        "error": " ".join(avisos) if not (errores == 0 and cerrada and
                                          conclusion_ok) else "",
        "resumen": ("Deducción correcta: todas las líneas son válidas y la "
                    "conclusión se alcanza." if
                    errores == 0 and cerrada and conclusion_ok else
                    "Hay %d línea(s) con problemas." % max(errores, 1)),
    }

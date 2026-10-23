"""Programa de lógica: vocabulario, formalización y deducción formal.

Uso:
    python3 main.py              cálculo de proposiciones
    python3 main.py --pred       cálculo de predicados
    python3 main.py --auto       acepta la formalización propuesta sin preguntar
    python3 main.py --olvidar    borra las frases recordadas
    python3 main.py --sin-aprender  no usa la memoria local

El programa pide un conjunto de frases por teclado, construye el vocabulario
empezando por la letra p, propone la formalización y pide confirmación; a
continuación muestra la deducción formal siguiendo las reglas del curso.
"""

import os
import sys

from formulas import parse_formula, render, atoms
from prover import prove
import formalize as fz
import asistente_ia
from aprendizaje import Aprendizaje
from version import VERSION


# --------------------------------------------------------------------------
# Presentación
# --------------------------------------------------------------------------
LINE = "=" * 70
THIN = "-" * 70


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------
def leer_frases():
    print("Escribe las frases, una en cada línea.")
    print("Marca la conclusión con '=>' delante (p. ej. '=> Por tanto, ...').")
    print("Termina con una línea vacía.")
    print()
    frases = []
    conclusion_marcada = False
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            # la línea vacía termina siempre la entrada
            break
        if line.startswith("=>"):
            conclusion = line[2:].strip()
            if conclusion:
                frases.append(conclusion)
            conclusion_marcada = True
            continue
        if conclusion_marcada:
            # el texto posterior a la conclusión se ignora
            continue
        frases.append(line)
    return frases


def confirmar(frase, formula, reader=input):
    """Muestra la propuesta y permite aceptarla o escribirla a mano.

    Devuelve siempre una fórmula.
    """
    propuesta = render(formula) if formula is not None else "(no reconocida)"
    while True:
        print()
        print("  %s" % frase)
        print("    propuesta:  %s" % propuesta)
        if formula is None:
            pedido = "    no se ha reconocido; escribe la fórmula: "
        else:
            pedido = "    ¿correcto? [Enter acepta, 'm' para escribirla]: "
        r = reader(pedido)
        r = r.strip()
        if not r and formula is not None:
            return formula
        if r.lower() in ("m", "manual", "no") or (not r and formula is None):
            while True:
                txt = reader("    escribe la fórmula: ").strip()
                if not txt:
                    continue
                try:
                    return parse_formula(txt)
                except Exception as exc:
                    print("    no se ha podido leer: %s" % exc)
        else:
            try:
                return parse_formula(r)
            except Exception as exc:
                print("    no se ha podido leer: %s" % exc)


def pedir_vocabulario(orden, sugerencias, quantified, reader=input):
    """Pide la descripción de cada letra, ofreciendo una propuesta."""
    textos = {}
    for letter in orden:
        if quantified:
            etiqueta = "%s(x)" % letter
            ayuda = '(propiedad, p. ej. "ser cubos")'
        else:
            etiqueta = letter
            ayuda = '(enunciado completo, p. ej. "Dios puede crearlo")'
        sugerencia = sugerencias.get(letter, "")
        while True:
            if sugerencia:
                print("  %s" % ayuda)
                print("    sugerencia: %s" % sugerencia)
            txt = reader("    %-8s := " % etiqueta).strip()
            if txt:
                textos[letter] = txt
                break
            if sugerencia:
                textos[letter] = sugerencia
                break
    return textos



# --------------------------------------------------------------------------
# Presentación de la deducción
# --------------------------------------------------------------------------
# Nombres de las reglas tal como aparecen en el libro.
NOMBRE_LIBRO = {
    "II": "TD", "Sil": "SH", "Dn": "DN", "EG1": "EG", "EG2": "EG",
    "EP1": "EP", "EP2": "EP", "Abs": "Abs", "IDN": "IDN",
}


def _cita(ln, nombre):
    """Texto de la justificación de una línea."""
    if ln.rule == "PREM":
        return ""
    if ln.hyp:
        return "Supuesto"
    if nombre == "TD" and len(ln.just) == 2:
        return "TD %d-%d" % (ln.just[0], ln.just[1])
    if nombre == "Abs" and len(ln.just) == 2:
        return "Abs %d-%d" % (ln.just[0], ln.just[1])
    if nombre == "Dil" and len(ln.just) >= 3 and len(ln.just) % 2 == 1:
        pares = ["%d-%d" % (ln.just[i], ln.just[i + 1])
                 for i in range(1, len(ln.just), 2)]
        return "Dil %d,%s" % (ln.just[0], ",".join(pares))
    return "%s %s" % (nombre, ",".join(str(j) for j in ln.just))


def formato_libro(lines):
    """Deducción con la notación del libro: −, ⌈, |, ⌊ y 'MP 1,3'."""
    out = []
    ancho = max([len(render(l.formula)) for l in lines] + [20]) + 4
    for i, ln in enumerate(lines):
        prof = ln.depth
        if prof == 0:
            marca = "\u2212 " if ln.rule == "PREM" else "  "
        elif ln.hyp:
            marca = "\u2308 "
        else:
            siguiente = lines[i + 1] if i + 1 < len(lines) else None
            if siguiente is None or siguiente.depth < prof or siguiente.hyp:
                marca = "\u230a "
            else:
                marca = "| "
        nombre = NOMBRE_LIBRO.get(ln.rule, ln.rule)
        cita = _cita(ln, nombre)
        texto = render(ln.formula)
        if cita:
            out.append("%s(%d) %-*s %s" % (marca, ln.n, ancho, texto, cita))
        else:
            out.append("%s(%d) %s" % (marca, ln.n, texto))
    out.append("")
    out.append("QED")
    return "\n".join(out)


def formato_examen(lines):
    """Formato compacto de la resolución del examen."""
    out = []
    for ln in lines:
        texto = render(ln.formula)
        if ln.rule == "PREM":
            out.append("  %s%-3d %s" % ("-", ln.n, texto))
        else:
            just = ",".join(str(j) for j in ln.just)
            out.append("   %-3d %s   %s(%s)" % (ln.n, texto, ln.rule, just))
    out.append("")
    out.append("   QED")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------
def main(argv):
    if "--version" in argv or "-v" in argv:
        print("Lógica v%s" % VERSION)
        return 0

    quantified = "--pred" in argv
    auto = "--auto" in argv
    examen = "--examen" in argv
    sin_aprender = "--sin-aprender" in argv or \
        os.environ.get("LOGICA_APRENDIZAJE") == "0"
    calculus = "cálculo de predicados" if quantified else \
        "cálculo de proposiciones"

    aprendizaje = None if sin_aprender else Aprendizaje()

    if "--olvidar" in argv:
        if aprendizaje is None:
            print("El aprendizaje está desactivado.")
            return 0
        aprendizaje.olvidar()
        print("Se ha borrado todo lo aprendido.")
        return 0

    print(LINE)
    print("  LÓGICA v%s — %s" % (VERSION, calculus))
    print(LINE)

    frases = leer_frases()
    if len(frases) < 2:
        print()
        print("Hacen falta al menos una premisa y una conclusión.")
        return 1

    # ---- formalización propuesta -------------------------------------
    print()
    print(THIN)
    print("FORMALIZACIÓN PROPUESTA")
    print(THIN)
    form = fz.Formalyzer(quantified, aprendizaje)
    propuestas = []
    fuentes = []
    for fr in frases:
        propuestas.append(form.formalize(fr))
        fuentes.append(form.fuente)

    # Si algo no se ha reconocido y hay un servicio de IA configurado, se le
    # pide una propuesta completa.  Sólo se envía algo si el usuario ha
    # definido LOGICA_IA_URL y LOGICA_IA_MODEL.
    if any(f is None for f in propuestas) and asistente_ia.configurado():
        print()
        print("  (Consultando el servicio de IA configurado…)")
        propuesta = asistente_ia.formalizar(frases, quantified)
        if propuesta:
            nuevas, validas = [], True
            for texto in propuesta["formulas"]:
                try:
                    nuevas.append(parse_formula(texto))
                except Exception:
                    validas = False
                    break
            if validas and len(nuevas) == len(frases):
                propuestas = nuevas
                fuentes = ["ia"] * len(frases)

    for i, fr in enumerate(frases):
        f = propuestas[i]
        etiqueta = "premisa" if i < len(frases) - 1 else "conclusión"
        if f is None:
            print("  %-11s (no reconocida)" % etiqueta)
        else:
            nota = ""
            if fuentes[i] == "aprendida":
                nota = "  (aprendida)"
            elif fuentes[i] == "ia":
                nota = "  (IA)"
            print("  %-11s %s%s" % (etiqueta, render(f), nota))
        print("  %-11s \"%s\"" % ("", fr))
    print()

    # ---- confirmación -----------------------------------------------
    if not auto:
        print("Revisa la formalización: puedes corregir cualquier línea.")
    print()
    for i, fr in enumerate(frases):
        if auto:
            continue
        propuestas[i] = confirmar(fr, propuestas[i])

    if any(f is None for f in propuestas):
        print()
        print("No se ha podido formalizar alguna frase.")
        print("Escribe su fórmula a mano (opción 'm') o revisa la redacción.")
        return 2

    premises = propuestas[:-1]
    goal = propuestas[-1]

    # ---- vocabulario -------------------------------------------------
    # Sólo interesan las letras que aparecen en las fórmulas confirmadas.
    # El orden es el de aparición en las frases, que es como se numera en
    # el examen: p := ..., q := ..., r := ...
    usadas = set()
    for f in propuestas:
        for a in atoms(f):
            usadas.add(a.data)

    orden, vistos = [], set()
    for t in form.vocab:
        if t.letter in usadas and t.letter not in vistos:
            vistos.add(t.letter)
            orden.append(t.letter)
    for f in propuestas:
        for a in atoms(f):
            if a.data not in vistos:
                vistos.add(a.data)
                orden.append(a.data)

    sugerencias = {}
    for t in form.vocab:
        if t.letter not in usadas:
            continue
        texto = t.text.strip(" ,.")
        if not texto:
            continue
        if quantified and not texto.lower().startswith(("ser ", "estar ")):
            texto = "ser " + texto
        sugerencias[t.letter] = texto

    print()
    print(THIN)
    print("VOCABULARIO")
    print(THIN)
    if auto:
        textos = {k: v for k, v in sugerencias.items()}
        for letter in orden:
            textos.setdefault(letter, "«%s»" % letter)
    else:
        textos = pedir_vocabulario(orden, sugerencias, quantified)
    print()
    for letter in orden:
        if quantified:
            print("  %-8s := %s" % (letter + "(x)", textos[letter]))
            print("  %-8s := %s" % ("¬" + letter + "(x)", "no " + textos[letter]))
        else:
            print("  %-8s := %s" % (letter, textos[letter]))
            print("  %-8s := %s" % ("¬" + letter, "no " + textos[letter]))
    print()

    # ---- deducción ----------------------------------------------------
    print("Buscando la deducción…")
    lines = prove(premises, goal)
    if lines is None:
        print()
        print("No se ha encontrado ninguna deducción con estas reglas.")
        print("Revisa la formalización: puede que la conclusión no se siga")
        print("de las premisas, que falte alguna premisa (por ejemplo, el")
        print("antecedente de un condicional) o que haya un connective mal.")
        return 2

    print()
    print(THIN)
    print("PREMISAS Y CONCLUSIÓN")
    print(THIN)
    for i, p in enumerate(premises, start=1):
        print("  %s%-3d %s" % ("-", i, render(p)))
    print("  %s   %s" % ("⊢", render(goal)))
    print()
    print(THIN)
    print("DEDUCCIÓN")
    print(THIN)
    if examen:
        print(formato_examen(lines))
    else:
        print(formato_libro(lines))
    print()

    # ---- aprendizaje --------------------------------------------------
    if aprendizaje is not None:
        guardadas = 0
        for fr, f in zip(frases, propuestas):
            if form.registrar(fr, f, textos):
                guardadas += 1
        if guardadas:
            print("  (Se han recordado %d frases para próximos ejercicios.)"
                  % guardadas)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

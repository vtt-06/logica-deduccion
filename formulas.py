"""Representación de fórmulas lógicas y presentación con la notación del curso.

Notación usada (según LOGICA - Cálculo de predicados / proposiciones):
    negación      ¬
    conjunción    ∧
    disyunción    ∨
    implicación   →
    coimplicación ↔
    generalizador (Λx)
    particularizador (Vx)

Las variables de enunciado se designan con minúsculas a partir de p.
"""

# --------------------------------------------------------------------------
# Cuantificadores
# --------------------------------------------------------------------------
GENERAL = "L"      # (Λx)  -- se escribe Lambda en pantalla
PARTIC = "V"       # (Vx)


class F:
    """Nodo de una fórmula bien formada (fbf)."""

    __slots__ = ("kind", "data", "children", "term")

    def __init__(self, kind, data=None, children=(), term="x"):
        self.kind = kind          # 'var','pred','not','and','or','imp','iff','forall','exists'
        self.data = data          # letra, o predicado, o variable ligada
        self.children = tuple(children)
        self.term = term          # término de los átomos de predicado

    # -- azúcar sintáctico --------------------------------------------------
    @staticmethod
    def var(name):
        return F("var", name)

    @staticmethod
    def pred(name, term="x"):
        return F("pred", name, (), term)

    @staticmethod
    def not_(a):
        return F("not", None, (a,))

    @staticmethod
    def and_(*parts):
        return F("and", None, parts)

    @staticmethod
    def or_(*parts):
        return F("or", None, parts)

    @staticmethod
    def imp(a, b):
        return F("imp", None, (a, b))

    @staticmethod
    def iff(a, b):
        return F("iff", None, (a, b))

    @staticmethod
    def forall(var, body):
        return F("forall", var, (body,))

    @staticmethod
    def exists(var, body):
        return F("exists", var, (body,))

    # -- utilidades --------------------------------------------------------
    def free_vars(self):
        if self.kind in ("var", "pred"):
            return set()
        if self.kind in ("forall", "exists"):
            return self.children[0].free_vars() - {self.data}
        out = set()
        for c in self.children:
            out |= c.free_vars()
        return out

    def __eq__(self, other):
        return isinstance(other, F) and self.key() == other.key()

    def __hash__(self):
        return hash(self.key())

    def key(self):
        if self.kind in ("var", "pred"):
            return (self.kind, self.data)
        return (self.kind,) + tuple(c.key() for c in self.children)

    def __repr__(self):
        return render(self)


# --------------------------------------------------------------------------
# Presentación
# --------------------------------------------------------------------------
# Precedencia del libro (Apuntes, observación 1.4.2):
#     nivel 1: ¬
#     nivel 2: ∧, ∨
#     nivel 3: →, ↔
# Las conectivas del mismo nivel no ligan más unas que otras: si se mezclan,
# hay que escribir paréntesis.  Las cadenas del mismo conjuntor o disyuntor
# sí se pueden escribir sin paréntesis.
_PREC = {"iff": 10, "imp": 10, "or": 20, "and": 20}
_SYM = {"iff": "↔", "imp": "→", "or": "∨", "and": "∧"}


def render(node):
    """Convierte una fórmula a la notación del curso.

    Precedencia (Apuntes 1.4.2): ¬ ; ∧ y ∨ ; → y ↔.
    Al mezclar conectivas del mismo nivel se añaden paréntesis para que la
    fórmula no sea ambigua.
    """
    return _render(node, 0, None)


def _needs_parens(kind, parent_prec, parent_kind):
    """¿Hace falta rodear este nodo de paréntesis en su contexto?"""
    if parent_prec == 0:
        return False
    if kind in ("var", "pred", "not", "forall", "exists"):
        return False
    prec = _PREC.get(kind)
    if prec is None:
        return False
    if prec < parent_prec:
        return True
    if prec > parent_prec:
        return False
    # Mismo nivel: sólo se omite el paréntesis si es el mismo conjuntor o
    # disyuntor (una cadena asociativa).  En los demás casos, paréntesis.
    return not (kind == parent_kind and kind in ("and", "or"))


def _render(node, parent_prec, parent_kind):
    """`parent_prec` es la precedencia del contexto; 0 = nivel superior."""
    k = node.kind

    if k == "var":
        return node.data
    if k == "pred":
        return "%s(%s)" % (node.data, node.term)

    if k == "not":
        s = "¬" + _render(node.children[0], 50, "not")
        return "(" + s + ")" if _needs_parens(k, parent_prec, parent_kind) else s

    if k in ("forall", "exists"):
        sym = "(Λ%s)" % node.data if k == "forall" else "(V%s)" % node.data
        s = sym + _render(node.children[0], 50, k)
        return "(" + s + ")" if _needs_parens(k, parent_prec, parent_kind) else s

    if k in _PREC:
        prec = _PREC[k]
        sym = _SYM[k]
        if k in ("and", "or"):
            s = sym.join(_render(c, prec, k) for c in node.children)
        else:
            s = (_render(node.children[0], prec, k) + sym +
                 _render(node.children[1], prec, k))
        return "(" + s + ")" if _needs_parens(k, parent_prec, parent_kind) else s

    raise ValueError("nodo desconocido: %r" % k)


# --------------------------------------------------------------------------
# Parser para las fórmulas que introduce el usuario al confirmar
# --------------------------------------------------------------------------
def parse_formula(text):
    """Convierte el texto introducido por el usuario en un objeto F.

    Acepta: p, q, C(x), (Vx), (Vx)C(x), ¬p, p ∧ q, p → q, ¬(p ∧ q), ...
    Los cuantificadores se escriben como (Vx) o (Λx) seguidos del cuerpo.

    Se sigue la precedencia del libro (Apuntes 1.4.2):
    ¬ ; ∧ y ∨ ; → y ↔.  Si se mezclan conectivas del mismo nivel sin
    paréntesis, se rechaza la fórmula para no interpretarla al azar.
    """
    text = text.strip()
    i = 0
    n = len(text)

    def peek():
        return text[i] if i < n else ""

    def skip_ws():
        nonlocal i
        while i < n and text[i].isspace():
            i += 1

    def parse_atom():
        nonlocal i
        skip_ws()
        ch = peek()
        if ch in "([":
            # ¿es un cuantificador (Vx) / (Λx)?
            j = i + 1
            if ch == "(" and j < n and text[j] in "VΛ":
                k = j + 1
                while k < n and text[k] in "xyzabcuvw":
                    k += 1
                if k < n and text[k] == ")":
                    var = text[j + 1:k]
                    i = k + 1
                    body = parse_expr()
                    kind = "exists" if text[j] == "V" else "forall"
                    return F(kind, var, (body,))
            cierre = ")" if ch == "(" else "]"
            i += 1
            inner = parse_expr()
            skip_ws()
            if peek() == cierre:
                i += 1
                return inner
            raise ValueError("falta '%s' en la posición %d" % (cierre, i))
        # variable o predicado
        if ch.isalpha():
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            name = text[i:j]
            i = j
            if peek() == "(":
                i += 1
                arg = ""
                while i < n and text[i] != ")":
                    arg += text[i]
                    i += 1
                if i >= n:
                    raise ValueError("falta ')' en el predicado %s" % name)
                i += 1
                return F.pred(name, arg.strip() or None)
            return F.var(name)
        raise ValueError("carácter inesperado: %r" % ch)

    def parse_not():
        nonlocal i
        skip_ws()
        if peek() == "¬":
            i += 1
            return F.not_(parse_not())
        return parse_atom()

    def parse_nivel2():
        """∧ y ∨ tienen la misma precedencia en el libro."""
        nonlocal i
        partes = [parse_not()]
        tipos = []
        while True:
            skip_ws()
            tipo = None
            if text.startswith("∧", i):
                tipo = "and"
            elif text.startswith("∨", i):
                tipo = "or"
            if tipo is None:
                break
            i += 1
            tipos.append(tipo)
            partes.append(parse_not())
        if not tipos:
            return partes[0]
        if len(set(tipos)) > 1:
            raise ValueError(
                "no se pueden mezclar ∧ y ∨ sin paréntesis: en el libro "
                "tienen la misma precedencia. Escribe, por ejemplo, "
                "«(p∧q)∨r» o «p∧(q∨r)»")
        if len(partes) == 2:
            return F(tipos[0], None, (partes[0], partes[1]))
        return F(tipos[0], None, tuple(partes))

    def parse_nivel3():
        """→ y ↔ tienen la misma precedencia en el libro."""
        nonlocal i
        left = parse_nivel2()
        operadores = []
        while True:
            skip_ws()
            tipo = None
            if text.startswith("→", i):
                tipo = "imp"
            elif text.startswith("↔", i):
                tipo = "iff"
            if tipo is None:
                break
            i += 1
            right = parse_nivel2()
            operadores.append(tipo)
            if len(operadores) == 1:
                left = F(tipo, None, (left, right))
            else:
                if len(set(operadores)) > 1:
                    raise ValueError(
                        "no se pueden mezclar → y ↔ sin paréntesis: en el "
                        "libro tienen la misma precedencia")
                raise ValueError(
                    "usa paréntesis para encadenar → o ↔: por ejemplo, "
                    "«p→(q→r)» o «(p↔q)↔r»")
        return left

    def parse_expr():
        return parse_nivel3()

    result = parse_expr()
    skip_ws()
    if i != n:
        raise ValueError("sobran caracteres: %r" % text[i:])
    return result


def flatten(node, kind):
    """Aplana un árbol n-ario de clase `kind` en una lista de componentes."""
    if node.kind == kind:
        out = []
        for c in node.children:
            out.extend(flatten(c, kind))
        return out
    return [node]


def atoms(node, out=None):
    """Devuelve el conjunto de átomos (variables y predicados) de una fórmula."""
    if out is None:
        out = []
    if node.kind == "var":
        if node not in out:
            out.append(node)
    elif node.kind == "pred":
        if node not in out:
            out.append(node)
    for c in node.children:
        atoms(c, out)
    return out

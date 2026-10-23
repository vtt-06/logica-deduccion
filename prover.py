"""Motor de deducción natural.

El programa trabaja en dos fases, igual que se hacen estas deducciones a mano:

  1. Saturación.  A partir de las premisas se calculan por adelantado las
     fórmulas intermedias que se pueden deducir, cada una con su
     justificación.  Esas líneas son las que después se citarán
     (Simp₂(3), DI₂(9), MT(5,6)...), y son las que aparecen numeradas en la
     resolución del examen.

  2. Deducción.  Se alcanza la conclusión hacia atrás.  Si la meta no sale
     con una sola regla, se abre una subdemostración: la conjunción se separa
     en dos metas, la disyunción en dos subdemostraciones, la implicación se
     demuestra suponiendo el antecedente y la negación de una conjunción se
     demuestra con las dos negaciones.

Las reglas son las de "LOGICA - Colección de Fórmulas utilizables en los
exámenes", con las abreviaturas que emplea el profesor.
"""

import itertools

from formulas import F, atoms, flatten


# ==========================================================================
# Utilidades de normalización
# ==========================================================================
def parts_and(f):
    return flatten(f, "and")


def parts_or(f):
    return flatten(f, "or")


def conj(*xs):
    return F("and", None, tuple(xs))


def disj(*xs):
    return F("or", None, tuple(xs))


def neg(x):
    return F.not_(x)


def subst(node, var, term):
    """Sustituye la variable `var` por el término `term`."""
    if node.kind == "var":
        return term if node.data == var else node
    if node.kind == "pred":
        if node.term == var:
            return F.pred(node.data, term.data)
        return node
    if node.kind in ("forall", "exists"):
        if node.data == var:
            return node
        return F(node.kind, node.data, (subst(node.children[0], var, term),))
    return F(node.kind, node.data,
             tuple(subst(c, var, term) for c in node.children))


def _fresh(used):
    for c in "abcdefghijklmnopqrstuvwxyz":
        if c not in used:
            return c
    raise RuntimeError("agotadas las variables")


def nf(f):
    """Forma normal de negación.

    Se empujan las negaciones hasta los átomos y se eliminan las dobles
    negaciones.  Esto es imprescindible: sin normalizar, la contraposición y
    la definición del implicador encadenan negaciones sin fin y se generan
    fórmulas del tipo ¬¬¬¬¬r que no llevan a ninguna parte.  Una vez
    normalizadas, esas cadenas se reducen a fórmulas que ya existen y la
    saturación se cierra.
    """
    k = f.kind
    if k in ("var", "pred"):
        return f
    if k == "not":
        inner = f.children[0]
        i = inner.kind
        if i == "not":
            return nf(inner.children[0])
        if i in ("var", "pred"):
            return F.not_(inner)
        if i == "and":
            return F("or", None, tuple(nf(neg(c)) for c in inner.children))
        if i == "or":
            return F("and", None, tuple(nf(neg(c)) for c in inner.children))
        if i == "imp":
            return conj(nf(inner.children[0]), nf(neg(inner.children[1])))
        if i == "forall":
            return F("exists", inner.data, (nf(neg(inner.children[0])),))
        if i == "exists":
            return F("forall", inner.data, (nf(neg(inner.children[0])),))
        return f
    if k in ("and", "or"):
        return F(k, None, tuple(nf(c) for c in f.children))
    if k in ("imp", "iff"):
        return F(k, None, tuple(nf(c) for c in f.children))
    if k in ("forall", "exists"):
        return F(k, f.data, (nf(f.children[0]),))
    return f


def _preds(node):
    return {a.data for a in atoms(node) if a.kind == "pred"}


def _vars(node):
    return {a.data for a in atoms(node) if a.kind == "var"}


def _atoms_of(node):
    return _preds(node) | _vars(node)


def _contains(f, g):
    """True si `g` aparece como subfórmula de `f`."""
    if f == g:
        return True
    return any(_contains(c, g) for c in f.children)


def _literals(f):
    """Literales (átomos y átomos negados) que aparecen en una fórmula."""
    out = set()
    for a in atoms(f):
        if a.kind == "var":
            out.add(a)
        else:
            out.add(a)
    return out


def _complexity(f):
    """Número de símbolos de una fórmula (para ordenar los lemas)."""
    total = [0]

    def rec(n):
        total[0] += 1
        for c in n.children:
            rec(c)

    rec(f)
    return total[0]


# ==========================================================================
# Reglas de un paso
# ==========================================================================
def rules_one_step(a, pool, pool_set, out):
    """Añade a `out` las deducciones de un paso que se apoyan en `a`."""
    def emit(f, rule, *support):
        f = nf(f)
        if f not in pool_set and f != a:
            out.append((f, rule, list(support)))

    # ---------------- cuantificadores ------------------------------------
    if a.kind in ("forall", "exists"):
        used = _atoms_of(a)
        v = _fresh(used)
        inst = subst(a.children[0], a.data, F.var(v))
        if a.kind == "exists":
            emit(inst, "EP1", a)
            emit(neg(inst), "EP2", a)
        else:
            emit(inst, "EG1", a)
            if inst.kind == "imp" and inst.children[0] == F.var(v):
                emit(F("imp", None, (F.var(v), inst.children[1])), "EG2", a)

    # ---------------- negación ------------------------------------------
    if a.kind == "not":
        inner = a.children[0]
        if inner.kind == "not":
            emit(inner.children[0], "Dn", a)
        elif inner.kind == "and":
            # De Morgan:  ¬(A ∧ B)  ⊢  ¬A ∨ ¬B
            ps = parts_and(inner)
            if len(ps) >= 2:
                emit(disj(neg(ps[0]), neg(ps[1])), "DM1", a)
        elif inner.kind == "or":
            # De Morgan:  ¬(A ∨ B)  ⊢  ¬A ∧ ¬B
            ps = parts_or(inner)
            if len(ps) == 2:
                emit(conj(neg(ps[0]), neg(ps[1])), "DM2", a)

    # ---------------- conjunción ----------------------------------------
    if a.kind == "and":
        ps = parts_and(a)
        for i, p in enumerate(ps, start=1):
            emit(p, "Simp%d" % i if len(ps) == 2 else "Simp", a)
        if len(ps) == 2 and ps[0] == ps[1]:
            emit(ps[0], "IDD", a)
        if len(ps) > 2:
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    emit(disj(ps[i], ps[j]), "DC", a)
        for p in ps:
            for g in pool:
                if g.kind == "imp" and g.children[0] == p:
                    # simplificación de la conjunción y modus ponens
                    emit(g.children[1], "MP", a, g)

    # ---------------- disyunción ----------------------------------------
    #  (A ∨ B ∨ ...) no permite deducir ningún disjunto, pero sí aplicar
    #  idempotencia y distributividad, como en la resolución del examen.
    if a.kind == "or":
        ps = parts_or(a)
        if len(ps) == 2 and ps[0] == ps[1]:
            emit(ps[0], "IDD", a)
        if len(ps) == 2:
            for i, p in enumerate(ps):
                if p.kind != "and":
                    continue
                otros = [x for j, x in enumerate(ps) if j != i]
                if len(otros) != 1:
                    continue
                c = otros[0]
                bs = parts_and(p)
                if len(bs) != 2:
                    continue
                # A ∨ (B∧C)  ⊢  (A∨B) ∧ (A∨C)
                # (A∧B) ∨ C  ⊢  (A∨C) ∧ (B∨C)
                emit(conj(disj(bs[0], c), disj(bs[1], c)), "DD", a)
                emit(conj(disj(c, bs[0]), disj(c, bs[1])), "DD", a)
    if a.kind == "and":
        ps = parts_and(a)
        if len(ps) == 2:
            for i, p in enumerate(ps):
                if p.kind != "or":
                    continue
                otros = [x for j, x in enumerate(ps) if j != i]
                if len(otros) != 1:
                    continue
                c = otros[0]
                bs = parts_or(p)
                if len(bs) != 2:
                    continue
                # A ∧ (B∨C)  ⊢  (A∧B) ∨ (A∧C)
                emit(disj(conj(c, bs[0]), conj(c, bs[1])), "DD", a)
                emit(disj(conj(bs[0], c), conj(bs[1], c)), "DD", a)

    # ---------------- implicador ----------------------------------------
    if a.kind == "imp":
        ant, cons = a.children[0], a.children[1]
        if ant in pool_set:
            emit(cons, "MP", a, ant)
        emit(disj(neg(ant), cons), "DI2", a)
        emit(F("imp", None, (neg(cons), neg(ant))), "Cp", a)
        emit(neg(conj(ant, neg(cons))), "DI1", a)

    # ---------------- coimplicador -------------------------------------
    if a.kind == "iff":
        x, y = a.children[0], a.children[1]
        emit(F("imp", None, (x, y)), "EI1", a)
        emit(F("imp", None, (y, x)), "EI2", a)
        emit(conj(x, y), "IC", a)


# ==========================================================================
# Reglas de rebote
# ==========================================================================
def rules_rebound(pool, pool_set, out):
    def emit(f, rule, *support):
        f = nf(f)
        if f not in pool_set and f not in pool:
            out.append((f, rule, list(support)))

    def emit_raw(f, rule, *support):
        """Como `emit`, pero conserva la negación sin empujar hacia dentro."""
        if f not in pool_set and f not in pool:
            out.append((f, rule, list(support)))

    for f in pool:
        # ---- implicador ---------------------------------------------
        if f.kind == "imp":
            ant, cons = f.children[0], f.children[1]
            ncons = nf(neg(cons))
            if ncons in pool_set:
                emit(neg(ant), "MT", f, ncons)
                # se guarda también ¬A tal cual, para poder escribir después
                # el paso de De Morgan como en el examen
                if neg(ant) != nf(neg(ant)):
                    emit_raw(neg(ant), "MT", f, ncons)
            for g in pool:
                if g.kind == "imp" and g.children[0] == cons:
                    emit(F("imp", None, (ant, g.children[1])), "Sil", f, g)
        # ---- disyunción ---------------------------------------------
        if f.kind == "or":
            ps = parts_or(f)
            # silogismo disyuntivo, también con más de dos disjuntos
            for i, p in enumerate(ps):
                np = nf(neg(p))
                if np in pool_set:
                    rest = [x for j, x in enumerate(ps) if j != i]
                    if len(rest) == 1:
                        emit(rest[0], "SD", f, np)
                    else:
                        emit(disj(*rest), "SD", f, np)
            if len(ps) == 2:
                for g in pool:
                    if g.kind != "or" or len(parts_or(g)) != 2:
                        continue
                    gs = parts_or(g)
                    lit = [x.children[0] for x in gs
                           if x.kind == "not" and x.children[0].kind != "not"]
                    for p in ps:
                        if nf(neg(p)) in gs:
                            for c in lit:
                                if c != p:
                                    emit(disj(p, c), "SD", f, g)

    # ---- dilema 1: (A ∨ B) → C , ¬A → C ⊢ B → C ---------------------
    for f in pool:
        if f.kind != "imp":
            continue
        ant, cons = f.children
        if ant.kind != "or":
            continue
        ps = parts_or(ant)
        if len(ps) != 2:
            continue
        for g in pool:
            if g.kind == "imp" and g.children[1] == cons:
                for p in ps:
                    if neg(p) == g.children[0]:
                        other = ps[1] if p == ps[0] else ps[0]
                        emit(F("imp", None, (other, cons)), "Dil1", f, g)


# ==========================================================================
# Fase 1: saturación acotada
# ==========================================================================
def saturate(premises, interest=None, cap=400, max_levels=4, max_size=5):
    """Cierre de las premisas limitado en tamaño, en niveles y en longitud.

    El límite de longitud es esencial: si no, la contraposición y la
    definición del implicador se encadenan indefinidamente y se generan
    fórmulas del tipo ¬¬¬¬¬r que no llevan a ninguna parte.

    Devuelve (pool, derivation).  `pool` es la lista de fórmulas obtenidas en
    orden de aparición y `derivation[i] = (regla, apoyos)` con los índices de
    `pool`; las premisas tienen regla None.
    """
    pool = [nf(p) for p in premises]
    pool_set = set(pool)
    derivation = {i: (None, ()) for i in range(len(pool))}

    def interesting(f):
        if _complexity(f) > max_size:
            return False
        if not interest:
            return True
        return bool(_atoms_of(f) & interest)

    frontier = list(range(len(pool)))
    for _ in range(max_levels):
        if not frontier:
            break
        cand = []
        for i in frontier:
            rules_one_step(pool[i], pool, pool_set, cand)
        rules_rebound(pool, pool_set, cand)
        new_frontier = []
        # se prefieren las fórmulas sencillas y próximas a la meta
        cand.sort(key=lambda t: _complexity(t[0]))
        for f, rule, support in cand:
            if f in pool_set or not interesting(f):
                continue
            idx = len(pool)
            derivation[idx] = (rule, tuple(support))
            pool.append(f)
            pool_set.add(f)
            new_frontier.append(idx)
        frontier = new_frontier
        if len(pool) >= cap:
            break
    return pool, derivation


# ==========================================================================
# Fase 2: construcción de la deducción
# ==========================================================================
class Failure(Exception):
    pass


class Budget:
    __slots__ = ("left",)

    def __init__(self, n):
        self.left = n

    def spend(self, k=1):
        self.left -= k
        if self.left <= 0:
            raise Failure()

    def fork(self):
        return Budget(max(self.left, 1))


class Line:
    __slots__ = ("formula", "rule", "just", "depth", "hyp", "n")

    def __init__(self, formula, rule, just=(), depth=0, hyp=False, n=0):
        self.formula = formula
        self.rule = rule
        self.just = list(just)
        self.depth = depth
        self.hyp = hyp
        self.n = n

    def __repr__(self):
        from formulas import render
        return "%s [%s]" % (render(self.formula), self.rule)


class ProofBuilder:
    def __init__(self, pool, derivation):
        self.pool = pool
        self.derivation = derivation
        self.index_of = {}
        for i, f in enumerate(pool):
            self.index_of.setdefault(f, i)
        self.lines = []
        self.formulas = []
        self.formula_index = {}
        self.emitted = set()      # fórmulas ya escritas
        self._mt_seen = set()     # metas que se están probando por MT

    # -- escritura de líneas ------------------------------------------------
    def emit(self, formula, rule, just, hyp=False, depth=0, force=False):
        """Escribe una línea.

        `force` la escribe aunque la fórmula ya estuviera escrita.  Hace
        falta para la conclusión de una subdemostración, que puede haberse
        deducido ya dentro de una de sus ramas.
        """
        if formula in self.emitted and not force:
            return self.formula_index[formula]
        self.emitted.add(formula)
        n = len(self.lines) + 1
        self.lines.append(Line(formula, rule, just, depth, hyp, n))
        self.formulas.append(formula)
        self.formula_index[formula] = n
        return n

    def cite(self, f):
        return self.formula_index.get(f)

    def mark(self):
        return len(self.lines)

    def rollback(self, mark):
        for ln in self.lines[mark:]:
            self.emitted.discard(ln.formula)
            self.formula_index.pop(ln.formula, None)
        del self.lines[mark:]
        del self.formulas[mark:]

    # -- subdemostraciones ---------------------------------------------------
    def clone(self):
        """Copia del contexto para trabajar en una subdemostración."""
        b = ProofBuilder(self.pool, self.derivation)
        b.index_of = self.index_of
        b.lines = list(self.lines)
        b.formulas = list(self.formulas)
        b.formula_index = dict(self.formula_index)
        b.emitted = set(self.emitted)
        return b

    def merge(self, other, mark):
        """Pasa al contexto principal las líneas nuevas de `other`.

        Devuelve el diccionario que traduce los números de línea de `other`
        a los nuevos números de este contexto.
        """
        nuevas = other.lines[mark:]
        base = len(self.lines)
        remap = {}
        for i, ln in enumerate(nuevas):
            remap[mark + i + 1] = base + i + 1
        for i, ln in enumerate(nuevas):
            ln.just = [remap.get(j, j) for j in ln.just]
            self.lines.append(ln)
            self.formulas.append(ln.formula)
            self.emitted.add(ln.formula)
            self.formula_index.setdefault(ln.formula, base + i + 1)
        for i, ln in enumerate(self.lines):
            ln.n = i + 1
        return remap

    # -- Incorporar una fórmula de la saturación --------------------------
    def ensure(self, f, budget, depth=0):
        """Escribe, si hace falta, la línea de `f` y las que la justifican."""
        if f in self.formula_index:
            return self.formula_index[f]
        i = self.index_of.get(f)
        if i is None:
            raise Failure()
        budget.spend()
        rule, support = self.derivation[i]
        if rule is None:                       # es una premisa
            raise Failure()
        just = []
        for s in support:
            just.append(self.ensure(s, budget, depth))
        return self.emit(f, rule, just, depth=depth)

    def ensure_pool(self, f, budget):
        """Igual que `ensure`, pero acepta también fórmulas no deducibles."""
        try:
            return self.ensure(f, budget)
        except Failure:
            raise

    # -- modus tollens hacia atrás -----------------------------------------
    def _mt_backward(self, goal, depth, budget):
        """Para demostrar ¬A busca una implicación A → B y prueba ¬B.

        Así sale la cadena natural del libro: de p → q, q → r y ¬r se
        obtiene primero ¬q (MT) y luego ¬p (MT), en vez de dar un rodeo
        con la contraposición.
        """
        objetivo = goal.children[0]
        if objetivo in self._mt_seen:
            return None
        self._mt_seen.add(objetivo)
        try:
            for f in list(self.formulas):
                if f.kind != "imp" or f.children[0] != objetivo:
                    continue
                try:
                    marca = self.mark()
                    nb = self.prove(neg(f.children[1]), depth,
                                    budget.fork())
                except Failure:
                    self.rollback(marca)
                    continue
                return self.emit(goal, "MT", [self.cite(f), nb],
                                 depth=depth)
            return None
        finally:
            self._mt_seen.discard(objetivo)

    # -- demostración ------------------------------------------------------
    def prove(self, goal, depth, budget):
        budget.spend()
        if depth > 20:
            raise Failure()

        # (1) ya está escrita
        n = self.cite(goal)
        if n is not None:
            return n

        # (1b) hay una línea equivalente pero escrita con doble negación
        #      (por ejemplo, de la premisa ¬¬p se deduce p)
        for f in list(self.formulas):
            if f != goal and nf(f) == goal:
                return self.emit(goal, "Dn", [self.formula_index[f]])

        # (1c) modus tollens hacia atrás: para ¬A, si hay A → B se prueba ¬B
        if goal.kind == "not":
            n = self._mt_backward(goal, depth, budget)
            if n is not None:
                return n

        # (2) está en la saturación: se escriben sus líneas
        if goal in self.index_of:
            try:
                return self.ensure(goal, budget, depth)
            except Failure:
                pass

        # (3) si la meta es una implicación, se prueba por TD: se supone el
        #     antecedente y se deduce el consecuente (consejo del libro)
        if goal.kind == "imp":
            try:
                return self._subproof(goal, depth, budget)
            except Failure:
                pass

        # (4) una sola regla sobre lo ya escrito
        just = self._elimination(goal)
        if just is not None:
            return self.emit(goal, just[0], just[1], depth=depth)

        # (5) incorporar un lema de la saturación y reintentar
        n = self._pool_lemma_tactic(goal, depth, budget)
        if n is not None:
            return n

        # (5b) una conjunción se prueba componente a componente.  Se hace
        #      antes del análisis de casos para no encadenar dilemas
        #      innecesarios cuando las dos partes ya están escritas.
        if goal.kind == "and":
            try:
                return self._subproof(goal, depth, budget)
            except Failure:
                pass

        # (6) análisis de casos sobre una disyunción disponible
        n = self._cases_tactic(goal, depth, budget)
        if n is not None:
            return n

        # (7) subdemostración
        return self._subproof(goal, depth, budget)

    # -- lema tomado de la saturación --------------------------------------
    def _pool_lemma_tactic(self, goal, depth, budget):
        """Escribe una fórmula intermedia y reintenta la meta.

        Los lemas salen de la saturación o de las reglas que se pueden aplicar
        sobre las líneas ya escritas (por ejemplo la contraposición `p → ¬s`
        de la premisa `s → ¬p`, que es la línea 4 de la solución del
        examen).  Así se obtienen exactamente las líneas intermedias que luego
        se citan.
        """
        if depth > 10 or budget.left <= 2:
            return None
        interest = _atoms_of(goal)
        lits = _literals(goal)

        def score(f):
            """Preferencia de una fórmula como lema para alcanzar la meta.

            Se priorizan las fórmulas que ya contienen la meta (o su negación)
            como subfórmula: son las que van a permitir el silogismo
            disyuntivo o el modus tollens.
            """
            if _contains(f, goal):
                return -4
            if _contains(f, neg(goal)):
                return -3
            return len(_literals(f) & lits)

        cands = []

        # (a) fórmulas de la saturación
        for f in self.pool:
            if f in self.formula_index:
                continue
            if _atoms_of(f) & interest:
                cands.append((-score(f),
                              0 if f.kind == "or" else
                              1 if f.kind == "imp" else 2,
                              _complexity(f), f, None))

        # (b) fórmulas deducibles en un paso de lo ya escrito
        fs = list(self.formulas)
        pool_set = set(fs)
        derived = []
        for f in fs:
            rules_one_step(f, fs, pool_set, derived)
        # Además de las reglas de un solo paso, hacen falta las que combinan
        # dos líneas ya escritas.  Por ejemplo, dentro del supuesto «p» hay
        # que aplicar el silogismo disyuntivo a «¬p ∨ ¬r» para obtener ¬r;
        # sin esta llamada, el lema nunca llegaba a escribirse.
        rules_rebound(fs, pool_set, derived)
        for f, rule, support in derived:
            if f in self.formula_index:
                continue
            if not (_atoms_of(f) & interest):
                continue
            if all(s in self.formula_index for s in support):
                just = [self.formula_index[s] for s in support]
                cands.append((-score(f),
                              0 if f.kind == "or" else
                              1 if f.kind == "imp" else 2,
                              _complexity(f), f, (rule, just)))

        cands.sort(key=lambda t: (t[0], t[1], t[2]))

        # Se prueban conjuntos de lemas ya seleccionados y se comprueba si con
        # ellos se alcanza la meta.  Es una mirada de un solo paso, muy
        # barata, y basta para los casos que se dan en el examen.
        targeted = [(t[3], t[4]) for t in cands if t[0] <= -3][:6]
        groups = []
        if len(targeted) > 1:
            groups.append(targeted)
        for k in (1, 2, 3, 5, 8):
            groups.append([(t[3], t[4]) for t in cands[:k]])

        done = set()
        for group in groups:
            if not group:
                continue
            sig = tuple(f.key() for f, _ in group)
            if sig in done:
                continue
            done.add(sig)
            mark = self.mark()
            try:
                for f, info in group:
                    if info is None:
                        self.ensure(f, budget, depth)
                    else:
                        self.emit(f, info[0], info[1], depth=depth)
                just = self._elimination(goal)
                if just is not None:
                    return self.emit(goal, just[0], just[1], depth=depth)
            except Failure:
                pass
            self.rollback(mark)
        return None

    # -- cierre del contexto de un supuesto --------------------------------
    def _expand_context(self, depth, budget, max_size=16, max_lines=60):
        """Escribe consecuencias inmediatas de las líneas del supuesto.

        La saturación global no conoce el antecedente que se acaba de suponer.
        Dentro de una subdemostración interesa encadenar unos pocos pasos
        (MP, MT, silogismo disyuntivo...) para que luego la meta se alcance
        con una regla normal.  Se hace una sola vez por supuesto y con topes
        estrictos para no disparar el tiempo de búsqueda.
        """
        # En predicados la instanciación genera muchas variantes; esta
        # táctica está pensada para las cadenas proposicionales.
        if any(a.kind == "pred" for f in self.formulas for a in atoms(f)):
            return
        emitidas = 0
        for _ in range(4):
            fs = list(self.formulas)
            pool_set = set(fs)
            derived = []
            for f in fs:
                rules_one_step(f, fs, pool_set, derived)
            rules_rebound(fs, pool_set, derived)
            candidatos, vistos = [], set()
            for f, rule, support in derived:
                if f in self.formula_index or f in vistos:
                    continue
                if _complexity(f) > max_size:
                    continue
                if not all(s in self.formula_index for s in support):
                    continue
                vistos.add(f)
                candidatos.append((_complexity(f), f, rule, support))
            if not candidatos:
                break
            candidatos.sort(key=lambda t: t[0])
            for _, f, rule, support in candidatos[:20]:
                if emitidas >= max_lines or budget.left <= 2:
                    return
                budget.spend()
                just = [self.formula_index[s] for s in support]
                self.emit(f, rule, just, depth=depth)
                emitidas += 1

    # -- análisis de casos --------------------------------------------------
    def _cases_tactic(self, goal, depth, budget):
        """Demuestra la meta en dos ramas suponiendo cada disjunto.

        Es la regla del silogismo disyuntivo encadenado: si de A ∨ B se
        deduce la meta por ambas ramas, la meta se deduce sin suponer nada.
        """
        if depth > 6 or budget.left <= 2:
            return None
        disjunctions = []
        for f in self.formulas:
            if f.kind == "or" and goal not in parts_or(f):
                ps = parts_or(f)
                if len(ps) == 2 and all(
                        not (x.kind == "not" and x.children[0] == goal)
                        for x in ps):
                    disjunctions.append(f)
        # se prefieren las disyunciones más pequeñas
        disjunctions.sort(key=_complexity)
        for d in disjunctions[:4]:
            ps = parts_or(d)
            ramas = []
            ok = True
            for p in ps:
                # cada rama se demuestra en un contexto aparte, para que lo
                # que se deduce dentro de ella no se mezcle con la otra
                sub = self.clone()
                mark = len(sub.lines)
                nh = sub.emit(p, "Hip", [], hyp=True, depth=depth + 1)
                try:
                    nn = sub.prove(goal, depth + 1, budget.fork())
                except Failure:
                    ok = False
                    break
                ramas.append((mark, nh, nn, sub))
            if not ok:
                continue
            just = [self.cite(d)]
            for mark, nh, nn, subctx in ramas:
                remap = self.merge(subctx, mark)
                just.append(remap.get(nh, nh))
                just.append(remap.get(nn, nn))
            return self.emit(goal, "Dil", just, depth=depth, force=True)
        return None

    def _elimination(self, goal):
        """(regla, justificaciones) si `goal` sale de lo ya escrito."""
        fs = self.formulas
        cand = []

        def has(f):
            return f in self.formula_index

        for f in fs:
            if f.kind == "imp" and f.children[1] == goal and has(f.children[0]):
                cand.append((0, "MP", [self.cite(f),
                                       self.formula_index[f.children[0]]]))
        if goal.kind == "not":
            lit = goal.children[0]
            for f in fs:
                if f.kind == "imp" and f.children[0] == lit \
                        and has(neg(f.children[1])):
                    cand.append((0, "MT", [self.cite(f),
                                           self.formula_index[neg(f.children[1])]]))
        for f in fs:
            if f.kind == "and" and goal in parts_and(f):
                cand.append((0, "Simp", [self.cite(f)]))
        if goal.kind == "imp":
            ga, gb = goal.children
            for f in fs:
                if f.kind != "imp" or f.children[0] != ga:
                    continue
                for g in fs:
                    if g.kind == "imp" and g.children[0] == f.children[1] \
                            and g.children[1] == gb:
                        cand.append((1, "Sil", [self.cite(f), self.cite(g)]))
        for f in fs:
            if f.kind == "or":
                ps = parts_or(f)
                if len(ps) == 2 and ps[0] == ps[1] == goal:
                    cand.append((0, "IDD", [self.cite(f)]))
                if len(ps) >= 2 and goal in ps:
                    i = ps.index(goal)
                    others = [x for j, x in enumerate(ps) if j != i]
                    for other in others:
                        if has(neg(other)):
                            cand.append((0, "SD", [self.cite(f),
                                                   self.formula_index[neg(other)]]))
                    # n-aria: se elimina un disjunto y se cita el último
                    if len(others) >= 2:
                        sub = disj(*others)
                        for other in others:
                            if has(neg(other)):
                                rest = [x for x in others if x != other]
                                if rest and all(has(x) for x in rest):
                                    just = [self.cite(f),
                                            self.formula_index[neg(other)]]
                                    just += [self.formula_index[x] for x in rest]
                                    cand.append((0, "SD", just))

        # Silogismo disyuntivo encadenado:
        #     (X ∨ G) , (G ∨ ¬X)   ⊢   G
        # Si X entonces ¬G por la segunda disyunción, lo que contradice X;
        # luego necesariamente G.
        for f in fs:
                if f.kind != "or":
                    continue
                ps = parts_or(f)
                if len(ps) != 2 or goal not in ps:
                    continue
                x = ps[1] if ps[0] == goal else ps[0]
                for g2 in fs:
                    if g2.kind != "or" or g2 is f:
                        continue
                    qs = parts_or(g2)
                    if len(qs) != 2 or goal not in qs:
                        continue
                    y = qs[1] if qs[0] == goal else qs[0]
                    if y == neg(x):
                        cand.append((0, "SD", [self.cite(f), self.cite(g2)]))
        for f in fs:
            # eliminación del negador: de ¬¬A se sigue A
            if f.kind == "not" and f.children[0].kind == "not" \
                    and f.children[0].children[0] == goal:
                cand.append((0, "Dn", [self.cite(f)]))
        if goal.kind == "imp":
            ga, gb = goal.children
            if ga.kind == "not" and gb.kind == "not":
                a, b = ga.children[0], gb.children[0]
                for f in fs:
                    # la contraposición de b→a es ¬a→¬b
                    if f.kind == "imp" and f.children[0] == b \
                            and f.children[1] == a:
                        cand.append((4, "Cp", [self.cite(f)]))
        if goal.kind == "or":
            ps = parts_or(goal)
            if len(ps) == 2:
                x, y = ps
                if x.kind == "not" and y.kind in ("var", "pred"):
                    for f in fs:
                        if f.kind == "imp" and f.children[0] == x.children[0] \
                                and f.children[1] == y:
                            cand.append((2, "DI2", [self.cite(f)]))
                if y.kind == "not" and x.kind in ("var", "pred"):
                    for f in fs:
                        if f.kind == "imp" and f.children[0] == y.children[0] \
                                and f.children[1] == x:
                            cand.append((2, "DI2", [self.cite(f)]))
        if goal.kind in ("var", "pred"):
            for f in fs:
                if f.kind in ("forall", "exists") and f.data == "x":
                    inst = subst(f.children[0], "x", goal)
                    if inst == goal:
                        cand.append((0, "EG", [self.cite(f)]))
                    if inst.kind == "imp" and inst.children[0] == goal:
                        cand.append((0, "EG2", [self.cite(f)]))
        # De Morgan:  ¬(A ∧ B) ⊢ ¬A ∨ ¬B    y    ¬(A ∨ B) ⊢ ¬A ∧ ¬B
        if goal.kind == "or" and len(parts_or(goal)) == 2:
            x, y = parts_or(goal)
            if x.kind == "not" and y.kind == "not":
                for f in fs:
                    if f.kind == "not" and f.children[0].kind == "and":
                        ps = parts_and(f.children[0])
                        if len(ps) == 2 and {x.children[0], y.children[0]} \
                                == set(ps):
                            cand.append((1, "DM1", [self.cite(f)]))
        if goal.kind == "and" and len(parts_and(goal)) == 2:
            x, y = parts_and(goal)
            if x.kind == "not" and y.kind == "not":
                for f in fs:
                    if f.kind == "not" and f.children[0].kind == "or":
                        ps = parts_or(f.children[0])
                        if len(ps) == 2 and {x.children[0], y.children[0]} \
                                == set(ps):
                            cand.append((1, "DM2", [self.cite(f)]))
        if not cand:
            return None
        cand.sort(key=lambda t: t[0])
        return cand[0][1], cand[0][2]

    def _subproof(self, goal, depth, budget):
        k = goal.kind

        if k == "and":
            ps = parts_and(goal)
            just = [self.prove(p, depth + 1, budget.fork()) for p in ps]
            return self.emit(goal, "IC", just, depth=depth)

        if k == "or":
            for p in parts_or(goal):
                mark = self.mark()
                try:
                    n = self.prove(p, depth + 1, budget.fork())
                except Failure:
                    self.rollback(mark)
                    continue
                return self.emit(goal, "Ad", [n], depth=depth)
            raise Failure()

        if k == "imp":
            ant, cons = goal.children
            sub = self.clone()
            mark = len(sub.lines)
            nh = sub.emit(ant, "Hip", [], hyp=True, depth=depth + 1)
            try:
                sub._expand_context(depth + 1, budget.fork())
                nc = sub.prove(cons, depth + 1, budget.fork())
            except Failure:
                raise
            remap = self.merge(sub, mark)
            just = [remap.get(nh, nh), remap.get(nc, nc)]
            return self.emit(goal, "II", just, depth=depth, force=True)

        if k == "not" and goal.children[0].kind in ("var", "pred"):
            if depth > 2:
                raise Failure()
            return self._reductio(goal, depth, budget)

        # un átomo también se puede probar por reducción al absurdo:
        # se supone ¬A, se llega a A ∧ ¬A y se concluye ¬¬A (Abs) y A (DN)
        if k in ("var", "pred"):
            if depth > 2:
                raise Failure()
            return self._reductio_atom(goal, depth, budget)

        if k == "exists":
            v = _fresh(_atoms_of(goal))
            body = subst(goal.children[0], goal.data, F.var(v))
            sub = self.clone()
            mark = len(sub.lines)
            try:
                n = sub.prove(body, depth, budget.fork())
            except Failure:
                raise
            remap = self.merge(sub, mark)
            return self.emit(goal, "IP", [remap.get(n, n)], depth=depth,
                             force=True)

        if k == "forall":
            v = _fresh(_atoms_of(goal))
            body = subst(goal.children[0], goal.data, F.var(v))
            sub = self.clone()
            mark = len(sub.lines)
            try:
                n = sub.prove(body, depth, budget.fork())
            except Failure:
                raise
            remap = self.merge(sub, mark)
            return self.emit(goal, "IG", [remap.get(n, n)], depth=depth,
                             force=True)

        raise Failure()

    def _reductio_atom(self, goal, depth, budget):
        """Prueba A suponiendo ¬A y llegando a la contradicción A ∧ ¬A."""
        sub = self.clone()
        mark = len(sub.lines)
        nh = sub.emit(neg(goal), "Hip", [], hyp=True, depth=depth + 1)
        try:
            nn = sub.prove(goal, depth + 1, budget.fork())
            ncontra = sub.emit(F.and_(goal, neg(goal)), "IC",
                               [nn, nh], depth=depth + 1, force=True)
        except Failure:
            raise
        remap = self.merge(sub, mark)
        nabs = self.emit(neg(neg(goal)), "Abs",
                         [remap.get(nh, nh), remap.get(ncontra, ncontra)],
                         depth=depth)
        return self.emit(goal, "Dn", [nabs], depth=depth, force=True)

    def _reductio(self, goal, depth, budget):
        """Para ¬A se supone A y se deriva ¬A; se cierra por absorción."""
        inner = goal.children[0]
        sub = self.clone()
        mark = len(sub.lines)
        nh = sub.emit(inner, "Hip", [], hyp=True, depth=depth + 1)
        try:
            nn = sub.prove(neg(inner), depth + 1, budget.fork())
        except Failure:
            raise
        remap = self.merge(sub, mark)
        just = [remap.get(nh, nh), remap.get(nn, nn)]
        return self.emit(goal, "Abs", just, depth=depth, force=True)


# ==========================================================================
# Comprobación semántica rápida (sólo cálculo de proposiciones)
# ==========================================================================
def _eval_prop(f, valor):
    k = f.kind
    if k == "var":
        return valor[f.data]
    if k == "not":
        return not _eval_prop(f.children[0], valor)
    if k == "and":
        return all(_eval_prop(c, valor) for c in f.children)
    if k == "or":
        return any(_eval_prop(c, valor) for c in f.children)
    if k == "imp":
        return (not _eval_prop(f.children[0], valor)) or \
            _eval_prop(f.children[1], valor)
    if k == "iff":
        return _eval_prop(f.children[0], valor) == \
            _eval_prop(f.children[1], valor)
    return None


def _semanticamente_valido(premises, goal):
    """True/False si se puede decidir por tabla de verdad; None si no.

    Antes de lanzar la búsqueda conviene saber si la conclusión se sigue de
    las premisas.  Así, un argumento inválido se rechaza al instante en vez
    de consumir el presupuesto de la demostración.
    """
    formulas = list(premises) + [goal]
    for f in formulas:
        for a in atoms(f):
            if a.kind != "var":
                return None
    letras = sorted(_atoms_of(goal).union(
        *[set(_atoms_of(p)) for p in premises]) if premises else
        set(_atoms_of(goal)))
    if len(letras) > 12:
        return None
    for bits in itertools.product([False, True], repeat=len(letras)):
        valor = dict(zip(letras, bits))
        if all(_eval_prop(p, valor) for p in premises):
            if not _eval_prop(goal, valor):
                return False
    return True


# ==========================================================================
# Punto de entrada
# ==========================================================================
def prove(premises, goal, caps=(250, 800), levels=(4, 6),
          budgets=(600, 4000, 25000)):
    """Demuestra `goal` a partir de `premises`.

    Devuelve una lista de objetos Line, o None si no se encuentra deducción.
    """
    if _semanticamente_valido(premises, goal) is False:
        return None
    # los átomos de interés son los de la conclusión y los de las premisas:
    # las líneas intermedias combinan unos y otros
    interest = _atoms_of(goal)
    for p in premises:
        interest |= _atoms_of(p)
    original = goal
    goal = nf(goal)
    base = _complexity(goal)
    for cap, lv in zip(caps, levels):
        # el límite de longitud se calcula a partir de la meta: las líneas
        # intermedias que hacen falta son algo más largas que la conclusión,
        # pero no hace falta llegar muy lejos.
        # Las fórmulas distributivas (DD) pueden ser bastante más largas que
        # la meta; por eso se prueban también tamaños mayores.
        for extra in (3, 7, 11, 15):
            pool, derivation = saturate(premises, interest, cap, lv,
                                        base + extra)
            for size in budgets:
                b = ProofBuilder(pool, derivation)
                for p in premises:
                    b.emit(p, "PREM", [])
                try:
                    n = b.prove(goal, 0, Budget(size))
                except (Failure, RecursionError):
                    continue
                if goal != original:
                    n = b.emit(original, "IDN", [n], depth=0, force=True)
                return prune(b.lines, n)
    # último recurso: sin saturación, sólo eliminación y subdemostración
    for size in budgets:
        b = ProofBuilder([], {})
        for p in premises:
            b.emit(p, "PREM", [])
        try:
            n = b.prove(goal, 0, Budget(size))
        except (Failure, RecursionError):
            continue
        if goal != original:
            n = b.emit(original, "IDN", [n], depth=0, force=True)
        return prune(b.lines, n)
    return None


def prune(lines, root=None):
    """Elimina las líneas que no se usan para llegar a la conclusión.

    Al añadir lemas auxiliares pueden quedar líneas intermedias sin citar;
    aquí se quita todo lo que no sea necesario para la línea `root` (por
    defecto, la última).
    """
    if not lines:
        return lines
    keep = set()
    stack = [root if root is not None else len(lines)]
    while stack:
        i = stack.pop()
        if i < 1 or i in keep or i > len(lines):
            continue
        keep.add(i)
        for j in lines[i - 1].just:
            stack.append(j)
    out = []
    for i, ln in enumerate(lines, start=1):
        if i in keep:
            ln.just = [j for j in ln.just if j in keep]
            out.append(ln)
    # renumerar
    remap = {}
    for new, ln in enumerate(out, start=1):
        remap[ln.n] = new
    for ln in out:
        ln.just = [remap[j] for j in ln.just]
        ln.n = 0
    for new, ln in enumerate(out, start=1):
        ln.n = new
    return out

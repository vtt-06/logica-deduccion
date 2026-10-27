"""Vocabulario y formalización automática de frases en español.

El programa no intenta "adivinar" con una lista de frases hechas: analiza la
frase por capas, de la conectiva más débil a la más fuerte (↔, →, ∨, ∧, ¬),
igual que se resuelve una fórmula.  Para decidir dónde termina una cláusula
usa un léxico de formas verbales del español y las palabras que suelen abrir
una oración principal.

Si una frase no se reconoce, se devuelve ``None`` y el programa pide al
usuario que la escriba a mano, en vez de inventarse una formalización.
"""

import re
from difflib import SequenceMatcher

from formulas import F, atoms, parse_formula, render

# --------------------------------------------------------------------------
# Letras de variables de enunciado: se empieza por p, como en el curso
# --------------------------------------------------------------------------
ATOM_LETTERS = "pqrstuvwxyz"


def _letra_enunciado(indice):
    """Letra para el enunciado número `indice` (empezando en 0).

    Se empieza en la p y se sigue el abecedario.  Si un ejercicio agota la
    z, se continúa con aa, ab, ac… para no reutilizar letras ni mezclar dos
    premisas en un mismo átomo.
    """
    if indice < len(ATOM_LETTERS):
        return ATOM_LETTERS[indice]
    resto = indice - len(ATOM_LETTERS)
    return chr(ord("a") + resto // 26) + chr(ord("a") + resto % 26)


class Term:
    """Un sintagma del vocabulario: nombre interno y texto del enunciado."""

    def __init__(self, letter, text, negated_text=None):
        self.letter = letter        # 'p', 'q'… en proposicional; 'C','D'… en predicados
        self.text = text
        self.negated_text = negated_text or ("no " + text)


# ==========================================================================
# Limpieza y utilidades de análisis
# ==========================================================================
def strip_accents(s):
    table = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
             "ü": "u", "Á": "A", "É": "E", "Í": "I", "Ó": "O",
             "Ú": "U", "Ü": "U"}
    return "".join(table.get(c, c) for c in s)


def _norm(text):
    """Clave de comparación: minúsculas, sin acentos y con los verbos en su
    raíz, para que "llueva" y "llueve" cuenten como el mismo enunciado."""
    # «habrás aprobado el examen» y «aprobarás el examen» son la misma
    # proposición.  Se reduce el futuro perfecto al infinitivo para que el
    # vocabulario no cree dos átomos distintos.
    text = re.sub(
        r"\b(?:habr[eé]|habr[áa]s|habr[áa]|habremos|habr[eé]is|habr[áa]n)"
        r"\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\b",
        lambda m: _participio_a_forma_futura(m.group(1)), text,
        flags=re.IGNORECASE)
    return " ".join(_stem_word(w) for w in _words(text))


def _participio_a_forma_futura(palabra):
    """Devuelve una forma verbal canónica equivalente a un participio.

    Se apoya en el léxico de verbos regulares.  La forma devuelta termina en
    «-as» para que ``_stem_word`` la reduzca a la misma raíz que el futuro
    simple («aprobarás»).  Si no se reconoce, se deja la palabra tal cual: es
    preferible no unir dos enunciados distintos antes que inventar una
    equivalencia.
    """
    clave = strip_accents(palabra.lower())
    tabla = globals().get("_PARTICIPIOS", {})
    if clave in tabla:
        return tabla[clave] + "as"
    return palabra


def _words(text):
    return re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", text)


def _claves_pred(text):
    """Claves de un predicado, uniendo singular y plural.

    "ser grandes" y "ser grande" tienen que ser el mismo predicado; lo mismo
    ocurre con "ser cubos"/"ser cubo" o "ser lectores"/"ser lector".  Se
    generan variantes quitando la -s final y, si existe, la -es final.
    """
    base = _norm(text)
    claves = {base}
    palabras = base.split()
    if not palabras:
        return claves
    ultima = palabras[-1]
    candidatas = []
    if ultima.endswith("s") and len(ultima) > 3:
        candidatas.append(ultima[:-1])
    if ultima.endswith("es") and len(ultima) > 4:
        candidatas.append(ultima[:-2])
    for cand in candidatas:
        claves.add(" ".join(palabras[:-1] + [cand]))
    return claves


def _depth_at(text, pos):
    """Profundidad de paréntesis en `pos` (0 = nivel superior)."""
    depth = 0
    for ch in text[:pos]:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
    return depth


def _top_matches(text, pattern):
    """Todas las apariciones de `pattern` fuera de paréntesis."""
    return [m for m in re.finditer(pattern, text, re.IGNORECASE)
            if _depth_at(text, m.start()) == 0]


def _split_at(text, pattern, last=False):
    """Parte `text` por un marcador de nivel superior."""
    ms = _top_matches(text, pattern)
    if not ms:
        return None
    m = ms[-1] if last else ms[0]
    izq = text[:m.start()].strip(" ,;")
    der = text[m.end():].strip(" ,;")
    if not izq or not der:
        return None
    return izq, der


def _leading(text, patterns):
    """Primer patrón que aparece al principio de la frase."""
    for pat in patterns:
        m = re.match(r"^\s*(?:" + pat + r")\b", text, re.IGNORECASE)
        if m:
            return m
    return None


def _outer_parens(text):
    """True si toda la frase está dentro de un paréntesis."""
    t = text.strip()
    if len(t) < 2 or t[0] not in "([{":
        return False
    depth = 0
    for i, ch in enumerate(t):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return i == len(t) - 1
    return False


def _split_comma(text):
    """Parte por la primera coma de nivel superior."""
    depth = 0
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            izq, der = text[:i], text[i + 1:]
            if izq.strip() and der.strip():
                return izq.strip(), der.strip()
            return None
    return None


# ==========================================================================
# Léxico
# ==========================================================================
# Palabras que suelen abrir la oración principal de un condicional.
CONS_STARTERS = {
    "se", "no", "me", "te", "le", "les", "nos", "el", "la", "los", "las",
    "un", "una", "unos", "unas", "este", "esta", "ese", "esa", "aquel",
    "aquella", "todo", "toda", "todos", "todas", "alguien", "nadie",
    "dios", "siempre", "nunca", "también", "tambien", "entonces", "por",
    "para", "con", "sin", "cuando", "mientras", "aunque", "hay", "existe",
    "yo", "tú", "tu", "él", "el", "ella", "nosotros", "vosotros", "ellos",
    "ellas", "esto", "eso", "aquello", "algo", "nada", "cada", "cualquier",
}

# Formas verbales frecuentes.  Se guardan sin acentos y en minúsculas.
VERB_WORDS = set("""
soy eres es somos sois son era eras eramos eran fui fuiste fue fuimos fueron
sea seas sean seria serian siendo sido ser estar estoy estas esta estamos
estais estan estaba estabamos estaban estuve estuvo estuvieron esten
estara estaran estaria estando estado haber he has ha hemos habeis han habia
habian hubo hubieron haya hayan habra habran habria tener tengo tienes tiene
tenemos teneis tienen tenia teniamos tenian tuvo tuvieron tenga tengan tendra
tendran tendria poder puedo puedes puede podemos podeis pueden podia podian
pudo pudieron pueda puedan podra podran podria querer quiero quieres quiere
queremos quereis quieren queria querian quiso quisieron quiera quieran querra
querran deber debo debes debe debemos deben debia debian debio debieron deba
deban debera deberan saber sabes sabe sabemos sabeis saben sabia sabian
supo supieron sepa sepan sabra sabran sabre sabras hacer hago haces hace
hacemos haceis hacen hacia hacian hizo hicieron haga hagan hara haran haria ir
voy vas va vamos vais van iba iban vaya vayan ira iran venir vengo vienes
viene venimos venis vienen venia venian vino vinieron venga vengan vendra
vendran decir digo dices dice decimos decis dicen decia decian dijo dijeron
diga digan dira diran ver veo ves ve vemos veis ven veia veian vio vieron vea
vean vera veran dar doy das da damos dais dan daba daban dio dieron den
dara daran poner pongo pones pone ponemos poneis ponen ponia ponian puso
pusieron ponga pongan pondra pondran salir salgo sales sale salimos salen
salia salian salio salieron salga salgan saldra saldran llegar llego llegas
llega llegamos llegan llegaba llegaban llego llegaron llegue lleguen llegara
pasar paso pasas pasa pasamos pasan pasaba pasaban paso pasaron pase pasen
pasara crear creo creas crea creamos crean creaba creaban creo crearon cree
creen creara crearan existir existo existes existe existimos existen existia
existian existio existieron exista existan existira existiran llover llueve
llovia llovio llovera lloveria llueva lluevan nevar nieva nevaba nevo nevara
nieve correr corro corres corre corremos corren corria corrian corrio
corrieron corra corran correra andar ando andas anda andamos andan andaba
andaban anduvo anduvieron ande anden andara estudiar estudio estudias estudia
estudiamos estudian estudiaba estudiaban estudio estudiaron estudie estudien
estudiara estudiaran aprobar apruebo apruebas aprueba aprobamos aprueban
aprobaba aprobaban aprobo aprobaron apruebe aprueben aprobara aprobaran
suspender suspendo suspende suspenden suspendio suspendieron suspenda ganar
gano ganas gana ganamos ganan gano ganaron gane ganen ganara viajar viajo
viajas viaja viajamos viajan viajaba viajaban viajo viajaron viaje viajen viajara perder pierdo
pierdes pierde perdemos pierden perdio perdieron pierda pierdan perdera comer
comes come comemos comen comia comian comio comieron coma coman comera
beber bebo bebes bebe bebemos beben bebia bebieron beba vivir vivo vives vive
vivimos viven vivia vivian vivio vivieron viva vivan vivira morir muero
mueres muere mueren murio murieron muera mueran morira amar amo amas ama
amamos aman amo amaron ame amen amara odiar odio odias odia odian odio
odiaron odie trabajar trabajo trabajas trabaja trabajamos trabajan trabajaba
trabajo trabajaron trabaje trabajen trabajara jugar juego juegas juega jugamos
juegan jugaba jugo jugaron juegue jueguen jugara leer leo lees lee leemos leen
leia leian leyo leyeron lea lean leera escribir escribo escribes escribeescribimos escriben escribia escribio escribieron escriba escriban escribira
comprar compro compras compra compran compro compraron compre compren comprara
vender vendo vendes vende venden vendio vendieron venda abrir abro abres abre
abren abrio abrieron abra abran abrira cerrar cierro cierras cierra cierran
cerro cerraron cierre cierren cerrara empezar empiezo empiezas empieza
empiezan empezo empezaron empiece empiecen empezara terminar termino terminas
termina terminan termino terminaron termine terminen terminara conseguir
consigo consigues consigue consiguen consiguio consiguieron consiga intentar
intento intentas intenta intentan intento intentaron intente necesitar
necesito necesitas necesita necesitan necesito necesitaron necesite parecer
parezco pareces parece parecen parecia parecio parecieron parezca resultar
resulto resultas resulta resultan resulto resultaron resulte conocer conozco
distingo distingues distingue distinguimos distinguen distinguia distinguian
distinguio distinguieron distinga distingan distinguira distinguiran
estudies apruebes suspendas corras andes comas vivas trabajes juegues leas
escribas compres vendas abras cierres empieces termines consigas intentes
necesites parezcas pienses creas sientas duermas hables escuches mires lleves
traigas dejes sigas entiendas recuerdes olvides encuentres esperes llames
tomes uses ocurra suceda llueva nieve salga llegue pase cree exista
conoces conoce conocen conocia conocio conocieron conozca pensar pienso
piensas piensa piensan pense penso pensaron piense piensen creer creo crees
cree creen creia creyo creyeron crea crean sentir siento sientes siente
sienten sintio sintieron sienta dormir duermo duermes duerme duermen durmio
durmieron duerma hablar hablo hablas habla hablan hablo hablaron hable hablen
hablara escuchar escucho escuchas escucha escuchan escucho escucharon
escuche mirar miro miras mira miran miro miraron mire llevar llevo llevas
lleva llevan llevo llevaron lleve traer traigo traes trae traen traia trajo
trajeron traiga dejar dejo dejas deja dejan dejo dejaron deje seguir sigo
sigues sigue siguen siguio siguieron siga entender entiendo entiendes
entiende entienden entendio entendieron entienda recordar recuerdo recuerdas
recuerda recuerdan recordo recordaron recuerde olvidar olvido olvidas olvida
olvidan olvido olvidaron olvide encontrar encuentro encuentras encuentra
encuentran encontro encontraron encuentre esperar espero esperas espera
esperan espero esperaron espere llamar llamo llamas llama llaman llamo
llamaron llame tomar tomo tomas toma toman tomo tomaron tome usar uso usas
usa usan use funcionar funciona funcionan funciono funcionara ocurrir ocurre
ocurren ocurrio ocurrira suceder sucede suceden sucedio depender depende
dependen dependio pertenecer pertenece pertenecen pertenecio contener contiene
contienen contuvo incluir incluye incluyen incluyo oir oigo oyes oye oyen oyo
oyeron oiga caer caigo caes cae caen cayo cayeron caiga subir subo subes sube
suben subio subieron suba bajar bajo bajas baja bajan bajo bajaron baje
entrar entro entras entra entran entro entraron entre volver vuelvo vuelves
vuelve vuelven volvio volvieron vuelva deber poder querer saber hacer decir
ver dar poner salir llegar pasar crear existir llover nevar correr andar
estudiar aprobar suspender ganar viajar perder comer beber vivir morir amar odiar
trabajar jugar leer escribir comprar vender abrir cerrar empezar terminar
conseguir intentar necesitar parecer resultar conocer pensar creer sentir
dormir hablar escuchar mirar llevar traer dejar seguir entender recordar
olvidar encontrar esperar llamar tomar usar funcionar ocurrir suceder
depender pertenecer contener incluir oir caer subir bajar entrar volver
""".split())

# Terminaciones que casi siempre delatan un verbo conjugado.
VERB_ENDINGS = ("ando", "iendo", "aron", "ieron", "aste", "iste",
                "aba", "aban", "abamos", "aremos", "eremos", "iremos",
                "aria", "erian", "arian")

# Lemas de verbos habituales que no están en la lista anterior.  A partir de
# ellos se generan las formas regulares, para que el programa reconozca
# verbos nuevos ("sudo", "gasto", "aprendo"...) sin depender de una lista de
# frases hechas.
VERB_LEMMAS = set("""
abrir acabar aceptar acompañar aconsejar acordar acostar actuar admirar
admitir adoptar adorar afirmar agradar aguantar ahorrar alabar almorzar amar
andar animar anunciar apagar aparecer aplaudir apoyar aprender aprobar arreglar
arriesgar asistir asociar asegurar atacar atender aumentar autorizar avanzar
averiguar bailar bajar beber bendecir buscar caber caer callar calentar cambiar
caminar cansar cantar cargar casar cenar ceder celebrar circular cocinar coger
colgar comenzar comer cometer comparar compartir comprar comprender comunicar conducir
confiar conocer conseguir considerar construir consumir contar contener
contestar continuar controlar convertir convivir correr cortar crear crecer
creer cruzar cuidar cumplir dar deber decidir decir declarar dejar demostrar
denunciar depender describir descubrir desear despedir destruir detener
devolver discutir disfrutar disponer distinguir divertir doler dormir dudar
echar elegir empezar emplear encender encontrar enfadar enfermar enseñar
entender entrar entregar enviar equivocar escapar escoger escribir escuchar
esperar esquiar establecer estar estudiar evitar exigir existir explicar
explorar exponer expresar faltar fijar fingir formar fumar funcionar ganar
gastar girar gobernar golpear gritar guardar gustar hablar hacer herir huir
imaginar impedir importar incluir indicar informar insistir intentar invertir
investigar ir jugar juntar jurar ladrar lanzar leer levantar limpiar llamar
llegar llenar llevar llorar llover luchar mantener mandar manejar marcar
masticar matar mejorar mentir merecer meter mirar mojar molestar montar morir
mover mostrar nadar nacer navegar necesitar negar nevar oir olvidar opinar
organizar pagar parar parecer participar partir pasar pedir pegar pensar perder
perdonar permitir pertenecer pesar picar pintar planear plantar poder poner
practicar preguntar prender preparar presentar prestar producir prohibir
prometer proponer proteger provocar publicar querer quedar quemar recibir
reclamar recordar recorrer referir regalar regar reir repetir representar
requerir reservar resolver responder resultar retirar reunir revelar robar
romper saber sacar salir saltar saludar satisfacer secar seguir sentar sentir
separar ser servir significar sobrevivir soler solicitar sonar sonreir
soportar sorprender subir suceder sudar sufrir sugerir sujetar sumar suponer
tapar temer tender tener terminar tirar tocar tomar trabajar traer tratar
triunfar unir usar utilizar vaciar valer vender venir ver vestir viajar vivir
volar volver votar
""".split())

# Palabras que, aunque parezcan una forma verbal regular, son nombres o
# adjetivos corrientes.
NOUN_STOP = set("""
dia tia mia tuya suya casa mesa silla puerta ventana tierra piedra agua nieve
lluvia calle ciudad universidad verdad libertad amistad felicidad realidad
sociedad partido estado cuidado lado modo mundo todo nada otro mismo tipo
tiempo cuerpo pueblo peligro numero ultimo proximo publico politico medico
tecnico fisico logico clasico basico rapido frio vacio propio limpio sucio
amplio simple doble libre facil dificil posible imposible grande pequeno
mediano alto bajo bueno malo nuevo viejo blanco negro rojo verde azul gris
rosa lunes martes miercoles jueves viernes sabado domingo hombre mujer nino
nina padre madre hermano hermana amigo amiga perro gato coche libro arbol flor
mar lugar materia historia filosofia logica informatica matematica ciencia
experiencia conciencia paciencia violencia presencia ausencia diferencia
importancia distancia instancia sustancia herencia tendencia urgencia
emergencia agencia idea linea familia memoria gracia especie serie paso trabajo
puesto dicho hecho vuelta vista sentido vestido salida llegada comida bebida
corrida subida bajada entrada compra venta cambio uso gasto sudor calor dolor
color olor sabor valor favor error horror temor rumor motor doctor director
actor autor
""".split())


def _formas_regulares(lema):
    """Formas regulares de un verbo, sin acentos y en minúsculas."""
    raiz = lema[:-2]
    if lema.endswith("ar"):
        terminaciones = (
            "o as a amos ais an e es emos eis en "
            "e aste o amos asteis aron "
            "aba abas abamos abais aban "
            "are aras ara aremos areis aran "
            "aria arias ariamos ariais arian "
            "ando ado"
        ).split()
    elif lema.endswith("er"):
        terminaciones = (
            "o es e emos eis en a as a amos ais an "
            "i iste io imos isteis ieron "
            "ia ias iamos iais ian "
            "ere eras era eremos ereis eran "
            "eria erias eriamos eriais erian "
            "iendo ido"
        ).split()
    else:
        terminaciones = (
            "o es e imos is en a as a amos ais an "
            "i iste io imos isteis ieron "
            "ia ias iamos iais ian "
            "ire iras ira iremos ireis iran "
            "iria irias iriamos iriais irian "
            "iendo ido"
        ).split()
    return {strip_accents(raiz + t) for t in terminaciones}


_VERB_FORMS = set()
_PARTICIPIOS = {}
for _lema in VERB_LEMMAS:
    _VERB_FORMS |= _formas_regulares(_lema)
    if _lema.endswith("ar"):
        _part = _lema[:-2] + "ado"
    else:
        _part = _lema[:-2] + "ido"
    _PARTICIPIOS[strip_accents(_part)] = _lema
# Las formas de dos letras ("de", "dé") coinciden con preposiciones y
# artículos; los verbos importantes de ese tamaño ya están en VERB_WORDS.
_VERB_FORMS = {f for f in _VERB_FORMS if len(f) >= 3}


# Raíces irregulares: formas que no se obtienen quitando una terminación.
_IRREG = {}
for _lema, _formas in {
        "ser": "es son era eran fue fueron sea sean soy eres somos sois sido",
        "estar": "estoy estas estamos estais estan estaba estaban estuvo "
                 "estuvieron estado estando",
        "haber": "he has ha hemos han habia habian hubo hubieron hay haya "
                 "hayan habra habran",
        "tener": "tengo tienes tiene tenemos tienen tenia tenian tuvo "
                 "tuvieron tenga tengan",
        "poder": "puedo puedes puede podemos pueden podia podian pudo "
                 "pudieron pueda puedan",
        "querer": "quiero quieres quiere queremos quieren queria querian "
                  "quiso quisieron quiera quieran",
        "hacer": "hago haces hace hacemos hacen hacia hacian hizo hicieron "
                 "haga hagan",
        "ir": "voy vas va vamos vais van iba iban",
        "venir": "vengo vienes viene venimos vienen venia venian vino "
                 "vinieron venga vengan",
        "decir": "digo dices dice decimos dicen decia decian dijo dijeron "
                 "diga digan",
        "ver": "veo ves ve vemos veis ven veia veian vio vieron vea vean",
        "dar": "doy das da damos dais dan daba daban dio dieron",
        "poner": "pongo pones pone ponemos ponen ponia ponian puso pusieron "
                 "ponga pongan",
        "saber": "sabes sabe sabemos sabeis saben sabia sabian supo supieron "
                 "sepa sepan",
        "llover": "llueve llueva llovia llovio llovera lloveria",
        "nevar": "nieva nieve nevaba nevo nevara",
}.items():
    for _f in _formas.split():
        _IRREG[strip_accents(_f.lower())] = _lema

# Futuros irregulares: la raíz no se obtiene quitando la terminación del
# infinitivo (podrás, tendrás, saldrás...), así que hay que reconocerlos
# expresamente para no confundirlos con nombres.  Se añaden después para no
# sobrescribir las formas de presente del diccionario anterior.
_FUTUROS_IRREG = {
    "ser": "sere seras sera seremos sereis seran",
    "estar": "estare estaras estara estaremos estareis estaran",
    "haber": "habre habras habra habremos habreis habran",
    "tener": "tendre tendras tendra tendremos tendreis tendran",
    "poder": "podre podras podra podremos podreis podran",
    "querer": "querre querras querra querremos querreis querran",
    "hacer": "hare haras hara haremos hareis haran",
    "ir": "ire iras ira iremos ireis iran",
    "venir": "vendre vendras vendra vendremos vendreis vendran",
    "decir": "dire diras dira diremos direis diran",
    "ver": "vere veras vera veremos vereis veran",
    "dar": "dare daras dara daremos dareis daran",
    "poner": "pondre pondras pondra pondremos pondreis pondran",
    "saber": "sabre sabras sabra sabremos sabreis sabran",
    "salir": "saldre saldras saldra saldremos saldreis saldran",
    "valer": "valdre valdras valdra valdremos valdreis valdran",
}
for _lema, _formas in _FUTUROS_IRREG.items():
    for _f in _formas.split():
        _IRREG[strip_accents(_f.lower())] = _lema

# Terminaciones que se quitan para obtener la raíz de un verbo.
_VERB_SUFIJOS = ("abamos", "aremos", "eremos", "iremos", "abais", "ariais",
                 "arian", "iendo", "ando", "ieron", "aron", "aban", "abas",
                 "aste", "iste", "ado", "ido", "amos", "emos", "imos", "ais",
                 "eis", "an", "en", "as", "es", "ar", "er", "ir", "o", "a",
                 "e")


def _stem_word(w):
    """Raíz aproximada de una palabra (sólo se tocan formas verbales)."""
    wl = strip_accents(w.lower())
    if wl in _IRREG:
        return _IRREG[wl]
    if wl in NOUN_STOP:
        return wl
    if wl not in VERB_WORDS and wl not in _VERB_FORMS:
        return wl
    for suf in _VERB_SUFIJOS:
        if wl.endswith(suf) and len(wl) - len(suf) >= 3:
            return wl[:-len(suf)]
    return wl


COND_FRONT = [
    r"siempre\s+y\s+cuando",
    r"siempre\s+que",
    r"a\s+condici[oó]n\s+de\s+que",
    r"con\s+tal\s+de\s+que",
    r"en\s+caso\s+de\s+que",
    r"en\s+el\s+caso\s+de\s+que",
    r"si",
    r"cuando",
]

COND_BACK = [
    r"siempre\s+y\s+cuando",
    r"siempre\s+que",
    r"a\s+condici[oó]n\s+de\s+que",
    r"con\s+tal\s+de\s+que",
    r"en\s+caso\s+de\s+que",
    r"cuando",
    r"si",
]

UNLESS_MARKERS = [r"a\s+menos\s+que", r"salvo\s+que", r"excepto\s+que",
                  r"a\s+no\s+ser\s+que"]

BICOND_MARKERS = [
    r"si\s+y\s+s[oó]lo\s+si",
    r"si\s+y\s+solo\s+si",
    r"si\s+y\s+nicamente\s+si",
    r"equivale\s+a",
    r"es\s+equivalente\s+a",
    r"sii",
]

NEG_EXPLICIT = [
    r"no\s+es\s+el\s+caso\s+de\s+que",
    r"no\s+es\s+cierto\s+que",
    r"no\s+es\s+verdad\s+que",
    r"no\s+se\s+da\s+el\s+caso\s+de\s+que",
    r"es\s+falso\s+que",
    r"no\s+ocurre\s+que",
    r"no\s+sucede\s+que",
]

SIMPLE_NEG = [r"no", r"nunca", r"jam[aá]s", r"ni"]

CONJ_MARKERS = [r"y", r"e", r"pero", r"aunque", r"sin\s+embargo",
                r"no\s+obstante", r"adem[aá]s", r"mientras\s+que",
                r"sino"]

DISJ_MARKERS = [r"o\s+bien", r"o", r"u"]

# Terminaciones de futuro, para localizar el verbo de la oración principal.
FUTURE_RE = (r"(?:sabr[áa]s?|ser[áa]n?|estar[áa]n?|har[áa]n?|tendr[áa]n?|"
             r"podr[áa]n?|deber[áa]n?|querr[áa]n?|vendr[áa]n?|dir[áa]n?|"
             r"saldr[ée]s?|saldr[áa]n?|pondr[ée]s?|pondr[áa]n?|"
             r"[a-záéíóúüñ]{3,}(?:ar[áa]n?|er[áa]n?|ir[áa]n?|"
             r"ar[áa]s|er[áa]s|ir[áa]s))")

# Palabras que no pueden cerrar la oración antecedente de un condicional.
FUNCTION_TAIL = {
    "se", "me", "te", "le", "les", "nos", "lo", "la", "los", "las", "el",
    "un", "una", "de", "del", "al", "a", "en", "con", "por", "para", "que",
    "y", "e", "o", "u", "ni", "si", "como", "cuando", "mientras", "pero",
    "sino", "sin", "sobre", "entre", "hasta", "desde", "su", "sus", "mi",
    "mis", "tu", "tus", "nuestro", "nuestra", "este", "esta", "ese", "esa",
    "bien", "mal", "muy", "mas", "menos", "tan", "tanto", "tambien",
    "tampoco", "solo", "aun", "ya", "siempre", "nunca", "jamas", "aqui",
    "alli", "hoy", "ayer", "manana", "ahora", "despues", "antes", "luego",
    "mucho", "poco", "bastante", "demasiado",
}

# Marcadores de conclusión que preceden a la frase
CONCLUSION_MARKERS = r"^\s*(?:por\s+tanto|por\s+consiguiente|por\s+lo\s+tanto|" \
                      r"por\s+conclusi[oó]n|en\s+conclusi[oó]n|" \
                      r"como\s+conclusi[oó]n|en\s+consecuencia|por\s+ende|" \
                      r"as[ií]\s+pues|de\s+donde|" \
                      r"luego|entonces|as[ií]\s+que|" \
                      r"por\s+ello)\s*[,;:]?\s*"


def tiene_marcador_conclusion(texto):
    """¿La frase empieza por un marcador de conclusión?

    Se usa tanto para quitar el marcador al formalizar como para saber qué
    línea es la conclusión aunque el usuario no haya escrito ``=>``.
    """
    return re.match(CONCLUSION_MARKERS, texto, re.IGNORECASE) is not None

# Palabras que suelen indicar una estructura lógica.  Si el analizador no
# consigue interpretarlas y acaba tratando toda la frase como un átomo, es
# una señal de que conviene pedir una segunda opinión a la IA.
_ESTRUCTURA_RE = re.compile(
    r"\b(?:" + "|".join([
        r"si", r"entonces", r"s[oó]lo\s+si", r"solo\s+si",
        r"si\s+y\s+s[oó]lo\s+si", r"si\s+y\s+solo\s+si",
        r"a\s+menos\s+que", r"salvo\s+que", r"excepto\s+que",
        r"a\s+no\s+ser\s+que", r"siempre\s+que", r"siempre\s+y\s+cuando",
        r"en\s+caso\s+de\s+que", r"cuando", r"para\s+que",
        r"necesario", r"suficiente", r"equivale", r"equivalente",
        r"o", r"u", r"y", r"e", r"pero", r"aunque", r"sin\s+embargo",
        r"no\s+obstante", r"adem[aá]s", r"mientras\s+que", r"sino",
        r"ni", r"no", r"nunca", r"jam[aá]s", r"todos", r"todas",
        r"todo", r"toda", r"alg[uú]n", r"alguna", r"algunos",
        r"algunas", r"ning[uú]n", r"ninguna", r"ninguno", r"existe",
        r"existen", r"hay", r"para\s+todo", r"s[oó]lo", r"solo",
    ]) + r")\b", re.IGNORECASE)

# Verbo copulativo para separar sujeto y predicado en predicados.
VERBS = r"(?:son|es|sea|sean|están|esta|están|está|siguen|siendo|fueron|eran|" \
        r"será|seran|serán|parecen|parece|resultan|resulta)"
VERB_BOUNDED = r"\b" + VERBS + r"\b"
VERB_RE = VERB_BOUNDED

# "sólo los A son B"  =  "B → A"
ONLY_PATTERN = (r"^\s*s[oó]lo\s+(?:los|las|el|la)\s+(?P<sujeto>.+?)"
                r"\s*,?\s*" + VERB_BOUNDED + r"\s+(?P<pred>.+)$")

# "Los/Las <sujeto> <verbo> <pred>"  también es universal
DEFITE_PATTERN = r"^\s*(?:los|las)\s+(?P<sujeto>.+?)\s*,?\s*" + VERB_BOUNDED + \
                 r"\s+(?P<pred>.+)$"

# Cuantificadores: el patrón quita las palabras del cuantificador y el resto
# se analiza como sujeto + predicado.
QUANT_PATTERNS = [
    (r"^\s*no\s+todos\s+(?:los|las)\s+", "not_all"),
    (r"^\s*no\s+todas\s+(?:los|las)\s+", "not_all"),
    (r"^\s*todos\s+los\s+", "forall"),
    (r"^\s*todas\s+las\s+", "forall"),
    (r"^\s*todos\s+las\s+", "forall"),
    (r"^\s*todas\s+los\s+", "forall"),
    (r"^\s*todo\s+el\s+", "forall"),
    (r"^\s*toda\s+la\s+", "forall"),
    (r"^\s*ning[uú]n\s+", "forall_neg"),
    (r"^\s*ninguna\s+", "forall_neg"),
    (r"^\s*ninguno\s+", "forall_neg"),
    (r"^\s*algunos\s+", "exists"),
    (r"^\s*algunas\s+", "exists"),
    (r"^\s*alg[uú]n\s+", "exists"),
    (r"^\s*alguna\s+", "exists"),
    (r"^\s*existen\s+", "exists"),
    (r"^\s*existe\s+", "exists"),
    (r"^\s*hay\s+algunos\s+", "exists"),
    (r"^\s*hay\s+algunas\s+", "exists"),
    (r"^\s*hay\s+alg[uú]n\s+", "exists"),
    (r"^\s*hay\s+alguna\s+", "exists"),
    (r"^\s*hay\s+un\s+", "exists"),
    (r"^\s*hay\s+una\s+", "exists"),
    (r"^\s*todos\s+", "forall"),
    (r"^\s*todas\s+", "forall"),
    (r"^\s*cada\s+", "forall"),
    (r"^\s*cualquier\s+", "forall"),
    (r"^\s*cualesquiera\s+", "forall"),
    (r"^\s*todo\s+", "forall"),
    (r"^\s*toda\s+", "forall"),
]


# ==========================================================================
# Detección de cláusulas
# ==========================================================================
def _has_verb(text):
    """Verdadero si el texto parece contener un verbo conjugado."""
    for w in _words(text):
        lw = w.lower()
        sw = strip_accents(lw)
        if sw in VERB_WORDS or lw in VERB_WORDS:
            return True
        if sw in NOUN_STOP or lw in NOUN_STOP:
            continue
        if sw in _IRREG:
            return True
        if sw in _VERB_FORMS:
            return True
        if len(sw) > 3 and sw.endswith(VERB_ENDINGS):
            return True
        if re.fullmatch(FUTURE_RE, sw):
            return True
    return False


def _clause_like(text):
    """¿La parte tiene pinta de oración (verbo o pronombre inicial)?"""
    t = text.strip(" ,;")
    if not t:
        return False
    if _has_verb(t):
        return True
    palabras = _words(t)
    return len(palabras) >= 2 and palabras[0].lower() in CONS_STARTERS


def _cond_split_ok(izq, der):
    """¿Es válido cortar aquí el antecedente y el consecuente?"""
    izq = izq.strip(" ,")
    der = der.strip(" ,")
    if not izq or not der:
        return False
    if not _has_verb(izq):
        return False
    ult = _words(izq)[-1].lower() if _words(izq) else ""
    if strip_accents(ult) in FUNCTION_TAIL:
        return False
    return _clause_like(der)


def _cond_comma_ok(izq, der):
    """Corte de condicional cuando la coma marca claramente la frontera.

    Delante de una coma, "Si A, B" ya está separado por la puntuación: no
    hace falta reconocer el verbo de B en el léxico.  Así funcionan también
    verbos que el programa no conoce ("Si corro, sudo").
    """
    izq = izq.strip(" ,")
    der = der.strip(" ,")
    wi, wd = _words(izq), _words(der)
    if not wi or not wd:
        return False
    if strip_accents(wi[-1].lower()) in FUNCTION_TAIL:
        return False
    if strip_accents(wd[0].lower()) in ("y", "e", "o", "u", "ni", "pero",
                                        "sino", "que"):
        return False
    if len(wi) == 1 and not _has_verb(izq):
        return False
    return True


def _split_conditional(resto):
    """Separa ``ANT CONS`` en un condicional sin coma ni "entonces".

    Se prueban varios puntos de corte y sólo se acepta el primero en el que
    la parte izquierda es de verdad una oración (tiene verbo y no termina en
    una palabra gramatical suelta) y la derecha puede abrir una principal.
    """
    resto = resto.strip(" ,")
    palabras = resto.split()
    if len(palabras) < 2:
        return None

    # "..., entonces ..."
    m = re.search(r"\bentonces\b", resto, re.IGNORECASE)
    if m and m.start() > 0:
        izq, der = resto[:m.start()], resto[m.end():]
        if _cond_split_ok(izq, der) or _cond_comma_ok(izq, der):
            return izq.strip(" ,"), der.strip(" ,")

    # "..., ..."
    for m in _top_matches(resto, r","):
        izq, der = resto[:m.start()], resto[m.start() + 1:]
        if _cond_split_ok(izq, der) or _cond_comma_ok(izq, der):
            return izq.strip(" ,"), der.strip(" ,")

    # una palabra que abre la oración principal, o un verbo en futuro
    for i, w in enumerate(palabras):
        if i == 0:
            continue
        wl = w.lower().strip(",;")
        if wl in CONS_STARTERS or re.match(FUTURE_RE, wl):
            izq = " ".join(palabras[:i])
            der = " ".join(palabras[i:])
            if _cond_split_ok(izq, der):
                return izq, der

    # detrás del primer verbo
    for i, w in enumerate(palabras):
        if i + 1 < len(palabras) and _has_verb(w):
            izq = " ".join(palabras[:i + 1])
            der = " ".join(palabras[i + 1:])
            if _cond_split_ok(izq, der):
                return izq, der
    return None


def _split_clause_connective(text, markers, allow_short=False,
                             short_right=False):
    """Parte por el primer conector cuyas dos partes son oraciones."""
    for pat in markers:
        for m in _top_matches(text, r"\b" + pat + r"\b"):
            izq = text[:m.start()].strip(" ,;")
            der = text[m.end():].strip(" ,;")
            if not (izq and der):
                continue
            if _clause_like(izq) and _clause_like(der):
                return izq, der
            # "es gallego o portugués": el segundo término hereda el verbo
            if allow_short:
                if _has_verb(izq) and len(_words(der)) <= 3 \
                        and der.lower() not in FUNCTION_TAIL:
                    return izq, der
                if _has_verb(der) and len(_words(izq)) <= 3 \
                        and izq.lower() not in FUNCTION_TAIL:
                    return izq, der
            if short_right and _has_verb(izq) and len(_words(der)) <= 2 \
                    and der.lower() not in FUNCTION_TAIL:
                return izq, der
    return None


def _concordancia_negativa(text):
    """Convierte el negativo concordado en el positivo equivalente.

    En español, «no tendrás que repetir ninguna asignatura» equivale a
    «no tendrás que repetir alguna asignatura»: la negación ya la aporta el
    «no» inicial.  Sin esta normalización, «ninguna asignatura» crearía un
    átomo distinto de «alguna asignatura» y no se podría enlazar con la
    premisa o la conclusión que usa la otra forma.
    """
    cambios = (
        (r"\bning[uú]n\b", "algún"),
        (r"\bninguno\b", "alguno"),
        (r"\bninguna\b", "alguna"),
        (r"\bnada\b", "algo"),
        (r"\bnadie\b", "alguien"),
    )
    for patron, sustituto in cambios:
        text = re.sub(patron, sustituto, text, flags=re.IGNORECASE)
    return text


def _clean(text):
    """Quita marcadores, normaliza y resuelve los "no" de sujeto."""
    text = text.strip()
    text = re.sub(CONCLUSION_MARKERS, "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^\s*sii\b", "si y sólo si", text, flags=re.IGNORECASE)

    # una "o" inicial es la conectiva, no parte del enunciado
    text = re.sub(r"^\s*o\s+(?:bien\s+)?", "", text, flags=re.IGNORECASE)

    # "sino" al principio es "si no" (condicional)
    text = re.sub(r"^\s*sino\b", "si no", text, flags=re.IGNORECASE)

    # el punto y coma separa oraciones igual que una coma
    text = text.replace(";", ",")

    text = text.strip(" .,;:")
    if not text:
        return ""

    # "Un partido no se gana" = ¬(un partido se gana), pero no se toca si la
    # frase empieza por una conectiva: en "Si no corro, corro" el "no"
    # pertenece al antecedente.
    if not re.match(r"^\s*no\b", text, re.IGNORECASE) and not re.match(
            r"^a\s+no\s+ser\s+que\b", text, re.IGNORECASE) and not re.match(
            r"^\s*(?:si|cuando|siempre|aunque|porque|mientras|para|"
            r"s[oó]lo|o|y|ni|luego|entonces|adem[aá]s)\b", text,
            re.IGNORECASE) and not re.match(
            r"^\s*(?:los|las|el|la|todos|todas|todo|toda|ning[uú]n|ninguna|"
            r"algunos|algunas|alg[uú]n|algun|cada|cualquier|existen|existe|"
            r"hay)\b", text, re.IGNORECASE):
        mn = re.match(r"^(?P<s>[^,]+?)\s+no\s+(?P<r>.+)$", text,
                      re.IGNORECASE)
        if mn and not _has_verb(mn.group("s")):
            text = "no " + mn.group("s") + " " + mn.group("r")
    return text


# ==========================================================================
# Vocabulario
# ==========================================================================
class Vocabulary:
    """Vocabulario: términos y sus textos."""

    def __init__(self, quantified):
        self.quantified = quantified   # True si hay predicados
        self.terms = []
        self._index = {}

    def add(self, text, negated_text=None, letter=None):
        text = text.strip().strip(" .,;:")
        if self.quantified:
            existente = self.find(text)
            if existente is not None:
                return existente
            claves = _claves_pred(text)
        else:
            claves = {_norm(text)}
        usadas = {t.letter for t in self.terms}
        if letter and letter not in usadas:
            elegida = letter
        elif self.quantified:
            elegida = self._next_predicate_letter()
        else:
            elegida = _letra_enunciado(len(self.terms))
        t = Term(elegida, text, negated_text)
        self.terms.append(t)
        for clave in claves:
            self._index.setdefault(clave, t)
        return t

    def _next_predicate_letter(self):
        used = {t.letter for t in self.terms}
        for c in "CDEFGHIJKLMNOPQRSTUVWXYZAB":
            if c not in used:
                return c
        raise RuntimeError("agotadas las letras de predicado")

    def __iter__(self):
        return iter(self.terms)

    def __len__(self):
        return len(self.terms)

    def find(self, text):
        if self.quantified:
            for clave in _claves_pred(text):
                t = self._index.get(clave)
                if t is not None:
                    return t
            return None
        clave = _norm(text)
        t = self._index.get(clave)
        if t is not None:
            return t
        # Variantes verbales no triviales: «aprobar el examen» y «apruebas el
        # examen» deben ser el mismo enunciado.  Sólo se hace con frases de
        # varias palabras y con una similitud muy alta, para no confundir
        # enunciados distintos («el cielo es azul» / «el cielo es verde»).
        palabras = clave.split()
        if len(palabras) < 2:
            return None
        mejor, mejor_ratio = None, 0.0
        for term in self.terms:
            otra = _norm(term.text)
            if len(otra.split()) != len(palabras):
                continue
            ratio = SequenceMatcher(None, clave, otra).ratio()
            if ratio > mejor_ratio:
                mejor, mejor_ratio = term, ratio
        if mejor is not None and mejor_ratio >= 0.88:
            return mejor
        return None


def _simplifica(f):
    """Quita dobles negaciones sin llegar a aplicar De Morgan."""
    if f is None:
        return None
    if f.kind == "not":
        inner = f.children[0]
        if inner.kind == "not":
            return _simplifica(inner.children[0])
        return F("not", None, (_simplifica(inner),))
    if f.kind in ("var", "pred"):
        return f
    if f.kind in ("forall", "exists"):
        return F(f.kind, f.data, (_simplifica(f.children[0]),))
    return F(f.kind, None, tuple(_simplifica(c) for c in f.children))


def _remapea(f, mapping):
    """Cambia las letras de una fórmula aprendida por las de esta frase."""
    if f.kind == "var":
        return F.var(mapping.get(f.data, f.data))
    if f.kind == "pred":
        return F.pred(mapping.get(f.data, f.data), f.term)
    if f.kind in ("forall", "exists"):
        return F(f.kind, f.data, (_remapea(f.children[0], mapping),))
    return F(f.kind, f.data,
             tuple(_remapea(c, mapping) for c in f.children))


# ==========================================================================
# Formalización
# ==========================================================================
class Formalyzer:
    """Traduce frases a fórmulas construyendo el vocabulario a la vez."""

    def __init__(self, quantified=False, aprendizaje=None):
        self.quantified = quantified
        self.vocab = Vocabulary(quantified)
        self.dominio = None
        self.avisos = []
        self.aprendizaje = aprendizaje
        self.fuente = "automática"
        self.confianza = "alta"
        self.motivo_confianza = ""

    # -- utilidades --------------------------------------------------------
    def _marcar_atomo(self, texto):
        """Marca una frase que se ha quedado sin estructura interna.

        Un átomo es correcto para enunciados simples («Llueve»).  Pero si la
        frase contiene conectivas, cuantificadores o signos de puntuación y
        aun así se ha convertido en un átomo, probablemente el analizador no
        ha entendido su estructura: conviene revisarla o consultar la IA.
        """
        self.confianza = "alta"
        self.motivo_confianza = ""
        if (_ESTRUCTURA_RE.search(texto) or
                any(c in texto for c in ",;:()[]")):
            self.confianza = "baja"
            self.motivo_confianza = (
                "La frase contiene una estructura lógica que el analizador "
                "local no ha podido interpretar; se ha tratado como un átomo.")

    def atom_for(self, text):
        t = self.vocab.find(text)
        if t is None:
            t = self.vocab.add(text)
        elif _norm(t.text) != _norm(text) and self.confianza != "baja":
            self.confianza = "baja"
            self.motivo_confianza = (
                "Se ha reutilizado el enunciado «%s» por su parecido con «%s»; "
                "conviene revisar que sean la misma idea." % (t.text, text))
        if self.quantified:
            return F.pred(t.letter, "x"), t
        return F.var(t.letter), t

    # -- punto de entrada --------------------------------------------------
    def formalize(self, sentence):
        text = _clean(sentence)
        if not text:
            return None
        self.fuente = "automática"
        self.confianza = "alta"
        self.motivo_confianza = ""
        if self.aprendizaje is not None:
            aprendida = self._desde_aprendizaje(text)
            if aprendida is not None:
                self.fuente = "aprendida"
                return aprendida
        return _simplifica(self._formula(text, top=True))

    # -- aprendizaje -------------------------------------------------------
    def _desde_aprendizaje(self, text):
        """Intenta reutilizar una formalización confirmada antes."""
        try:
            datos = self.aprendizaje.buscar(text, self.quantified)
        except Exception:
            return None
        if not datos:
            return None
        try:
            formula = parse_formula(datos.get("formula", ""))
        except Exception:
            return None
        vocab = datos.get("vocab") or {}
        for a in atoms(formula):
            if not vocab.get(a.data):
                return None
        # En una coincidencia exacta se conservan las letras originales: son
        # las de la formalización de referencia del usuario.  Sólo se reasigna
        # si esa letra ya está ocupada por otro enunciado.
        exacta = datos.get("tipo") == "exacta"
        mapping = {}
        for a in atoms(formula):
            texto = vocab[a.data]
            termino = self.vocab.find(texto)
            if termino is None:
                termino = self.vocab.add(texto, letter=a.data if exacta else None)
            mapping[a.data] = termino.letter
        resultado = _remapea(formula, mapping)
        # En una coincidencia exacta se respeta tal cual la fórmula de
        # referencia (por ejemplo, la doble negación del ejemplo de clase).
        return resultado if exacta else _simplifica(resultado)

    def registrar(self, sentence, formula, textos=None):
        """Guarda una formalización confirmada para reutilizarla luego."""
        if self.aprendizaje is None or formula is None:
            return False
        propios = {t.letter: t.text for t in self.vocab}
        usados = {}
        for a in atoms(formula):
            if a.data in usados:
                continue
            texto = propios.get(a.data)
            if not texto and textos:
                texto = textos.get(a.data)
            if texto:
                usados[a.data] = texto
        if not usados:
            return False
        return self.aprendizaje.guardar(_clean(sentence), render(formula),
                                        usados, self.quantified)

    # -- análisis ----------------------------------------------------------
    def _formula(self, text, top=False):
        text = _clean(text)
        if not text:
            return None

        if _outer_parens(text):
            return self._formula(text[1:-1], top)

        # En predicados, el nivel superior se resuelve como sujeto+predicado.
        if self.quantified and top:
            r = self._quantified_formula(text)
            if r is not None:
                return r

        # cuantificadores (sólo en el cálculo de predicados; en el de
        # proposiciones "existe un X" es un enunciado simple)
        q = self._quantifier(text) if self.quantified else None
        if q is not None:
            kind, rest = q
            body = self._formula(rest)
            if body is None:
                body = self.atom_for(rest)[0]
            if kind == "exists":
                return F.exists("x", body)
            if kind == "forall":
                return F.forall("x", body)
            if kind == "forall_neg":
                return F.forall("x", F.not_(body))
            if kind == "not_all":
                return F.not_(F.forall("x", body))

        # "Sabrás si es gallego o portugués" es una interrogativa indirecta:
        # todo el sintagma es un solo enunciado (como en el libro).
        if re.match(r"^\s*(?:sabr[eé]s?|sabrás|sabras|sabes|sabe|sabemos|"
                    r"sab[eé]is|sabeis|saben|saber)\s+si\b", text,
                    re.IGNORECASE):
            if self.quantified:
                return self._property(text)[0]
            return self.atom_for(text)[0]

        # 1) bicondicional:  A ↔ B
        for pat in BICOND_MARKERS:
            sp = _split_at(text, r"\b" + pat + r"\b")
            if sp:
                a = self._formula(sp[0])
                b = self._formula(sp[1])
                if a is not None and b is not None:
                    return F.iff(a, b)

        # 2) "Sólo si A, B"  ->  B → A
        if re.match(r"^\s*s[oó]lo\s+si\b", text, re.IGNORECASE):
            resto = re.sub(r"^\s*s[oó]lo\s+si\b\s*", "", text,
                           flags=re.IGNORECASE)
            partes = _split_conditional(resto)
            if partes:
                b = self._formula(partes[0])      # orden del texto
                a = self._formula(partes[1])
                if a is not None and b is not None:
                    return F.imp(a, b)

        # 3) condicional delante:  Si A, B  ->  A → B
        m = _leading(text, COND_FRONT)
        if m:
            resto = text[m.end():].strip(" ,")
            partes = _split_conditional(resto)
            if partes:
                a = self._formula(partes[0])
                b = self._formula(partes[1])
                if a is not None and b is not None:
                    return F.imp(a, b)

        # 4) necesidad y suficiencia
        for pat, ant, cons in (
                (r"^para\s+que\s+(?P<a>.+?)\s+(?:es|ser[áa]|resulta)\s+"
                 r"necesario\s+(?P<b>.+)$", "a", "b"),
                (r"^(?:es|ser[áa]|resulta)\s+necesario\s+(?P<a>.+?)\s+"
                 r"para\s+(?P<b>.+)$", "b", "a"),
                (r"^(?P<a>.+?)\s+es\s+(?:una\s+)?condici[oó]n\s+necesaria\s+"
                 r"para\s+(?P<b>.+)$", "b", "a"),
                (r"^(?P<a>.+?)\s+es\s+(?:una\s+)?condici[oó]n\s+suficiente\s+"
                 r"para\s+(?P<b>.+)$", "a", "b"),
                (r"^(?:es|ser[áa])\s+suficiente\s+(?P<a>.+?)\s+para\s+"
                 r"(?P<b>.+)$", "a", "b"),
                (r"^(?P<a>.+?)\s+es\s+necesario\s+para\s+(?P<b>.+)$",
                 "b", "a"),
                (r"^(?P<a>.+?)\s+es\s+suficiente\s+para\s+(?P<b>.+)$",
                 "a", "b")):
            m = re.match(pat, text, re.IGNORECASE)
            if m:
                a = self._formula(m.group(ant))
                b = self._formula(m.group(cons))
                if a is not None and b is not None:
                    return F.imp(a, b)

        # 5) "A sólo si B"  ->  A → B
        sp = _split_at(text, r"\bs[oó]lo\s+si\b")
        if sp:
            a = self._formula(sp[0])
            b = self._formula(sp[1])
            if a is not None and b is not None:
                return F.imp(a, b)

        # 6) "A a menos que B"  ->  ¬A → B
        for pat in UNLESS_MARKERS:
            sp = _split_at(text, r"\b" + pat + r"\b")
            if sp:
                a = self._formula(sp[0])
                b = self._formula(sp[1])
                if a is not None and b is not None:
                    return F.imp(F.not_(a), b)

        # 6b) "A menos que A, B"  ->  ¬A → B
        m = _leading(text, UNLESS_MARKERS)
        if m:
            partes = _split_conditional(text[m.end():].strip(" ,"))
            if partes:
                a = self._formula(partes[0])
                b = self._formula(partes[1])
                if a is not None and b is not None:
                    return F.imp(F.not_(a), b)

        # 6c) "Aunque A, B"  ->  A ∧ B
        m = _leading(text, [r"aunque", r"a\s+pesar\s+de\s+que",
                            r"pese\s+a\s+que"])
        if m:
            partes = _split_conditional(text[m.end():].strip(" ,"))
            if partes:
                a = self._formula(partes[0])
                b = self._formula(partes[1])
                if a is not None and b is not None:
                    return F.and_(a, b)

        # 7) negaciones explícitas.  Van antes que los condicionales:
        #    "No es verdad que si A, B" es ¬(A→B), no un condicional.
        m = _leading(text, NEG_EXPLICIT)
        if m:
            inner = self._formula(text[m.end():])
            if inner is not None:
                return F.not_(inner)

        # 8) condicional detrás: "A si B", "A cuando B"…  ->  B → A
        for pat in COND_BACK:
            for m in reversed(_top_matches(text, r"\b" + pat + r"\b")):
                izq = text[:m.start()].strip(" ,")
                der = text[m.end():].strip(" ,")
                if not (izq and der):
                    continue
                # el "si" tiene que abrir una cláusula: no vale tras "y",
                # "que", etc.
                if _words(izq) and strip_accents(
                        _words(izq)[-1].lower()) in {"y", "e", "o", "u", "ni",
                                                     "pero", "que", "sino",
                                                     "aunque", "mientras"}:
                    continue
                # "saber si", "decir si"… no son condicionales
                if re.match(r"^(?:sab|conoc|pregunt|dime|dinos|averigu)",
                            izq, re.IGNORECASE):
                    continue
                if not (_clause_like(izq) and _clause_like(der)):
                    continue
                a = self._formula(izq)
                b = self._formula(der)
                if a is not None and b is not None:
                    return F.imp(b, a)

        # 9) "sólo los A son B"  ->  B → A
        m = re.match(r"^\s*s[oó]lo\s+(?:los|las|el|la)\s+(?P<a>.+?)\s*,?\s*"
                     r"(?:son|es)\s+(?P<b>.+)$", text, re.IGNORECASE)
        if m:
            a = self._formula(m.group("a"))
            b = self._formula(m.group("b"))
            if a is not None and b is not None:
                return F.imp(b, a)

        # 10) "ni A ni B" / "no A ni B"  ->  ¬A ∧ ¬B
        for m in _top_matches(text, r"\bni\b"):
            izq = text[:m.start()].strip(" ,")
            der = text[m.end():].strip(" ,")
            if not (izq and der):
                continue
            if not (_clause_like(izq) and _clause_like(der)):
                continue
            a = self._formula(izq)
            b = self._formula(der)
            if a is not None and b is not None:
                if not re.match(r"^\s*(?:no|nunca|jam[aá]s|ni)\b", izq,
                                re.IGNORECASE):
                    a = F.not_(a)
                if not re.match(r"^\s*(?:no|nunca|jam[aá]s|ni)\b", der,
                                re.IGNORECASE):
                    b = F.not_(b)
                return F.and_(a, b)

        # 10b) conjunción marcada con coma: "A, pero B", "A, y B"…  La coma
        #      hace que el "pero" una oraciones enteras.
        for m in reversed(_top_matches(
                text, r",\s*(?:pero|y|e|aunque|sin\s+embargo|no\s+obstante|"
                      r"sino|mientras\s+que)\b")):
            izq = text[:m.start()].strip(" ,")
            der = text[m.end():].strip(" ,")
            if not (izq and der):
                continue
            a = self._formula(izq)
            b = self._formula(der)
            if a is not None and b is not None:
                return F.and_(a, b)

        # 11) disyunción
        sp = _split_clause_connective(text, DISJ_MARKERS, allow_short=True)
        if sp:
            a = self._formula(sp[0])
            b = self._formula(sp[1])
            if a is not None and b is not None:
                return F("or", None, (a, b))

        # 12) conjunción (y también "pero", "aunque", "sin embargo"…)
        sp = _split_clause_connective(text, CONJ_MARKERS, short_right=True)
        if sp:
            a = self._formula(sp[0])
            b = self._formula(sp[1])
            if a is not None and b is not None:
                return F.and_(a, b)

        # 13) enumeración con comas: "A, B y C"
        sp = _split_comma(text)
        if sp and _clause_like(sp[0]) and _clause_like(sp[1]):
            a = self._formula(sp[0])
            b = self._formula(sp[1])
            if a is not None and b is not None:
                return F.and_(a, b)

        # 14) negación simple
        m = _leading(text, SIMPLE_NEG)
        if m:
            resto = _concordancia_negativa(text[m.end():])
            inner = self._formula(resto)
            if inner is not None:
                return F.not_(inner)

        # 15) átomo
        if top:
            self._marcar_atomo(text)
        if self.quantified:
            return self._property(text)[0]
        return self.atom_for(text)[0]

    def _quantifier(self, text):
        """Detecta el cuantificador inicial y devuelve (tipo, resto)."""
        for pat, kind in QUANT_PATTERNS:
            m = re.match(pat, text, re.IGNORECASE)
            if m:
                rest = text[m.end():].strip(" ,")
                return kind, rest
        return None

    # -- cálculo de predicados --------------------------------------------
    def _quantified_formula(self, text):
        """Formaliza una frase del cálculo de predicados."""
        text = re.sub(CONCLUSION_MARKERS, "", text, flags=re.IGNORECASE)

        # "existe(n)/hay (un) X que Y"  ->  (Vx)Y(x)
        m = re.match(r"^(?:existe[n]?|hay)\s+(?:un|una|unos|unas|alg[uú]n|"
                     r"alguna|algunos|algunas)?\s*(?P<sujeto>.+?)\s+que\s+"
                     r"(?P<pred>.+)$", text, re.IGNORECASE)
        if m:
            if self.dominio is None:
                self.dominio = m.group("sujeto")
            return F.exists("x", self._property(m.group("pred"))[0])

        # "Sólo los SUJETO son PRED"  =  PRED → SUJETO
        m = re.match(ONLY_PATTERN, text, re.IGNORECASE)
        if m:
            sujeto, predicado = m.group("sujeto"), m.group("pred")
            if self.dominio is None:
                self.dominio = sujeto
            extra = self._extra_adjective(sujeto)
            p, _ = self._property(predicado)
            if extra:
                q, _ = self._property(extra)
                return F.forall("x", F.imp(p, q))
            return F.forall("x", F.imp(p, self._property(sujeto)[0]))

        # "Los SUJETO son PRED"  →  universal
        m = re.match(DEFITE_PATTERN, text, re.IGNORECASE)
        if m:
            kind, rest = "forall", text[m.start("sujeto"):]
        else:
            q = self._quantifier(text)
            if q is None:
                return None
            kind, rest = q

        sujeto, predicado = self._split_subject(rest)
        if not sujeto or not predicado:
            return None
        if self.dominio is None:
            self.dominio = sujeto

        negado = False
        if re.search(r"\bno\b\s*$", sujeto, re.IGNORECASE):
            sujeto = re.sub(r"\bno\b\s*$", "", sujeto, flags=re.IGNORECASE)
            negado = True
        mneg = re.match(r"^\s*no\s+" + VERB_BOUNDED + r"\s+(?P<p>.+)$",
                         predicado, re.IGNORECASE)
        if mneg:
            negado = True
            predicado = mneg.group("p").strip()

        # "son PRED a menos que Q"  =  ¬PRED → Q
        for pat in UNLESS_MARKERS:
            munless = _split_at(predicado, r"\b" + pat + r"\b")
            if munless:
                p, _ = self._property(munless[0])
                qf = self._formula(munless[1])
                if qf is not None:
                    return F.forall("x", F.imp(F.not_(p), qf))

        p, _ = self._property(predicado)
        if negado:
            p = F.not_(p)

        extra = self._extra_adjective(sujeto)
        if extra and kind == "forall":
            q, _ = self._property(extra)
            return F.forall("x", F.imp(q, p))

        if kind == "exists":
            return F.exists("x", p)
        if kind == "forall_neg":
            return F.forall("x", F.not_(p))
        if kind == "not_all":
            return F.not_(F.forall("x", p))
        return F.forall("x", p)

    def _extra_adjective(self, sujeto):
        """Parte del sujeto que no es el dominio común (p. ej. "grandes")."""
        if self.dominio and sujeto.lower().startswith(self.dominio.lower()):
            resto = sujeto[len(self.dominio):].strip(" ,")
            return resto
        if self.dominio is None:
            self.dominio = sujeto
        return ""

    def _split_subject(self, text):
        """Separa el sujeto del predicado."""
        m = re.search(VERB_RE, text, re.IGNORECASE)
        if m:
            return text[:m.start()].strip(" ,"), text[m.end():].strip(" ,")
        # cualquier otro verbo: "hombres vuelan"
        palabras = text.split()
        for i, w in enumerate(palabras):
            if i > 0 and _has_verb(w):
                return " ".join(palabras[:i]), " ".join(palabras[i:])
        return None, None

    def _property(self, texto):
        """Crea (o reutiliza) el predicado que significa `texto`."""
        texto = texto.strip(" ,.")
        texto = re.sub(r"^\s*(?:sean|son|es|ser)\s+", "", texto,
                       flags=re.IGNORECASE)
        texto = texto.strip(" ,.")
        if not texto:
            texto = "ser"

        # negación: "no ser grandes" / "no grandes"
        negado = False
        if re.match(r"^no\s+", texto, re.IGNORECASE):
            negado = True
            texto = re.sub(r"^no\s+", "", texto, flags=re.IGNORECASE).strip()

        # "cubos, dodecaedros o tetraedros" son varios predicados unidos
        m = re.search(r"\s+(?P<con>o|u|y|e)\s+", texto, re.IGNORECASE)
        if m:
            con = "or" if m.group("con").lower() in ("o", "u") else "and"
            izq = texto[:m.start()]
            der = texto[m.end():]
            piezas = [p.strip() for p in re.split(r"\s*,\s*", izq) if p.strip()]
            piezas.append(der.strip())
            formulas = [self._property(p)[0] for p in piezas]
            out = formulas[0]
            for f in formulas[1:]:
                out = F(con, None, (out, f))
            if negado:
                out = F.not_(out)
            return out, None

        if not re.match(r"^\s*(ser|estar|tener)\s", texto, re.IGNORECASE) \
                and not _has_verb(texto):
            texto = "ser " + texto
        t = self.vocab.find(texto)
        if t is None:
            t = self.vocab.add(texto)
        p = F.pred(t.letter, "x")
        return (F.not_(p) if negado else p), t

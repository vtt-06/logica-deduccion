"""Búsqueda web opcional para dar contexto al formalizador.

Usa la página HTML de DuckDuckGo, sin claves ni dependencias externas.  No
sustituye al analizador: los resultados son texto libre y pueden ser
irrelevantes.  Se envían al modelo de IA (si está configurado) como pistas,
nunca se convierten directamente en fórmulas.
"""

import html
import re
import urllib.parse
import urllib.request

URL_BUSQUEDA = "https://html.duckduckgo.com/html/"
TIMEOUT = 8
MAX_RESULTADOS = 3
MAX_TEXTO = 450
PROFESOR = "Pascual Julián Iranzo"

_PATRON = re.compile(
    r'<a[^>]*class="[^"]*\bresult__a\b[^"]*"[^>]*href="([^"]+)"[^>]*>'
    r'(.*?)</a>.*?'
    r'<a[^>]*class="[^"]*\bresult__snippet\b[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL)


def _limpia(fragmento):
    fragmento = re.sub(r"<[^>]+>", " ", fragmento or "")
    fragmento = html.unescape(fragmento)
    return " ".join(fragmento.split())


def _url_real(url):
    if url.startswith("//"):
        url = "https:" + url
    partes = urllib.parse.urlparse(url)
    parametros = urllib.parse.parse_qs(partes.query)
    if "uddg" in parametros and parametros["uddg"]:
        return parametros["uddg"][0]
    return url


def extraer_resultados(pagina, limite=MAX_RESULTADOS):
    """Convierte el HTML de DuckDuckGo en una lista de resultados."""
    resultados = []
    for coincidencia in _PATRON.finditer(pagina or ""):
        titulo = _limpia(coincidencia.group(2))
        resumen = _limpia(coincidencia.group(3))
        if not titulo or not resumen:
            continue
        resultados.append({
            "title": titulo[:200],
            "url": _url_real(coincidencia.group(1)),
            "snippet": resumen[:MAX_TEXTO],
        })
        if len(resultados) >= limite:
            break
    return resultados


def _buscar_consulta(consulta, limite):
    url = URL_BUSQUEDA + "?" + urllib.parse.urlencode({"q": consulta})
    peticion = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Version/17.0 Safari/605.1.15"),
        "Accept-Language": "es-ES,es;q=0.9",
    })
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            pagina = respuesta.read().decode("utf-8", "replace")
    except Exception:
        return []
    return extraer_resultados(pagina, limite)


def buscar(frase, limite=MAX_RESULTADOS, general=False):
    """Busca una frase y devuelve ``[{title, url, snippet}]``.

    Se intenta primero una consulta orientada a los materiales de la UCLM
    del profesor Pascual Julián Iranzo.  Si no hay resultados, se hace una
    búsqueda general.  Con ``general=True`` se combinan ambas búsquedas para
    que una frase desconocida no quede limitada a la página del profesor.
    Ante cualquier error de red o de formato devuelve una lista vacía: la
    aplicación sigue funcionando sin búsqueda.
    """
    consultas = [
        "%s lógica formal UCLM %s" % (frase, PROFESOR),
        "%s lógica formal" % frase,
    ]
    resultados, vistos = [], set()
    for consulta in consultas:
        for resultado in _buscar_consulta(consulta, limite):
            url = resultado.get("url", "")
            if url in vistos:
                continue
            vistos.add(url)
            resultados.append(resultado)
        if resultados and not general:
            break
    return resultados[:limite * 2 if general else limite]

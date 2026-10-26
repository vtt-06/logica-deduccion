"""Aprendizaje local de formalizaciones.

Guarda las frases que el usuario ha confirmado (o corregido) y reutiliza su
formalización en frases nuevas:

- Coincidencia exacta: la misma frase vuelve a producir la misma fórmula.
- Imitación por plantilla: se sustituyen los enunciados concretos por huecos
  y se conservan las palabras conectivas.  Por ejemplo, de

      "Si llueve, me mojo."  ->  p→q

  se aprende la plantilla ``si §, §``; después

      "Si nieva, me abrigo."

  se propone como ``p→q``.

El almacén es un JSON local.  No se envía nada a internet.
"""

import hashlib
import json
import os
import re
import threading
from datetime import datetime

RUTA_POR_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "aprendizaje.json")
LIMITE_EXACTAS = 1500
LIMITE_PLANTILLAS = 400
LIMITE_EJERCICIOS = 300
LIMITE_FRASES_MEMORIA = 500
LIMITE_BANCO = 2000

# Palabras que no deben quedar dentro de un hueco: si aparecen, la frase
# necesita el analizador (negaciones, conectivas, cuantificadores...) y no
# conviene imitar una plantilla que las ignoraría.
_PALABRAS_LOGICAS = {
    "no", "nunca", "jamas", "ni", "tampoco", "si", "entonces", "y", "e",
    "o", "u", "pero", "aunque", "sino", "solo", "solamente", "cuando",
    "siempre", "salvo", "excepto", "menos", "necesario", "necesaria",
    "suficiente", "todos", "todas", "todo", "toda", "algun", "alguna",
    "alguno", "algunos", "algunas", "ningun", "ninguna", "ninguno",
    "existe", "hay", "equivale", "cierto", "verdad", "falso",
}


def _hueco_limpio(texto):
    palabras = re.findall(r"[a-záéíóúüñ]+", _sin_acentos(texto.lower()))
    return not any(p in _PALABRAS_LOGICAS for p in palabras)


def _plural_palabra(palabra):
    if not palabra or not palabra[-1].isalpha():
        return palabra
    if palabra[-1].lower() in "sxz":
        return palabra
    if palabra[-1].lower() in "aeiouáéíóú":
        return palabra + "s"
    return palabra + "es"


def _singular_palabra(palabra):
    if palabra.endswith("ces") and len(palabra) > 3:
        return palabra[:-2] + "z"
    if palabra.endswith("es") and len(palabra) > 2:
        return palabra[:-2]
    if palabra.endswith("s") and len(palabra) > 1:
        return palabra[:-1]
    return palabra


def _plural_frase(texto):
    return " ".join(_plural_palabra(p) for p in texto.split())


def _singular_frase(texto):
    return " ".join(_singular_palabra(p) for p in texto.split())


def _variantes(texto):
    """Formas con las que un enunciado puede aparecer en la frase.

    Sirve sobre todo para predicados: «ser cubo» aparece en el texto como
    «son cubos», «cuerpo geométrico» como «cuerpos geométricos», etc.
    """
    variantes = {texto}
    for forma in (_plural_frase(texto), _singular_frase(texto)):
        if forma:
            variantes.add(forma)
    m = re.match(r"(ser|estar)\s+(.+)", texto, re.IGNORECASE)
    if m:
        resto = m.group(2)
        for base in {resto, _plural_frase(resto), _singular_frase(resto)}:
            for verbo in ("es", "son", "sea", "sean", "era", "eran",
                          "fue", "fueron", "está", "están", "esté",
                          "estén", "estaba", "estaban"):
                variantes.add(verbo + " " + base)
    return [v for v in variantes if v]


def _sin_acentos(texto):
    tabla = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u",
             "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U"}
    return "".join(tabla.get(c, c) for c in texto)


_CONCLUSION_RE = re.compile(
    r"^\s*(?:por\s+tanto|por\s+consiguiente|por\s+lo\s+tanto|luego|"
    r"entonces|as[ií]\s+que|en\s+consecuencia|por\s+ello)\s*[,;:]?\s*",
    re.IGNORECASE)


def _clave(texto):
    """Clave de comparación de una frase.

    Se elimina el marcador de conclusión («Por tanto, …») para que la misma
    frase se reconozca tanto si se guardó con él como si el analizador ya lo
    había quitado antes de buscarla.
    """
    texto = _sin_acentos(texto.lower())
    texto = _CONCLUSION_RE.sub("", texto)
    texto = " ".join(texto.split())
    return texto.strip(" .,;:¿?¡!")


def _limpia(texto):
    return " ".join(texto.split()).strip().rstrip(".").strip()


class Aprendizaje:
    """Almacén local de frases confirmadas y plantillas."""

    def __init__(self, ruta=None):
        self.ruta = (ruta or os.environ.get("LOGICA_APRENDIZAJE_RUTA")
                     or RUTA_POR_DEFECTO)
        self._lock = threading.RLock()
        self.datos = {"version": 1, "exactas": {}, "plantillas": [],
                      "ejercicios": [], "banco": []}
        self._cargar()

    # -- persistencia ------------------------------------------------------
    def _cargar(self):
        try:
            with open(self.ruta, encoding="utf-8") as fh:
                datos = json.load(fh)
        except (OSError, ValueError):
            return
        if not isinstance(datos, dict):
            return
        exactas = datos.get("exactas")
        plantillas = datos.get("plantillas")
        ejercicios = datos.get("ejercicios")
        banco = datos.get("banco")
        if isinstance(plantillas, list):
            self.datos["plantillas"] = plantillas
        if isinstance(ejercicios, list):
            self.datos["ejercicios"] = ejercicios
        cambio_banco = False
        if isinstance(banco, list):
            for entrada in banco:
                if not isinstance(entrada, dict):
                    continue
                limpio = re.sub(r"^=>\s*", "",
                                str(entrada.get("texto", ""))).strip()
                if limpio != entrada.get("texto", ""):
                    entrada["texto"] = limpio
                    cambio_banco = True
            self.datos["banco"] = banco
        if isinstance(exactas, dict):
            # Migración suave: versiones anteriores guardaban la conclusión
            # con el marcador «Por tanto, …», que luego no coincidía con la
            # frase ya limpia.  Se conservan los datos y sólo se normaliza la
            # clave.
            migradas, cambio = {}, False
            for clave, valor in exactas.items():
                if not isinstance(valor, dict):
                    migradas[clave] = valor
                    continue
                frase = valor.get("frase") or clave
                nueva = _clave(str(frase)) or clave
                if nueva != clave:
                    cambio = True
                anterior = migradas.get(nueva)
                if (anterior is None or
                        str(valor.get("actualizado", "")) >=
                        str(anterior.get("actualizado", ""))):
                    migradas[nueva] = valor
            if len(migradas) != len(exactas):
                cambio = True
            self.datos["exactas"] = migradas
            if cambio:
                self._guardar()
        if cambio_banco:
            self._guardar()

    def _guardar(self):
        try:
            carpeta = os.path.dirname(self.ruta)
            if carpeta:
                os.makedirs(carpeta, exist_ok=True)
            temporal = self.ruta + ".tmp"
            with open(temporal, "w", encoding="utf-8") as fh:
                json.dump(self.datos, fh, ensure_ascii=False, indent=1)
            os.replace(temporal, self.ruta)
        except OSError:
            # El aprendizaje es una ayuda: si no se puede escribir, la
            # aplicación sigue funcionando.
            pass

    # -- consulta ----------------------------------------------------------
    def buscar(self, frase, cuantificado):
        """Devuelve ``{'formula', 'vocab', 'tipo'}`` o ``None``."""
        clave = _clave(frase)
        tipo_calculo = "pred" if cuantificado else "prop"
        with self._lock:
            exacta = self.datos["exactas"].get(clave)
            if exacta and exacta.get("calculus") == tipo_calculo:
                return {"formula": exacta.get("formula", ""),
                        "vocab": dict(exacta.get("vocab") or {}),
                        "tipo": "exacta"}

            texto = _limpia(frase)
            plantillas = sorted(self.datos["plantillas"],
                                key=lambda p: -int(p.get("usos", 0)))
            for plantilla in plantillas:
                if plantilla.get("calculus") != tipo_calculo:
                    continue
                patron = plantilla.get("regex")
                huecos = plantilla.get("huecos") or []
                if not patron or not huecos:
                    continue
                try:
                    coincidencia = re.match(patron, texto, re.IGNORECASE)
                except re.error:
                    continue
                if not coincidencia:
                    continue
                trozos = [g.strip(" ,;") for g in coincidencia.groups()]
                if len(trozos) != len(huecos):
                    continue
                vocab, valido = {}, True
                for letra, trozo in zip(huecos, trozos):
                    if not trozo or not _hueco_limpio(trozo):
                        valido = False
                        break
                    if letra in vocab and _clave(vocab[letra]) != _clave(trozo):
                        valido = False
                        break
                    vocab[letra] = trozo
                if not valido:
                    continue
                plantilla["usos"] = int(plantilla.get("usos", 0)) + 1
                return {"formula": plantilla.get("formula", ""),
                        "vocab": vocab, "tipo": "plantilla"}
        return None

    # -- registro ----------------------------------------------------------
    def guardar(self, frase, formula, vocab, cuantificado):
        """Guarda o actualiza una frase confirmada.

        ``formula`` es el texto de la fórmula y ``vocab`` un diccionario
        ``{letra: texto del enunciado}``.
        """
        if not frase or not formula or not vocab:
            return False
        clave = _clave(frase)
        if not clave:
            return False
        tipo_calculo = "pred" if cuantificado else "prop"
        ahora = datetime.now().isoformat(timespec="seconds")

        with self._lock:
            anterior = self.datos["exactas"].get(clave) or {}
            self.datos["exactas"][clave] = {
                "frase": frase,
                "formula": formula,
                "vocab": dict(vocab),
                "calculus": tipo_calculo,
                "usos": int(anterior.get("usos", 0)) + 1,
                "actualizado": ahora,
            }
            self._podar_exactas()

            plantilla = self._crear_plantilla(frase, formula, vocab,
                                              tipo_calculo, ahora)
            if plantilla:
                self._insertar_plantilla(plantilla)
            self._guardar()
        return True

    def registrar_frase(self, frase, formula, vocab=None, cuantificado=False,
                        fuente=""):
        """Añade una frase al banco visible, sin usarla para aprender.

        Se llama en cuanto se formaliza una frase, aunque la deducción no
        llegue a completarse.  Así el banco de frases nunca aparece vacío
        después de usar la aplicación.  Es un registro de consulta: no
        interviene en la reutilización automática de fórmulas.
        """
        texto = " ".join(str(frase or "").split()).strip()
        texto = re.sub(r"^=>\s*", "", texto).strip()
        formula = str(formula or "").strip()
        if not texto or not formula:
            return False
        clave = _clave(texto)
        if not clave:
            return False
        tipo_calculo = "pred" if cuantificado else "prop"
        ahora = datetime.now().isoformat(timespec="seconds")
        vocabulario = {}
        if isinstance(vocab, dict):
            for letra, descripcion in vocab.items():
                descripcion = re.sub(r"^=>\s*", "",
                                     str(descripcion or "")).strip()
                if descripcion:
                    vocabulario[str(letra)] = descripcion
        registro = {
            "texto": texto,
            "formula": formula,
            "vocab": vocabulario,
            "calculus": tipo_calculo,
            "fuente": str(fuente or ""),
            "actualizado": ahora,
        }
        with self._lock:
            for i, anterior in enumerate(self.datos["banco"]):
                if not isinstance(anterior, dict):
                    continue
                if (anterior.get("calculus") == tipo_calculo and
                        _clave(str(anterior.get("texto", ""))) == clave):
                    registro["usos"] = int(anterior.get("usos", 0)) + 1
                    registro["primera_vez"] = anterior.get(
                        "primera_vez", anterior.get("actualizado", ahora))
                    self.datos["banco"][i] = registro
                    self._guardar()
                    return True
            registro["usos"] = 1
            registro["primera_vez"] = ahora
            self.datos["banco"].insert(0, registro)
            if len(self.datos["banco"]) > LIMITE_BANCO:
                del self.datos["banco"][LIMITE_BANCO:]
            self._guardar()
        return True

    def _podar_exactas(self):
        exactas = self.datos["exactas"]
        if len(exactas) <= LIMITE_EXACTAS:
            return
        ordenadas = sorted(exactas.items(),
                           key=lambda kv: kv[1].get("actualizado", ""))
        for clave, _ in ordenadas[:len(exactas) - LIMITE_EXACTAS]:
            exactas.pop(clave, None)

    def _crear_plantilla(self, frase, formula, vocab, tipo_calculo, ahora):
        """Sustituye los enunciados por huecos y construye una expresión."""
        texto = _limpia(frase)
        apariciones = []
        for letra, enunciado in vocab.items():
            enunciado = _limpia(enunciado or "")
            if len(enunciado) < 2 or not _hueco_limpio(enunciado):
                continue
            for variante in _variantes(enunciado):
                for m in re.finditer(re.escape(variante), texto,
                                     re.IGNORECASE):
                    apariciones.append((m.start(), m.end(), letra))

        # Nos quedamos con apariciones que no se solapen; si dos enunciados
        # comparten texto, gana el más largo.
        apariciones.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        elegidas = []
        for inicio, fin, letra in apariciones:
            if any(not (fin <= i or inicio >= f) for i, f, _ in elegidas):
                continue
            elegidas.append((inicio, fin, letra))
        elegidas.sort()

        if len({letra for _, _, letra in elegidas}) < 2:
            return None

        piezas, huecos, pos = [], [], 0
        for inicio, fin, letra in elegidas:
            piezas.append(("literal", texto[pos:inicio]))
            piezas.append(("hueco", letra))
            huecos.append(letra)
            pos = fin
        piezas.append(("literal", texto[pos:]))

        literal = "".join(t for clase, t in piezas if clase == "literal")
        if len(re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", literal)) < 2:
            return None

        partes = ["^"]
        for clase, valor in piezas:
            if clase == "literal":
                if valor:
                    partes.append(re.escape(valor).replace(r"\ ", r"\s+"))
            else:
                partes.append("(.+?)")
        partes.append("$")
        patron = "".join(partes)

        esqueleto = "".join(
            ("§" if clase == "hueco" else " ".join(valor.split()))
            for clase, valor in piezas).strip()

        return {
            "esqueleto": esqueleto,
            "regex": patron,
            "huecos": huecos,
            "formula": formula,
            "ejemplo": frase,
            "vocab": dict(vocab),
            "calculus": tipo_calculo,
            "usos": 0,
            "actualizado": ahora,
        }

    def _insertar_plantilla(self, nueva):
        clave = (nueva["regex"], nueva["formula"], nueva["calculus"])
        for i, vieja in enumerate(self.datos["plantillas"]):
            if (vieja.get("regex"), vieja.get("formula"),
                    vieja.get("calculus")) == clave:
                nueva["usos"] = int(vieja.get("usos", 0))
                self.datos["plantillas"][i] = nueva
                return
        self.datos["plantillas"].append(nueva)
        if len(self.datos["plantillas"]) > LIMITE_PLANTILLAS:
            self.datos["plantillas"].sort(
                key=lambda p: int(p.get("usos", 0)))
            sobra = len(self.datos["plantillas"]) - LIMITE_PLANTILLAS
            del self.datos["plantillas"][:sobra]

    # -- memoria de ejercicios ---------------------------------------------
    def guardar_ejercicio(self, ejercicio):
        """Guarda un ejercicio completo (frases, fórmulas y deducción).

        Las frases sueltas sirven para reconocer enunciados, pero para poder
        revisar después la formalización y la prueba hace falta guardar el
        ejercicio entero.  Se identifica por sus frases y fórmulas, de modo
        que volver a deducirlo actualiza el mismo registro en lugar de crear
        duplicados.
        """
        if not isinstance(ejercicio, dict):
            return None
        frases = ejercicio.get("frases")
        if not isinstance(frases, list) or len(frases) < 2:
            return None
        textos = []
        for frase in frases:
            if isinstance(frase, dict):
                textos.append(str(frase.get("text", "")))
            else:
                textos.append(str(frase))
        formulas = [str(f.get("formula", "")) if isinstance(f, dict) else ""
                    for f in frases]
        base = "||".join(_clave(t) for t in textos) + "###" + "|".join(formulas)
        identificador = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
        ahora = datetime.now().isoformat(timespec="seconds")
        nuevo = dict(ejercicio)
        nuevo["id"] = identificador
        nuevo["actualizado"] = ahora
        with self._lock:
            for i, anterior in enumerate(self.datos["ejercicios"]):
                if anterior.get("id") == identificador:
                    nuevo["usos"] = int(anterior.get("usos", 0)) + 1
                    self.datos["ejercicios"][i] = nuevo
                    self._guardar()
                    return identificador
            nuevo["usos"] = 1
            self.datos["ejercicios"].insert(0, nuevo)
            if len(self.datos["ejercicios"]) > LIMITE_EJERCICIOS:
                del self.datos["ejercicios"][LIMITE_EJERCICIOS:]
            self._guardar()
        return identificador

    def listar_memoria(self):
        """Resumen de ejercicios guardados y frases sueltas reutilizables."""
        with self._lock:
            ejercicios = []
            for ejercicio in sorted(
                    self.datos["ejercicios"],
                    key=lambda e: str(e.get("actualizado", "")),
                    reverse=True):
                frases = ejercicio.get("frases") or []
                titulo = ""
                if frases:
                    ultima = frases[-1]
                    titulo = (ultima.get("text", "") if isinstance(ultima, dict)
                              else str(ultima))
                ejercicios.append({
                    "id": ejercicio.get("id", ""),
                    "titulo": titulo,
                    "meta": ejercicio.get("meta", ""),
                    "frases": len(frases),
                    "usos": int(ejercicio.get("usos", 0)),
                    "actualizado": ejercicio.get("actualizado", ""),
                    "calculus": ejercicio.get("calculus", "prop"),
                })
            frases = []
            for valor in sorted(self.datos["exactas"].values(),
                                key=lambda v: str(v.get("actualizado", "")),
                                reverse=True):
                if not isinstance(valor, dict):
                    continue
                frases.append({
                    "texto": valor.get("frase", ""),
                    "formula": valor.get("formula", ""),
                    "vocab": dict(valor.get("vocab") or {}),
                    "calculus": valor.get("calculus", "prop"),
                    "usos": int(valor.get("usos", 0)),
                    "actualizado": valor.get("actualizado", ""),
                })
                if len(frases) >= LIMITE_FRASES_MEMORIA:
                    break
            banco = []
            for valor in sorted(self.datos["banco"],
                                key=lambda v: str(v.get("actualizado", "")),
                                reverse=True):
                if not isinstance(valor, dict):
                    continue
                texto = re.sub(r"^=>\s*", "",
                               str(valor.get("texto", ""))).strip()
                banco.append({
                    "texto": texto,
                    "formula": valor.get("formula", ""),
                    "vocab": dict(valor.get("vocab") or {}),
                    "calculus": valor.get("calculus", "prop"),
                    "fuente": valor.get("fuente", ""),
                    "usos": int(valor.get("usos", 0)),
                    "actualizado": valor.get("actualizado", ""),
                })
            return {"ejercicios": ejercicios, "frases": frases,
                    "banco": banco}

    def obtener_ejercicio(self, identificador):
        with self._lock:
            for ejercicio in self.datos["ejercicios"]:
                if ejercicio.get("id") == identificador:
                    return dict(ejercicio)
        return None

    # -- mantenimiento -----------------------------------------------------
    def estadisticas(self):
        with self._lock:
            return {
                "exactas": len(self.datos["exactas"]),
                "plantillas": len(self.datos["plantillas"]),
                "ejercicios": len(self.datos["ejercicios"]),
                "banco": len(self.datos["banco"]),
            }

    def olvidar(self):
        with self._lock:
            self.datos = {"version": 1, "exactas": {}, "plantillas": [],
                          "ejercicios": [], "banco": []}
            try:
                if os.path.exists(self.ruta):
                    os.remove(self.ruta)
            except OSError:
                pass
            return True

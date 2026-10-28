/* Lógica — deducción asistida (cliente) */

(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const estado = {
    calculo: "prop",
    items: [],
    vocab: [],
    lineas: [],
    plain: "",
    plantilla: null,
    plantillaTexto: "",
  };

  const EJEMPLOS = {
    corro: {
      calculo: "prop",
      texto: "Si no corro, corro.\n=> Por tanto, sino puedo andar, corro.",
    },
    examen: {
      calculo: "prop",
      texto:
        "Un cuerpo indestructible existe si Dios puede y quiere crearlo.\n" +
        "Si Dios es todopoderoso, entonces no existe un cuerpo que sea indestructible.\n" +
        "Dios es todopoderoso y si quiere crear un cuerpo indestructible, puede hacerlo.\n" +
        "=> Por consiguiente, no es el caso de que Dios quiera crear un cuerpo indestructible.",
      formulas: ["q∧r→p", "s→¬p", "s∧(r→q)", "¬r"],
    },
    predicados: {
      calculo: "pred",
      texto:
        "Todos los cuerpos geométricos son cubos a menos que sean dodecaedros o tetraedros.\n" +
        "Sólo los cuerpos geométricos grandes son tetraedros.\n" +
        "Algunos cuerpos geométricos son pequeños o medianos.\n" +
        "Los cuerpos geométricos grandes no son pequeños o medianos.\n" +
        "=> Por tanto, algunos cuerpos geométricos son cubos o dodecaedros.",
      formulas: [
        "(Λx)(¬C(x)→D(x)∨T(x))",
        "(Λx)(T(x)→G(x))",
        "(Vx)¬G(x)",
        "(Λx)(G(x)→¬¬G(x))",
        "(Vx)(C(x)∨D(x))",
      ],
    },
    clima: {
      calculo: "prop",
      texto:
        "Si llueve y hace frío, me quedo en casa.\n" +
        "Llueve y hace frío.\n" +
        "=> Por tanto, me quedo en casa.",
    },
  };

  const GLOSARIO = {
    MP: "De A→B y A se sigue B (modus ponens).",
    MT: "De A→B y ¬B se sigue ¬A (modus tollens).",
    SH: "De A→B y B→C se sigue A→C (silogismo hipotético).",
    Simp1: "De A∧B se sigue A (simplificación).",
    Simp2: "De A∧B se sigue B (simplificación).",
    Simp: "De una conjunción se sigue uno de sus componentes.",
    IC: "De A y B se sigue A∧B (introducción del conjuntor).",
    Ad: "De A se sigue A∨B (adición).",
    SD: "De A∨B y ¬A se sigue B (silogismo disyuntivo).",
    Dil: "Análisis de casos: de A∨B, A→C y B→D se sigue C∨D.",
    DI1: "A→B equivale a ¬(A∧¬B).",
    DI2: "A→B equivale a ¬A∨B.",
    DD: "Distributividad: A∨(B∧C) equivale a (A∨B)∧(A∨C), y también para el conjuntor.",
    IDD: "Idempotencia: A∨A equivale a A (y A∧A a A).",
    DM1: "¬(A∧B) equivale a ¬A∨¬B (De Morgan).",
    DM2: "¬(A∨B) equivale a ¬A∧¬B (De Morgan).",
    DN: "¬¬A equivale a A (doble negación).",
    IDN: "De A se sigue ¬¬A.",
    Cp: "A→B equivale a ¬B→¬A (contraposición).",
    TD: "Si al suponer A se llega a B, entonces A→B (teorema de deducción).",
    Abs: "Si un supuesto lleva a una contradicción, se cierra y se concluye la meta.",
    EG: "De (Λx)P(x) se sigue P(a) (eliminación del generalizador).",
    IG: "Si P(a) vale para un a arbitrario, vale (Λx)P(x).",
    EP: "De (Vx)P(x) se sigue P(a) para un a nuevo.",
    IP: "De P(a) se sigue (Vx)P(x) (introducción del particularizador).",
    EI1: "De A↔B se sigue A→B.",
    EI2: "De A↔B se sigue B→A.",
    DC: "De una conjunción se sigue la disyunción de sus componentes.",
    Dil1: "Paso abreviado de dilema.",
  };

  /* ------------------------------------------------------------------ */
  /* Utilidades                                                         */
  /* ------------------------------------------------------------------ */
  function crear(tag, clase, texto) {
    const nodo = document.createElement(tag);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = texto;
    return nodo;
  }

  function aviso(nodo, mensaje, tipo) {
    nodo.classList.toggle("aviso--ok", Boolean(mensaje) && tipo === "ok");
    if (!mensaje) {
      nodo.hidden = true;
      nodo.textContent = "";
      return;
    }
    nodo.hidden = false;
    nodo.textContent = mensaje;
  }

  const CLAVE_IA_LOCAL = "logica.proveedorIA";

  function leerProveedorIA() {
    try {
      const guardado = JSON.parse(localStorage.getItem(CLAVE_IA_LOCAL) || "null");
      if (!guardado || !guardado.url || !guardado.model) return null;
      return {
        url: String(guardado.url).trim(),
        model: String(guardado.model).trim(),
        key: String(guardado.key || "").trim(),
      };
    } catch (error) {
      return null;
    }
  }

  function cabecerasIA() {
    const proveedor = leerProveedorIA();
    if (!proveedor) return {};
    const cabeceras = {
      "X-Logica-IA-URL": proveedor.url,
      "X-Logica-IA-MODEL": proveedor.model,
    };
    if (proveedor.key) cabeceras["X-Logica-IA-KEY"] = proveedor.key;
    return cabeceras;
  }

  async function pedir(url, datos) {
    const respuesta = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...cabecerasIA() },
      body: JSON.stringify(datos),
    });
    let cuerpo;
    try {
      cuerpo = await respuesta.json();
    } catch (e) {
      throw new Error("El servidor no ha respondido correctamente.");
    }
    if (!respuesta.ok && cuerpo.error) throw new Error(cuerpo.error);
    return cuerpo;
  }

  function cargando(boton, activo) {
    const texto = boton.querySelector(".boton__texto");
    const espera = boton.querySelector(".boton__cargando");
    boton.disabled = activo;
    if (texto) texto.hidden = activo;
    if (espera) espera.hidden = !activo;
  }

  function irA(nodo) {
    if (!nodo) return;
    nodo.hidden = false;
    nodo.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function marcarPaso(numero, estadoPaso) {
    const paso = document.querySelector('.paso[data-paso="' + numero + '"]');
    if (!paso) return;
    paso.classList.remove("activo", "hecho");
    if (estadoPaso) paso.classList.add(estadoPaso);
  }

  /* ------------------------------------------------------------------ */
  /* Paso 1: cálculo y ejemplos                                         */
  /* ------------------------------------------------------------------ */
  const area = $("#frases");
  const avisoEntrada = $("#aviso-entrada");

  function guardarBorrador() {
    try {
      localStorage.setItem("logica.frases", area.value);
      localStorage.setItem("logica.calculo", estado.calculo);
    } catch (e) { /* modo privado */ }
  }

  function restaurarBorrador() {
    try {
      const texto = localStorage.getItem("logica.frases");
      const calculo = localStorage.getItem("logica.calculo");
      if (texto) area.value = texto;
      if (calculo === "pred" || calculo === "prop") fijarCalculo(calculo);
    } catch (e) { /* modo privado */ }
  }

  function fijarCalculo(valor) {
    estado.calculo = valor;
    $$(".segmento").forEach((b) => {
      const activo = b.dataset.calculo === valor;
      b.classList.toggle("activo", activo);
      b.setAttribute("aria-pressed", activo ? "true" : "false");
    });
    area.placeholder = valor === "pred"
      ? "Todos los hombres son mortales.\n=> Por tanto, algún hombre es mortal."
      : "Si no corro, corro.\n=> Por tanto, sino puedo andar, corro.";
    guardarBorrador();
  }

  // Al salir del cuadro de texto, si hay una conclusión introducida por
  // «Por tanto», «Por consiguiente»… se añade la flecha de forma visible.
  // La detección interna funciona aunque el usuario no llegue a salir.
  area.addEventListener("blur", normalizarMarcadoresConclusion);

  $$(".segmento").forEach((boton) => {
    boton.addEventListener("click", () => fijarCalculo(boton.dataset.calculo));
  });

  area.addEventListener("input", guardarBorrador);

  $$(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const ejemplo = EJEMPLOS[chip.dataset.ejemplo];
      if (!ejemplo) return;
      area.value = ejemplo.texto;
      fijarCalculo(ejemplo.calculo);
      estado.plantilla = ejemplo.formulas ? ejemplo.formulas.slice() : null;
      estado.plantillaTexto = ejemplo.texto;
      guardarBorrador();
      area.focus();
      aviso(avisoEntrada, "");
      detenerVoz(true);
      avisoVoz("");
    });
  });

  $("#btn-limpiar").addEventListener("click", () => {
    area.value = "";
    estado.plantilla = null;
    estado.plantillaTexto = "";
    guardarBorrador();
    aviso(avisoEntrada, "");
    ["#formalizacion", "#resultado", "#explicacion"].forEach((s) => {
      $(s).hidden = true;
    });
    marcarPaso(1, "activo");
    marcarPaso(2, "");
    marcarPaso(3, "");
    detenerVoz(true);
    avisoVoz("");
    area.focus();
  });

  $("#btn-reformalizar").addEventListener("click", () => {
    // No se borra la plantilla: si el texto no ha cambiado, al volver a
    // formalizar se reutilizan exactamente las mismas fórmulas.  Así el
    // botón es seguro aunque se pulse sin querer.
    $("#formalizacion").hidden = true;
    $("#resultado").hidden = true;
    $("#explicacion").hidden = true;
    marcarPaso(1, "activo");
    marcarPaso(2, "");
    marcarPaso(3, "");
    detenerVoz(true);
    avisoVoz("");
    irA($("#entrada"));
    area.focus();
  });

  /* ------------------------------------------------------------------ */
  /* Dictado por voz (API del navegador, sin dependencias)              */
  /* ------------------------------------------------------------------ */
  const btnVoz = $("#btn-voz");
  const estadoVoz = $("#estado-voz");
  const Reconocimiento = window.SpeechRecognition ||
    window.webkitSpeechRecognition;
  let reconocimientoVoz = null;
  let escuchandoVoz = false;
  let silenciarVoz = false;

  function avisoVoz(texto, esError = false) {
    if (!estadoVoz) return;
    estadoVoz.textContent = texto || "";
    estadoVoz.classList.toggle("voz__estado--error", Boolean(esError));
  }

  function detenerVoz(silenciar = false) {
    if (reconocimientoVoz && escuchandoVoz) {
      if (silenciar) silenciarVoz = true;
      try { reconocimientoVoz.stop(); } catch (e) { /* ya parado */ }
    }
  }

  function agregarFraseDictada(texto) {
    const limpio = (texto || "").trim();
    if (!limpio) return;
    const frase = /[.!?…]$/.test(limpio) ? limpio : limpio + ".";
    const actual = area.value.replace(/\s+$/, "");
    area.value = actual ? actual + "\n" + frase : frase;
    guardarBorrador();
    area.focus();
    area.selectionStart = area.selectionEnd = area.value.length;
  }

  function pintarBotonVoz(activo) {
    if (!btnVoz) return;
    btnVoz.classList.toggle("escuchando", activo);
    btnVoz.setAttribute("aria-pressed", activo ? "true" : "false");
    const texto = btnVoz.querySelector(".boton__texto");
    const espera = btnVoz.querySelector(".boton__cargando");
    if (texto) texto.hidden = activo;
    if (espera) espera.hidden = !activo;
  }

  if (!Reconocimiento) {
    if (btnVoz) {
      btnVoz.disabled = true;
      btnVoz.title = "El dictado no está disponible en este navegador. " +
        "Prueba Chrome o Edge.";
    }
    avisoVoz("Dictado no disponible en este navegador; puedes escribir las " +
      "frases.", true);
  } else if (btnVoz) {
    btnVoz.addEventListener("click", () => {
      if (escuchandoVoz) {
        detenerVoz();
        return;
      }

      aviso(avisoEntrada, "");
      avisoVoz("Escuchando… habla una frase y pausa.");
      silenciarVoz = false;
      const rec = new Reconocimiento();
      reconocimientoVoz = rec;
      rec.lang = "es-ES";
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      let huboFinal = false;
      let huboError = false;

      rec.onstart = () => {
        escuchandoVoz = true;
        pintarBotonVoz(true);
      };

      rec.onresult = (evento) => {
        let interim = "";
        for (let i = evento.resultIndex; i < evento.results.length; i++) {
          const resultado = evento.results[i];
          if (!resultado || !resultado[0]) continue;
          const texto = resultado[0].transcript || "";
          if (resultado.isFinal) {
            agregarFraseDictada(texto);
            huboFinal = true;
          } else {
            interim += texto;
          }
        }
        if (interim) {
          avisoVoz("Escuchando… " + interim);
        } else if (huboFinal) {
          avisoVoz("Frase añadida. Sigue hablando o pulsa «Detener».");
        }
      };

      rec.onerror = (evento) => {
        huboError = true;
        const codigo = evento.error || "";
        let texto = "No se ha podido usar el micrófono.";
        if (codigo === "not-allowed" || codigo === "service-not-allowed") {
          texto = "Micrófono no permitido. Actívalo en el navegador y usa " +
            "localhost o una conexión segura (HTTPS).";
        } else if (codigo === "no-speech") {
          texto = "No se ha oído nada. Prueba a hablar más cerca del micrófono.";
        } else if (codigo === "audio-capture") {
          texto = "No se encuentra el micrófono.";
        } else if (codigo === "network") {
          texto = "El reconocimiento de voz necesita conexión a internet.";
        }
        avisoVoz(texto, true);
      };

      rec.onend = () => {
        escuchandoVoz = false;
        pintarBotonVoz(false);
        if (silenciarVoz) {
          silenciarVoz = false;
          avisoVoz("");
          return;
        }
        if (huboError) return;
        if (huboFinal) {
          avisoVoz("Dictado terminado. Revisa las frases antes de formalizar.");
        } else {
          avisoVoz("Dictado terminado.");
        }
      };

      try {
        rec.start();
      } catch (e) {
        escuchandoVoz = false;
        pintarBotonVoz(false);
        avisoVoz("No se ha podido iniciar el dictado.", true);
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Paso 2: formalización                                              */
  /* ------------------------------------------------------------------ */
  const listaFormulas = $("#lista-formulas");
  const listaVocab = $("#lista-vocabulario");
  const avisoFormal = $("#aviso-formal");

  function dividirOraciones(linea) {
    // Separa varias oraciones escritas en la misma línea.  Sólo cortamos
    // cuando después del punto (o ?/!) hay un espacio y empieza otra frase
    // con mayúscula o signo de apertura; así no rompemos abreviaturas como
    // «p. ej.» ni fórmulas.
    const trozos = [];
    let inicio = 0;
    const corte = /[.!?](?=\s+[¿¡"«A-ZÁÉÍÓÚÑ])/g;
    let encontrado;
    while ((encontrado = corte.exec(linea)) !== null) {
      const trozo = linea.slice(inicio, encontrado.index + 1).trim();
      if (trozo) trozos.push(trozo);
      inicio = encontrado.index + 1;
    }
    const ultimo = linea.slice(inicio).trim();
    if (ultimo) trozos.push(ultimo);
    return trozos;
  }

  // Marcadores que introducen la conclusión.  «Entonces» se excluye cuando
  // forma parte de un condicional («Si..., entonces...»).
  const MARCADOR_CONCLUSION = new RegExp(
    "^\\s*(?:por\\s+tanto|por\\s+consiguiente|por\\s+lo\\s+tanto|" +
    "por\\s+conclusi[oó]n|en\\s+conclusi[oó]n|como\\s+conclusi[oó]n|" +
    "en\\s+consecuencia|por\\s+ende|as[ií]\\s+pues|de\\s+donde|" +
    "luego|entonces|as[ií]\\s+que|por\\s+ello)(?=\\s|[,;:.!?]|$)", "i");

  function esConclusion(frase) {
    const limpia = frase.trim();
    if (/^si\b/i.test(limpia) && /^entonces\b/i.test(limpia)) {
      return false;
    }
    return MARCADOR_CONCLUSION.test(limpia);
  }

  function leerFrases(texto) {
    const lineas = texto.split(/\r?\n/);
    const premisas = [];
    const conclusiones = [];
    let cerrado = false;
    for (const cruda of lineas) {
      const linea = cruda.trim();
      if (!linea || cerrado) continue;

      if (linea.includes("=>")) {
        const partes = linea.split("=>");
        const antes = partes.shift().trim();
        const despues = partes.join("=>").trim();
        if (antes) premisas.push(...dividirOraciones(antes));
        if (despues) conclusiones.push(...dividirOraciones(despues));
        cerrado = true;
      } else {
        for (const oracion of dividirOraciones(linea)) {
          if (esConclusion(oracion)) {
            conclusiones.push(oracion);
          } else if (!conclusiones.length) {
            premisas.push(oracion);
          }
          // Lo que venga después de una conclusión no se toma como premisa.
        }
      }
    }
    return conclusiones.length
      ? [...premisas, ...conclusiones]
      : premisas;
  }

  function normalizarMarcadoresConclusion() {
    const lineas = area.value.split(/\r?\n/);
    const salida = [];
    let cerrado = false;
    for (const linea of lineas) {
      if (cerrado) {
        salida.push(linea);
        continue;
      }
      if (linea.includes("=>")) {
        cerrado = true;
        salida.push(linea);
        continue;
      }
      const oraciones = dividirOraciones(linea);
      const indice = oraciones.findIndex(esConclusion);
      if (indice >= 0) {
        const antes = oraciones.slice(0, indice).join(" ").trim();
        const despues = oraciones.slice(indice).join(" ").trim();
        if (antes) salida.push(antes);
        if (despues) salida.push("=> " + despues);
        cerrado = true;
      } else {
        salida.push(linea);
      }
    }
    // Si no hay marcador ni «=>», la última frase es la conclusión:
    // se marca también de forma visible para que el usuario la vea.
    if (!cerrado) {
      const noVacias = salida
        .map((linea, indice) => linea.trim() ? indice : -1)
        .filter((indice) => indice >= 0);
      const totalOraciones = noVacias.reduce(
        (total, indice) => total + dividirOraciones(salida[indice]).length, 0);
      if (noVacias.length && totalOraciones >= 2) {
        const ultimo = noVacias[noVacias.length - 1];
        const oraciones = dividirOraciones(salida[ultimo]);
        if (oraciones.length > 1) {
          const anteriores = oraciones.slice(0, -1).join(" ").trim();
          const conclusion = oraciones[oraciones.length - 1].trim();
          salida[ultimo] = (anteriores ? anteriores + " " : "") +
            "=> " + conclusion;
        } else if (salida[ultimo].trim()) {
          salida[ultimo] = "=> " + salida[ultimo].trim();
        }
      }
    }
    const nuevo = salida.join("\n");
    if (nuevo !== area.value) {
      area.value = nuevo;
      localStorage.setItem("logica.frases", nuevo);
    }
  }

  function pintarFormulas(items) {
    listaFormulas.textContent = "";
    items.forEach((item, indice) => {
      const caja = crear("div", "formula-item " +
        (item.role === "conclusion" ? "rol-conclusion" : ""));

      const cabecera = crear("div", "formula-item__cabecera");
      const rol = crear("span", "rol " + (item.role === "conclusion"
        ? "rol--conclusion" : "rol--premisa"),
        item.role === "conclusion" ? "Conclusión" : "Premisa " + (indice + 1));
      const texto = crear("span", "formula-item__texto", "«" + item.text + "»");
      cabecera.append(rol, texto);
      if (item.source === "aprendida" || item.source === "ia") {
        cabecera.append(crear("span", "sello " +
          (item.source === "ia" ? "sello--ia" : ""),
          item.source === "ia" ? "A.E." : "aprendida"));
      }

      const etiqueta = crear("label", "etiqueta", "Fórmula");
      etiqueta.setAttribute("for", "formula-" + indice);
      etiqueta.hidden = true;

      const input = crear("input", "formula-input");
      input.id = "formula-" + indice;
      input.type = "text";
      input.value = item.formula || "";
      input.spellcheck = false;
      input.autocapitalize = "off";
      input.setAttribute("autocomplete", "off");
      input.setAttribute("aria-label",
        "Fórmula de la " + (item.role === "conclusion" ? "conclusión" : "premisa " + (indice + 1)));

      const pie = crear("p", "formula-item__pie");
      if (!item.ok) {
        pie.textContent = "No se ha reconocido la frase. Escribe la fórmula a mano.";
        input.classList.add("no-valida");
      }

      input.addEventListener("input", () => {
        input.classList.remove("no-valida");
        pie.textContent = "";
        aviso(avisoFormal, "");
      });

      caja.append(cabecera, etiqueta, input, pie);
      if (item.source === "aprendida") {
        caja.append(crear("p", "formula-item__nota",
          "Recuperada de una frase que ya confirmaste. Revisa que siga siendo correcta."));
      } else if (item.source === "ia") {
        caja.append(crear("p", "formula-item__nota",
          "Propuesta por la ayuda exterior (A.E.). Revísala antes de deducir."));
      } else if (item.ok && item.confianza === "baja") {
        caja.append(crear("p", "formula-item__nota formula-item__nota--revisar",
          (item.motivo_confianza || "Esta frase se ha tratado como un átomo.") +
          " Revísala o pide ayuda exterior (A.E.)."));
      }
      listaFormulas.append(caja);
    });
  }

  const alfabetoLetras = $("#alfabeto-letras");
  const alfabetoNota = $("#alfabeto-nota");

  function letrasAlfabeto() {
    if (estado.calculo === "pred") {
      return "CDEFGHIJKLMNOPQRSTUVWXYZAB".split("");
    }
    return "pqrstuvwxyz".split("");
  }

  function pintarAlfabeto(usadas) {
    if (!alfabetoLetras || !alfabetoNota) return;
    const alfabeto = letrasAlfabeto();
    const conjunto = new Set(usadas);
    let siguiente = alfabeto.find((letra) => !conjunto.has(letra)) || "";
    // Si se agotan p…z, el analizador continúa con aa, ab, ac…  Se muestran
    // esas letras para que el alfabeto visible coincida con el del ejercicio.
    const extra = usadas.filter((letra) => !alfabeto.includes(letra));
    if (!siguiente) {
      let i = 0;
      do {
        siguiente = String.fromCharCode(97 + Math.floor(i / 26)) +
          String.fromCharCode(97 + (i % 26));
        i += 1;
      } while (conjunto.has(siguiente));
      extra.push(siguiente);
    }
    alfabetoLetras.textContent = "";
    alfabeto.concat(extra).forEach((letra) => {
      const ficha = crear("span", "vocabulario__letra", letra);
      if (conjunto.has(letra)) {
        ficha.classList.add("vocabulario__letra--usada");
      } else if (letra === siguiente) {
        ficha.classList.add("vocabulario__letra--siguiente");
        ficha.title = "Siguiente letra libre";
      }
      alfabetoLetras.append(ficha);
    });
    if (!usadas.length) {
      alfabetoNota.textContent =
        "La primera letra que se asigne será la " + (siguiente || "p") + ".";
    } else {
      alfabetoNota.textContent = "Se usan " + usadas.length +
        (usadas.length === 1 ? " letra" : " letras") + ". " +
        "Si hace falta otra, será la " + siguiente + ".";
    }
  }

  function letrasDeFormulas(formulas) {
    const encontradas = [];
    const patron = estado.calculo === "pred" ? /([A-Z])\s*\(/g : /[a-z]+/g;
    (formulas || []).forEach((formula) => {
      let coincidencia;
      patron.lastIndex = 0;
      while ((coincidencia = patron.exec(formula)) !== null) {
        const letra = estado.calculo === "pred" ? coincidencia[1]
          : coincidencia[0];
        if (!encontradas.includes(letra)) encontradas.push(letra);
      }
    });
    return encontradas.map((letra) => ({ letter: letra, text: "" }));
  }

  function pintarVocabulario(vocab) {
    listaVocab.textContent = "";
    const lista = vocab || [];
    pintarAlfabeto(lista.map((v) => v.letter));
    if (!lista.length) {
      listaVocab.append(crear("p", "vocabulario__vacio",
        "Todavía no hay letras asignadas."));
      return;
    }
    lista.forEach((v) => {
      const fila = crear("div", "vocab-item");
      const letra = crear("span", "vocab-item__letra",
        estado.calculo === "pred" ? v.letter + "(x)" : v.letter);
      const input = crear("input", "vocab-input");
      input.type = "text";
      input.value = v.text || "";
      input.placeholder = "descripción de " + v.letter;
      input.setAttribute("aria-label", "Descripción de " + v.letter);
      input.dataset.letra = v.letter;
      fila.append(letra, input);
      listaVocab.append(fila);
    });
  }

  async function formalizar(forzarIA = false) {
    normalizarMarcadoresConclusion();
    const frases = leerFrases(area.value);
    if (frases.length < 2) {
      aviso(avisoEntrada,
        "Escribe al menos una premisa y la conclusión (con => delante).");
      area.focus();
      return false;
    }
    aviso(avisoEntrada, "");
    const boton = forzarIA ? $("#btn-consultar-ia") : $("#btn-resolver");
    cargando(boton, true);
    if (forzarIA) {
      aviso(avisoFormal,
        "Consultando la ayuda exterior (A.E.)… puede tardar hasta 40 segundos.",
        "");
    }
    const botonAEDeduccion = $("#btn-ayuda-deduccion");
    if (botonAEDeduccion) botonAEDeduccion.hidden = true;
    try {
      if (estado.plantilla && !forzarIA &&
          area.value.trim() === estado.plantillaTexto.trim()) {
        const formulas = estado.plantilla;
        if (formulas.length === frases.length) {
          estado.items = frases.map((texto, i) => ({
            text: texto,
            role: i === frases.length - 1 ? "conclusion" : "premisa",
            formula: formulas[i],
            ok: true,
          }));
          estado.vocab = letrasDeFormulas(formulas);
          pintarFormulas(estado.items);
          pintarVocabulario(estado.vocab);
          $("#resultado").hidden = true;
          $("#explicacion").hidden = true;
          aviso(avisoFormal, "");
          marcarPaso(1, "hecho");
          marcarPaso(2, "activo");
          marcarPaso(3, "");
          irA($("#formalizacion"));
          return true;
        }
      }
      const data = await pedir("/api/formalizar", {
        sentences: frases,
        calculus: estado.calculo,
        force_ai: forzarIA,
      });
      if (!data.ok) {
        aviso(avisoEntrada, data.error || "No se ha podido formalizar.");
        return false;
      }
      estado.items = data.items;
      estado.vocab = data.vocab || [];
      pintarFormulas(estado.items);
      pintarVocabulario(estado.vocab);
      $("#resultado").hidden = true;
      $("#explicacion").hidden = true;
      let mensajeFormal = data.aviso_ia || "";
      if (!mensajeFormal && data.ia_aplicada &&
          data.motivo_ia === "baja_confianza") {
        mensajeFormal = "Se ha consultado la ayuda exterior (A.E.) porque una " +
          "frase no se entendía bien con el analizador local. Revisa las " +
          "fórmulas marcadas como A.E.";
      }
      aviso(avisoFormal, mensajeFormal,
        data.ia_aplicada ? "ok" : "");
      if (/No se ha podido consultar la ayuda exterior/.test(mensajeFormal)) {
        const panelIA = $("#panel-ia");
        if (panelIA) panelIA.open = true;
      }
      marcarPaso(1, "hecho");
      marcarPaso(2, "activo");
      marcarPaso(3, "");
      invalidarMemoria();
      if (data.banco_guardadas) actualizarAprendizaje();
      irA($("#formalizacion"));
      return true;
    } catch (error) {
      aviso(avisoEntrada, error.message || "Error de conexión.");
      return false;
    } finally {
      cargando(boton, false);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Paso 3: deducción                                                  */
  /* ------------------------------------------------------------------ */
  const lineasPrueba = $("#lineas-prueba");
  const resumen = $("#resumen-ejercicio");
  const avisoCopiar = $("#aviso-copiar");

  function claseRegla(raw) {
    if (/^(EG|IG|EP|IP|EI)/.test(raw)) return "regla--pred";
    if (/^(MP|MT|SH|Sil|Cp|DI|TD|II)/.test(raw)) return "regla--imp";
    if (/^(IC|Simp|DC|DM2)/.test(raw)) return "regla--and";
    if (/^(SD|Dil|Ad|DM1|DD|IDD)/.test(raw)) return "regla--or";
    if (/^(Dn|DN|IDN|Abs)/.test(raw)) return "regla--neg";
    return "";
  }

  function pintarResumen(premisas, meta) {
    resumen.textContent = "";
    premisas.forEach((formula, i) => {
      const fila = crear("div", "resumen__linea");
      fila.append(crear("span", "et", "−" + (i + 1)),
        document.createTextNode(" " + formula));
      resumen.append(fila);
    });
    const filaMeta = crear("div", "resumen__linea resumen__meta");
    filaMeta.append(crear("span", "et", "⊢"),
      document.createTextNode(" " + meta));
    resumen.append(filaMeta);
  }

  function pintarPrueba(lineas, contenedor = lineasPrueba, conQed = true) {
    contenedor.textContent = "";
    lineas.forEach((ln) => {
      const fila = crear("div", "prueba__linea");
      if (ln.rawRule === "PREM") fila.classList.add("es-premisa");
      if (ln.hyp) fila.classList.add("es-supuesto");
      if (ln.marker === "⌊") fila.classList.add("es-cierre");
      if (ln.n === lineas.length) fila.classList.add("es-meta");
      fila.style.setProperty("--sangria", (ln.depth * 1.1) + "rem");

      fila.append(
        crear("span", "marcador", ln.marker === " " ? "" : ln.marker),
        crear("span", "num", String(ln.n)),
        crear("span", "formula", ln.formula)
      );

      const cita = crear("span", "cita");
      const regla = crear("span", "regla " + claseRegla(ln.rawRule), ln.label);
      cita.append(regla);
      if (ln.citation) {
        const resto = ln.citation.replace(ln.label, "").trim();
        if (resto) cita.append(document.createTextNode(" " + resto));
      }
      fila.append(cita);
      contenedor.append(fila);
    });

    if (conQed) {
      const qed = crear("div", "qed", "QED");
      contenedor.append(qed);
    }
  }

  function pintarExplicaciones(lineas) {
    const lista = $("#lista-explicaciones");
    lista.textContent = "";
    lineas.forEach((ln) => {
      const caja = crear("div", "explicacion");
      const num = crear("span", "explicacion__num", String(ln.n));
      const cuerpo = crear("div", "explicacion__cuerpo");

      const cabecera = crear("div", "explicacion__cabecera");
      cabecera.append(
        crear("span", "regla " + claseRegla(ln.rawRule), ln.label),
        crear("span", "explicacion__formula", ln.formula)
      );

      const texto = crear("p", null, ln.explanation);
      cuerpo.append(cabecera, texto);
      caja.append(num, cuerpo);
      lista.append(caja);
    });

    const reglas = $("#lista-reglas");
    reglas.textContent = "";
    const usadas = [];
    lineas.forEach((ln) => {
      if (ln.rawRule === "PREM" || ln.hyp) return;
      if (!usadas.includes(ln.label)) usadas.push(ln.label);
    });
    usadas.forEach((nombre) => {
      const caja = crear("div", "glosario__item");
      caja.append(crear("strong", null, nombre),
        crear("span", null, GLOSARIO[nombre] || "Regla de la deducción."));
      reglas.append(caja);
    });
    if (!usadas.length) {
      reglas.append(crear("p", "nota-red", "En esta deducción sólo hay premisas."));
    }
  }

  function recogerFormulas() {
    return $$(".formula-input").map((input) => input.value.trim());
  }

  function recogerVocabulario() {
    const vocab = {};
    $$(".vocab-input").forEach((input) => {
      const texto = input.value.trim();
      if (input.dataset.letra && texto) vocab[input.dataset.letra] = texto;
    });
    return vocab;
  }

  function marcarErrores(errores) {
    $$(".formula-input").forEach((input, i) => {
      const pie = input.parentElement.querySelector(".formula-item__pie");
      const error = errores[String(i)];
      if (error) {
        input.classList.add("no-valida");
        if (pie) pie.textContent = error;
      }
    });
    const primero = $(".formula-input.no-valida");
    if (primero) primero.focus();
  }

  async function deducir(mostrarCarga, forzarIA = false) {
    const formulas = recogerFormulas();
    if (formulas.length < 2 || formulas.some((f) => !f)) {
      aviso(avisoFormal, "Falta alguna fórmula por escribir.");
      return false;
    }
    const boton = forzarIA ? $("#btn-ayuda-deduccion") : $("#btn-deducir");
    if (mostrarCarga) cargando(boton, true);
    if (forzarIA) {
      aviso(avisoFormal,
        "Consultando la ayuda exterior (A.E.)… puede tardar hasta 40 segundos.",
        "");
    }
    // No borrar el aviso verde de que se ha consultado la IA al deducir.
    if (!avisoFormal.classList.contains("aviso--ok")) {
      aviso(avisoFormal, "");
    }
    try {
      const data = await pedir("/api/deducir", {
        formulas,
        sentences: estado.items.map((item) => item.text),
        vocab: recogerVocabulario(),
        force_ai: forzarIA,
      });
      if (!data.ok) {
        if (data.errores) marcarErrores(data.errores);
        $("#resultado").hidden = true;
        $("#explicacion").hidden = true;
        marcarPaso(2, "activo");
        marcarPaso(3, "");
        aviso(avisoFormal, data.error || "No se ha encontrado la deducción.");
        const botonAE = $("#btn-ayuda-deduccion");
        if (botonAE) botonAE.hidden = !(data.puede_ae || data.ia);
        $("#formalizacion").scrollIntoView({ behavior: "smooth", block: "start" });
        return false;
      }
      const botonAE = $("#btn-ayuda-deduccion");
      if (botonAE) botonAE.hidden = true;
      estado.lineas = data.lines;
      estado.plain = data.plain;
      let repintarFormulas = false;
      if (data.correcciones) {
        Object.entries(data.correcciones).forEach(([indice, formula]) => {
          const item = estado.items[Number(indice)];
          if (item) {
            item.formula = formula;
            item.ok = true;
            item.confianza = "alta";
            item.motivo_confianza = "";
            if (data.ia_aplicada) {
              item.source = "ia";
              repintarFormulas = true;
            }
          }
          const input = $("#formula-" + indice);
          if (input) {
            input.value = formula;
            input.classList.remove("no-valida");
          }
        });
      }
      if (data.ia_aplicada && data.vocab) {
        estado.vocab = data.vocab;
        pintarVocabulario(data.vocab);
      }
      if (repintarFormulas) pintarFormulas(estado.items);
      if (data.aviso_variante) {
        aviso(avisoFormal, data.aviso_variante, "");
      }
      if (data.ia_aplicada && data.aviso_ia) {
        aviso(avisoFormal, data.aviso_ia, "ok");
      }
      pintarResumen(data.premises, data.goal);
      pintarPrueba(data.lines);
      pintarExplicaciones(data.lines);
      $("#resultado").hidden = false;
      $("#explicacion").hidden = false;
      marcarPaso(2, "hecho");
      marcarPaso(3, "activo");
      aviso(avisoCopiar, "");
      irA($("#resultado"));
      invalidarMemoria();
      if (data.aprendido) actualizarAprendizaje();
      return true;
    } catch (error) {
      const mensaje = error.message || "Error de conexión.";
      aviso(avisoFormal, mensaje);
      if (/No se ha podido consultar la ayuda exterior/.test(mensaje)) {
        const panelIA = $("#panel-ia");
        if (panelIA) panelIA.open = true;
      }
      return false;
    } finally {
      if (mostrarCarga) cargando(boton, false);
    }
  }

  $("#btn-resolver").addEventListener("click", async () => {
    const ok = await formalizar();
    if (ok) await deducir(true);
  });

  $("#btn-deducir").addEventListener("click", () => deducir(true));

  const btnAyudaDeduccion = $("#btn-ayuda-deduccion");
  if (btnAyudaDeduccion) {
    btnAyudaDeduccion.addEventListener("click", () => deducir(true, true));
  }

  const btnConsultarIA = $("#btn-consultar-ia");
  if (btnConsultarIA) {
    btnConsultarIA.addEventListener("click", async () => {
      const ok = await formalizar(true);
      if (ok) await deducir(true);
    });
  }

  /* ------------------------------------------------------------------ */
  /* Copiar y descargar                                                 */
  /* ------------------------------------------------------------------ */
  async function copiarTexto(texto) {
    try {
      await navigator.clipboard.writeText(texto);
      return true;
    } catch (e) {
      const auxiliar = document.createElement("textarea");
      auxiliar.value = texto;
      auxiliar.setAttribute("readonly", "");
      auxiliar.style.position = "fixed";
      auxiliar.style.opacity = "0";
      document.body.append(auxiliar);
      auxiliar.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      auxiliar.remove();
      return ok;
    }
  }

  $("#btn-copiar").addEventListener("click", async () => {
    const ok = await copiarTexto(estado.plain || "");
    aviso(avisoCopiar, ok ? "Deducción copiada." : "No se ha podido copiar.", "ok");
  });

  $("#btn-descargar").addEventListener("click", () => {
    const blob = new Blob([estado.plain || ""], { type: "text/plain;charset=utf-8" });
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(blob);
    enlace.download = "deduccion.txt";
    document.body.append(enlace);
    enlace.click();
    enlace.remove();
    URL.revokeObjectURL(enlace.href);
  });

  /* ------------------------------------------------------------------ */
  /* Memoria local de frases                                            */
  /* ------------------------------------------------------------------ */
  const textoAprendizaje = $("#texto-aprendizaje");

  async function actualizarAprendizaje() {
    if (!textoAprendizaje) return;
    try {
      const respuesta = await fetch("/api/aprendizaje", {
        cache: "no-store",
        headers: cabecerasIA(),
      });
      const datos = await respuesta.json();
      const botonIA = $("#btn-consultar-ia");
      if (botonIA) botonIA.hidden = !datos.ia;
      if (!datos.ia) {
        const botonAE = $("#btn-ayuda-deduccion");
        if (botonAE) botonAE.hidden = true;
      }
      const versionTexto = $("#version-texto");
      if (versionTexto && datos.version) {
        versionTexto.textContent = "Lógica · v" + datos.version;
      }
      if (!datos.activo) {
        textoAprendizaje.textContent =
          "La memoria está desactivada en este servidor.";
        return;
      }
      const exactas = datos.exactas || 0;
      const plantillas = datos.plantillas || 0;
      const ejercicios = datos.ejercicios || 0;
      const banco = datos.banco || 0;
      const frasesVisibles = banco || exactas;
      if (!frasesVisibles && !plantillas && !ejercicios) {
        textoAprendizaje.textContent =
          "Todavía no hay frases guardadas. Cada frase que formalices se " +
          "guardará automáticamente en el banco.";
      } else {
        const frases = frasesVisibles === 1 ? "1 frase" : frasesVisibles + " frases";
        const patrones = plantillas === 1 ? "1 patrón" : plantillas + " patrones";
        const completos = ejercicios === 1 ? "1 ejercicio completo"
          : ejercicios + " ejercicios completos";
        textoAprendizaje.textContent =
          "Guardadas " + frases + ", " + patrones + " de imitación y " +
          completos + ". Pulsa «Ver memoria de frases» para revisarlas.";
      }
      const estadoIA = $("#estado-ia");
      if (estadoIA) {
        if (datos.ia) {
          estadoIA.textContent = "Ayuda exterior (A.E.) conectada" +
            (datos.modelo ? " (" + datos.modelo + ")" : "") +
            (datos.gratuita ? ", servicio gratuito" : "") +
            (datos.busqueda ? " con búsqueda web." : " sin búsqueda web.");
        } else {
          estadoIA.textContent =
            "Ayuda exterior (A.E.) no configurada: sólo se usa el " +
            "analizador local.";
        }
      }
    } catch (e) {
      textoAprendizaje.textContent =
        "No se ha podido consultar la memoria local.";
    }
  }

  /* ------------------------------------------------------------------ */
  /* Menús laterales: definiciones y guía de teoría                     */
  /* ------------------------------------------------------------------ */
  const menusLaterales = [];

  function configurarMenuLateral({ menu, boton, botonCerrar }) {
    if (!menu || !boton) return null;

    let focoAntes = null;

    function enfocables() {
      return Array.from(menu.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), ' +
        'select:not([disabled]), textarea:not([disabled]), ' +
        '[tabindex]:not([tabindex="-1"])'
      )).filter((nodo) => !nodo.hidden &&
        nodo.getClientRects().length > 0);
    }

    function abrir() {
      if (!menu.hidden) return;
      menusLaterales.forEach((otro) => {
        if (otro.menu !== menu && !otro.menu.hidden) {
          otro.menu.hidden = true;
          otro.boton.setAttribute("aria-expanded", "false");
        }
      });
      focoAntes = document.activeElement;
      menu.hidden = false;
      menu.scrollTop = 0;
      boton.setAttribute("aria-expanded", "true");
      document.body.classList.add("menu-lateral-abierto");
      if (botonCerrar) botonCerrar.focus();
    }

    function cerrar() {
      if (menu.hidden) return;
      menu.hidden = true;
      boton.setAttribute("aria-expanded", "false");
      if (!menusLaterales.some((otro) => !otro.menu.hidden)) {
        document.body.classList.remove("menu-lateral-abierto");
      }
      if (focoAntes && focoAntes !== document.body &&
          document.contains(focoAntes)) {
        focoAntes.focus();
      } else {
        boton.focus();
      }
      focoAntes = null;
    }

    boton.addEventListener("click", abrir);
    if (botonCerrar) {
      botonCerrar.addEventListener("click", cerrar);
    }
    menu.querySelectorAll("[data-cerrar-menu]").forEach((cerrarMenu) => {
      cerrarMenu.addEventListener("click", cerrar);
    });
    menu.addEventListener("click", (evento) => {
      if (evento.target === menu) cerrar();
    });
    menu.querySelectorAll(".menu-teoria__indice a").forEach((enlace) => {
      enlace.addEventListener("click", (evento) => {
        evento.preventDefault();
        const destino = document.querySelector(enlace.getAttribute("href"));
        if (destino) destino.scrollIntoView({ block: "start" });
      });
    });
    document.addEventListener("keydown", (evento) => {
      if (menu.hidden) return;
      if (evento.key === "Escape") {
        evento.preventDefault();
        cerrar();
        return;
      }
      if (evento.key !== "Tab") return;
      const lista = enfocables();
      if (!lista.length) return;
      const primero = lista[0];
      const ultimo = lista[lista.length - 1];
      if (!menu.contains(document.activeElement)) {
        evento.preventDefault();
        primero.focus();
      } else if (evento.shiftKey && document.activeElement === primero) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primero.focus();
      }
    });

    const control = { menu, boton, cerrar };
    menusLaterales.push(control);
    return control;
  }

  const menuDefiniciones = configurarMenuLateral({
    menu: $("#menu-definiciones"),
    boton: $("#btn-definiciones"),
    botonCerrar: $("#btn-cerrar-definiciones")
  });

  const menuTeoria = configurarMenuLateral({
    menu: $("#menu-teoria"),
    boton: $("#btn-teoria"),
    botonCerrar: $("#btn-cerrar-teoria")
  });

  /* ------------------------------------------------------------------ */
  /* Buscador de definiciones y teoría                                  */
  /* ------------------------------------------------------------------ */
  const buscadorEntrada = $("#buscador-entrada");
  const buscadorLimpiar = $("#buscador-limpiar");
  const buscadorResultados = $("#buscador-resultados");
  const buscadorIndice = [];
  let buscadorActivo = -1;

  function normalizarTexto(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function crearIndiceBuscador() {
    const fichas = [];
    const definiciones = $$("#menu-definiciones .definicion");
    definiciones.forEach((articulo) => {
      const tituloEl = articulo.querySelector(".definicion__titulo");
      const textoEl = articulo.querySelector(".definicion__texto");
      const seccion = articulo.closest(".teoria-seccion");
      const capitulo = seccion ? seccion.querySelector("h3") : null;
      const titulo = tituloEl ? tituloEl.textContent : "";
      const texto = textoEl ? textoEl.textContent : "";
      if (!titulo.trim()) return;
      fichas.push({
        tipo: "definicion",
        titulo: titulo.replace(/\s+/g, " ").trim(),
        contexto: capitulo ? capitulo.textContent.trim() : "Definición",
        texto: texto.replace(/\s+/g, " ").trim(),
        destino: articulo,
        menu: menuDefiniciones
      });
    });

    $$("#menu-teoria .teoria-seccion").forEach((seccion) => {
      const tituloEl = seccion.querySelector("h3");
      if (!tituloEl) return;
      const kicker = seccion.querySelector(".teoria-kicker");
      fichas.push({
        tipo: "teoria",
        titulo: tituloEl.textContent.replace(/\s+/g, " ").trim(),
        contexto: kicker ? kicker.textContent.trim() : "Guía de teoría",
        texto: seccion.textContent.replace(/\s+/g, " ").trim(),
        destino: seccion,
        menu: menuTeoria
      });
    });

    fichas.forEach((ficha) => {
      ficha.tituloNorm = normalizarTexto(ficha.titulo);
      ficha.contextoNorm = normalizarTexto(ficha.contexto);
      ficha.textoNorm = normalizarTexto(ficha.texto);
    });
    return fichas;
  }

  function resaltarTexto(texto, terminos) {
    const fragmento = document.createDocumentFragment();
    if (!terminos.length) {
      fragmento.append(document.createTextNode(texto));
      return fragmento;
    }
    const patron = new RegExp(
      "(" + terminos.map((t) =>
        t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")",
      "gi");
    let ultimo = 0;
    String(texto).replace(patron, (coincidencia, _grupo, posicion) => {
      if (posicion > ultimo) {
        fragmento.append(document.createTextNode(
          texto.slice(ultimo, posicion)));
      }
      const marca = document.createElement("mark");
      marca.textContent = coincidencia;
      fragmento.append(marca);
      ultimo = posicion + coincidencia.length;
      return coincidencia;
    });
    if (ultimo < texto.length) {
      fragmento.append(document.createTextNode(texto.slice(ultimo)));
    }
    return fragmento;
  }

  function recortarTexto(texto, terminos) {
    const limite = 150;
    if (texto.length <= limite) return texto;
    let posicion = -1;
    for (const termino of terminos) {
      const encontrado = normalizarTexto(texto).indexOf(normalizarTexto(termino));
      if (encontrado !== -1 && (posicion === -1 || encontrado < posicion)) {
        posicion = encontrado;
      }
    }
    if (posicion < 0) return texto.slice(0, limite) + "…";
    const inicio = Math.max(0, posicion - 45);
    const fin = Math.min(texto.length, inicio + limite);
    return (inicio > 0 ? "…" : "") + texto.slice(inicio, fin) +
      (fin < texto.length ? "…" : "");
  }

  function buscarFichas(consulta) {
    const terminos = normalizarTexto(consulta).split(" ").filter(Boolean);
    if (!terminos.length) return [];
    const resultados = [];
    buscadorIndice.forEach((ficha) => {
      const enTitulo = terminos.every((t) => ficha.tituloNorm.includes(t));
      const enContexto = terminos.every((t) => ficha.contextoNorm.includes(t) ||
        ficha.tituloNorm.includes(t));
      const textoCompleto = ficha.tituloNorm + " " + ficha.contextoNorm +
        " " + ficha.textoNorm;
      if (!terminos.every((t) => textoCompleto.includes(t))) return;
      let puntos = 60;
      if (enTitulo) {
        puntos = ficha.tituloNorm.startsWith(terminos[0]) ? 160 : 140;
      } else if (enContexto) {
        puntos = 100;
      }
      puntos -= Math.min(30, Math.floor(ficha.texto.length / 1200));
      resultados.push({ ficha, puntos });
    });
    resultados.sort((a, b) => {
      if (a.ficha.tipo !== b.ficha.tipo) {
        return a.ficha.tipo === "definicion" ? -1 : 1;
      }
      return b.puntos - a.puntos;
    });
    const definiciones = resultados.filter((r) =>
      r.ficha.tipo === "definicion").slice(0, 9);
    const teoria = resultados.filter((r) =>
      r.ficha.tipo === "teoria").slice(0, 6);
    return definiciones.concat(teoria).map((r) => r.ficha);
  }

  function cerrarResultadosBuscador() {
    if (!buscadorResultados) return;
    buscadorResultados.hidden = true;
    buscadorResultados.textContent = "";
    buscadorEntrada.setAttribute("aria-expanded", "false");
    buscadorEntrada.removeAttribute("aria-activedescendant");
    buscadorActivo = -1;
  }

  function marcarResultadoActivo() {
    const botones = Array.from(
      buscadorResultados.querySelectorAll(".buscador__resultado"));
    botones.forEach((boton, indice) => {
      const activo = indice === buscadorActivo;
      boton.classList.toggle("activo", activo);
      boton.setAttribute("aria-selected", activo ? "true" : "false");
    });
    const actual = botones[buscadorActivo];
    if (actual) {
      buscadorEntrada.setAttribute("aria-activedescendant", actual.id);
      actual.scrollIntoView({ block: "nearest" });
    } else {
      buscadorEntrada.removeAttribute("aria-activedescendant");
    }
  }

  function abrirResultadoBuscador(ficha) {
    if (!ficha) return;
    cerrarResultadosBuscador();
    if (ficha.menu) ficha.menu.boton.click();
    window.setTimeout(() => {
      ficha.destino.scrollIntoView({ block: "center" });
      ficha.destino.classList.remove("buscador-destino");
      void ficha.destino.offsetWidth;
      ficha.destino.classList.add("buscador-destino");
      window.setTimeout(() => {
        ficha.destino.classList.remove("buscador-destino");
      }, 2600);
    }, 70);
  }

  function renderResultadosBuscador(resultados, consulta) {
    if (!buscadorResultados) return;
    buscadorResultados.textContent = "";
    buscadorActivo = -1;

    if (!resultados.length) {
      const vacio = crear("p", "buscador__vacio",
        "No hay definiciones ni teoría que coincidan con «" +
        consulta.trim() + "».");
      buscadorResultados.append(vacio);
    } else {
      const terminos = consulta.trim().split(/\s+/).filter(Boolean);
      let tipoAnterior = null;
      resultados.forEach((ficha, indice) => {
        if (ficha.tipo !== tipoAnterior) {
          tipoAnterior = ficha.tipo;
          buscadorResultados.append(crear("p", "buscador__grupo",
            ficha.tipo === "definicion" ? "Definiciones" : "Teoría"));
        }
        const boton = crear("button", "buscador__resultado");
        boton.type = "button";
        boton.id = "buscador-resultado-" + indice;
        boton.setAttribute("role", "option");
        boton.setAttribute("aria-selected", "false");

        const linea = crear("span", "buscador__resultado-titulo");
        const texto = crear("span");
        texto.append(resaltarTexto(ficha.titulo, terminos));
        linea.append(texto);
        linea.append(crear("span", "buscador__tipo buscador__tipo--" +
          ficha.tipo, ficha.tipo === "definicion" ? "Definición" : "Teoría"));
        boton.append(linea);

        if (ficha.contexto) {
          boton.append(crear("span", "buscador__resultado-contexto",
            ficha.contexto));
        }
        const resumen = crear("span", "buscador__resultado-texto");
        resumen.append(resaltarTexto(
          recortarTexto(ficha.texto, terminos), terminos));
        boton.append(resumen);

        boton.addEventListener("click", () => abrirResultadoBuscador(ficha));
        boton.addEventListener("pointermove", () => {
          buscadorActivo = indice;
          marcarResultadoActivo();
        });
        buscadorResultados.append(boton);
      });
      buscadorResultados.append(crear("p", "buscador__pie",
        "↑ ↓ para moverte · Enter para abrir · Esc para cerrar"));
    }

    buscadorResultados.hidden = false;
    buscadorEntrada.setAttribute("aria-expanded", "true");
  }

  function ejecutarBusqueda() {
    if (!buscadorEntrada || !buscadorResultados) return;
    const consulta = buscadorEntrada.value;
    if (buscadorLimpiar) buscadorLimpiar.hidden = !consulta.length;
    if (normalizarTexto(consulta).length < 2) {
      cerrarResultadosBuscador();
      return;
    }
    renderResultadosBuscador(buscarFichas(consulta), consulta);
  }

  if (buscadorEntrada && buscadorResultados) {
    buscadorIndice.push(...crearIndiceBuscador());

    buscadorEntrada.addEventListener("input", ejecutarBusqueda);
    buscadorEntrada.addEventListener("focus", () => {
      if (buscadorEntrada.value.trim().length >= 2) ejecutarBusqueda();
    });
    buscadorEntrada.addEventListener("keydown", (evento) => {
      const botones = Array.from(
        buscadorResultados.querySelectorAll(".buscador__resultado"));
      if (evento.key === "ArrowDown") {
        if (!botones.length) return;
        evento.preventDefault();
        buscadorActivo = (buscadorActivo + 1) % botones.length;
        marcarResultadoActivo();
      } else if (evento.key === "ArrowUp") {
        if (!botones.length) return;
        evento.preventDefault();
        buscadorActivo = buscadorActivo <= 0
          ? botones.length - 1 : buscadorActivo - 1;
        marcarResultadoActivo();
      } else if (evento.key === "Enter") {
        if (buscadorActivo >= 0 && botones[buscadorActivo]) {
          evento.preventDefault();
          botones[buscadorActivo].click();
        }
      } else if (evento.key === "Escape") {
        cerrarResultadosBuscador();
      }
    });
    if (buscadorLimpiar) {
      buscadorLimpiar.addEventListener("click", () => {
        buscadorEntrada.value = "";
        buscadorLimpiar.hidden = true;
        cerrarResultadosBuscador();
        buscadorEntrada.focus();
      });
    }
    document.addEventListener("click", (evento) => {
      if (!evento.target.closest(".buscador")) cerrarResultadosBuscador();
    });
  }

  /* ------------------------------------------------------------------ */
  /* Memoria: ejercicios completos para revisar                         */
  /* ------------------------------------------------------------------ */
  const btnVerMemoria = $("#btn-ver-memoria");
  const btnRecargarMemoria = $("#btn-recargar-memoria");
  const memoriaItems = $("#memoria-items");
  const memoriaDetalle = $("#memoria-detalle");
  const memoriaCuenta = $("#memoria-cuenta");
  const memoriaEstado = {
    cargado: false,
    ejercicios: [],
    frases: [],
    banco: [],
    seleccion: null,
  };
  let menuMemoriaControl = null;

  function invalidarMemoria() {
    memoriaEstado.cargado = false;
  }

  function fechaMemoria(iso) {
    if (!iso) return "";
    const fecha = new Date(iso);
    if (Number.isNaN(fecha.getTime())) return iso;
    return fecha.toLocaleDateString("es-ES", {
      day: "2-digit", month: "short", year: "numeric",
    });
  }

  function contarMemoria(n, singular, plural) {
    return n + " " + (n === 1 ? singular : plural);
  }

  function tituloMemoria(texto) {
    const limpio = String(texto || "").replace(MARCADOR_CONCLUSION, "")
      .replace(/^[\s,;:.\-–—]+/, "").trim();
    if (!limpio) return "";
    return limpio.charAt(0).toLocaleUpperCase("es") + limpio.slice(1);
  }

  function marcarMemoriaActiva(id) {
    memoriaItems.querySelectorAll(".memoria__item").forEach((item) => {
      item.classList.toggle("activo", item.dataset.memoriaId === id ||
        item.dataset.fraseId === id || item.dataset.bancoId === id);
    });
  }

  async function cargarMemoria(forzar = false) {
    if (!memoriaItems) return;
    if (memoriaEstado.cargado && !forzar) {
      renderMemoriaLista();
      return;
    }
    memoriaCuenta.textContent = "Cargando…";
    memoriaItems.textContent = "";
    memoriaItems.append(crear("p", "memoria__vacio",
      "Leyendo la memoria local…"));
    try {
      const respuesta = await fetch("/api/memoria", { cache: "no-store" });
      const datos = await respuesta.json();
      if (!datos.ok) throw new Error(datos.error || "No se pudo leer la memoria.");
      memoriaEstado.ejercicios = datos.ejercicios || [];
      memoriaEstado.frases = datos.frases || [];
      memoriaEstado.banco = datos.banco || [];
      memoriaEstado.cargado = true;
      renderMemoriaLista();
    } catch (error) {
      memoriaCuenta.textContent = "Memoria no disponible";
      memoriaItems.textContent = "";
      memoriaItems.append(crear("p", "memoria__vacio",
        error.message || "No se ha podido consultar la memoria local."));
    }
  }

  function renderMemoriaLista() {
    if (!memoriaItems) return;
    memoriaItems.textContent = "";
    const ejercicios = memoriaEstado.ejercicios;
    const frases = memoriaEstado.frases;
    const banco = memoriaEstado.banco;
    if (!ejercicios.length && !frases.length && !banco.length) {
      memoriaCuenta.textContent = "Sin frases guardadas";
      memoriaItems.append(crear("p", "memoria__vacio",
        "Todavía no hay frases guardadas. Cada frase que formalices se " +
        "guardará aquí automáticamente."));
      return;
    }

    const totalFrases = banco.length || frases.length;
    const partes = [];
    if (totalFrases) {
      partes.push(contarMemoria(totalFrases, "frase", "frases"));
    }
    if (ejercicios.length) {
      partes.push(contarMemoria(ejercicios.length, "ejercicio", "ejercicios"));
    }
    memoriaCuenta.textContent = partes.join(" · ");

    // Las frases van primero: es el contenido que se genera solo al
    // formalizar. Los ejercicios completos se muestran debajo.
    const bloqueEjercicios = document.createDocumentFragment();
    if (ejercicios.length) {
      bloqueEjercicios.append(crear("p", "memoria__grupo", "Ejercicios deducidos"));
      ejercicios.forEach((ejercicio) => {
        const boton = crear("button", "memoria__item");
        boton.type = "button";
        boton.dataset.memoriaId = ejercicio.id;
        boton.append(
          crear("span", "memoria-item__titulo",
            tituloMemoria(ejercicio.titulo) || "Ejercicio guardado"),
          crear("span", "memoria-item__meta",
            (ejercicio.recuperado ? "Recuperado · " : "") +
            contarMemoria(ejercicio.frases, "frase", "frases") + " · " +
            (ejercicio.usos === 1 ? "1 vez" : ejercicio.usos + " veces") +
            (ejercicio.actualizado ? " · " + fechaMemoria(ejercicio.actualizado) : "")),
          crear("span", "memoria-item__formula", "⊢ " + ejercicio.meta)
        );
        boton.addEventListener("click", () => seleccionarEjercicio(ejercicio.id));
        bloqueEjercicios.append(boton);
      });
    }

    if (banco.length) {
      memoriaItems.append(crear("p", "memoria__grupo", "Frases guardadas"));
      banco.forEach((frase, indice) => {
        const boton = crear("button", "memoria__item");
        boton.type = "button";
        const idFrase = "banco-" + indice;
        boton.dataset.bancoId = idFrase;
        boton.append(
          crear("span", "memoria-item__titulo", tituloMemoria(frase.texto)),
          crear("span", "memoria-item__meta",
            "Fórmula: " + frase.formula +
            (frase.usos > 1 ? " · " + frase.usos + " veces" : "") +
            (frase.actualizado ? " · " + fechaMemoria(frase.actualizado) : "")),
          crear("span", "memoria-item__formula", frase.formula)
        );
        boton.addEventListener("click", () => {
          memoriaEstado.seleccion = idFrase;
          marcarMemoriaActiva(idFrase);
          renderDetalleFrase(frase, true);
        });
        memoriaItems.append(boton);
      });
    } else if (frases.length) {
      // Compatibilidad con memorias antiguas: frases sueltas sin ejercicio.
      memoriaItems.append(crear("p", "memoria__grupo", "Frases guardadas"));
      frases.forEach((frase, indice) => {
        const boton = crear("button", "memoria__item");
        boton.type = "button";
        const idFrase = "frase-" + indice;
        boton.dataset.fraseId = idFrase;
        boton.append(
          crear("span", "memoria-item__titulo", tituloMemoria(frase.texto)),
          crear("span", "memoria-item__meta",
            "Fórmula: " + frase.formula +
            (frase.actualizado ? " · " + fechaMemoria(frase.actualizado) : "")),
          crear("span", "memoria-item__formula", frase.formula)
        );
        boton.addEventListener("click", () => {
          memoriaEstado.seleccion = idFrase;
          marcarMemoriaActiva(idFrase);
          renderDetalleFrase(frase);
        });
        memoriaItems.append(boton);
      });
    }

    memoriaItems.append(bloqueEjercicios);

    // Mantener la selección actual si sigue existiendo; si no, abrir la
    // primera frase y, si no hay banco, el primer ejercicio disponible.
    const id = memoriaEstado.seleccion;
    const indiceBanco = typeof id === "string" && id.startsWith("banco-")
      ? Number(id.slice("banco-".length)) : -1;
    if (indiceBanco >= 0 && banco[indiceBanco]) {
      marcarMemoriaActiva(id);
      renderDetalleFrase(banco[indiceBanco], true);
      return;
    }
    if (id && ejercicios.some((e) => e.id === id)) {
      marcarMemoriaActiva(id);
      return;
    }
    if (banco.length) {
      memoriaEstado.seleccion = "banco-0";
      marcarMemoriaActiva("banco-0");
      renderDetalleFrase(banco[0], true);
      return;
    }
    if (ejercicios.length) {
      seleccionarEjercicio(ejercicios[0].id);
      return;
    }
    memoriaEstado.seleccion = "frase-0";
    marcarMemoriaActiva("frase-0");
    renderDetalleFrase(frases[0]);
  }

  async function seleccionarEjercicio(id) {
    if (!id) return;
    memoriaEstado.seleccion = id;
    marcarMemoriaActiva(id);
    memoriaDetalle.textContent = "";
    memoriaDetalle.append(crear("p", "memoria__vacio",
      "Cargando la formalización y la deducción…"));
    try {
      const respuesta = await fetch("/api/memoria?id=" +
        encodeURIComponent(id), { cache: "no-store" });
      const datos = await respuesta.json();
      if (!datos.ok) throw new Error(datos.error || "No se pudo abrir el ejercicio.");
      renderDetalleEjercicio(datos.ejercicio);
    } catch (error) {
      memoriaDetalle.textContent = "";
      memoriaDetalle.append(crear("p", "memoria__vacio",
        error.message || "No se ha podido abrir el ejercicio."));
    }
  }

  function bloqueMemoria(titulo) {
    const bloque = crear("section", "memoria__bloque");
    bloque.append(crear("h4", null, titulo));
    return bloque;
  }

  function renderDetalleEjercicio(ejercicio) {
    memoriaDetalle.textContent = "";
    const frases = ejercicio.frases || [];
    const ultima = frases.length ? frases[frases.length - 1] : null;
    const titulo = ultima ? tituloMemoria(ultima.text) : "Ejercicio guardado";
    memoriaDetalle.append(crear("h3", null, titulo || "Ejercicio guardado"));
    memoriaDetalle.append(crear("p", "memoria__detalle-meta",
      contarMemoria(frases.length, "frase", "frases") + " · " +
      (ejercicio.usos === 1 ? "1 vez" : (ejercicio.usos || 0) + " veces") +
      (ejercicio.actualizado ? " · " + fechaMemoria(ejercicio.actualizado) : "")));

    if (ejercicio.aviso) {
      memoriaDetalle.append(crear("p", "memoria__aviso", ejercicio.aviso));
    }

    const bloqueFrases = bloqueMemoria("Frases y formalización");
    const listaFrases = crear("div", "memoria__frases");
    frases.forEach((frase, indice) => {
      const conclusion = frase.role === "conclusion" || indice === frases.length - 1;
      const caja = crear("div", "memoria__frase" +
        (conclusion ? " memoria__frase--conclusion" : ""));
      caja.append(
        crear("span", "memoria__rol",
          conclusion ? "Conclusión" : "Premisa " + (indice + 1)),
        crear("p", "memoria__texto", frase.text || ""),
        crear("code", "memoria__formula", frase.formula || "")
      );
      listaFrases.append(caja);
    });
    bloqueFrases.append(listaFrases);
    memoriaDetalle.append(bloqueFrases);

    const vocab = Object.entries(ejercicio.vocab || {});
    if (vocab.length) {
      const bloqueVocab = bloqueMemoria("Vocabulario");
      const rejilla = crear("div", "memoria__vocab");
      vocab.sort((a, b) => a[0].localeCompare(b[0], "es"));
      vocab.forEach(([letra, texto]) => {
        const item = crear("div", "memoria__vocab-item");
        item.append(crear("strong", null, letra), document.createTextNode(texto));
        rejilla.append(item);
      });
      bloqueVocab.append(rejilla);
      memoriaDetalle.append(bloqueVocab);
    }

    const lineas = ejercicio.lineas || [];
    const bloquePrueba = bloqueMemoria("Deducción");
    if (lineas.length) {
      const prueba = crear("div", "prueba");
      const contenedor = crear("div", "prueba__lineas");
      pintarPrueba(lineas, contenedor, false);
      prueba.append(contenedor);
      bloquePrueba.append(prueba);
    } else {
      bloquePrueba.append(crear("p", "memoria__vacio",
        "Este registro no tiene la prueba guardada."));
    }
    memoriaDetalle.append(bloquePrueba);

    const conExplicacion = lineas.filter((ln) => ln.explanation);
    if (conExplicacion.length) {
      const bloquePasos = bloqueMemoria("Explicación de los pasos");
      const pasos = crear("div", "memoria__pasos");
      conExplicacion.forEach((ln) => {
        const detalle = crear("details", "memoria__paso");
        const resumen = crear("summary");
        resumen.append(
          crear("strong", null, String(ln.n) + "."),
          document.createTextNode(" " + ln.formula + " — " + ln.label +
            (ln.citation ? " " + ln.citation : ""))
        );
        detalle.append(resumen, crear("p", null, ln.explanation));
        pasos.append(detalle);
      });
      bloquePasos.append(pasos);
      memoriaDetalle.append(bloquePasos);
    }

    if (ejercicio.plain) {
      const bloqueTexto = bloqueMemoria("Texto de la deducción");
      const pre = crear("pre", "memoria__plain", ejercicio.plain);
      bloqueTexto.append(pre);
      memoriaDetalle.append(bloqueTexto);
    }

    const acciones = crear("div", "memoria__acciones");
    const cargar = crear("button", "memoria__cargar", "Cargar en el editor");
    cargar.type = "button";
    cargar.addEventListener("click", () => cargarEjercicioEnEditor(ejercicio));
    acciones.append(cargar);
    memoriaDetalle.append(acciones);
  }

  function renderDetalleFrase(frase, esBanco = false) {
    memoriaDetalle.textContent = "";
    memoriaDetalle.append(crear("h3", null,
      tituloMemoria(frase.texto) || "Frase guardada"));
    memoriaDetalle.append(crear("p", "memoria__detalle-meta",
      "Fórmula: " + (frase.formula || "") +
      (frase.usos > 1 ? " · " + frase.usos + " veces" : "") +
      (frase.actualizado ? " · " + fechaMemoria(frase.actualizado) : "")));
    memoriaDetalle.append(crear("p", "memoria__vacio",
      esBanco
        ? "Esta frase se guardó automáticamente al formalizarla. Puedes " +
          "cargarla en el editor para corregirla o deducir el ejercicio."
        : "Esta frase se guardó antes de que la memoria almacenara " +
          "ejercicios completos. Vuelve a deducirla para ver aquí su prueba."));

    const bloqueVocab = bloqueMemoria("Vocabulario");
    const vocab = Object.entries(frase.vocab || {});
    if (vocab.length) {
      const rejilla = crear("div", "memoria__vocab");
      vocab.sort((a, b) => a[0].localeCompare(b[0], "es"));
      vocab.forEach(([letra, texto]) => {
        const item = crear("div", "memoria__vocab-item");
        item.append(crear("strong", null, letra), document.createTextNode(texto));
        rejilla.append(item);
      });
      bloqueVocab.append(rejilla);
    } else {
      bloqueVocab.append(crear("p", "memoria__vacio", "Sin vocabulario guardado."));
    }
    memoriaDetalle.append(bloqueVocab);

    const acciones = crear("div", "memoria__acciones");
    const cargar = crear("button", "memoria__cargar", "Cargar frase en el editor");
    cargar.type = "button";
    cargar.addEventListener("click", () => {
      area.value = frase.texto || "";
      guardarBorrador();
      if (menuMemoriaControl) menuMemoriaControl.cerrar();
      area.focus();
      $("#entrada").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    acciones.append(cargar);
    memoriaDetalle.append(acciones);
  }

  function cargarEjercicioEnEditor(ejercicio) {
    const frases = ejercicio.frases || [];
    const lineas = frases.map((frase, indice) => {
      let texto = String(frase.text || "").trim();
      if (indice === frases.length - 1 && !texto.startsWith("=>")) {
        texto = "=> " + tituloMemoria(texto);
      }
      return texto;
    });
    estado.calculo = ejercicio.calculus === "pred" ? "pred" : "prop";
    fijarCalculo(estado.calculo);
    area.value = lineas.join("\n");
    guardarBorrador();
    if (menuMemoriaControl) menuMemoriaControl.cerrar();
    area.focus();
    $("#entrada").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (btnVerMemoria) {
    menuMemoriaControl = configurarMenuLateral({
      menu: $("#menu-memoria"),
      boton: btnVerMemoria,
      botonCerrar: $("#btn-cerrar-memoria")
    });
    btnVerMemoria.addEventListener("click", () => cargarMemoria());
  }
  if (btnRecargarMemoria) {
    btnRecargarMemoria.addEventListener("click", () => cargarMemoria(true));
  }

  /* ------------------------------------------------------------------ */
  /* Tablas de verdad                                                   */
  /* ------------------------------------------------------------------ */
  const btnVerdad = $("#btn-verdad");
  const formVerdad = $("#verdad-form");
  const campoVerdad = $("#verdad-formula");
  const avisoVerdad = $("#verdad-aviso");
  const resultadoVerdad = $("#verdad-resultado");
  const btnCalcularVerdad = $("#btn-calcular-verdad");
  let menuVerdadControl = null;

  function avisoVerdadTexto(texto) {
    if (!avisoVerdad) return;
    avisoVerdad.textContent = texto || "";
    avisoVerdad.hidden = !texto;
  }

  function ponerCargandoVerdad(activo) {
    if (!btnCalcularVerdad) return;
    btnCalcularVerdad.disabled = activo;
    const texto = btnCalcularVerdad.querySelector(".verdad__calcular-texto");
    const cargando = btnCalcularVerdad.querySelector(
      ".verdad__calcular-cargando");
    if (texto) texto.hidden = activo;
    if (cargando) cargando.hidden = !activo;
  }

  function usarConclusionActual(mostrarError = true) {
    if (estado.items && estado.items.length) {
      const conclusion = estado.items[estado.items.length - 1];
      if (conclusion && conclusion.formula) {
        campoVerdad.value = conclusion.formula;
        avisoVerdadTexto("");
        return true;
      }
    }
    if (mostrarError) {
      avisoVerdadTexto("Primero formaliza un ejercicio para poder usar su " +
        "conclusión. También puedes escribir una fórmula a mano.");
    }
    return false;
  }

  function celdaValor(valor) {
    const celda = crear("td");
    const caja = crear("span", "verdad__valor " +
      (valor ? "verdad__valor--v" : "verdad__valor--f"), valor ? "V" : "F");
    celda.append(caja);
    return celda;
  }

  function renderTablaVerdad(datos) {
    resultadoVerdad.textContent = "";
    const resumen = crear("div", "verdad__resumen");
    resumen.append(crear("code", "verdad__formula", datos.formula));
    const etiquetas = {
      tautologia: "Tautología",
      contradiccion: "Contradicción",
      contingente: "Contingente",
    };
    resumen.append(crear("span", "verdad__badge verdad__badge--" +
      datos.clasificacion, etiquetas[datos.clasificacion] ||
      datos.clasificacion));
    resultadoVerdad.append(resumen);

    const variables = datos.variables || [];
    const filas = datos.filas || [];
    resultadoVerdad.append(crear("p", "verdad__detalle",
      datos.resumen + " " + variables.length +
      (variables.length === 1 ? " variable" : " variables") + " · " +
      filas.length + (filas.length === 1 ? " fila" : " filas") + "."));

    const scroll = crear("div", "verdad__tabla-scroll");
    const tabla = crear("table", "verdad__tabla");
    tabla.setAttribute("aria-label", "Tabla de verdad de " + datos.formula);
    const cabecera = document.createElement("thead");
    const filaCabecera = document.createElement("tr");
    variables.forEach((variable) => {
      const th = crear("th", null, variable);
      th.scope = "col";
      filaCabecera.append(th);
    });
    const thResultado = crear("th", null, datos.formula);
    thResultado.scope = "col";
    filaCabecera.append(thResultado);
    cabecera.append(filaCabecera);
    tabla.append(cabecera);

    const cuerpo = document.createElement("tbody");
    filas.forEach((fila) => {
      const tr = document.createElement("tr");
      (fila.valores || []).forEach((valor) => tr.append(celdaValor(valor)));
      tr.append(celdaValor(fila.resultado));
      cuerpo.append(tr);
    });
    tabla.append(cuerpo);
    scroll.append(tabla);
    resultadoVerdad.append(scroll);
  }

  async function calcularTablaVerdad(evento) {
    if (evento) evento.preventDefault();
    const formula = campoVerdad.value.trim();
    if (!formula) {
      avisoVerdadTexto("Escribe una fórmula para generar su tabla de verdad.");
      campoVerdad.focus();
      return;
    }
    avisoVerdadTexto("");
    ponerCargandoVerdad(true);
    try {
      const respuesta = await fetch("/api/tabla-verdad", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ formula })
      });
      const datos = await respuesta.json();
      if (!datos.ok) throw new Error(datos.error || "No se pudo generar la tabla.");
      localStorage.setItem("logica.verdad.formula", formula);
      renderTablaVerdad(datos);
    } catch (error) {
      avisoVerdadTexto(error.message || "No se ha podido generar la tabla.");
    } finally {
      ponerCargandoVerdad(false);
    }
  }

  if (formVerdad) {
    formVerdad.addEventListener("submit", calcularTablaVerdad);
  }
  $$(".verdad__chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (!campoVerdad) return;
      campoVerdad.value = chip.dataset.formula || "";
      avisoVerdadTexto("");
      campoVerdad.focus();
    });
  });
  const btnVerdadConclusion = $("#btn-verdad-conclusion");
  if (btnVerdadConclusion) {
    btnVerdadConclusion.addEventListener("click", () => {
      if (usarConclusionActual()) campoVerdad.focus();
    });
  }
  if (btnVerdad) {
    menuVerdadControl = configurarMenuLateral({
      menu: $("#menu-verdad"),
      boton: btnVerdad,
      botonCerrar: $("#btn-cerrar-verdad")
    });
    btnVerdad.addEventListener("click", () => {
      avisoVerdadTexto("");
      if (campoVerdad && !campoVerdad.value.trim()) {
        if (!usarConclusionActual(false)) {
          const guardada = localStorage.getItem("logica.verdad.formula");
          if (guardada) campoVerdad.value = guardada;
        }
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Resplandor RGB que sigue al ratón                                  */
  /* ------------------------------------------------------------------ */
  const resplandor = $("#cursor-glow");
  const punteroFino = window.matchMedia("(pointer: fine)");
  const punteroGrueso = window.matchMedia("(any-pointer: coarse)");
  if (resplandor && punteroFino.matches && !punteroGrueso.matches) {
    let visible = false;

    document.addEventListener("pointermove", (evento) => {
      // En pantallas táctiles no se hace nada.
      if (evento.pointerType && evento.pointerType !== "mouse") return;
      resplandor.style.setProperty("--mx", evento.clientX + "px");
      resplandor.style.setProperty("--my", evento.clientY + "px");
      if (!visible) {
        visible = true;
        resplandor.classList.add("cursor-glow--activo");
      }
    }, { passive: true });

    document.addEventListener("pointerleave", () => {
      visible = false;
      resplandor.classList.remove("cursor-glow--activo");
    });
    window.addEventListener("blur", () => {
      visible = false;
      resplandor.classList.remove("cursor-glow--activo");
    });
  }

  /* ------------------------------------------------------------------ */
  /* A.E. con la clave del navegador                                    */
  /* ------------------------------------------------------------------ */
  function configurarProveedorIA() {
    const url = $("#ia-url");
    const modelo = $("#ia-modelo");
    const clave = $("#ia-clave");
    const estadoLocal = $("#estado-ia-local");
    const btnGuardar = $("#btn-guardar-ia");
    const btnBorrar = $("#btn-borrar-ia");
    if (!url || !modelo || !clave || !estadoLocal) return;

    function pintarEstado(mensaje) {
      const proveedor = leerProveedorIA();
      if (mensaje) {
        estadoLocal.textContent = mensaje;
        return;
      }
      estadoLocal.textContent = proveedor
        ? "A.E. usará tu clave con el modelo " + proveedor.model +
          ". Se guarda sólo en este navegador."
        : "Ahora mismo A.E. usa la configuración del servidor.";
    }

    function rellenar() {
      const proveedor = leerProveedorIA();
      url.value = proveedor ? proveedor.url : "";
      modelo.value = proveedor ? proveedor.model : "";
      clave.value = proveedor ? proveedor.key : "";
      pintarEstado("");
    }

    btnGuardar?.addEventListener("click", () => {
      const datos = {
        url: url.value.trim(),
        model: modelo.value.trim(),
        key: clave.value.trim(),
      };
      if (!datos.url || !datos.model) {
        pintarEstado("Escribe la dirección y el modelo del servicio.");
        return;
      }
      try {
        localStorage.setItem(CLAVE_IA_LOCAL, JSON.stringify(datos));
      } catch (error) {
        pintarEstado("El navegador no permite guardar la configuración.");
        return;
      }
      pintarEstado("Guardado. La próxima consulta de A.E. usará tu clave.");
      actualizarAprendizaje();
    });

    btnBorrar?.addEventListener("click", () => {
      try {
        localStorage.removeItem(CLAVE_IA_LOCAL);
      } catch (error) {
        /* sin almacenamiento: no hay nada que borrar */
      }
      rellenar();
      pintarEstado("Configuración borrada. A.E. vuelve a la del servidor.");
      actualizarAprendizaje();
    });

    rellenar();
  }

  /* ------------------------------------------------------------------ */
  /* Instalación como aplicación (PWA)                                  */
  /* ------------------------------------------------------------------ */
  function configurarInstalacion() {
    const boton = $("#btn-instalar-app");
    const avisoInstalar = $("#aviso-instalar");
    if (!boton) return;

    const instalada =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;
    if (!instalada) boton.hidden = false;

    let prompt = null;
    window.addEventListener("beforeinstallprompt", (evento) => {
      evento.preventDefault();
      prompt = evento;
      boton.hidden = false;
    });
    window.addEventListener("appinstalled", () => {
      boton.hidden = true;
      if (avisoInstalar) avisoInstalar.hidden = true;
    });

    boton.addEventListener("click", async () => {
      if (prompt) {
        prompt.prompt();
        try {
          await prompt.userChoice;
        } catch (error) {
          /* el navegador puede cancelar el diálogo */
        }
        prompt = null;
        boton.hidden = true;
        return;
      }
      if (avisoInstalar) {
        avisoInstalar.hidden = false;
        avisoInstalar.textContent =
          "Para instalarla, usa el icono de instalar de la barra de " +
          "direcciones (Chrome o Edge). En iPhone o iPad, pulsa Compartir " +
          "y después «Añadir a pantalla de inicio».";
      }
    });
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        /* sin service worker la web sigue funcionando */
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* Arranque                                                           */
  /* ------------------------------------------------------------------ */
  configurarProveedorIA();
  configurarInstalacion();
  restaurarBorrador();
  if (!area.value) {
    area.value = EJEMPLOS.corro.texto;
  }
  fijarCalculo(estado.calculo);
  actualizarAprendizaje();
})();

# Lógica — vocabulario, formalización y deducción formal

Programa que toma un conjunto de frases por teclado, construye el vocabulario
empezando por la letra `p`, propone la formalización y obtiene la deducción
formal siguiendo las reglas de la colección de fórmulas del curso.

**Versión actual: 2.1.1.** La web la muestra al pie, dentro de un rectángulo
negro con el texto en degradado rojo, naranja y morado.

Las reglas y la notación están tomadas de:

- *LOGICA — Reglas de Cálculo de Proposiciones* (Colección de Fórmulas
  utilizables en los exámenes)
- *LOGICA — Reglas de Cálculo de Predicados* (misma colección)
- *Resolución Examen Ordinario 22* (ejemplos de formato)
- *Resumen de Lógica* (formalización de la lengua, semántica)
- *Apuntes de Lógica* de 114 páginas (precedencia de conectivas,
  observación 1.4.2)
- *Lógica simbólica para informáticos*, de Pascual (definiciones del curso)

---

## Cómo se usa

```bash
cd "/Users/victortoledotorrico/Library/CloudStorage/OneDrive-UniversidaddeCastilla-LaMancha/Ingeniería Informatica/2º Curso/1º Cuatrimestre/Lógica/Academia/logica"

python3 main.py          # cálculo de proposiciones
python3 main.py --pred   # cálculo de predicados
python3 main.py --auto   # acepta la formalización propuesta sin preguntar
python3 main.py --examen # deducción en el formato compacto del examen
```

Por defecto la deducción se escribe con la notación del libro (⌈ | ⌊ para las
subdemostraciones y citas como `MP 1,3`). Con `--examen` se usa el formato
compacto de la resolución del examen (`Simp2(3)`, `QED`).

No hace falta instalar nada: sólo Python 3.

### El flujo

1. **Las frases.** Se escriben una en cada línea. La conclusión se marca con
   `=>` delante:

   ```
   > Un cuerpo indestructible existe si Dios puede y quiere crearlo.
   > Si Dios es todopoderoso, entonces no existe un cuerpo que sea indestructible.
   > Dios es todopoderoso y si quiere crear un cuerpo indestructible, puede hacerlo.
   > => Por consiguiente, no es el caso de que Dios quiera crear un cuerpo indestructible.
   >                    (línea vacía para terminar)
   ```

   No hace falta escribir `=>` a mano: si una oración empieza por «Por tanto»,
   «Por consiguiente», «Por conclusión», «En consecuencia», «Así que»…, la web
   la reconoce como conclusión y añade `=>` automáticamente al salir del
   cuadro de texto. El programa de terminal también acepta esos marcadores.

2. **La formalización propuesta.** El programa la enseña y pregunta por cada
   línea si es correcta. Con `m` se escribe a mano.

   Al escribirla a mano se usa la notación del curso:

   | Símbolo | Significado | Cómo se escribe |
   |---|---|---|
   | `¬` | negación | `¬p` |
   | `∧` | conjunción | `p ∧ q` |
   | `∨` | disyunción | `p ∨ q` |
   | `→` | implicación | `p → q` |
   | `↔` | coimplicación | `p ↔ q` |
   | `(Λx)` | generalizador (todos) | `(Λx)C(x)` |
   | `(Vx)` | particularizador (algunos) | `(Vx)C(x)` |

   La precedencia es la de los apuntes (observación 1.4.2): `¬` liga más;
   después `∧` y `∨`, que están al mismo nivel; y después `→` y `↔`, también
   al mismo nivel. Por eso `p→q∧r` es `p→(q∧r)`, pero al mezclar `∧` con `∨`
   o `→` con `↔` hay que escribir paréntesis: `(p∧q)∨r`, `p→(q→r)`.

3. **El vocabulario.** Se pide la descripción de cada letra; el programa
   ofrece una sugerencia y basta con pulsar Enter para aceptarla.

4. **La deducción.** Se imprime con las líneas numeradas y la regla aplicada
   a cada paso, con la notación del libro (`−` premisa, `⌈` supuesto, `|`
   línea auxiliar, `⌊` cierre):

   ```
   DEDUCCIÓN
   ----------------------------------------------------------------------
   − (1) q∧r→p
   − (2) s→¬p
   − (3) s∧(r→q)
     (4) r→q                      Simp2 3
     (5) ¬r∨q                     DI2 4
     (6) ¬p                       MP 3,2
     (7) ¬q∨¬r                    MT 1,6
     (8) ¬r                       SD 5,7

   QED
   ```

   Una implicación se demuestra como en el libro: se abre una subdemostración
   con el antecedente y se cierra con `TD`:

   ```
   − (1) p∧q→r
   − (2) r→s
   ⌈ (3) p∧q
   | (4) r                        MP 1,3
   ⌊ (5) s                        MP 2,4
     (6) p∧q→s                    TD 3-5
   ```

---

## Versión web

La misma aplicación se puede usar desde el navegador, sin instalar nada. Por
defecto el servidor se ejecuta en tu ordenador y sólo escucha en la red local;
no envía las frases a ningún servicio externo.

```bash
python3 web/server.py             # http://localhost:8000
python3 web/server.py --port 9000 # otro puerto
```

Al arrancar, la terminal muestra dos direcciones:

```
En este ordenador:  http://localhost:8000
Desde otro equipo:  http://192.168.x.x:8000
```

Para abrirla desde el móvil o la tablet, conéctate a la **misma red WiFi** y
usa la segunda dirección. Si macOS pregunta si permites conexiones entrantes,
acepta.

La página sigue el mismo flujo que el programa de terminal:

1. **Escribe** una frase por línea (o varias en la misma línea, separadas por
   puntos) y marca la conclusión con `=>`.
2. **Revisa** la formalización propuesta. Cada fórmula se puede corregir
   directamente; también se puede cambiar el texto del vocabulario. Antes de
   las fórmulas aparece siempre el **alfabeto del ejercicio**: las letras
   usadas y la siguiente libre. Se empieza en `p` y se sigue el abecedario
   (`q, r, s, t, u, v, w, x, y, z`); si se agotan, continúa con `aa`, `ab`…,
   de modo que nunca se mezclan dos premisas en una sola letra. El botón
   **«Editar las frases»** vuelve al paso 1 sin borrar nada.
3. **Deduce**: la prueba aparece con la notación del libro, se puede copiar o
   descargar, y debajo está la explicación de cada línea y de la regla usada.

Incluye ejemplos de un clic (incluidos los dos ejercicios del examen), guarda
el último borrador en el navegador y funciona en pantallas de móvil.

### Buscador

Justo debajo de la cabecera hay una **lupa** para buscar a la vez en las
definiciones y en la guía de teoría. Los resultados se agrupan por tipo y
muestran el capítulo al que pertenecen. Al pulsar uno, se abre el menú
correspondiente y se resalta el apartado encontrado. También se puede navegar
con las flechas `↑` `↓`, abrir con `Enter` y cerrar con `Esc`.

### Guía de teoría

El botón **«Teoría»** de la izquierda abre un menú secundario con una guía
completa para preparar los ejercicios. Incluye:

- las cinco conectivas, su símbolo, sus palabras típicas y su tabla de verdad;
- un diccionario de frases a fórmulas: negación, conjunción, disyunción,
  condicionales, bicondicionales, «a menos que», «sólo si», etc.;
- el listado completo de formas de `resumen_logica_bueno.pdf`, con ejemplos
  como «p o q», «si p entonces q», «p pero q» o «p sólo si q», y la fórmula
  correspondiente a cada una;
- cuantificadores y las fórmulas habituales de «todos», «alguno», «ninguno»
  y «sólo los»;
- precedencia, paréntesis y ejemplos de fórmulas ambiguas;
- las reglas de deducción natural con los nombres del curso;
- estrategias de prueba, errores frecuentes y una lista de comprobación;
- un ejercicio de deducción resuelto y el ejemplo de predicados de los loros.

Se cierra con el botón **«Cerrar»**, con **Escape** o con el botón
**«Volver a la aplicación»**. El fondo usa el mismo degradado rojo, naranja y
morado de la cabecera, en una versión más clara.

### Definiciones

El botón **«Definiciones»** de la izquierda abre un segundo menú secundario,
con estética roja y naranja, que reúne las definiciones literales de los
*Apuntes de Lógica* de 114 páginas y del libro *Lógica simbólica para
informáticos*, de Pascual. Las definiciones que aparecen en ambos documentos se
muestran una sola vez. No se han reescrito: se conserva la redacción original y
solo se normalizan acentos y símbolos tipográficos.

Está organizado por capítulos, con índice interno:

- argumentos, enunciados y principio de bivalencia;
- formas enunciativas, grado, atribución veritativa, valoración, tautología,
  contradicción, contingencia y conjuntos adecuados de conectivas;
- formas argumentativas y consecuencia lógica;
- sistemas formales, deducción, demostración, consistencia, decidibilidad y
  equivalencia demostrable;
- deducción natural, reglas básicas y reglas derivadas;
- sintaxis de predicados: términos, fórmulas atómicas, fbf, cuantificadores y
  fórmulas cerradas o abiertas;
- semántica de predicados: interpretaciones, valoraciones, satisfacibilidad,
  verdad, modelos, consecuencia lógica e independencia;
- sistema KL, tautologías en KL y sustituciones.

Cada definición lleva su nombre en negrita y con un tamaño ligeramente mayor
que el texto. El menú se cierra igual que el de teoría: con **«Cerrar»**, con
**Escape**, pulsando fuera del panel o con **«Volver a la aplicación»**.

### Tablas de verdad

El botón **«Tablas de verdad»** de la derecha abre una herramienta con paleta
verde y azul para calcular la tabla de una fórmula de enunciados. Se puede
escribir con la notación del curso (`¬`, `∧`, `∨`, `→`, `↔`) o con la notación
habitual de programación (`!`, `&`, `|`, `->`, `<->`).

La tabla muestra todas las combinaciones de las variables (V/F), el valor de
la fórmula en cada fila y su clasificación semántica:

- **Tautología**: verdadera en todas las filas.
- **Contradicción**: falsa en todas las filas.
- **Contingente**: verdadera en unas filas y falsa en otras.

Incluye ejemplos rápidos y un botón para usar como fórmula la conclusión del
ejercicio que se acaba de formalizar.

### Dictado por voz

Junto al cuadro de texto hay un botón **«Dictar»**. Al pulsarlo, el navegador
pide permiso para usar el micrófono y va añadiendo una línea por cada frase
que reconoce; al terminar, pulsa **«Detener»**. Las frases se añaden en
lenguaje natural (no hace falta decir símbolos como `∧`): el analizador se
encarga de las conectivas.

El dictado usa la API de reconocimiento de voz del propio navegador, así que
no añade dependencias al servidor. Limitaciones:

- Funciona mejor en **Chrome o Edge**; Firefox no lo incluye. Safari puede
  ofrecer una versión parcial.
- Necesita **permiso de micrófono** y un contexto seguro: `localhost` o
  HTTPS. Si abres la web desde el móvil con `http://192.168.x.x:8000`, es
  posible que el navegador bloquee el micrófono.
- Según el navegador, el audio puede enviarse al proveedor de reconocimiento
  (por ejemplo, Google en Chrome), no a este servidor. No dictes datos que no
  quieras compartir.
- Revisa siempre el texto reconocido: puede confundir palabras o cortar una
  frase al hacer una pausa.

### Aprendizaje y banco de frases

Cada frase que se formaliza se guarda automáticamente en el **banco de
frases** de `aprendizaje.json`, aunque la deducción no llegue a completarse.
Además, cada ejercicio que se deduce bien se guarda completo. La próxima vez:

- Si la frase es **exacta**, se recupera su fórmula (aparece marcada como
  «aprendida»).
- Si se parece a una frase ya confirmada, se imita su **plantilla**: se
  sustituyen los enunciados por huecos y se conservan las palabras conectivas.
  Por ejemplo, de «En tanto llueva, me mojo» con fórmula `p→q` se aprende la
  plantilla `en tanto §, §`, que sirve para «En tanto nieva, me abrigo».

El botón **«Ver memoria de frases»**, situado al final de la página, abre un
menú con el banco de frases y los ejercicios guardados. Al pulsar en una frase
se muestra su fórmula y su vocabulario; al pulsar en un ejercicio se muestra
su formalización, su vocabulario, la prueba línea a línea, la explicación de
cada paso y el texto de la deducción. Desde ahí también se puede cargar en el
editor para repetirlo.

Los ejercicios que se guardaron antes de existir esta memoria completa sólo
tenían frases sueltas. La aplicación los agrupa por el momento en que se
dedujeron y reconstruye su deducción a partir de las fórmulas guardadas cuando
es posible; aparecen marcados como «Recuperado».

La memoria es local cuando se ejecuta en tu ordenador. En la versión pública
de Render es compartida entre los visitantes del servicio y se guarda en el
almacenamiento efímero de la instancia: se conserva mientras el servicio no se
redespliegue ni se reinicie. Para conservarla de forma permanente hace falta un
disco persistente o una base de datos externa. Se puede borrar desde la
terminal:

```bash
python3 main.py --olvidar        # borra las frases recordadas
python3 main.py --sin-aprender   # usa el programa sin memoria
```

Si quieres guardar la memoria en otro sitio (por ejemplo, para las pruebas):

```bash
LOGICA_APRENDIZAJE_RUTA=/ruta/a/mi_aprendizaje.json python3 main.py
```

La imitación es deliberadamente prudente. Sólo se aprende una plantilla si
hay al menos dos enunciados distintos y quedan palabras conectivas suficientes;
no se generaliza a partir de una simple coma. Aun así, **la fórmula aprendida
se sigue mostrando para que la revises**.

### Conectar con internet: IA + búsqueda web

La aplicación **no navega por su cuenta**. Para que consulte internet hay que
darle un servicio de IA compatible con OpenAI y, si se quiere, activar la
búsqueda web. Todo está desactivado por defecto.

> En este equipo la IA ya está configurada con **Groq** y el modelo
> `openai/gpt-oss-120b`. Los pasos de Google AI Studio que siguen son una
> alternativa si prefieres otra cuenta o proveedor.

#### Opción recomendada: Google AI Studio (tiene nivel gratuito)

1. Entra directamente en <https://aistudio.google.com/apikey>, inicia sesión
   con una cuenta de Google **personal** y crea una clave de API. No hace falta
   tarjeta para el nivel gratuito.
2. Copia el archivo de ejemplo:

   ```bash
   cp web/config_ia.env.example web/config_ia.env
   ```

3. Abre `web/config_ia.env` y rellena los datos:

   ```bash
   LOGICA_IA_URL=https://generativelanguage.googleapis.com/v1beta/openai
   LOGICA_IA_MODEL=gemini-3.8-flash
   LOGICA_IA_KEY=tu-clave-de-Google
   LOGICA_BUSQUEDA=1
   ```

4. Arranca la web con doble clic en `web/iniciar.command` o con:

   ```bash
   python3 web/server.py
   ```

5. En la página, al final de «Reglas de uso rápido», debe aparecer
   **«IA conectada (gemini-3.8-flash) con búsqueda web.»**

Si tu cuenta no tiene ese modelo, cambia `LOGICA_IA_MODEL` por otro que
aparezca en tu panel de Google AI Studio.

#### Qué pasa al escribir un ejercicio

1. Se prueba primero la **memoria local** y el analizador de siempre.
2. Se consulta la IA cuando una frase no se reconoce **o cuando el analizador
   la ha reducido a un átomo aunque contenga conectivas, cuantificadores o
   puntuación que no ha sabido interpretar**. Los átomos simples («Llueve»)
   no disparan la consulta. También puedes pulsar **«Ayuda exterior (A.E.)»** para
   pedir una segunda opinión aunque la formalización local haya funcionado.
3. Si `LOGICA_BUSQUEDA=1`, se busca en **DuckDuckGo** y se recogen títulos y
   resúmenes. En las frases dudosas se combinan los materiales de la UCLM de
   **Pascual Julián Iranzo** con una búsqueda general, para no limitar la
   respuesta a una sola fuente.
4. Esas frases y esos resúmenes se envían al modelo de IA.
5. La respuesta se valida con el analizador de fórmulas del curso.
6. La fórmula aparece marcada como **«A.E.»** (ayuda exterior) para que la revises antes de
   deducir. Si algo falla, se vuelve al funcionamiento local sin romper nada.

La búsqueda sola no resuelve el ejercicio: los resultados son texto libre y
pueden ser de otro ejercicio. El modelo es el que interpreta esos resultados
con las reglas del curso. Si no hay modelo configurado, la búsqueda no se
activa.

#### Otras conexiones compatibles

Cualquier servicio con API compatible con OpenAI sirve. Algunos ejemplos
(consulta precios, límites y nombres de modelo actuales):

| Servicio | `LOGICA_IA_URL` | Modelo de ejemplo |
|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenRouter | `https://openrouter.ai/api/v1` | algún modelo gratuito |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.1` |

Con Ollama no se envía nada a internet: el modelo se ejecuta en tu ordenador.

Si Google AI Studio muestra **«Failed to list projects: permission denied»**,
suele ser porque la cuenta es de la universidad o no tiene proyectos de Google
Cloud. La alternativa más sencilla es Groq: crea una clave en
<https://console.groq.com/keys> y ejecuta el asistente

```bash
./web/configurar_groq.command
```

o haz doble clic en `web/configurar_groq.command`. Pide la clave, la guarda y
reinicia la web.

#### Privacidad y límites

- Si no existe `web/config_ia.env` y no hay variables `LOGICA_IA_*`, **no se
  envía nada a internet**.
- Con la búsqueda activada, las frases se envían a DuckDuckGo; después, las
  frases y los resúmenes se envían al proveedor de IA. No lo actives con datos
  que no quieras compartir.
- La clave se guarda en texto plano en `web/config_ia.env`. Protégela:
  `chmod 600 web/config_ia.env`, y no compartas ni subas esa carpeta.
- Los planes gratuitos tienen límites y los modelos cambian. Si el servicio
  devuelve error, la app sigue funcionando en local.

---

## Abreviaturas de las reglas

Se usan las del profesor en las soluciones del examen.

### Proposiciones

| Abreviatura | Regla |
|---|---|
| `MP` | `A → B , A ⊢ B` (modus ponens) |
| `MT` | `A → B , ¬B ⊢ ¬A` (modus tollens) |
| `Sil` / `SH` | `A → B , B → C ⊢ A → C` (silogismo; en el libro, `SH`) |
| `Simp1` / `Simp2` | `A ∧ B ⊢ A` / `⊢ B` (simplificación) |
| `SD` | `A ∨ B , ¬B ⊢ A` (silogismo disyuntivo, también encadenado) |
| `IC` | `A , B ⊢ A ∧ B` (introducción del conjuntor) |
| `Ad` | `A ⊢ A ∨ B` (adición) |
| `DN` | `¬¬A ⊢ A` (eliminación del negador) |
| `IDN` | `A ⊢ ¬¬A` (introducción del negador) |
| `Cp` | `A → B ⊢ ¬B → ¬A` (contraposición) |
| `DI1` | `A → B ⊢ ¬(A ∧ ¬B)` (definición del implicador 1) |
| `DI2` | `A → B ⊢ ¬A ∨ B` (definición del implicador 2) |
| `DD` | `A ∨ (B ∧ C) ⊢ (A ∨ B) ∧ (A ∨ C)` (distributividad) |
| `IDD` | `A ∨ A ⊢ A` / `A ∧ A ⊢ A` (idempotencia) |
| `DM1` | `¬(A ∧ B) ⊢ ¬A ∨ ¬B` (De Morgan) |
| `DM2` | `¬(A ∨ B) ⊢ ¬A ∧ ¬B` (De Morgan) |
| `Supuesto` | hipótesis de una subdemostración (`⌈`) |
| `TD` | introducción del implicador (teorema de deducción) |
| `Abs` | cierre por contradicción (absorción) |
| `Dil` | dilema / análisis de casos sobre una disyunción |

### Predicados

| Abreviatura | Regla |
|---|---|
| `EG` | `(Λx)P(x) ⊢ P(a)` (eliminación del generalizador) |
| `EP` | `(Vx)P(x) ⊢ P(a)` (eliminación del particularizador) |
| `IP` | `P(a) ⊢ (Vx)P(x)` (introducción del particularizador) |
| `IG` | `P(a) ⊢ (Λx)P(x)` (introducción del generalizador) |

---

## Los archivos

| Archivo | Contenido |
|---|---|
| `main.py` | El programa: entrada, confirmación, vocabulario y salida. |
| `formulas.py` | Fórmulas bien formadas, notación del curso y analizador. |
| `tablas_verdad.py` | Evaluación de fórmulas y generación de tablas de verdad. |
| `prover.py` | Motor de deducción: las reglas y la búsqueda de la prueba. |
| `formalize.py` | Vocabulario desde `p` y análisis de las frases por capas. |
| `aprendizaje.py` | Memoria local: frases confirmadas y plantillas por imitación. |
| `asistente_ia.py` | Conector opcional con una IA compatible con OpenAI. |
| `busqueda.py` | Búsqueda opcional en DuckDuckGo para dar contexto a la IA. |
| `web/config_ia.env.example` | Plantilla para configurar la IA y la búsqueda. |
| `aprendizaje.json` | Datos aprendidos (se crea al primer ejercicio deducido). |
| `test_logica.py` | Batería de pruebas del motor de deducción. |
| `web/server.py` | Servidor web local (sólo biblioteca estándar). |
| `web/static/` | Interfaz: HTML, estilos y JavaScript. |

### Pruebas

```bash
python3 test_logica.py
```

Comprueba 97 ejercicios: modus ponens, tollens, silogismo, simplificación,
adición, silogismo disyuntivo y su versión encadenada, doble negación,
contraposición, De Morgan, definición del implicador, distributividad,
idempotencia, introducción del conjuntor, análisis de casos, tres ejercicios
de examen (incluido el Ordinario 2020 con `DD` e `IDD`), cinco de predicados,
siete del aprendizaje local, uno del lector de resultados de búsqueda,
dieciocho de precedencia, paréntesis y corchetes, seis de confianza del
analizador y dos de variantes verbales y claves de aprendizaje. De ellos, 33
son de formalización: dirección de los condicionales, negaciones, `ni…ni`,
`aunque`, `a menos que`, verbos no registrados, etc.

Incluye además regresiones de **dirección**: comprueba que no se demuestran
cosas que no se siguen (`p → q ⊬ q → p`, `p → q, ¬p ⊬ ¬q`, `¬p ⊬ p`…) y que
la formalización de los condicionales va en el sentido del libro.

Cada prueba verifica tres cosas:

1. que toda línea se apoye sólo en líneas anteriores,
2. que la última línea sea la conclusión,
3. que la conclusión **se siga de verdad** de las premisas, comprobándolo con
   tabla de verdad (en el cálculo de proposiciones).

### Cómo busca la prueba

El motor trabaja en dos fases, igual que se hacen estas deducciones a mano:

1. **Saturación.** A partir de las premisas se calculan por adelantado las
   fórmulas intermedias que se pueden deducir, cada una con su justificación.
   Son las líneas que luego se citan (`Simp₂(3)`, `DI₂(9)`, `MT(6,7)`…).

2. **Deducción.** Se alcanza la conclusión hacia atrás. Si la meta no sale con
   una sola regla, se abre una subdemostración: la conjunción se separa en
   dos metas, la disyunción en dos ramas, la implicación se demuestra
   suponiendo el antecedente.

Un detalle importante: **todas las fórmulas se normalizan a forma normal de
negación** antes de guardarlas. Sin esa normalización, la contraposición y la
definición del implicador encadenan negaciones sin fin (`¬¬¬¬¬r`) y la
búsqueda se desborda; normalizadas, esas cadenas se reducen a fórmulas que ya
existen y la saturación se cierra.

---

## Ejemplos comprobados

Los dos ejemplos de la *Resolución Examen Ordinario 22* están reproducidos en
`ejemplos/`:

- `ejemplos/proposiciones.txt` — el de la página 1
- `ejemplos/predicados.txt` — el de la página 4

```bash
python3 main.py < ejemplos/proposiciones.txt
python3 main.py --pred < ejemplos/predicados.txt
```

La deducción que sale del ejemplo de predicados coincide con la del profesor
(en formato de libro):

```
− (1) (Λx)(¬C(x)→D(x)∨T(x))
− (2) (Λx)(T(x)→G(x))
− (3) (Vx)¬G(x)
  (4) ¬C(a)→D(a)∨T(a)          EG 1
  (5) C(a)∨(D(a)∨T(a))         DI2 4
  (6) T(a)→G(a)                EG 2
  (7) ¬G(a)                    EP 3
  (8) ¬T(a)                    MT 6,7
  (9) C(a)∨D(a)                SD 5,8
  (10) (Vx)(C(x)∨D(x))         IP 9
```

---

## La dirección de los condicionales

Es el punto que más se presta a error. El programa lee estas construcciones
como en el libro:

| Enunciado | Formalización |
|---|---|
| `Si A, B` / `Si A entonces B` | `A → B` |
| `A si B` | `B → A` |
| `A sólo si B` | `A → B` |
| `Sólo si A, B` | `B → A` |
| `A a menos que B` | `¬A → B` |
| `Para que A es necesario B` | `A → B` |
| `A es necesario para B` | `B → A` |
| `A es suficiente para B` | `A → B` |
| `A cuando B` / `A siempre que B` | `B → A` |
| `Siempre que A, B` | `A → B` |

Fíjate en la diferencia: **`Llueve si hace frío`** es `q → p` (si hace frío,
llueve), mientras que **`Llueve sólo si hace frío`** es `p → q` (si llueve,
hace frío). El programa ya no las confunde.

---

## Cómo formaliza

La formalización no es una lista de frases hechas: el analizador va partiendo
la oración por capas, de la conectiva más débil a la más fuerte, igual que se
resuelve una fórmula (`↔`, `→`, `∨`, `∧`, `¬`). Para saber dónde acaba una
cláusula usa un léxico de formas verbales y las palabras que suelen abrir una
oración principal (`se`, `no`, `el`, `cuando`…). Además unifica las
conjugaciones de un mismo verbo, de modo que `llueva` y `llueve` cuentan como
el mismo enunciado.

Reconoce, entre otras, estas construcciones:

| Construcción | Formalización |
|---|---|
| `A y B`, `A e B`, `A pero B`, `A aunque B`, `A sin embargo B` | `A ∧ B` |
| `A o B`, `o bien A o B` | `A ∨ B` |
| `Ni A ni B`, `No A ni B` | `¬A ∧ ¬B` |
| `No A`, `Nunca A`, `Jamás A` | `¬A` |
| `No es cierto que A`, `Es falso que A`, `No es verdad que A` | `¬A` |
| `A si y sólo si B`, `A equivale a B` | `A ↔ B` |
| `Si A, B`, `Si A entonces B`, `Siempre que A, B`, `En caso de que A, B` | `A → B` |
| `A si B`, `A cuando B`, `A siempre que B` | `B → A` |
| `A sólo si B` | `A → B` |
| `Sólo si A, B` | `B → A` |
| `A a menos que B`, `A salvo que B`, `A excepto que B` | `¬A → B` |
| `A menos que A, B` | `¬A → B` |
| `Aunque A, B` | `A ∧ B` |
| `Para que A es necesario B` | `A → B` |
| `A es necesario para B` | `B → A` |
| `A es suficiente para B` | `A → B` |
| `Todos los A son B`, `Los A son B`, `Cada A es B` | `(Λx)B(x)` |
| `Ningún A es B` | `(Λx)¬B(x)` |
| `No todos los A son B` | `¬(Λx)B(x)` |
| `Algún A es B`, `Algunos A son B` | `(Vx)B(x)` |
| `Existe un A que B`, `Hay un A que B` | `(Vx)B(x)` |
| `Sólo los A son B` | `(Λx)(B(x) → A(x))` |

Cuando la frase es ambigua, el programa elige la lectura más habitual en los
ejercicios y **siempre enseña la fórmula para que la corrijas**. Si una
palabra no está en el léxico, la trata como parte de un enunciado simple en
vez de inventarse una conectiva.

---

## Lo que el programa NO hace

Conviene tener esto claro antes de usarlo:

- **La formalización automática es una propuesta, no una garantía.** Reconoce
  las conectivas y las construcciones de la tabla anterior, y genera las
  formas regulares de una lista amplia de verbos (además de los irregulares
  habituales). Aun así, el español tiene infinitas variantes: un verbo muy
  poco frecuente o una oración con varias subordinadas puede necesitar una
  lectura que el programa no elige. **Por eso siempre hay que revisar la
  formalización**; si está mal, la deducción tampoco lo estará, y tanto el
  programa como la web permiten corregirla línea a línea.

- **Si la conclusión no se sigue de las premisas, no hay deducción.** Es lo
  correcto, pero conviene recordarlo cuando el programa dice que no ha
  encontrado nada: puede ser que la formalización sea incorrecta.

- **Variante de clase.** Si la formalización literal de una implicación con
  antecedente negado no permite deducir la conclusión, la web prueba a quitar
  esa negación del antecedente (por ejemplo, `¬s→¬t` pasa a `s→¬t`) y, si así
  sale la deducción, la muestra con un aviso y corrige la fórmula en pantalla.
  Es una ayuda para coincidir con la formalización usada en clase, no una
  licencia para cambiar premisas sin que el usuario lo sepa.

- El cálculo de predicados usa un solo término, `x`, y una constante nueva
  (`a`, `b`, …) en las instancias. Es lo suficiente para los ejercicios
  habituales, pero no cubre los casos con varios términos libres.

# Subir la aplicación

Esta carpeta contiene **solo lo necesario** para ejecutar la web.

## Qué hay que subir

Sube el contenido completo de esta carpeta, manteniendo las subcarpetas
`web` y `web/static`.

No subas:

- `aprendizaje.json` (memoria local de tu ordenador; el servidor crea la suya).
- `web/config_ia.env` (puede contener claves privadas).
- `__pycache__`, `.vscode` ni archivos `.DS_Store`.

## Render

1. Crea un repositorio en GitHub y sube el contenido de esta carpeta.
2. En Render: **New → Web Service**, conecta el repositorio.
3. Render leerá `render.yaml` y usará:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python3 web/server.py`
4. `render.yaml` activa el aprendizaje con `LOGICA_APRENDIZAJE=1`. El banco de
   frases se guarda siempre, incluso con `LOGICA_APRENDIZAJE=0`; esa variable
   sólo controla la reutilización automática de fórmulas. Ten en cuenta que
   todos los visitantes comparten el mismo archivo y que, en el plan gratuito,
   Render puede borrarlo al reiniciar o redesplegar. Para conservarlo hace
   falta un disco persistente o una base de datos externa.
5. Pulsa **Deploy**. La dirección será parecida a
   `https://logica-deduccion.onrender.com`.

## Activar la ayuda exterior (A.E.)

La ayuda exterior funciona **sin configurar nada**: si no hay proveedor, se
usa el servicio gratuito `text.pollinations.ai` (modelo `openai-fast`), que no
necesita clave. Tiene un límite de una petición cada 30 segundos por IP.

Para desactivarla por completo, define `LOGICA_IA_FALLBACK=0`. Para tener más
fiabilidad y sin ese límite, configura un proveedor propio en **Environment**
del servicio de Render.

Con una cuenta de Groq (nivel gratuito), añade:

| Variable | Valor |
| --- | --- |
| `LOGICA_IA_URL` | `https://api.groq.com/openai/v1` |
| `LOGICA_IA_MODEL` | `openai/gpt-oss-120b` |
| `LOGICA_IA_KEY` | tu clave de Groq |
| `LOGICA_BUSQUEDA` | `1` (opcional, para buscar antes en internet) |

Con Google AI Studio, usa
`https://generativelanguage.googleapis.com/v1beta/openai` y el modelo que
tengas disponible.

No pongas la clave en `render.yaml` ni en el repositorio: es público. Guárdala
sólo en las variables de entorno de Render. Después de añadirla, pulsa
**Manual Deploy**. Si la clave funciona, el pie de la página mostrará
«Ayuda exterior (A.E.) conectada».

También puedes usar tu clave sin tocar Render: en el paso 2 de la web, abre
«A.E. con tu propia clave», escribe la dirección, el modelo y la clave, y
pulsa **Guardar**. Se guarda sólo en el navegador y viaja con cada consulta;
el servidor no la escribe en disco ni la incluye en sus registros. El botón
**Quitar** borra esa configuración y vuelve a la del servidor.

Con la ayuda exterior activa, si una formalización no permite encontrar la
deducción, la web consulta al modelo una formalización alternativa. La
propuesta se comprueba con el motor local antes de mostrarla y las fórmulas
corregidas aparecen marcadas como «A.E.».

El plan gratuito de Render duerme la aplicación tras unos minutos sin uso;
la primera visita después puede tardar en despertar.

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

El plan gratuito de Render duerme la aplicación tras unos minutos sin uso;
la primera visita después puede tardar en despertar.

# Subir la aplicación

Esta carpeta contiene **solo lo necesario** para ejecutar la web.

## Qué hay que subir

Sube el contenido completo de esta carpeta, manteniendo las subcarpetas
`web` y `web/static`.

No subas:

- `aprendizaje.json` (memoria local; además no debe compartirse entre visitantes).
- `web/config_ia.env` (puede contener claves privadas).
- `__pycache__`, `.vscode` ni archivos `.DS_Store`.

## Render

1. Crea un repositorio en GitHub y sube el contenido de esta carpeta.
2. En Render: **New → Web Service**, conecta el repositorio.
3. Render leerá `render.yaml` y usará:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python3 web/server.py`
4. La variable `LOGICA_APRENDIZAJE=0` desactiva la memoria compartida. Si
   quieres activarla, cámbiala a `1`, pero ten en cuenta que todos los
   visitantes compartirán el mismo archivo y que Render puede borrarlo al
   reiniciar.
5. Pulsa **Deploy**. La dirección será parecida a
   `https://logica-deduccion.onrender.com`.

El plan gratuito de Render duerme la aplicación tras unos minutos sin uso;
la primera visita después puede tardar en despertar.

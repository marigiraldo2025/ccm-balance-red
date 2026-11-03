# CCM Televisión – Balance de la red de fibra óptica

Aplicación para explorar el modelo de optimización (método ε-constraint) que propone
qué cajas NAP cambiar de puerto PON para repartir mejor la carga de la red.

## Cómo abrirla

### Opción fácil (Windows)
1. Instale Python 3.10 o superior desde https://www.python.org (marque la casilla
   "Add Python to PATH" durante la instalación).
2. Haga doble clic en **Iniciar_aplicacion.bat**.
   La primera vez instala lo necesario (tarda unos minutos); luego se abre el navegador.

### Opción fácil (Mac / Linux)
1. Instale Python 3.10 o superior.
2. Abra una terminal en esta carpeta y ejecute: `sh iniciar_aplicacion.sh`

### Opción manual
```
pip install -r requirements.txt
streamlit run app.py
```

## Archivos
- `app.py` – la aplicación (interfaz, gráficas y textos).
- `modelo.py` – el modelo de optimización (mismo modelo del proyecto, en funciones).
- `base_modelo_olt.csv` – base de datos limpia de usuarios.
- `logo_ccm.png` – logo de la empresa.
- `resultados_guardados/` – cálculos ya hechos; si se repiten los mismos parámetros,
  los resultados aparecen al instante.
- `precalcular.py` – opcional: vuelve a calcular y guardar los niveles por defecto
  (`python precalcular.py Detallado`).
- `.streamlit/config.toml` – colores institucionales de la app.

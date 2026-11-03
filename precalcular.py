"""Calcula y guarda los resultados de los tres niveles con los parámetros por defecto,
para que la aplicación los muestre al instante."""
import pickle, sys, time
from pathlib import Path
import modelo

AQUI = Path(__file__).parent
df = modelo.cargar_datos(AQUI / "base_modelo_olt.csv")
niveles = sys.argv[1:] or list(modelo.NIVELES)
for nivel in niveles:
    cfg = {k: v for k, v in modelo.NIVELES[nivel].items() if k != "texto"}
    p = modelo.Parametros(**cfg)
    t = time.time()
    r = modelo.ejecutar(df, p, lambda f, m: print(f"[{nivel}] {f:.0%} {m}", flush=True))
    destino = AQUI / "resultados_guardados" / modelo.nombre_archivo(p)
    pickle.dump(r, open(destino, "wb"))
    print(f"[{nivel}] guardado en {destino.name} ({time.time() - t:.0f} s)", flush=True)

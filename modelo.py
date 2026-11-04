"""
Motor de optimización CCM - Balance de la red GPON.

Es el mismo modelo epsilon-constraint del proyecto (gpon_econstraintfinal.py),
reorganizado en funciones para que la aplicación pueda cambiar los parámetros
y mostrar el avance del cálculo.

    min  U  (+ pequeños desempates por cruces de barrio y por NAPs movidas)
    s.a. U >= carga del puerto j / capacidad           para cada puerto j
         cada NAP queda en exactamente un puerto
         clientes del puerto j <= máximo de clientes
         cruces de barrio      <= eps2   (se barre)
         NAPs movidas          <= eps5   (se barre)
         clientes con PRO débil <= los que hay hoy
         asignaciones con PRO estimada < PRO mínima: prohibidas
"""

import time
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix

DELTA = 2e-4        # desempate: con igual U, menos cruces de barrio
DELTA_MOV = 2e-5    # desempate: con igual U y cruces, menos NAPs movidas


@dataclass
class Parametros:
    bw_max: float = 2500          # Mbps de referencia por puerto PON
    max_clientes: int = 128       # clientes máximos por puerto
    misma_olt: bool = True        # una NAP solo se mueve dentro de su OLT
    pro_degradada: float = -25.0  # dBm: por debajo, el cliente tiene señal débil
    pro_min: float = -27.0        # dBm: por debajo, el cambio queda prohibido
    n_eps2: int = 3               # niveles de cruces de barrio a explorar
    n_eps5: int = 3               # niveles de intervenciones a explorar
    nodos_max: int = 300          # límite de nodos del branch & bound
    tiempo_max: float = 20        # segundos máximos por cálculo
    gap_rel: float = 1e-6
    olts: tuple = field(default_factory=tuple)  # vacío = todas

    def clave(self):
        d = asdict(self)
        d["olts"] = tuple(sorted(d["olts"]))
        for k, v in d.items():
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                d[k] = round(float(v), 4)
        return tuple(sorted(d.items()))


# ----------------------------------------------------------------------
# Datos
# ----------------------------------------------------------------------
def cargar_datos(archivo):
    df = pd.read_csv(archivo, encoding="utf-8-sig")
    df = df.rename(columns={"Barrio": "barrio", "NAP": "nap", "OLT": "olt",
                            "PRO_dBm": "pro", "Plan_Mbps": "mbps"})
    df["barrio"] = df["barrio"].fillna("SIN BARRIO")
    df["id_puerto"] = (df["olt"] + "-" + df["Tarjeta"] + "-P"
                       + df["Puerto"].astype(int).astype(str))
    return df


def _moda(s):
    return s.mode().iloc[0]


def construir_instancia(df, p: Parametros):
    fijos = df[df["nap"].isna()].groupby("id_puerto").agg(
        bw=("mbps", "sum"), clientes=("mbps", "size"))
    naps = df.dropna(subset=["nap"]).groupby("nap").agg(
        barrio=("barrio", _moda),
        puerto_actual=("id_puerto", _moda),
        clientes=("nap", "size"),
        bw=("mbps", "sum"),
        pro=("pro", "mean"),
    ).reset_index()
    naps["olt"] = naps["puerto_actual"].str.split("-").str[0]

    puertos = sorted(df["id_puerto"].unique())
    olt_puerto = {q: q.split("-")[0] for q in puertos}
    barrio_puerto = df.groupby("id_puerto")["barrio"].agg(_moda).to_dict()
    pro_puerto = df.groupby("id_puerto")["pro"].mean().to_dict()

    pares, costo, mover, peso_pro, pro_est = [], [], [], [], []
    prohibidos = 0
    for i, nap in naps.iterrows():
        pro_base = pro_puerto.get(nap["puerto_actual"], np.nan)
        for j, q in enumerate(puertos):
            if p.misma_olt and olt_puerto[q] != nap["olt"]:
                continue
            se_mueve = q != nap["puerto_actual"]
            delta = pro_puerto.get(q, np.nan) - pro_base
            pro_ij = nap["pro"] + (delta if (se_mueve and not np.isnan(delta)) else 0)
            if se_mueve and not np.isnan(pro_ij) and pro_ij < p.pro_min:
                prohibidos += 1
                continue
            pares.append((i, j))
            mover.append(int(se_mueve))
            costo.append(int(se_mueve and nap["barrio"] != barrio_puerto[q]))
            degradada = (not np.isnan(pro_ij)) and pro_ij < p.pro_degradada
            peso_pro.append(nap["clientes"] if degradada else 0)
            pro_est.append(pro_ij)

    fijos = fijos.reindex(puertos, fill_value=0)
    return dict(naps=naps, puertos=puertos, fijos=fijos, pares=np.array(pares),
                costo=np.array(costo, float), mover=np.array(mover, float),
                peso_pro=np.array(peso_pro, float), pro_est=np.array(pro_est, float),
                prohibidos=prohibidos, barrio_puerto=barrio_puerto)


def _restricciones(inst, p):
    naps, puertos, fijos, pares = inst["naps"], inst["puertos"], inst["fijos"], inst["pares"]
    n_naps, n_puertos, m = len(naps), len(puertos), len(pares)
    n_var = m + 1
    bw, cli = naps["bw"].values, naps["clientes"].values
    A_asig = lil_matrix((n_naps, n_var))
    A_util = lil_matrix((n_puertos, n_var))
    A_cap = lil_matrix((n_puertos, n_var))
    for k, (i, j) in enumerate(pares):
        A_asig[i, k] = 1
        A_util[j, k] = bw[i] / p.bw_max
        A_cap[j, k] = cli[i]
    A_util[:, m] = -1
    base = [LinearConstraint(csr_matrix(A_asig), 1, 1),
            LinearConstraint(csr_matrix(A_util), -np.inf, -fijos["bw"].values / p.bw_max),
            LinearConstraint(csr_matrix(A_cap), -np.inf,
                             p.max_clientes - fijos["clientes"].values)]
    integralidad = np.append(np.ones(m), 0)
    limites = Bounds(np.zeros(n_var), np.append(np.ones(m), np.inf))
    return base, integralidad, limites


def _fila(coef):
    return csr_matrix(np.append(coef, 0.0).reshape(1, -1))


def _resolver(c, base, integralidad, limites, p, extras=()):
    t0 = time.perf_counter()
    res = milp(c, constraints=list(base) + list(extras), integrality=integralidad,
               bounds=limites,
               options={"node_limit": int(p.nodos_max), "time_limit": float(p.tiempo_max),
                        "mip_rel_gap": p.gap_rel})
    if res.x is None:
        return None
    res.tiempo = time.perf_counter() - t0
    res.exacta = res.status == 0
    return res


# ----------------------------------------------------------------------
# Situación actual (sin optimizar)
# ----------------------------------------------------------------------
def situacion_actual(df, p: Parametros):
    if p.olts:
        df = df[df["olt"].isin(p.olts)]
    puertos = sorted(df["id_puerto"].unique())
    # mismo criterio del modelo: los clientes de una caja se cuentan en el puerto
    # más frecuente de esa caja
    df = df.copy()
    con_nap = df["nap"].notna()
    puerto_nap = df[con_nap].groupby("nap")["id_puerto"].agg(_moda)
    df.loc[con_nap, "id_puerto"] = df.loc[con_nap, "nap"].map(puerto_nap)
    por_puerto = df.groupby("id_puerto").agg(
        mbps=("mbps", "sum"), clientes=("mbps", "size"),
        pro=("pro", "mean")).reindex(puertos)
    por_puerto["olt"] = [q.split("-")[0] for q in puertos]
    por_puerto["carga"] = por_puerto["mbps"] / p.bw_max
    return por_puerto


# ----------------------------------------------------------------------
# Programa completo
# ----------------------------------------------------------------------
def ejecutar(df, p: Parametros, progreso=lambda frac, msg: None):
    if p.olts:
        df = df[df["olt"].isin(p.olts)].copy()
    progreso(0.02, "Preparando los datos de la red")
    inst = construir_instancia(df, p)
    naps, puertos, fijos, pares = inst["naps"], inst["puertos"], inst["fijos"], inst["pares"]
    costo, mover, peso_pro, pro_est = (inst["costo"], inst["mover"],
                                       inst["peso_pro"], inst["pro_est"])
    m = len(pares)
    base, integ, lim = _restricciones(inst, p)

    def F2(x): return float(costo @ np.round(x[:-1]))
    def F4(x): return float(peso_pro @ np.round(x[:-1]))
    def F5(x): return float(mover @ np.round(x[:-1]))

    c_U = np.zeros(m + 1); c_U[-1] = 1
    c_F2 = np.append(costo, 0.0)
    c_F5 = np.append(mover, 0.0)
    c_obj = c_U + DELTA * c_F2 + DELTA_MOV * c_F5

    x_actual = np.array([1.0 if puertos[j] == naps.loc[i, "puerto_actual"] else 0.0
                         for i, j in pares] + [0.0])
    carga_actual = (naps.groupby("puerto_actual")["bw"].sum().reindex(puertos, fill_value=0)
                    + fijos["bw"]).astype(float)
    cli_actual = (naps.groupby("puerto_actual")["clientes"].sum().reindex(puertos, fill_value=0)
                  + fijos["clientes"]).astype(float)
    U_actual = carga_actual.max() / p.bw_max
    f4_actual = F4(x_actual)
    r_F4 = LinearConstraint(_fila(peso_pro), -np.inf, f4_actual)

    n_total = 2 + p.n_eps2 * p.n_eps5
    hechos = 0

    # --- Tabla de pagos ---
    progreso(0.05, "Buscando el mejor balance posible (paso 1 de 2 de preparación)")
    res_U = _resolver(c_U, base, integ, lim, p, [r_F4])
    if res_U is None:
        raise RuntimeError("No fue posible encontrar una solución con estos parámetros. "
                           "Pruebe con una señal mínima más baja o más clientes por puerto.")
    U_estrella = res_U.x[-1]
    hechos += 1
    progreso(0.05 + 0.9 * hechos / n_total,
             "Midiendo cuántos cambios exige ese mejor balance (paso 2 de 2 de preparación)")
    r_U = LinearConstraint(c_U.reshape(1, -1), -np.inf, U_estrella * (1 + 1e-3))
    res_xU = _resolver(c_F2 + DELTA_MOV * c_F5, base, integ, lim, p, [r_F4, r_U])
    x_U = res_xU.x if res_xU is not None else res_U.x
    f2_max, f5_max = F2(x_U), F5(x_U)
    hechos += 1

    eps2_vals = np.unique(np.round(np.linspace(0, f2_max, p.n_eps2)))
    eps5_vals = np.unique(np.round(np.linspace(0, f5_max, p.n_eps5 + 1)[1:]))
    eps5_vals = eps5_vals[eps5_vals > 0] if (eps5_vals > 0).any() else eps5_vals
    n_total = 2 + len(eps2_vals) * len(eps5_vals)

    soluciones, infactibles = [], []
    for e5 in eps5_vals:
        for e2 in eps2_vals:
            progreso(0.05 + 0.9 * hechos / n_total,
                     f"Evaluando alternativa {hechos - 1} de {n_total - 2}: "
                     f"hasta {e5:.0f} cajas movidas y hasta {e2:.0f} cambios de barrio")
            extras = [r_F4, LinearConstraint(_fila(costo), -np.inf, e2),
                      LinearConstraint(_fila(mover), -np.inf, e5)]
            res = _resolver(c_obj, base, integ, lim, p, extras)
            hechos += 1
            if res is None:
                infactibles.append({"eps2": e2, "eps5": e5, "U": np.nan})
                continue
            x = res.x
            soluciones.append({"eps2": e2, "eps5": e5, "U": res.x[-1],
                               "F2": int(F2(x)), "F4": int(F4(x)), "F5": int(F5(x)),
                               "exacta": res.exacta, "tiempo": res.tiempo,
                               "_x": np.round(x[:-1])})

    # Se agrega la solución de mejor balance como una alternativa más
    soluciones.append({"eps2": f2_max, "eps5": f5_max, "U": U_estrella,
                       "F2": int(F2(x_U)), "F4": int(F4(x_U)), "F5": int(F5(x_U)),
                       "exacta": res_U.exacta, "tiempo": res_U.tiempo,
                       "_x": np.round(x_U[:-1]), "mejor_balance": True})

    tabla = pd.DataFrame(soluciones)
    tabla["mejor_balance"] = tabla.get("mejor_balance", False).fillna(False).astype(bool)
    # recalcular U real con la asignación redondeada
    cargas, clientes = {}, {}
    U_real = []
    for k, s in tabla.iterrows():
        x = s["_x"]
        c = fijos["bw"].astype(float).copy()
        cl = fijos["clientes"].astype(float).copy()
        sel = np.where(x == 1)[0]
        for kk in sel:
            i, j = pares[kk]
            c.iloc[j] += naps.loc[i, "bw"]
            cl.iloc[j] += naps.loc[i, "clientes"]
        cargas[k], clientes[k] = c, cl
        U_real.append(c.max() / p.bw_max)
    tabla["U"] = U_real
    malla = pd.concat([tabla.loc[~tabla["mejor_balance"], ["eps2", "eps5", "U", "F2", "F5"]],
                       pd.DataFrame(infactibles, columns=["eps2", "eps5", "U"])],
                      ignore_index=True)

    # quitar alternativas repetidas (mismos resultados en los 4 indicadores)
    firma = tabla[["U", "F2", "F4", "F5"]].round(4).apply(tuple, axis=1)
    tabla = tabla.loc[~firma.duplicated()].copy()

    obj = tabla[["U", "F2", "F4", "F5"]].values.astype(float)
    def dominada(k):
        return any(np.all(obj[q] <= obj[k] + 1e-9) and np.any(obj[q] < obj[k] - 1e-9)
                   for q in range(len(obj)) if q != k)
    tabla["pareto"] = [not dominada(k) for k in range(len(tabla))]
    tabla = tabla.sort_values(["F5", "U"]).reset_index()
    tabla = tabla.rename(columns={"index": "_orig"})
    tabla.insert(0, "sol", range(1, len(tabla) + 1))
    mapa = dict(zip(tabla["sol"], tabla["_orig"]))
    cargas = {int(s): cargas[o] for s, o in mapa.items()}
    clientes = {int(s): clientes[o] for s, o in mapa.items()}

    # Recomendada: mismo criterio del proyecto (Pareto, pocas intervenciones
    # y pocos cruces, y entre esas la de mejor balance)
    pareto = tabla[tabla["pareto"]]
    cand = pareto[(pareto["F5"] <= np.median(eps5_vals))
                  & (pareto["F2"] <= np.median(eps2_vals))]
    recomendada = int((cand if len(cand) else pareto).sort_values("U").iloc[0]["sol"])

    # Detalle de NAPs movidas por alternativa
    movidas = []
    for _, s in tabla.iterrows():
        x = s["_x"]
        for kk in np.where((x == 1) & (mover == 1))[0]:
            i, j = pares[kk]
            movidas.append({"sol": s["sol"], "NAP": naps.loc[i, "nap"],
                            "Barrio": naps.loc[i, "barrio"],
                            "Clientes": int(naps.loc[i, "clientes"]),
                            "Mbps vendidos": float(naps.loc[i, "bw"]),
                            "Puerto actual": naps.loc[i, "puerto_actual"],
                            "Puerto nuevo": puertos[j],
                            "Barrio del puerto nuevo": inst["barrio_puerto"][puertos[j]],
                            "Cambia de barrio": "Sí" if costo[kk] else "No",
                            "Señal actual (dBm)": round(naps.loc[i, "pro"], 2),
                            "Señal estimada (dBm)": round(pro_est[kk], 2)})
    movidas = pd.DataFrame(movidas)
    progreso(1.0, "Cálculo terminado")

    return dict(tabla=tabla.drop(columns=["_x", "_orig"]), movidas=movidas,
                puertos=puertos, carga_actual=carga_actual, cli_actual=cli_actual,
                cargas=cargas, clientes=clientes, U_actual=U_actual, f4_actual=f4_actual,
                U_estrella=U_estrella, eps2_vals=eps2_vals, eps5_vals=eps5_vals,
                recomendada=recomendada, malla=malla, n_naps=len(naps), n_puertos=len(puertos),
                n_usuarios=len(df), n_fijos=int(df["nap"].isna().sum()),
                prohibidos=inst["prohibidos"], params=asdict(p))


# ----------------------------------------------------------------------
# Niveles de detalle que ve el usuario (malla de alternativas y tiempo)
# ----------------------------------------------------------------------
NIVELES = {
    "Rápido": dict(n_eps2=3, n_eps5=3, nodos_max=300, tiempo_max=20,
                   texto="9 alternativas. Tarda entre 1 y 3 minutos."),
    "Equilibrado": dict(n_eps2=4, n_eps5=4, nodos_max=1000, tiempo_max=45,
                        texto="16 alternativas. Tarda entre 5 y 12 minutos."),
    "Detallado": dict(n_eps2=5, n_eps5=5, nodos_max=3000, tiempo_max=120,
                      texto="25 alternativas, igual que en el estudio. "
                            "Puede tardar entre 20 y 50 minutos."),
}


def nombre_archivo(p: Parametros):
    import hashlib
    h = hashlib.md5(repr(p.clave()).encode()).hexdigest()[:12]
    return f"resultado_{h}.json"


# ----------------------------------------------------------------------
# Guardado portable de resultados (JSON, no depende de la versión de pandas)
# ----------------------------------------------------------------------
def a_json(r):
    import json
    def df(d): return json.loads(d.to_json(orient="split", index=False))
    def serie(s): return {"index": list(map(str, s.index)), "values": [float(v) for v in s.values]}
    out = {k: v for k, v in r.items() if k not in
           ("tabla", "movidas", "malla", "carga_actual", "cli_actual", "cargas", "clientes",
            "eps2_vals", "eps5_vals", "params")}
    out = {k: (v.item() if hasattr(v, "item") else v) for k, v in out.items()}
    out.update(tabla=df(r["tabla"]), movidas=df(r["movidas"]), malla=df(r["malla"]),
               carga_actual=serie(r["carga_actual"]), cli_actual=serie(r["cli_actual"]),
               cargas={str(k): serie(v) for k, v in r["cargas"].items()},
               clientes={str(k): serie(v) for k, v in r["clientes"].items()},
               eps2_vals=[float(v) for v in r["eps2_vals"]],
               eps5_vals=[float(v) for v in r["eps5_vals"]],
               params={k: (list(v) if isinstance(v, tuple) else v) for k, v in r["params"].items()})
    return json.dumps(out)


def de_json(texto):
    import json
    d = json.loads(texto)
    def df(x): return pd.DataFrame(x["data"], columns=x["columns"])
    def serie(x): return pd.Series(x["values"], index=x["index"], dtype=float)
    d["tabla"], d["movidas"], d["malla"] = df(d["tabla"]), df(d["movidas"]), df(d["malla"])
    d["tabla"]["pareto"] = d["tabla"]["pareto"].astype(bool)
    d["tabla"]["sol"] = d["tabla"]["sol"].astype(int)
    if len(d["movidas"]):
        d["movidas"]["sol"] = d["movidas"]["sol"].astype(int)
    d["carga_actual"], d["cli_actual"] = serie(d["carga_actual"]), serie(d["cli_actual"])
    d["cargas"] = {int(k): serie(v) for k, v in d["cargas"].items()}
    d["clientes"] = {int(k): serie(v) for k, v in d["clientes"].items()}
    d["eps2_vals"], d["eps5_vals"] = np.array(d["eps2_vals"]), np.array(d["eps5_vals"])
    d["params"]["olts"] = tuple(d["params"]["olts"])
    return d

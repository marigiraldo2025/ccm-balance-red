"""
CCM Televisión - Balance de la red de fibra óptica
Aplicación para explorar y ejecutar el modelo de optimización (método epsilon-constraint).

Ejecutar con:   streamlit run app.py
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import modelo

AQUI = Path(__file__).parent
ARCHIVO_DATOS = AQUI / "base_modelo_olt.csv"
CARPETA_RESULTADOS = AQUI / "resultados_guardados"
CARPETA_RESULTADOS.mkdir(exist_ok=True)
LOGO = AQUI / "logo_ccm.png"

# ----------------------------------------------------------------------
# Colores institucionales
# ----------------------------------------------------------------------
NARANJA = "#FF6B00"
NARANJA_SUAVE = "#FFB27A"
AZUL = "#0A3D7A"
AZUL_MEDIO = "#2F6DB5"
AZUL_CLARO = "#A9C4E6"
GRIS = "#C9D1DB"
GRIS_TEXTO = "#5B6B7F"
TEXTO = "#1B2B40"

st.set_page_config(page_title="CCM | Balance de la red de fibra",
                   page_icon=str(LOGO), layout="wide")

st.markdown(f"""
<style>
    .block-container {{max-width: 1120px; padding-top: 2.2rem; padding-bottom: 4rem;}}
    #MainMenu, footer, [data-testid="stDecoration"] {{visibility: hidden;}}
    h1, h2, h3 {{color: {AZUL}; letter-spacing: -0.01em;}}
    .marca {{display:flex; align-items:center; gap:1.4rem; padding-bottom:1.2rem;
             border-bottom: 3px solid {NARANJA}; margin-bottom: 1.2rem;}}
    .marca h1 {{margin:0; padding:0; font-size:2.1rem; line-height:1.15;}}
    .marca p {{margin:0.3rem 0 0 0; color:{GRIS_TEXTO}; font-size:1.02rem;}}
    .indice {{font-size:0.9rem; color:{GRIS_TEXTO}; margin-bottom:0.6rem;}}
    .indice a {{color:{AZUL}; text-decoration:none; margin-right:1.1rem;
               border-bottom:1px solid {AZUL_CLARO};}}
    .indice a:hover {{color:{NARANJA}; border-color:{NARANJA};}}
    .seccion {{display:flex; align-items:baseline; gap:0.8rem; margin-top:3.2rem;
               margin-bottom:0.3rem; padding-top:0.4rem; border-top:1px solid #E3E8EF;}}
    .seccion .num {{color:{NARANJA}; font-weight:700; font-size:1.05rem;}}
    .seccion h2 {{margin:0; padding:0; font-size:1.6rem;}}
    .intro {{color:{GRIS_TEXTO}; font-size:1.0rem; margin-bottom:1.2rem; max-width:860px;}}
    .kpi {{border:1px solid #E3E8EF; border-top:4px solid {AZUL}; border-radius:6px;
           padding:0.9rem 1rem 0.8rem 1rem; min-height:128px; background:#FFFFFF;}}
    .kpi.naranja {{border-top-color:{NARANJA};}}
    .kpi .etq {{font-size:0.82rem; color:{GRIS_TEXTO}; text-transform:uppercase;
                letter-spacing:0.04em;}}
    .kpi .val {{font-size:1.75rem; font-weight:700; color:{AZUL}; line-height:1.25;}}
    .kpi.naranja .val {{color:{NARANJA};}}
    .kpi .sub {{font-size:0.86rem; color:{GRIS_TEXTO};}}
    .param-nombre {{font-weight:700; color:{AZUL}; font-size:1.02rem; margin-bottom:0.15rem;}}
    .param-texto {{color:{TEXTO}; font-size:0.94rem; margin-bottom:0.2rem;}}
    .param-reco {{color:{GRIS_TEXTO}; font-size:0.84rem;}}
    .glosario dt {{font-weight:700; color:{AZUL}; margin-top:0.6rem;}}
    .glosario dd {{margin-left:0; color:{TEXTO}; font-size:0.95rem;}}
    .resumen {{background:#F3F6FA; border-left:4px solid {NARANJA}; padding:1rem 1.2rem;
               border-radius:4px; font-size:1.03rem; line-height:1.55; margin:0.6rem 0 1.4rem 0;}}
    .lectura {{color:{GRIS_TEXTO}; font-size:0.9rem; margin:-0.4rem 0 1.6rem 0;
               padding-left:0.8rem; border-left:2px solid {AZUL_CLARO};}}
    .graf-titulo {{font-weight:700; color:{AZUL}; font-size:1.12rem; margin:1.4rem 0 0 0;}}
    .graf-sub {{color:{GRIS_TEXTO}; font-size:0.92rem; margin:0.1rem 0 0 0;}}
    .stButton > button[kind="primary"] {{background:{NARANJA}; border-color:{NARANJA};
                                        font-weight:600; padding:0.55rem 1.6rem;}}
    .stDownloadButton > button {{border-color:{AZUL}; color:{AZUL};}}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def num(x, d=0):
    """Número con formato colombiano: 34.850,5"""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    s = f"{x:,.{d}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def veces(u):
    return f"{num(u, 1)} veces"


def seccion(numero, titulo, ancla, intro=None):
    st.markdown(f'<div class="seccion" id="sec-{ancla}"><span class="num">{numero}</span>'
                f'<h2>{titulo}</h2></div>', unsafe_allow_html=True)
    if intro:
        st.markdown(f'<div class="intro">{intro}</div>', unsafe_allow_html=True)


def kpi(col, etiqueta, valor, sub="", naranja=False):
    col.markdown(f'<div class="kpi {"naranja" if naranja else ""}"><div class="etq">{etiqueta}</div>'
                 f'<div class="val">{valor}</div><div class="sub">{sub}</div></div>',
                 unsafe_allow_html=True)


def titulo_grafica(titulo, sub=""):
    st.markdown(f'<div class="graf-titulo">{titulo}</div>'
                + (f'<div class="graf-sub">{sub}</div>' if sub else ""), unsafe_allow_html=True)


def lectura(texto):
    st.markdown(f'<div class="lectura"><b>Cómo leer esta gráfica:</b> {texto}</div>',
                unsafe_allow_html=True)


def estilo(fig, alto=420, leyenda_titulo=None):
    fig.update_layout(
        template="plotly_white", height=alto,
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=13, color=TEXTO),
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    title=dict(text=leyenda_titulo) if leyenda_titulo else None,
                    font=dict(size=13), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", font_size=13, bordercolor=GRIS),
        bargap=0.15,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRIS, ticks="outside", tickcolor=GRIS,
                     title_font=dict(size=13, color=GRIS_TEXTO))
    fig.update_yaxes(gridcolor="#EDF1F6", zeroline=False, title_font=dict(size=13, color=GRIS_TEXTO))
    return fig


def mostrar(fig):
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]})


@st.cache_data
def cargar_base():
    return modelo.cargar_datos(ARCHIVO_DATOS)


def ruta_resultado(p):
    return CARPETA_RESULTADOS / modelo.nombre_archivo(p)


def leer_resultado(p):
    ruta = ruta_resultado(p)
    if ruta.exists():
        try:
            return modelo.de_json(ruta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  archivo dañado o de otra versión
            return None
    return None


df = cargar_base()
TODAS_OLT = sorted(df["olt"].unique())
DEF = modelo.Parametros()

# Al abrir la app se carga el cálculo guardado más completo con los valores recomendados
if "resultado" not in st.session_state:
    st.session_state.resultado = None
    st.session_state.nivel_inicial = "Rápido"
    for nivel in ["Detallado", "Equilibrado", "Rápido"]:
        cfg = {k: v for k, v in modelo.NIVELES[nivel].items() if k != "texto"}
        r = leer_resultado(modelo.Parametros(**cfg))
        if r is not None:
            st.session_state.resultado = r
            st.session_state.nivel_inicial = nivel
            break

# ----------------------------------------------------------------------
# Encabezado
# ----------------------------------------------------------------------
c_logo, c_tit = st.columns([1, 6], vertical_alignment="center")
with c_logo:
    st.image(str(LOGO), width=120)
with c_tit:
    st.markdown("""
    <div style="border-bottom:3px solid #FF6B00; padding-bottom:0.9rem;">
      <h1 style="margin:0; padding:0; font-size:2.1rem;">Balance de la red de fibra óptica</h1>
      <p style="margin:0.35rem 0 0 0; color:#5B6B7F; font-size:1.05rem;">
        Herramienta para decidir qué cajas de distribución conviene cambiar de puerto
        para repartir mejor la carga de la red, con el menor trabajo técnico posible.</p>
    </div>""", unsafe_allow_html=True)

st.markdown("""
<div class="indice" style="margin-top:1.2rem;">
  <a href="#sec-red-hoy">1. Su red hoy</a>
  <a href="#sec-supuestos">2. Supuestos y glosario</a>
  <a href="#sec-parametros">3. Parámetros</a>
  <a href="#sec-ejecutar">4. Ejecutar</a>
  <a href="#sec-resultados">5. Resultados</a>
  <a href="#sec-plan">6. Plan de trabajo</a>
</div>""", unsafe_allow_html=True)

st.markdown(f"""
<div class="intro" style="margin-top:1rem;">
Hoy algunos puertos de la red atienden muchos más clientes y planes que otros. Eso hace que
los clientes de los puertos más llenos tengan más riesgo de lentitud en horas pico.
La herramienta busca <b>qué cajas (NAP) mover a otro puerto</b> para emparejar la carga.
Como cada cambio exige una visita técnica, no hay una sola respuesta: mover más cajas
reparte mejor la carga, pero cuesta más trabajo. Por eso se calculan varias alternativas y
se <b>recomienda una</b> que logra buena parte de la mejora con pocas visitas.
</div>""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 1. Su red hoy
# ----------------------------------------------------------------------
seccion("01", "Su red hoy", "red-hoy",
        "Fotografía de la red tal como está registrada en la base de datos, antes de hacer "
        "cualquier cambio.")

olts_vista = st.session_state.get("olts_sel") or TODAS_OLT
bw_vista = st.session_state.get("bw_max", DEF.bw_max)
hoy = modelo.situacion_actual(df, modelo.Parametros(bw_max=bw_vista, olts=tuple(olts_vista)))
df_vista = df[df["olt"].isin(olts_vista)]

k1, k2, k3, k4 = st.columns(4)
kpi(k1, "Clientes", num(len(df_vista)), f"{num(df_vista['nap'].isna().sum())} sin caja registrada")
kpi(k2, "Cajas de distribución (NAP)", num(df_vista["nap"].nunique()),
    f"en {num(df_vista['barrio'].nunique())} barrios")
kpi(k3, "Puertos", num(len(hoy)), f"en {len(olts_vista)} equipos OLT")
top = hoy["carga"].idxmax()
kpi(k4, "Puerto más cargado", veces(hoy["carga"].max()),
    f"{top}: {num(hoy.loc[top, 'mbps'])} Mbps vendidos", naranja=True)

# Gráfica: carga de cada puerto hoy
titulo_grafica("Carga de cada puerto hoy",
               f"Cuántas veces su capacidad de referencia ({num(bw_vista)} Mbps) tiene vendida "
               "cada puerto, del más cargado al menos cargado")
orden = hoy.sort_values("carga", ascending=False)
n_top = 5
colores = [NARANJA] * n_top + [AZUL_MEDIO] * (len(orden) - n_top)
fig = go.Figure()
fig.add_bar(x=list(range(1, len(orden) + 1)), y=orden["carga"], marker_color=colores,
            customdata=np.c_[orden.index, orden["olt"], orden["mbps"], orden["clientes"]],
            hovertemplate="<b>%{customdata[0]}</b><br>Equipo: %{customdata[1]}"
                          "<br>Carga: %{y:.1f} veces su capacidad"
                          "<br>Mbps vendidos: %{customdata[2]:,.0f}"
                          "<br>Clientes: %{customdata[3]}<extra></extra>",
            showlegend=False)
# entradas de leyenda claras
fig.add_scatter(x=[None], y=[None], mode="markers", marker=dict(color=NARANJA, size=12, symbol="square"),
                name=f"Los {n_top} puertos más cargados")
fig.add_scatter(x=[None], y=[None], mode="markers", marker=dict(color=AZUL_MEDIO, size=12, symbol="square"),
                name="Demás puertos")
prom = hoy["carga"].mean()
fig.add_hline(y=prom, line=dict(color=AZUL, dash="dash", width=2))
fig.add_scatter(x=[None], y=[None], mode="lines", line=dict(color=AZUL, dash="dash", width=2),
                name=f"Promedio de la red ({num(prom, 1)} veces)")
fig.update_xaxes(title="Puertos ordenados de mayor a menor carga", showticklabels=False)
fig.update_yaxes(title="Carga (veces la capacidad del puerto)")
mostrar(estilo(fig, 400))
lectura("cada barra es un puerto. Si la carga estuviera bien repartida, todas las barras "
        "tendrían una altura parecida a la línea punteada del promedio. Las barras naranjas "
        "son los puertos con más planes vendidos: ahí es donde los clientes tienen más riesgo "
        "de lentitud. Pase el cursor sobre una barra para ver el detalle del puerto.")

# Gráfica: por OLT
titulo_grafica("Diferencia entre el puerto más lleno y el promedio en cada equipo OLT",
               "Entre más separadas estén las dos barras, más desbalanceado está el equipo")
por_olt = hoy.groupby("olt").agg(maximo=("carga", "max"), promedio=("carga", "mean"),
                                 puertos=("carga", "size"))
fig = go.Figure()
fig.add_bar(x=por_olt.index, y=por_olt["promedio"], name="Carga promedio de sus puertos",
            marker_color=AZUL_CLARO, text=[num(v, 1) for v in por_olt["promedio"]],
            textposition="outside", hovertemplate="%{x}<br>Promedio: %{y:.1f} veces<extra></extra>")
fig.add_bar(x=por_olt.index, y=por_olt["maximo"], name="Carga de su puerto más lleno",
            marker_color=NARANJA, text=[num(v, 1) for v in por_olt["maximo"]],
            textposition="outside", hovertemplate="%{x}<br>Puerto más lleno: %{y:.1f} veces<extra></extra>")
fig.update_layout(barmode="group")
fig.update_xaxes(title="Equipo OLT")
fig.update_yaxes(title="Carga (veces la capacidad del puerto)",
                 range=[0, por_olt["maximo"].max() * 1.18])
mostrar(estilo(fig, 380))
lectura("para cada equipo, la barra azul muestra cuánto tiene vendido un puerto típico y la "
        "naranja cuánto tiene el puerto más lleno. Una diferencia grande indica que hay "
        "margen para pasar cajas del puerto lleno a puertos con menos carga del mismo equipo.")

# ----------------------------------------------------------------------
# 2. Supuestos y glosario
# ----------------------------------------------------------------------
seccion("02", "Supuestos y glosario", "supuestos",
        "Palabras que aparecen en la herramienta y las condiciones que se tomaron como ciertas "
        "para hacer los cálculos.")

g1, g2 = st.columns(2, gap="large")
with g1:
    st.markdown("#### Palabras clave")
    st.markdown("""
<dl class="glosario">
<dt>Equipo OLT</dt>
<dd>Equipo central de la empresa del que sale la fibra hacia los barrios. La red tiene
varios (por ejemplo C300, OLT12, OLT14, ZTE11).</dd>
<dt>Puerto</dt>
<dd>Cada salida de fibra de un equipo OLT. Un puerto alimenta varias cajas y, por medio de
ellas, a muchos clientes que comparten la misma capacidad.</dd>
<dt>Caja de distribución (NAP)</dt>
<dd>Caja instalada en la calle o en un edificio a la que se conectan los clientes cercanos.
Es lo que la herramienta propone cambiar de puerto: la caja se mueve completa, con todos
sus clientes.</dd>
<dt>Carga de un puerto</dt>
<dd>Suma de las velocidades de los planes vendidos en ese puerto, dividida entre su
capacidad de referencia. Una carga de 10 veces significa que se vendieron planes que, sumados,
equivalen a 10 veces lo que el puerto puede entregar al mismo tiempo. Es normal que sea mayor
que 1, porque no todos los clientes usan su plan completo a la vez; lo importante es que no
haya puertos mucho más cargados que otros.</dd>
<dt>Señal del cliente (potencia óptica, en dBm)</dt>
<dd>Intensidad de la luz que llega al módem del cliente. Son números negativos: entre más
cerca de cero, mejor. Una señal de -20 dBm es buena; una de -27 dBm es muy débil.</dd>
<dt>Intervención técnica</dt>
<dd>Visita de un técnico para cambiar una caja de puerto. Cada caja movida es una
intervención y genera un corte breve del servicio a sus clientes.</dd>
<dt>Cambio de barrio</dt>
<dd>Cuando una caja pasa a un puerto que atiende principalmente otro barrio. Es menos
deseable porque complica el mantenimiento y el desplazamiento del personal.</dd>
</dl>""", unsafe_allow_html=True)

with g2:
    st.markdown("#### Qué busca la herramienta")
    st.markdown(f"""
<dl class="glosario">
<dt>1. Bajar la carga del puerto más lleno</dt>
<dd>Es la meta principal: que el puerto más cargado de la red quede lo menos cargado posible.</dd>
<dt>2. Hacer pocas visitas técnicas</dt>
<dd>Mover la menor cantidad de cajas posible.</dd>
<dt>3. Evitar cambios de barrio</dt>
<dd>Preferir que cada caja quede en un puerto de su mismo barrio.</dd>
<dt>4. No empeorar la señal</dt>
<dd>Ninguna alternativa puede dejar más clientes con señal débil de los que hay hoy.</dd>
</dl>""", unsafe_allow_html=True)
    st.markdown("#### Condiciones que se asumen")
    st.markdown("""
<dl class="glosario">
<dd>- La carga se mide con los planes vendidos (Mbps contratados), no con el consumo real.</dd>
<dd>- Los clientes que no tienen caja registrada no se pueden mover: se quedan en su puerto,
pero sí cuentan en su carga y en su número de clientes.</dd>
<dd>- La señal que tendría una caja en otro puerto se estima así: su señal actual más la
diferencia entre la señal promedio del puerto nuevo y la del puerto actual.</dd>
<dd>- El barrio de una caja y el de un puerto es el barrio más frecuente entre sus clientes.</dd>
<dd>- Las metas 2 y 3 se exploran con distintos límites; por eso el resultado es un grupo de
alternativas y no una sola.</dd>
</dl>""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 3. Parámetros
# ----------------------------------------------------------------------
seccion("03", "Parámetros", "parametros",
        "Valores que puede ajustar antes de calcular. Junto a cada uno se explica qué significa "
        "y qué pasa si lo cambia. Si no está seguro, deje el valor recomendado.")


def fila_param(nombre, texto, recomendado):
    a, b = st.columns([3, 2], gap="large", vertical_alignment="center")
    a.markdown(f'<div class="param-nombre">{nombre}</div><div class="param-texto">{texto}</div>'
               f'<div class="param-reco">Valor recomendado: {recomendado}</div>',
               unsafe_allow_html=True)
    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)
    return b


with st.container(border=True):
    b = fila_param("Equipos OLT a incluir",
                   "Elija qué equipos quiere revisar. Si analiza uno solo, el cálculo es mucho "
                   "más rápido, pero solo se proponen cambios en ese equipo.",
                   "todos los equipos")
    olts_sel = b.multiselect("Equipos OLT", TODAS_OLT, default=TODAS_OLT, key="olts_sel",
                             label_visibility="collapsed", placeholder="Elija al menos un equipo")

    b = fila_param("Capacidad de referencia de cada puerto (Mbps)",
                   "Velocidad total que un puerto puede entregar al mismo tiempo. En la tecnología "
                   "de la red (GPON) es de unos 2.500 Mbps. Sirve como unidad para medir la carga: "
                   "cambiarla cambia la escala de las cifras, pero casi no cambia qué cajas "
                   "conviene mover.",
                   "2.500 Mbps")
    bw_max = b.number_input("Capacidad", min_value=500, max_value=20000, value=int(DEF.bw_max),
                            step=100, key="bw_max", label_visibility="collapsed")

    b = fila_param("Máximo de clientes por puerto",
                   "Cantidad máxima de clientes que puede atender un puerto según los divisores "
                   "instalados. La herramienta nunca propone dejar un puerto con más clientes "
                   "que este número.",
                   "128 clientes")
    max_cli = b.number_input("Máximo de clientes", min_value=16, max_value=512,
                             value=DEF.max_clientes, step=8, label_visibility="collapsed")

    b = fila_param("Mover cajas solo dentro del mismo equipo OLT",
                   "Si está activo, una caja solo puede pasar a otro puerto de su mismo equipo. "
                   "Es lo habitual, porque pasar a otro equipo suele exigir tender fibra nueva. "
                   "Desactivarlo da más opciones, pero el cálculo es mucho más lento.",
                   "activo")
    misma_olt = b.toggle("Solo dentro del mismo equipo", value=DEF.misma_olt)

    b = fila_param("Señal mínima permitida (dBm)",
                   "Si al mover una caja su señal estimada queda por debajo de este valor, ese "
                   "cambio no se permite. Un valor más bajo (por ejemplo -28) permite más "
                   "cambios pero con más riesgo de fallas; uno más alto (por ejemplo -26) es "
                   "más prudente.",
                   "-27 dBm")
    pro_min = b.slider("Señal mínima", min_value=-30.0, max_value=-22.0, value=DEF.pro_min,
                       step=0.5, format="%.1f dBm", label_visibility="collapsed")

    b = fila_param("Límite de señal débil (dBm)",
                   "Por debajo de este valor se considera que un cliente tiene señal débil. "
                   "Ninguna alternativa puede aumentar la cantidad de clientes en esa situación.",
                   "-25 dBm")
    pro_deg = b.slider("Señal débil", min_value=-29.0, max_value=-20.0, value=DEF.pro_degradada,
                       step=0.5, format="%.1f dBm", label_visibility="collapsed")

    b = fila_param("Nivel de detalle del cálculo",
                   "Cuántas alternativas se calculan y cuánto tiempo se le da a cada una. Más "
                   "detalle da resultados más finos, pero tarda más.",
                   "Equilibrado")
    nivel = b.radio("Nivel", list(modelo.NIVELES), horizontal=True,
                    index=list(modelo.NIVELES).index(st.session_state.nivel_inicial),
                    label_visibility="collapsed")
    b.caption(modelo.NIVELES[nivel]["texto"])

errores = []
if not olts_sel:
    errores.append("Elija al menos un equipo OLT.")
if pro_min > pro_deg:
    errores.append("La señal mínima permitida no puede ser mayor que el límite de señal débil.")
for e in errores:
    st.warning(e)

cfg = {k: v for k, v in modelo.NIVELES[nivel].items() if k != "texto"}
olts_param = tuple(sorted(olts_sel)) if set(olts_sel) != set(TODAS_OLT) else tuple()
params = modelo.Parametros(bw_max=float(bw_max), max_clientes=int(max_cli), misma_olt=misma_olt,
                           pro_degradada=float(pro_deg), pro_min=float(pro_min),
                           olts=olts_param, **cfg)

# ----------------------------------------------------------------------
# 4. Ejecutar
# ----------------------------------------------------------------------
seccion("04", "Ejecutar el cálculo", "ejecutar",
        "Pulse el botón para calcular las alternativas con los parámetros de arriba. Si ese "
        "cálculo ya se hizo antes, los resultados aparecen de inmediato.")

guardado = leer_resultado(params)
c1, c2 = st.columns([1, 2], vertical_alignment="center")
with c1:
    ejecutar = st.button("Calcular alternativas", type="primary", disabled=bool(errores),
                         width="stretch")
with c2:
    if guardado is not None:
        st.markdown(f'<span style="color:{GRIS_TEXTO}">Ya existe un cálculo guardado con estos '
                    'parámetros. Al pulsar el botón se mostrará al instante.</span>',
                    unsafe_allow_html=True)
        recalcular = st.checkbox("Calcular de nuevo de todas formas")
    else:
        st.markdown(f'<span style="color:{GRIS_TEXTO}">Tiempo aproximado: '
                    f'{modelo.NIVELES[nivel]["texto"].split(". ", 1)[1]} Mantenga esta '
                    'ventana abierta mientras termina.</span>', unsafe_allow_html=True)
        recalcular = True

if ejecutar:
    if guardado is not None and not recalcular:
        st.session_state.resultado = guardado
        st.success("Resultados cargados.")
    else:
        barra = st.progress(0.0, text="Iniciando el cálculo")
        try:
            r = modelo.ejecutar(df, params,
                                lambda f, m: barra.progress(min(max(f, 0.0), 1.0), text=m))
            try:
                ruta_resultado(params).write_text(modelo.a_json(r), encoding="utf-8")
            except Exception:  # noqa: BLE001  (p. ej. servidor sin permiso de escritura)
                pass
            st.session_state.resultado = r
            barra.progress(1.0, text="Cálculo terminado")
            st.success("Cálculo terminado. Revise los resultados abajo.")
        except Exception as e:  # noqa: BLE001
            barra.empty()
            st.error(f"No fue posible completar el cálculo. {e}")

R = st.session_state.resultado

# ----------------------------------------------------------------------
# 5. Resultados
# ----------------------------------------------------------------------
seccion("05", "Resultados", "resultados",
        "Alternativas encontradas y comparación con la red actual. La alternativa recomendada "
        "aparece seleccionada; puede elegir cualquier otra para ver su efecto.")

if R is None:
    st.info("Todavía no hay resultados. Ajuste los parámetros y pulse «Calcular alternativas».")
    st.stop()

pr = R["params"]
if modelo.nombre_archivo(modelo.Parametros(**{**pr, "olts": tuple(pr["olts"])})) != \
        modelo.nombre_archivo(params):
    st.markdown(
        f'<div class="resumen" style="border-left-color:{AZUL_MEDIO}">Los resultados que se '
        'muestran corresponden a un cálculo con parámetros distintos a los que tiene '
        'seleccionados ahora. Para ver el efecto de sus cambios, pulse «Calcular alternativas».'
        '</div>', unsafe_allow_html=True)

tabla = R["tabla"].copy()
BW = pr["bw_max"]
rec = R["recomendada"]
U0 = R["U_actual"]
puertos = R["puertos"]
olt_de = pd.Series([q.split("-")[0] for q in puertos], index=puertos)


def etiqueta_alt(s):
    fila = tabla.set_index("sol").loc[s]
    base = (f"Alternativa {s}: mover {int(fila.F5)} cajas, "
            f"puerto más lleno {num(fila.U, 1)} veces")
    return base + ("  (recomendada)" if s == rec else "")


st.markdown('<div class="param-nombre" style="margin-top:0.4rem">Alternativa a revisar</div>',
            unsafe_allow_html=True)
sel = st.selectbox("Alternativa", tabla["sol"].tolist(), index=tabla["sol"].tolist().index(rec),
                   format_func=etiqueta_alt, label_visibility="collapsed")
fs = tabla.set_index("sol").loc[sel]
carga_n = R["cargas"][sel]
cli_n = R["clientes"][sel]
mov_sel = R["movidas"][R["movidas"]["sol"] == sel] if len(R["movidas"]) else pd.DataFrame()

mejora = (U0 - fs.U) / U0 * 100
mejora_max = (U0 - tabla["U"].min()) / U0 * 100
k1, k2, k3, k4 = st.columns(4)
kpi(k1, "Puerto más lleno", veces(fs.U), f"hoy: {veces(U0)}")
kpi(k2, "Reducción de la carga", f"{num(mejora, 1)} %",
    f"la mayor posible encontrada: {num(mejora_max, 1)} %", naranja=True)
kpi(k3, "Cajas a mover", num(fs.F5), f"{num(mov_sel['Clientes'].sum() if len(mov_sel) else 0)} "
    "clientes con corte breve")
kpi(k4, "Cambios de barrio", num(fs.F2), f"clientes con señal débil: {num(fs.F4)} "
    f"(hoy {num(R['f4_actual'])})")

frase_cero = fs.F5 == 0
frase_barrio = ("todas quedan en puertos de su mismo barrio" if fs.F2 == 0 else
                f"{num(fs.F2)} de ellas pasan a un puerto de otro barrio")
frase_senal = ("sin aumentar la cantidad de clientes con señal débil"
               if fs.F4 <= R["f4_actual"] else "")
if frase_cero:
    st.markdown(f'<div class="resumen">La <b>alternativa {sel}</b> no mueve ninguna caja: '
                f'corresponde a dejar la red como está hoy, con el puerto más lleno en '
                f'<b>{num(U0 * BW)} Mbps</b> vendidos.</div>', unsafe_allow_html=True)
else:
    st.markdown(f"""
<div class="resumen">
Con la <b>alternativa {sel}</b>{" (recomendada)" if sel == rec else ""} se mueven
<b>{num(fs.F5)} cajas</b> de puerto ({frase_barrio}). El puerto más lleno de la red pasa de
tener vendidos <b>{num(U0 * BW)} Mbps</b> a <b>{num(fs.U * BW)} Mbps</b>, una reducción del
<b>{num(mejora, 1)} %</b>{", " + frase_senal if frase_senal else ""}.
{"Esta alternativa logra " + num(mejora / mejora_max * 100 if mejora_max else 0, 0)
 + " % de la mejora máxima encontrada." if mejora_max > 0 else ""}
</div>""", unsafe_allow_html=True)

# --- Gráfica 1: mejora vs. cajas movidas ---
titulo_grafica("¿Cuánto mejora la red por cada caja que se mueve?",
               "Mejor resultado posible según la cantidad de cajas que se esté dispuesto a mover")
curva = (tabla[tabla["pareto"]].sort_values(["F5", "U"])
         .groupby("F5", as_index=False).first())
curva = curva[curva["U"] <= curva["U"].cummin() + 1e-9]
xs = np.r_[0, curva["F5"].values]
ys = np.r_[U0, curva["U"].values]
fig = go.Figure()
otras = tabla[~tabla["sol"].isin(curva["sol"])]
if len(otras):
    fig.add_scatter(x=otras["F5"], y=otras["U"], mode="markers", name="Otras alternativas calculadas",
                    marker=dict(size=8, color=GRIS, line=dict(color=GRIS_TEXTO, width=1)),
                    customdata=otras["sol"],
                    hovertemplate="Alternativa %{customdata}<br>Cajas movidas: %{x}"
                                  "<br>Puerto más lleno: %{y:.2f} veces<extra></extra>")
fig.add_scatter(x=xs, y=ys, mode="lines+markers", name="Mejor carga posible para ese número de cajas",
                line=dict(color=AZUL_MEDIO, width=3, shape="hv"),
                marker=dict(size=9, color=AZUL_MEDIO),
                hovertemplate="Cajas movidas: %{x}<br>Puerto más lleno: %{y:.2f} veces<extra></extra>")
fig.add_scatter(x=[0], y=[U0], mode="markers", name="Red actual (sin mover nada)",
                marker=dict(size=14, color=AZUL, symbol="square"),
                hovertemplate="Red actual<br>Puerto más lleno: %{y:.2f} veces<extra></extra>")
fr = tabla.set_index("sol").loc[rec]
fig.add_scatter(x=[fr.F5], y=[fr.U], mode="markers", name=f"Alternativa recomendada ({rec})",
                marker=dict(size=20, color=NARANJA, symbol="star", line=dict(color="white", width=1)),
                hovertemplate=f"Alternativa {rec} (recomendada)<br>Cajas movidas: %{{x}}"
                              "<br>Puerto más lleno: %{y:.2f} veces<extra></extra>")
if sel != rec:
    fig.add_scatter(x=[fs.F5], y=[fs.U], mode="markers", name=f"Alternativa seleccionada ({sel})",
                    marker=dict(size=18, color="rgba(0,0,0,0)", line=dict(color=AZUL, width=3)),
                    hovertemplate=f"Alternativa {sel}<br>Cajas movidas: %{{x}}"
                                  "<br>Puerto más lleno: %{y:.2f} veces<extra></extra>")
fig.update_xaxes(title="Cajas movidas (visitas técnicas)", rangemode="tozero")
fig.update_yaxes(title="Carga del puerto más lleno (veces su capacidad)")
mostrar(estilo(fig, 440))
lectura("la línea azul baja a medida que se mueven más cajas: más trabajo técnico, mejor "
        "balance. Observe que al principio la línea baja rápido y después casi se aplana; a "
        "partir de ese punto, cada visita adicional aporta muy poco. La estrella naranja es la "
        "alternativa recomendada, que está cerca de ese punto de equilibrio.")

# --- Gráfica 2: carga por puerto antes y después ---
titulo_grafica(f"Carga de cada puerto: hoy frente a la alternativa {sel}",
               "Puertos ordenados de mayor a menor carga actual")
ordenp = (R["carga_actual"] / BW).sort_values(ascending=False)
idx = ordenp.index
xpos = list(range(1, len(idx) + 1))
fig = go.Figure()
fig.add_bar(x=xpos, y=ordenp.values, name="Hoy", marker_color=GRIS,
            customdata=np.c_[idx, olt_de[idx], R["cli_actual"][idx]],
            hovertemplate="<b>%{customdata[0]}</b><br>Hoy: %{y:.1f} veces"
                          "<br>Clientes hoy: %{customdata[2]:.0f}<extra></extra>")
fig.add_scatter(x=xpos, y=(carga_n[idx] / BW).values, name=f"Con la alternativa {sel}",
                mode="markers", marker=dict(color=AZUL_MEDIO, size=7, line=dict(color="white", width=0.5)),
                customdata=np.c_[idx, cli_n[idx]],
                hovertemplate="<b>%{customdata[0]}</b><br>Después: %{y:.1f} veces"
                              "<br>Clientes después: %{customdata[1]:.0f}<extra></extra>")
fig.add_hline(y=U0, line=dict(color=GRIS_TEXTO, dash="dot", width=1.5))
fig.add_hline(y=fs.U, line=dict(color=NARANJA, dash="dash", width=2))
fig.add_scatter(x=[None], y=[None], mode="lines", line=dict(color=GRIS_TEXTO, dash="dot"),
                name=f"Puerto más lleno hoy ({num(U0, 1)})")
fig.add_scatter(x=[None], y=[None], mode="lines", line=dict(color=NARANJA, dash="dash", width=2),
                name=f"Puerto más lleno después ({num(fs.U, 1)})")
fig.update_xaxes(title="Puertos (pase el cursor para ver el nombre)", showticklabels=False)
fig.update_yaxes(title="Carga (veces la capacidad del puerto)")
mostrar(estilo(fig, 440))
lectura("cada barra gris es la carga de un puerto hoy y el punto azul encima o dentro de ella "
        "es su carga después de los cambios. En los puertos de la izquierda (los más llenos) el "
        "punto azul queda por debajo del borde de la barra: esos puertos se alivian. Algunos puertos de la derecha suben un poco "
        "porque reciben las cajas. La línea naranja muestra el nuevo techo de la red.")

# --- Gráfica 3: puerto más lleno por OLT ---
titulo_grafica("Puerto más lleno de cada equipo OLT: hoy frente a la alternativa",
               "Muestra en qué equipos se concentra la mejora")
mx0 = (R["carga_actual"] / BW).groupby(olt_de).max()
mx1 = (carga_n / BW).groupby(olt_de).max()
fig = go.Figure()
fig.add_bar(x=mx0.index, y=mx0.values, name="Hoy", marker_color=GRIS,
            text=[num(v, 1) for v in mx0.values], textposition="outside",
            hovertemplate="%{x}<br>Hoy: %{y:.2f} veces<extra></extra>")
fig.add_bar(x=mx1.index, y=mx1.values, name=f"Con la alternativa {sel}", marker_color=AZUL_MEDIO,
            text=[num(v, 1) for v in mx1.values], textposition="outside",
            hovertemplate="%{x}<br>Después: %{y:.2f} veces<extra></extra>")
fig.update_layout(barmode="group")
fig.update_xaxes(title="Equipo OLT")
fig.update_yaxes(title="Carga del puerto más lleno (veces)", range=[0, mx0.max() * 1.18])
mostrar(estilo(fig, 380))
lectura("si la barra azul es más baja que la gris, el puerto más lleno de ese equipo mejora. "
        "Cuando ambas barras son iguales, en ese equipo no fue necesario mover cajas para "
        "mejorar la red.")

# --- Gráfica 4: qué tan parejos quedan ---
titulo_grafica("¿Qué tan pareja queda la carga entre puertos?",
               "Cada punto es un puerto; la caja agrupa a la mitad de los puertos")
u0 = (R["carga_actual"] / BW).values
u1 = (carga_n / BW).values
fig = go.Figure()
fig.add_box(y=u0, name="Hoy", marker_color=GRIS_TEXTO, fillcolor="rgba(201,209,219,0.45)",
            line_color=GRIS_TEXTO, boxpoints="all", jitter=0.45, pointpos=0,
            marker=dict(size=5, opacity=0.6), hovertemplate="%{y:.2f} veces<extra>Hoy</extra>")
fig.add_box(y=u1, name=f"Con la alternativa {sel}", marker_color=AZUL_MEDIO,
            fillcolor="rgba(47,109,181,0.18)", line_color=AZUL_MEDIO, boxpoints="all",
            jitter=0.45, pointpos=0, marker=dict(size=5, opacity=0.6),
            hovertemplate="%{y:.2f} veces<extra>Después</extra>")
fig.update_yaxes(title="Carga de cada puerto (veces su capacidad)")
fig.update_layout(showlegend=False)
mostrar(estilo(fig, 420))
st.markdown(
    f'<div class="lectura"><b>Cómo leer esta gráfica:</b> entre más baja quede la parte de '
    f'arriba de la nube de puntos, menos puertos sobrecargados hay. La línea dentro de cada '
    f'caja es la carga del puerto típico. Variación entre puertos: hoy {num(u0.std(), 2)}, '
    f'con la alternativa {num(u1.std(), 2)} (un número menor indica una red más pareja).</div>',
    unsafe_allow_html=True)

# --- Gráfica 5: mapa de alternativas ---
malla = R.get("malla")
if malla is not None and len(malla):
    titulo_grafica("Mapa de todas las alternativas calculadas",
                   "Carga del puerto más lleno según los límites que se fijen a las visitas "
                   "técnicas y a los cambios de barrio")
    e2 = sorted(malla["eps2"].unique())
    e5 = sorted(malla["eps5"].unique())
    piv = malla.pivot_table(index="eps5", columns="eps2", values="U", dropna=False).reindex(
        index=e5, columns=e2)
    z = piv.values
    texto = [["Sin solución" if np.isnan(v) else num(v, 1) for v in fila] for fila in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"hasta {int(v)}" for v in e2], y=[f"hasta {int(v)}" for v in e5],
        text=texto, texttemplate="%{text}", textfont=dict(size=14),
        colorscale=[[0, AZUL], [0.5, "#F4F6F9"], [1, NARANJA]],
        colorbar=dict(title=dict(text="Carga del<br>puerto más<br>lleno (veces)", side="top"),
                      thickness=14),
        hovertemplate="Cambios de barrio permitidos: %{x}<br>Cajas que se pueden mover: %{y}"
                      "<br>Puerto más lleno: %{z:.2f} veces<extra></extra>",
        xgap=3, ygap=3))
    fig.update_xaxes(title="Cambios de barrio permitidos", type="category", showgrid=False)
    fig.update_yaxes(title="Cajas que se pueden mover", type="category", showgrid=False)
    mostrar(estilo(fig, 420))
    lectura("cada casilla es un cálculo con un tope distinto. Hacia arriba se permiten más "
            "cajas movidas y hacia la derecha más cambios de barrio. El color azul indica una "
            "red mejor balanceada y el naranja una red más desbalanceada. Si al aumentar un "
            "tope el número casi no cambia, ese tope no vale la pena aflojarlo.")

# --- Gráfica 6: cajas por barrio ---
if len(mov_sel):
    titulo_grafica(f"Barrios donde se hacen los cambios (alternativa {sel})",
                   "Cantidad de cajas a mover en cada barrio")
    pb = (mov_sel.assign(n=1).pivot_table(index="Barrio", columns="Cambia de barrio", values="n",
                                          aggfunc="sum", fill_value=0))
    for c in ["No", "Sí"]:
        if c not in pb:
            pb[c] = 0
    pb = pb.assign(total=pb.sum(axis=1)).sort_values("total")
    fig = go.Figure()
    fig.add_bar(y=pb.index, x=pb["No"], orientation="h", name="Queda en un puerto de su mismo barrio",
                marker_color=AZUL_MEDIO, hovertemplate="%{y}<br>%{x} cajas<extra></extra>")
    fig.add_bar(y=pb.index, x=pb["Sí"], orientation="h", name="Pasa a un puerto de otro barrio",
                marker_color=NARANJA, hovertemplate="%{y}<br>%{x} cajas<extra></extra>")
    fig.update_layout(barmode="stack", legend_traceorder="normal")
    fig.update_xaxes(title="Cajas a mover", dtick=1, showgrid=True, gridcolor="#EDF1F6")
    fig.update_yaxes(title=None)
    mostrar(estilo(fig, max(300, 34 * len(pb) + 120)))
    lectura("sirve para organizar las cuadrillas: muestra en qué barrios se concentra el "
            "trabajo. La parte naranja son cajas que pasarían a un puerto que atiende "
            "principalmente otro barrio.")

# --- Tabla comparativa ---
titulo_grafica("Comparación de todas las alternativas",
               "Use esta tabla para elegir según su presupuesto y su personal técnico disponible")
comp = pd.DataFrame({
    "Alternativa": [f"{s} (recomendada)" if s == rec else str(s) for s in tabla["sol"]],
    "Cajas a mover": tabla["F5"],
    "Cambios de barrio": tabla["F2"],
    "Puerto más lleno (veces)": tabla["U"].round(2),
    "Mbps en el puerto más lleno": (tabla["U"] * BW).round(0),
    "Reducción (%)": ((U0 - tabla["U"]) / U0 * 100).round(1),
    "Clientes con señal débil": tabla["F4"],
    "Vale la pena": np.where(tabla["pareto"], "Sí", "No, hay otra mejor en todo"),
})
st.dataframe(
    comp, hide_index=True, width="stretch",
    column_config={
        "Reducción (%)": st.column_config.ProgressColumn(
            "Reducción de la carga máxima", format="%.1f %%", min_value=0,
            max_value=float(max(comp["Reducción (%)"].max(), 1))),
        "Mbps en el puerto más lleno": st.column_config.NumberColumn(format="localized"),
    })
st.markdown('<div class="lectura"><b>Nota:</b> «Vale la pena = No» significa que existe otra '
            'alternativa que es igual o mejor en todo (carga, cajas, cambios de barrio y señal). '
            'La recomendada se elige entre las que valen la pena, buscando pocas visitas, pocos '
            'cambios de barrio y el mejor balance.</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 6. Plan de trabajo
# ----------------------------------------------------------------------
seccion("06", "Plan de trabajo", "plan",
        f"Lista de cajas que se deben cambiar de puerto en la alternativa {sel}. Puede "
        "descargarla para entregarla al equipo técnico.")

if len(mov_sel):
    plan = mov_sel.drop(columns="sol").sort_values(["Puerto actual", "NAP"]).reset_index(drop=True)
    plan.insert(0, "N.º", range(1, len(plan) + 1))
    st.dataframe(plan, hide_index=True, width="stretch",
                 column_config={"Mbps vendidos": st.column_config.NumberColumn(format="localized"),
                                "Señal actual (dBm)": st.column_config.NumberColumn(format="%.2f"),
                                "Señal estimada (dBm)": st.column_config.NumberColumn(format="%.2f")})
else:
    plan = pd.DataFrame()
    st.info("Esta alternativa no requiere mover cajas.")

# Excel descargable
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    comp.to_excel(w, sheet_name="Alternativas", index=False)
    if len(plan):
        plan.to_excel(w, sheet_name=f"Plan alternativa {sel}", index=False)
    if len(R["movidas"]):
        R["movidas"].rename(columns={"sol": "Alternativa"}).to_excel(
            w, sheet_name="Cajas de todas", index=False)
    pd.DataFrame({"Puerto": puertos, "Equipo OLT": olt_de.values,
                  "Clientes hoy": R["cli_actual"].values,
                  "Mbps vendidos hoy": R["carga_actual"].values,
                  "Carga hoy (veces)": (R["carga_actual"] / BW).round(3).values,
                  f"Clientes alt. {sel}": cli_n.values,
                  f"Mbps vendidos alt. {sel}": carga_n.values,
                  f"Carga alt. {sel} (veces)": (carga_n / BW).round(3).values}
                 ).to_excel(w, sheet_name="Carga por puerto", index=False)
    pd.DataFrame({"Parámetro": ["Capacidad de referencia (Mbps)", "Máximo de clientes por puerto",
                                "Solo dentro del mismo equipo", "Señal mínima permitida (dBm)",
                                "Límite de señal débil (dBm)", "Equipos incluidos"],
                  "Valor": [pr["bw_max"], pr["max_clientes"], "Sí" if pr["misma_olt"] else "No",
                            pr["pro_min"], pr["pro_degradada"],
                            ", ".join(pr["olts"]) if pr["olts"] else "Todos"]}
                 ).to_excel(w, sheet_name="Parámetros usados", index=False)

d1, d2 = st.columns(2)
d1.download_button("Descargar resultados completos (Excel)", buf.getvalue(),
                   file_name=f"CCM_balance_red_alternativa_{sel}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   width="stretch")
if len(plan):
    d2.download_button(f"Descargar solo el plan de la alternativa {sel} (CSV)",
                       plan.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"CCM_plan_trabajo_alternativa_{sel}.csv", mime="text/csv",
                       width="stretch")

# ----------------------------------------------------------------------
# Detalle técnico (opcional)
# ----------------------------------------------------------------------
st.markdown('<div style="height:2.5rem"></div>', unsafe_allow_html=True)
with st.expander("Detalle técnico del modelo (para el equipo de ingeniería)"):
    st.markdown(f"""
Modelo de programación entera mixta resuelto con el método **ε-constraint** (SciPy / HiGHS).

- **Variables:** x<sub>ij</sub> = 1 si la NAP *i* queda en el puerto *j*; U = utilización máxima.
- **F1 (objetivo):** minimizar U, con U ≥ BW<sub>j</sub> / BW<sub>max</sub> para cada puerto.
- **F2 ≤ ε2:** cruces de barrio. **F5 ≤ ε5:** NAPs movidas. Ambos se barren en una malla.
- **F4 ≤ valor actual:** clientes con PRO < {pr['pro_degradada']} dBm.
- Asignaciones con PRO estimada < {pr['pro_min']} dBm prohibidas
  ({num(R['prohibidos'])} combinaciones en este cálculo).
- Capacidad: clientes por puerto ≤ {pr['max_clientes']}.
- Desempates: {modelo.DELTA} · F2 y {modelo.DELTA_MOV} · F5 en la función objetivo.
- Límite por problema: {num(pr['nodos_max'])} nodos o {num(pr['tiempo_max'])} s.
- Instancia: {num(R['n_naps'])} NAPs, {num(R['n_puertos'])} puertos,
  {num(R['n_usuarios'])} usuarios ({num(R['n_fijos'])} sin NAP, tratados como carga fija).
""", unsafe_allow_html=True)
    tec = tabla.rename(columns={"sol": "Solución", "eps2": "ε2", "eps5": "ε5", "U": "U (F1)",
                                "F2": "F2", "F4": "F4", "F5": "F5",
                                "exacta": "Óptimo garantizado", "tiempo": "Tiempo (s)",
                                "pareto": "Pareto"})
    st.dataframe(tec.drop(columns=["mejor_balance"], errors="ignore"), hide_index=True,
                 width="stretch")

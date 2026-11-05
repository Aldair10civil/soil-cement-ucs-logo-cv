# -*- coding: utf-8 -*-
"""
================================================================================
app.py - Predictor Suelo-Cemento CNP Peru (interfaz Streamlit)
================================================================================
Ejecutar:  py -3.11 -m streamlit run app.py
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_DIR = Path(__file__).resolve().parent
_MODELO_DIR = _DIR / "models"
for p in (_DIR, _MODELO_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from predictor import predecir                                   # noqa: E402
from clasificacion import clasificar_aashto_detallado, SIGNIFICADO_SUCS  # noqa: E402
from region import REGIONES, NOTA_SALES_CAL, sugerir_region       # noqa: E402
from estabilizadores import evaluar_estabilizadores, APTO, NO_APTO, NO_VERIFICADO  # noqa: E402
from curva import (curva_dosificacion, encontrar_optimo, rango_fhwa,   # noqa: E402
                   dosificacion_practica, Y1_MIN_MPA, Y1_MIN_KGCM2, MPA_A_KGCM2)
from reporte import generar_texto_informe, generar_pdf, AVISO_LEGAL   # noqa: E402

st.set_page_config(page_title="Predictor Suelo-Cemento CNP Peru",
                   page_icon="🛣️", layout="wide")

SEMAFORO = {APTO: "🟢", NO_APTO: "🔴", NO_VERIFICADO: "🟡",
           True: "🟢", False: "🔴"}

# ------------------------------------------------------------------ helpers
def semaforo(ok: bool) -> str:
    return "🟢" if ok else "🔴"


def init_state():
    defaults = {"quimico": {}, "predicho": None, "curva_df": None,
               "estab_resultados": None, "clasif": None}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


init_state()

st.title("🛣️ Predictor Suelo-Cemento para Caminos No Pavimentados (CNP)")
st.caption("Herramienta de prediseno para estabilizacion de suelos con cemento.")
st.warning(AVISO_LEGAL, icon="⚠️")

# ============================================================================
# CAPA 0.1 — UBICACION DEL PROYECTO
# ============================================================================
st.header("Paso 1 — Ubicacion y contexto del proyecto")
c1, c2, c3 = st.columns(3)
with c1:
    departamento = st.text_input("Departamento", "Ayacucho")
    provincia = st.text_input("Provincia", "Huamanga")
with c2:
    distrito = st.text_input("Distrito", "")
    nombre_proyecto = st.text_input("Nombre del proyecto", "Camino vecinal")
with c3:
    altitud = st.number_input("Altitud (m.s.n.m.)", min_value=0, max_value=6000,
                              value=3200, step=50)
    imd = st.number_input("IMD - Indice Medio Diario de transito (veh/dia)",
                          min_value=0, value=0, step=10)

sugerida, ambiguo, candidatas = sugerir_region(altitud)
if ambiguo:
    st.info(f"A {altitud} m.s.n.m. la region no es unica por altitud (el "
           f"Cuadro N02 MTC solapa Costa/Sierra/Ceja de Selva en ciertas "
           f"cotas). Confirme la region segun la vertiente de su proyecto.")
region_sel = st.selectbox("Region (confirme o corrija la sugerencia)",
                          options=list(REGIONES.keys()),
                          index=list(REGIONES.keys()).index(sugerida))
if altitud > 3000:
    st.info("Altitud > 3000 msnm: aplicar consideraciones especiales de "
           "climas frios en curado y tiempos de compactacion.", icon="🥶")

info_region = REGIONES[region_sel]
with st.expander(f"Cuadro N02 MTC — Alternativas aplicables en {region_sel}",
                 expanded=True):
    st.markdown(f"**Suelos predominantes:** {info_region['suelos']}")
    st.markdown(f"**Estabilizadores aplicables:** "
               f"{', '.join(info_region['estabilizadores'])}")
    st.caption(NOTA_SALES_CAL)

st.divider()

# ============================================================================
# CAPA 0.1(b) — PROPIEDADES DEL SUELO (comunes a clasificacion + RNA)
# ============================================================================
st.header("Paso 2 — Propiedades del suelo")
st.caption("Ensayos MTC E-107 (granulometria), E-110/E-111 (Atterberg), "
          "E-115 (Proctor Modificado).")

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Granulometria")
    X1 = st.number_input("X1 - Grava, % ret. N4", 0.0, 100.0, 55.0, 0.1)
    X2 = st.number_input("X2 - Arena, % pasa N4 ret. N200", 0.0, 100.0, 30.0, 0.1)
    X3 = st.number_input("X3 - Finos, % pasa N200", 0.0, 100.0, 15.0, 0.1)
    suma = X1 + X2 + X3
    if abs(suma - 100) > 2:
        st.error(f"Error: granulometria no suma 100% (suma actual = {suma:.1f}%)")
    else:
        st.success(f"Granulometria OK (suma = {suma:.1f}%)")
with col2:
    st.subheader("Atterberg")
    np_suelo = st.checkbox("Suelo No Plastico (NP)")
    if np_suelo:
        X4 = X5 = X6 = 0.0
        st.caption("LL = LP = IP = 0 (No Plastico)")
    else:
        X4 = st.number_input("X4 - Limite Liquido LL (%)", 0.0, 100.0, 20.0, 0.1)
        X5 = st.number_input("X5 - Limite Plastico LP (%)", 0.0, 100.0, 15.0, 0.1)
        X6 = max(0.0, X4 - X5)
        st.metric("X6 - Indice de Plasticidad IP", f"{X6:.1f} %")
with col3:
    st.subheader("Compactacion (Proctor Modificado E-115)")
    X7 = st.number_input("X7 - OCH (%)", 0.0, 40.0, 9.0, 0.1)
    X8 = st.number_input("X8 - MDS (g/cm3)", 1.0, 3.0, 2.10, 0.001, format="%.3f")
    if X8 <= 1.5:
        st.warning("Verificar dato de compactacion (MDS <= 1.5 g/cm3 es inusual).")

suelo_x1_x6 = {"X1": X1, "X2": X2, "X3": X3, "X4": X4, "X5": X5, "X6": X6}
clasif = clasificar_aashto_detallado(X1, X2, X3, X4, X5, X6)
st.session_state["clasif"] = clasif

cA, cB = st.columns([1, 2])
with cA:
    st.metric("Clasificacion AASHTO", clasif["grupo"])
    st.metric("Categoria", clasif["categoria"])
    st.metric("Exigencia Durham normativa", f"<= {clasif['exigencia_durham']:.0f} %")
with cB:
    st.markdown(f"**SUCS probable:** {', '.join(clasif['sucs_probable']) or '-'}  ")
    st.markdown(f"**SUCS posible:** {', '.join(clasif['sucs_posible']) or '-'}  ")
    st.markdown(f"**SUCS posible pero improbable:** "
               f"{', '.join(clasif['sucs_improbable']) or '-'}")
    with st.popover("Significado de las siglas SUCS"):
        for k, v in SIGNIFICADO_SUCS.items():
            st.markdown(f"**{k}** = {v}")

if clasif["grupo"] in ("A-4", "A-5", "A-6", "A-7-5", "A-7-6"):
    st.warning(f"🟡 Suelo arcilloso/limoso detectado (clasificacion "
              f"{clasif['grupo']}). Suelo-cemento es tecnicamente posible pero "
              "economicamente no recomendable para carreteras no pavimentadas "
              "(CNP). Considere estabilizacion con cal o evalue otra cantera "
              "con material granular.", icon="🟡")
else:
    st.success("🟢 Suelo granular apto para estabilizacion con cemento Portland.")

st.divider()

# ============================================================================
# CAPA 0.3/0.4 — SELECTOR DE ALTERNATIVA (estabilizadores)
# ============================================================================
st.header("Paso 3 — Evaluacion de alternativas de estabilizador (Cuadro 9.2 MTC)")
st.caption("La norma RD-003-2015 MTC exige evaluar minimo 3 estabilizadores a "
          "nivel de laboratorio antes de elegir la solucion basica.")

with st.expander("Parametros quimicos (opcionales, mejoran la evaluacion)"):
    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
    cmo = qc1.number_input("Materia organica CMO (%)", value=None,
                           min_value=0.0, max_value=100.0, step=0.1)
    sulfatos = qc2.number_input("Sulfatos SO4 (%)", value=None,
                                min_value=0.0, max_value=100.0, step=0.01)
    equiv_arena = qc3.number_input("Equivalente de arena (%)", value=None,
                                   min_value=0.0, max_value=100.0, step=1.0)
    abrasion = qc4.number_input("Abrasion Los Angeles (%)", value=None,
                                min_value=0.0, max_value=100.0, step=1.0)
    ph = qc5.number_input("pH", value=None, min_value=0.0, max_value=14.0, step=0.1)
    st.caption("Si no se ingresan, el criterio queda 'no verificado' — nunca "
              "se asume que un estabilizador es apto sin dato.")

quimico = {"CMO": cmo, "sulfatos": sulfatos, "equiv_arena": equiv_arena,
          "abrasion": abrasion, "ph": ph}

if st.button("🔍 Evaluar alternativas de estabilizador", type="primary"):
    st.session_state["estab_resultados"] = evaluar_estabilizadores(
        suelo_x1_x6, clasif["grupo"], quimico)

if st.session_state["estab_resultados"]:
    filas = []
    for r in st.session_state["estab_resultados"]:
        fallas = [d for d, e in r["criterios"] if e == NO_APTO]
        no_verif = [d for d, e in r["criterios"] if e == NO_VERIFICADO]
        detalle = "; ".join(fallas) if fallas else ("; ".join(no_verif) if no_verif else "-")
        filas.append({"Estabilizador": r["nombre"],
                      "Suelo apto": SEMAFORO[r["estado"]],
                      "Restriccion / dato faltante": detalle,
                      "Dosificacion": r["dosificacion"], "Curado": r["curado"]})
    st.dataframe(pd.DataFrame(filas), width='stretch', hide_index=True)
    st.caption("🟢 Apto  🔴 No apto  🟡 No verificado (falta dato quimico)")
    st.success(f"Se evaluaron {len(st.session_state['estab_resultados'])} "
              "estabilizadores (cumple el minimo normativo de 3).")

alternativa = st.radio("Alternativa a desarrollar en detalle:",
                       ["Cemento Portland"] + [r["nombre"] for r in
                        (st.session_state["estab_resultados"] or []) if
                        r["nombre"] != "Cemento Portland"],
                       horizontal=True)

if alternativa != "Cemento Portland":
    r = next(r for r in st.session_state["estab_resultados"] if r["nombre"] == alternativa)
    st.info(f"**Modelo predictivo no disponible para {alternativa}.** Se "
           f"identifica como trabajo futuro. Parametros de control "
           f"(informativos): dosificacion {r['dosificacion']}, curado "
           f"{r['curado']}, normas {r['normas']}.")
    st.stop()

st.divider()

# ============================================================================
# CAPA 1 — FILTRO NORMATIVO MTC (cemento Portland)
# ============================================================================
st.header("Paso 4 — Verificacion normativa (Cuadro 9.2 MTC)")
checks = [
    ("Limite Liquido > 40%", X4 > 40, "LL por debajo del limite Cuadro 9.2 MTC"),
    ("Indice de Plasticidad >= 18%", X6 >= 18, "IP por debajo del limite Cuadro 9.2 MTC"),
    ("Finos <= 35%", X3 <= 35, "Exceso de finos para suelo-cemento"),
    ("Granulometria suma 100% (+-2%)", abs(suma - 100) <= 2,
     "Granulometria no suma 100%"),
    ("MDS > 1.5 g/cm3", X8 > 1.5, "Verificar dato de compactacion"),
    ("Clasificacion AASHTO preferente (A-1 a A-3)",
     clasif["grupo"] in ("A-1-a", "A-1-b", "A-3", "A-2-4", "A-2-5", "A-2-6", "A-2-7"),
     "Suelo fuera del rango preferente AASHTO"),
]
tabla_check = pd.DataFrame([{"Criterio": c, "Estado": semaforo(ok),
                            "Observacion": "-" if ok else msg}
                           for c, ok, msg in checks])
st.dataframe(tabla_check, width='stretch', hide_index=True)
if not all(ok for _, ok, _ in checks):
    st.warning("Uno o mas criterios no se cumplen. Puede continuar bajo su "
              "criterio profesional, pero quedara registrado en el reporte.")

rf = rango_fhwa(clasif["grupo"])
if rf:
    st.info(f"Su suelo es **{clasif['grupo']}**. El rango recomendado de "
           f"cemento segun FHWA (Cuadro 9.4) es **{rf[0]} - {rf[1]}%**. Se "
           "sugiere ensayar dentro de este rango.")

st.divider()

# ============================================================================
# CAPA 2 — PREDICCION (un solo punto)
# ============================================================================
st.header("Paso 5 — Prediccion (RNA)")
X9 = st.slider("X9 - Cemento (%, en peso de suelo seco)", 0.5, 15.0, 5.0, 0.1)
if rf and not (rf[0] <= X9 <= rf[1]):
    st.warning(f"Dosificacion fuera del rango recomendado FHWA "
              f"({rf[0]}-{rf[1]}%) para este tipo de suelo.")

if st.button("🔮 PREDECIR", type="primary", width='stretch'):
    entrada = {"X1": X1, "X3": X3, "X4": X4, "X6": X6, "X7": X7, "X8": X8, "X9": X9}
    st.session_state["predicho"] = predecir(entrada)
    st.session_state["entrada_actual"] = entrada

if st.session_state["predicho"]:
    r = st.session_state["predicho"]
    y1, y1kg = r["Y1_MPa"], round(r["Y1_MPa"] * MPA_A_KGCM2, 1)
    y2 = r["durham"]

    if r["avisos"]:
        for a in r["avisos"]:
            st.warning(a, icon="⚠️")

    rc1, rc2 = st.columns(2)
    with rc1:
        st.subheader("Resistencia Y1 (MTC E-1103)")
        st.metric("Resistencia predicha", f"{y1:.2f} MPa  ({y1kg:.1f} kg/cm2)")
        if y1 < Y1_MIN_MPA:
            st.error("🔴 La predicción NO SUPERA el minimo normativo de la "
                    "RD N°003-2015-MTC/14 (18 kg/cm2, evaluación preliminar). "
                    "Aumentar % cemento o evaluar otra cantera.")
        elif y1 < 2.0:
            st.warning("🟡 La predicción SUPERA el minimo normativo (evaluación "
                      "preliminar). Verificar con ensayo MTC E-1103.")
        elif y1 < 3.0:
            st.success("🟢 La predicción supera el minimo normativo con margen "
                      "adecuado (evaluación preliminar). Dosificacion aceptable "
                      "sujeta a verificación experimental.")
        else:
            st.success("🟢 La predicción supera holgadamente el minimo normativo "
                      "(evaluación preliminar). Evaluar reducir % cemento por "
                      "economia, sujeta a verificación experimental.")
        st.caption(f"R2 LOGO (suelo nuevo) = 0.467 · R2 LODO "
                  "(dosis faltante del mismo suelo) = 0.64")
    with rc2:
        st.subheader("Durabilidad Y2 (MTC E-1104, Durham)")
        if y2["veredicto"] == "CUMPLE":
            st.success(f"🟢 Veredicto del clasificador: CUMPLE (evaluación preliminar)")
        else:
            st.error(f"🔴 Veredicto del clasificador: NO CUMPLE (evaluación preliminar)")
        st.caption(f"Exigencia normativa segun grupo AASHTO "
                  f"({clasif['categoria']}): <= {y2['umbral_normativo_pct']:.0f}%")
        st.caption("El 77% NO es la probabilidad de acierto de esta prediccion "
                  "puntual: es la exactitud historica del clasificador sobre "
                  "el conjunto de 22 registros de prueba bajo LOGO-CV (no es "
                  "una probabilidad calibrada por caso). Ademas, el modelo de "
                  "regresion para Y2 tiene R2 LOGO negativo en todos los "
                  "algoritmos probados: el valor numerico de perdida de peso "
                  "no es confiable, solo el veredicto CUMPLE/NO CUMPLE. Se "
                  "requiere ensayo MTC E-1104 para confirmacion.")

st.divider()

# ============================================================================
# CAPA 2(b) — MODO CURVA COMPLETA
# ============================================================================
st.header("Paso 6 — Modo Curva Completa (1% a 10% de cemento)")
if st.button("📈 Generar Curva Completa"):
    base = {"X1": X1, "X3": X3, "X4": X4, "X6": X6, "X7": X7, "X8": X8}
    st.session_state["curva_df"] = curva_dosificacion(base, 1.0, 10.0, 0.5)
    st.session_state["curva_base"] = base

if st.session_state["curva_df"] is not None:
    df = st.session_state["curva_df"]
    opt = encontrar_optimo(df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.cemento, y=df.Y1_MPa, mode="lines+markers",
                             name="Y1 - Resistencia (MPa)", line=dict(color="#2a78d6")))
    fig.add_hline(y=Y1_MIN_MPA, line_dash="dash", line_color="#d03b3b",
                 annotation_text="Minimo normativo 1.765 MPa")
    if opt:
        fig.add_trace(go.Scatter(x=[opt["cemento"]], y=[opt["Y1_MPa"]],
                                 mode="markers", marker=dict(size=16, color="#1baf7a",
                                 symbol="star"), name="Optimo"))
    fig.update_layout(title="Curva de dosificacion: % Cemento vs Resistencia Y1",
                      xaxis_title="Cemento (%)", yaxis_title="Y1 (MPa)",
                      template="plotly_white", height=420)
    st.plotly_chart(fig, width='stretch')

    tabla = df.copy()
    tabla["Cumple Y1"] = tabla.cumple_Y1.map(semaforo)
    tabla["Cumple Y2"] = tabla.cumple_Y2.map(semaforo)
    tabla["Cumple Ambos"] = tabla.apply(
        lambda r: (semaforo(r.cumple_ambos) + " <- OPTIMO"
                  if opt and r.cemento == opt["cemento"] else semaforo(r.cumple_ambos)),
        axis=1)
    st.dataframe(tabla[["cemento", "Y1_MPa", "Y1_kgcm2", "Cumple Y1", "Y2_pct",
                       "Cumple Y2", "Cumple Ambos"]].rename(columns={
                       "cemento": "% Cemento", "Y1_kgcm2": "Y1 (kg/cm2)",
                       "Y2_pct": "Y2 (%)"}),
                width='stretch', hide_index=True)

    if opt:
        kg_m3, bolsas_m3 = dosificacion_practica(opt["cemento"], X8)
        st.session_state["dosif_practica"] = (kg_m3, bolsas_m3)
        st.success(f"**% cemento OPTIMO = {opt['cemento']}%** -> "
                  f"{kg_m3} kg/m3 = {bolsas_m3} bolsas/m3 (bolsa 42.5 kg)")
        costo_bolsa = st.number_input("Precio referencial por bolsa (S/.)",
                                      1.0, 100.0, 28.0, 0.5)
        st.metric("Costo estimado de cemento por m3",
                 f"S/. {bolsas_m3 * costo_bolsa:.2f}")
    else:
        st.session_state["dosif_practica"] = None
        st.error("Ninguna dosificacion entre 1% y 10% cumple ambos criterios "
                "(resistencia y durabilidad). Evalue otra cantera o "
                "estabilizador.")

st.divider()

# ============================================================================
# CAPA 4 — REPORTE
# ============================================================================
st.header("Paso 7 — Reporte de diseno")
st.caption("Metodo de diseno de espesor: USACE/NAASRA para EE <= 10^6, "
          "AASHTO 1993 para EE > 10^6 (modulo informativo, no calculado aqui).")

if st.button("📄 Generar Reporte PDF", type="primary"):
    if not st.session_state["predicho"]:
        st.error("Primero prediga con el boton PREDECIR (Paso 5).")
    else:
        r = st.session_state["predicho"]
        opt = encontrar_optimo(st.session_state["curva_df"]) if \
            st.session_state["curva_df"] is not None else None
        contexto = {
            "proyecto": {"nombre": nombre_proyecto, "departamento": departamento,
                        "provincia": provincia, "distrito": distrito,
                        "altitud": altitud, "region": region_sel, "imd": imd or "no especificado"},
            "suelo": {**suelo_x1_x6, "X7": X7, "X8": X8, "X9": X9},
            "clasif": clasif,
            "y1_mpa": r["Y1_MPa"], "y1_kgcm2": round(r["Y1_MPa"] * MPA_A_KGCM2, 1),
            "y2": r["durham"], "avisos": r["avisos"], "optimo": opt,
            "dosif_practica": st.session_state.get("dosif_practica"),
            "fecha": datetime.now().strftime("%d/%m/%Y"),
        }
        texto = generar_texto_informe(contexto)
        st.text_area("Vista previa del informe", texto, height=300)

        imagen_curva = None
        if st.session_state["curva_df"] is not None:
            imagen_curva = str(_DIR / "_curva_tmp.png")
            try:
                fig.write_image(imagen_curva, width=1000, height=550)
            except Exception:
                imagen_curva = None  # kaleido no instalado: PDF sin grafico

        ruta_pdf = _DIR / f"informe_{nombre_proyecto.replace(' ', '_')}.pdf"
        generar_pdf(texto, ruta_pdf, imagen_curva, nombre_proyecto)
        with open(ruta_pdf, "rb") as f:
            st.download_button("⬇️ Descargar informe PDF", f,
                              file_name=ruta_pdf.name, mime="application/pdf")

st.divider()
st.caption("Software SUELO-CEMENTO CNP PERU -- herramienta de prediseno preliminar.")

# -*- coding: utf-8 -*-
"""
================================================================================
curva.py - Modo Curva Completa: predice Y1/Y2 para 1%-10% de cemento
Software predictor suelo-cemento CNP Peru
================================================================================
Envuelve predictor.predecir() (SOFTWARE/models/) para generar la curva de
dosificacion y ubicar el % de cemento OPTIMO: el minimo que cumple Y1>=1.765
MPa (18 kg/cm2, Cuadro N01 MTC) Y el veredicto Durham (Y2) simultaneamente.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

if not getattr(sys, "frozen", False):
    # Modo script: predictor.py vive en ./models, hay que agregarlo a sys.path.
    # Empaquetado (PyInstaller): predictor ya es un modulo interno bundleado
    # (ver build_exe.spec, pathex incluye models/), y __file__ no es fiable
    # bajo congelamiento, asi que se omite este paso.
    _MODELO_DIR = Path(__file__).resolve().parent / "models"
    if str(_MODELO_DIR) not in sys.path:
        sys.path.insert(0, str(_MODELO_DIR))
from predictor import predecir  # noqa: E402

MPA_A_KGCM2 = 10.197
Y1_MIN_MPA = 1.765          # Cuadro N01 MTC (=18.0 kg/cm2)
Y1_MIN_KGCM2 = round(Y1_MIN_MPA * MPA_A_KGCM2, 1)

# Rango de cemento recomendado por grupo AASHTO (FHWA, Cuadro 9.4)
RANGO_FHWA = {
    "A-1-a": (3, 5), "A-1-b": (5, 8),
    "A-2-4": (5, 9), "A-2-5": (5, 9), "A-2-6": (5, 9), "A-2-7": (5, 9),
    "A-3": (7, 11), "A-4": (7, 12), "A-5": (8, 13), "A-6": (9, 15),
    "A-7-5": (10, 16), "A-7-6": (10, 16),
}


def rango_fhwa(grupo_aashto: str):
    return RANGO_FHWA.get(grupo_aashto)


BOLSA_KG = 42.5

# Coeficiente estructural a2 (AASHTO 1993) para la capa de suelo-cemento,
# segun resistencia (ver PROCESO_CONSTRUCTIVO en reporte.py / Cuadro
# "COEFICIENTES ESTRUCTURALES"): a2 = 0.15 a 0.25 para resistencia de
# 30 a 65 kg/cm2. Interpolado linealmente entre esos dos puntos de
# referencia; fuera de ese rango se usa el extremo mas cercano (no se
# extrapola mas alla de la referencia).
A2_MIN, A2_MAX = 0.15, 0.25
Y1_KGCM2_A2_MIN, Y1_KGCM2_A2_MAX = 30.0, 65.0


def coeficiente_estructural_a2(y1_kgcm2: float) -> float:
    """a2 (AASHTO 1993) estimado a partir de la resistencia Y1 (kg/cm2). Es
    un dato de SALIDA para que el ingeniero lo use en su propio calculo de
    espesor con AASHTO 1993 (SN = a2 x D2 x m2) -- requiere ademas CBR de
    subrasante y ejes equivalentes del proyecto especifico, que este
    software no tiene, por lo que NO calcula espesor ni costo."""
    t = (y1_kgcm2 - Y1_KGCM2_A2_MIN) / (Y1_KGCM2_A2_MAX - Y1_KGCM2_A2_MIN)
    t = max(0.0, min(1.0, t))
    return round(A2_MIN + t * (A2_MAX - A2_MIN), 3)


def dosificacion_practica(pct_cemento: float, mds_g_cm3: float,
                          bolsa_kg: float = BOLSA_KG) -> dict:
    """
    Cantidad de cemento por m3 de MEZCLA (no depende del espesor de capa ni
    de precios -- eso requiere datos especificos del proyecto que el
    software no tiene, ver coeficiente_estructural_a2()):
      kg/m3   = (%cemento/100) x MDS x 1000
      bolsas/m3 = kg/m3 / 42.5
    """
    kg_m3 = (pct_cemento / 100.0) * mds_g_cm3 * 1000.0
    bolsas_m3 = kg_m3 / bolsa_kg
    return {"kg_m3": round(kg_m3, 1), "bolsas_m3": round(bolsas_m3, 2)}


def curva_dosificacion(datos_base: dict, x9_min=1.0, x9_max=12.0, paso=0.5) -> pd.DataFrame:
    """
    datos_base: dict con X1,X3,X4,X6,X7,X8 (SIN X9, se varia aqui).
    Retorna DataFrame: cemento, Y1_MPa, Y1_kgcm2, cumple_Y1, Y2_pct,
    Y2_veredicto, exigencia_durham, cumple_Y2, cumple_ambos, grupo_aashto,
    kg_m3, bolsas_m3 (cemento por m3 de mezcla), a2 (coeficiente estructural
    AASHTO 1993 estimado desde Y1, dato de salida para el diseno de espesor
    que el ingeniero hace aparte -- este software no calcula espesor ni costo).
    """
    filas = []
    x9 = x9_min
    while x9 <= x9_max + 1e-9:
        entrada = dict(datos_base); entrada["X9"] = round(x9, 2)
        r = predecir(entrada)
        cumple_y1 = r["Y1_MPa"] >= Y1_MIN_MPA
        cumple_y2 = r["durham"]["veredicto"] == "CUMPLE"
        y1_kgcm2 = round(r["Y1_MPa"] * MPA_A_KGCM2, 1)
        dp = dosificacion_practica(entrada["X9"], datos_base["X8"])
        filas.append({
            "cemento": entrada["X9"],
            "Y1_MPa": r["Y1_MPa"],
            "Y1_kgcm2": y1_kgcm2,
            "cumple_Y1": cumple_y1,
            "Y2_pct": r["durham"]["Y2_perdida_pct"],
            "Y2_veredicto": r["durham"]["veredicto"],
            "exigencia_durham": r["durham"]["umbral_normativo_pct"],
            "cumple_Y2": cumple_y2,
            "cumple_ambos": cumple_y1 and cumple_y2,
            "grupo_aashto": r["clasificacion_aashto"]["grupo"],
            "a2": coeficiente_estructural_a2(y1_kgcm2),
            **dp,
        })
        x9 = round(x9 + paso, 2)
    return pd.DataFrame(filas)


def encontrar_optimo(df: pd.DataFrame):
    """Primera fila (menor % cemento) que cumple AMBOS criterios, o None."""
    ok = df[df.cumple_ambos]
    if ok.empty:
        return None
    return ok.iloc[0].to_dict()


def evaluar_escenario(y1_mpa: float, y2_pct: float, limite_durham: float) -> dict:
    """
    Evalua el escenario combinado resistencia (Y1, MTC E-1103) + durabilidad
    (Y2 Durham, MTC E-1104) para UNA dosificacion puntual. 4 de los 5
    escenarios posibles (el 5to, "ninguna dosis del rango normativo cumple",
    se evalua sobre toda la curva 1%-12% -- ver mensaje_ninguna_dosis_cumple).
    Devuelve {"escenario": 1-4, "color": str, "mensaje": str}.
    """
    cumple_y1 = y1_mpa >= Y1_MIN_MPA
    cumple_y2 = y2_pct <= limite_durham
    y1_kg = round(y1_mpa * MPA_A_KGCM2, 1)

    if cumple_y1 and cumple_y2:
        return {"escenario": 1, "color": "verde",
                "mensaje": ("ESTIMACION PRELIMINAR: el modelo predice que esta "
                           "dosificacion alcanza los umbrales de resistencia (MTC "
                           "E-1103) y durabilidad (MTC E-1104). Pendiente de "
                           "verificacion mediante el ensayo de laboratorio "
                           "correspondiente y de los demas requisitos obligatorios "
                           "del Cuadro 9.2 (materia organica, sulfatos, abrasion) "
                           "no evaluados por este software. NO constituye "
                           "aprobacion ni aceptacion para diseno.")}
    if cumple_y1 and not cumple_y2:
        return {"escenario": 2, "color": "naranja",
                "mensaje": (f"ESTIMACION PRELIMINAR: cumple resistencia pero NO "
                           f"cumple durabilidad. Perdida Durham estimada = "
                           f"{y2_pct:.1f}%. Maximo admisible = {limite_durham:.0f}%. "
                           "La mezcla tendria resistencia suficiente pero se "
                           "degradaria prematuramente ante ciclos de "
                           "humedecimiento y secado, segun el modelo predictivo "
                           "(pendiente de verificacion experimental). "
                           f"Sugerencia: evaluar aumentar el % de cemento hasta "
                           f"que Y2 <= {limite_durham:.0f}%.")}
    if cumple_y2 and not cumple_y1:
        return {"escenario": 3, "color": "naranja",
                "mensaje": (f"ESTIMACION PRELIMINAR: cumple durabilidad pero NO "
                           f"cumple resistencia. Resistencia estimada = "
                           f"{y1_mpa:.2f} MPa ({y1_kg:.1f} kg/cm2). Minimo "
                           f"requerido = {Y1_MIN_MPA:.3f} MPa ({Y1_MIN_KGCM2:.1f} "
                           "kg/cm2). La mezcla seria durable pero no soportaria "
                           "las cargas de trafico, segun el modelo predictivo "
                           "(pendiente de verificacion experimental). Sugerencia: "
                           f"evaluar aumentar el % de cemento hasta que Y1 >= "
                           f"{Y1_MIN_MPA:.3f} MPa.")}
    return {"escenario": 4, "color": "rojo",
            "mensaje": (f"ESTIMACION PRELIMINAR: no cumple resistencia ni "
                       f"durabilidad. Resistencia estimada = {y1_mpa:.2f} MPa "
                       f"(min: {Y1_MIN_MPA:.3f} MPa). Perdida Durham estimada = "
                       f"{y2_pct:.1f}% (max: {limite_durham:.0f}%), segun el "
                       "modelo predictivo. La dosificacion actual parece "
                       "insuficiente. Sugerencia: evaluar aumentar "
                       "significativamente el % de cemento; confirmar con "
                       "ensayo de laboratorio.")}


def mensaje_ninguna_dosis_cumple() -> dict:
    """Escenario 5: barrido 1%-12% completo y ninguna dosis cumple ambos
    criterios simultaneamente (encontrar_optimo() devolvio None)."""
    return {"escenario": 5, "color": "rojo_oscuro",
            "mensaje": ("ESTIMACION PRELIMINAR: segun el modelo predictivo, "
                       "ninguna dosificacion dentro del rango normativo MTC "
                       f"(1%-12%) alcanzaria simultaneamente resistencia "
                       f"(>= {Y1_MIN_MPA:.3f} MPa) y durabilidad. Esto no "
                       "constituye una declaracion de no aptitud definitiva -- "
                       "requiere confirmacion mediante ensayo de laboratorio. "
                       "Se recomienda evaluar estabilizadores alternativos segun "
                       "Cuadro 9.1/9.2 MTC: Cal (si IP >= 10%), Emulsion "
                       "asfaltica (si IP <= 8%), Cloruro de calcio (si IP <= 15%), "
                       "u otros productos quimicos -- ver Etapa 6 (Reporte) para "
                       "el detalle de restricciones por tipo de suelo.")}


if __name__ == "__main__":
    base = {"X1": 55.14, "X3": 8.82, "X4": 16.44, "X6": 3.91, "X7": 9.0, "X8": 2.173}
    df = curva_dosificacion(base)
    print(df.to_string(index=False))
    opt = encontrar_optimo(df)
    print("\nOptimo:", opt)
    print("\nRango FHWA A-1-a:", rango_fhwa("A-1-a"))

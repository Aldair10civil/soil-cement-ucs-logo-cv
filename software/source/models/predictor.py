# -*- coding: utf-8 -*-
"""
================================================================================
predictor.py  -  Modulo de inferencia para el SOFTWARE de prediccion
Proyecto : RNA suelo-cemento
Requiere : py -3.11 (scikit-learn, joblib, numpy)  ->  py -3.11 -m pip install joblib scikit-learn
================================================================================
Carga los modelos 'best' (modelo_Y1_best.joblib, modelo_Y2_best.joblib) y expone
una funcion predecir() lista para conectar a una GUI (Tkinter/PyQt) o web
(Flask/Streamlit). Equivale al wrapper de inferencia de una CNN.

USO RAPIDO
----------
    from predictor import predecir
    r = predecir({"X1": 55.0, "X3": 8.0, "X4": 16.0, "X6": 4.0,
                  "X7": 9.0, "X8": 2.17, "X9": 5.0})
    print(r["Y1_MPa"], r["durham"]["veredicto"])

CLI
---
    py -3.11 predictor.py                      # corre el ejemplo
    py -3.11 predictor.py 55 8 16 4 9 2.17 5   # X1 X3 X4 X6 X7 X8 X9
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import joblib

def _base_dir():
    # Empaquetado con PyInstaller: los datos van en sys._MEIPASS/models
    # (ver SOFTWARE/build_exe.spec). En modo script, es la carpeta de este archivo.
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "models"
    return Path(__file__).resolve().parent


_DIR = _base_dir()
_CACHE = {}

# Suelos con curva verificada en el dataset de entrenamiento (v7) con finos >35%:
# solo USIL Mazamari C-5 (1 de 23 suelos). El modelo es, en la practica,
# un modelo de suelos GRANULARES; A-4 a A-7 estan casi sin representar.
_SUELOS_FINOS_EN_ENTRENAMIENTO = 1
_SUELOS_TOTAL_ENTRENAMIENTO = 23


def _cargar(nombre):
    if nombre not in _CACHE:
        _CACHE[nombre] = joblib.load(_DIR / f"modelo_{nombre}_best.joblib")
    return _CACHE[nombre]


def clasificar_aashto(finos, ll, ip):
    """
    Clasificacion AASHTO simplificada (M 145) a partir de finos (% pasa N200),
    LL e IP, y la exigencia normativa de perdida Durham (MTC E-1104) segun el
    grupo. No distingue subgrupos que no cambian la exigencia (p.ej. A-1-a vs
    A-1-b, o A-7-5 vs A-7-6), porque el dataset no registra % pasa N40.

    Tabla (MTC / PCA):
      A-1, A-2-4, A-2-5, A-3            (granular)    -> perdida Durham <=14 %
      A-2-6, A-2-7, A-4, A-5            (transicion)  -> perdida Durham <=10 %
      A-6, A-7                          (arcilla)     -> perdida Durham <=7 %
    """
    ip = ip or 0.0
    if finos <= 35:
        if ip > 10:
            return {"grupo": "A-2-6 / A-2-7", "categoria": "transicion",
                    "exigencia_durham": 10.0}
        return {"grupo": "A-1 / A-2-4 / A-2-5 / A-3", "categoria": "granular",
                "exigencia_durham": 14.0}
    else:
        if ip > 10:
            return {"grupo": "A-6 / A-7", "categoria": "arcilla",
                    "exigencia_durham": 7.0}
        return {"grupo": "A-4 / A-5", "categoria": "transicion",
                "exigencia_durham": 10.0}


def _predecir_uno(bundle, x_vec):
    xs = bundle["scaler_X"].transform(x_vec.reshape(1, -1))
    y = bundle["modelo"].predict(xs).reshape(-1, 1)
    return float(bundle["scaler_y"].inverse_transform(y).ravel()[0])


def _avisos_rango(bundle, datos):
    """Advierte si alguna entrada esta fuera del rango de entrenamiento."""
    avisos = []
    for f in bundle["features"]:
        lo, hi = bundle["rangos"][f]
        if datos[f] < lo or datos[f] > hi:
            avisos.append(f"{f} ({datos[f]}) fuera del rango entrenado [{lo}, {hi}]")
    return avisos


def _confianza_y2(bundle, datos):
    """
    Nivel de confianza de la prediccion Y2 segun que tan parecido es el suelo
    de entrada al dataset de entrenamiento (bundle["rangos"], especifico de
    Y2 -- SOLO 22 filas, distinto del rango de Y1). 3 niveles:
      ALTA  (verde)  : todas las variables dentro del rango entrenado.
      MEDIA (amarillo): dentro del rango, pero alguna a <=10% del limite.
      BAJA  (rojo)   : alguna variable fuera del rango (extrapolacion).
    """
    fuera, cerca_borde = [], []
    for f in bundle["features"]:
        lo, hi = bundle["rangos"][f]
        v = datos[f]
        if v < lo or v > hi:
            fuera.append(f)
            continue
        margen = (hi - lo) * 0.10
        if margen > 0 and (v <= lo + margen or v >= hi - margen):
            cerca_borde.append(f)

    n = bundle.get("n_LOGO") or bundle["metricas"].get("n_LOGO", "?")
    if fuera:
        vars_txt = ", ".join(fuera)
        return {
            "nivel": "BAJA", "color": "rojo",
            "variables": fuera,
            "mensaje": (f"Confianza: BAJA. Este suelo tiene propiedades fuera del "
                       f"rango de entrenamiento del modelo Y2 ({vars_txt}; el modelo "
                       f"solo tiene {n} datos disponibles). El valor de Y2 mostrado es "
                       "una EXTRAPOLACION y NO debe usarse para diseno sin validar. "
                       "Se REQUIERE ensayo MTC E-1104 en laboratorio."),
        }
    if cerca_borde:
        vars_txt = ", ".join(cerca_borde)
        return {
            "nivel": "MEDIA", "color": "amarillo",
            "variables": cerca_borde,
            "mensaje": (f"Confianza: MEDIA. Las variables {vars_txt} de este suelo "
                       "estan cerca del limite del rango de datos de entrenamiento "
                       f"del modelo Y2 (solo {n} datos disponibles). Se recomienda "
                       "validar con ensayo MTC E-1104."),
        }
    return {
        "nivel": "ALTA", "color": "verde",
        "variables": [],
        "mensaje": ("Confianza: ALTA (suelo dentro del rango de datos de "
                   f"entrenamiento del modelo Y2, {n} datos)."),
    }


def predecir(datos: dict) -> dict:
    """
    datos: dict con las 7 variables Config A:
        X1 Grava(%ret N4), X3 Finos(%pasa N200), X4 LL, X6 IP,
        X7 OCH(%), X8 MDS(g/cm3), X9 Cemento(%)
    Devuelve dict con Y1 (resistencia MPa), Durham (Y2 % + veredicto MTC) y avisos.
    """
    bY1, bY2 = _cargar("Y1"), _cargar("Y2")
    feats = bY1["features"]
    faltan = [f for f in feats if f not in datos]
    if faltan:
        raise ValueError(f"Faltan variables de entrada: {faltan}")

    # Entradas fisicamente invalidas (no "fuera de dominio", sino imposibles
    # segun su definicion de ensayo) se rechazan aqui, ANTES de los avisos de
    # rango/extrapolacion de _avisos_rango. Esto distingue un dato imposible
    # (requiere corregir la entrada) de un dato valido pero extrapolado
    # (requiere solo advertencia).
    if datos.get("X6", 0.0) is not None and float(datos.get("X6", 0.0)) < 0:
        raise ValueError(
            f"X6 (IP = {datos['X6']}) es fisicamente invalido: el indice de "
            "plasticidad no puede ser negativo (IP = LL - LP >= 0 por "
            "definicion del ensayo MTC E-111/E-112). Corrija el dato de "
            "entrada; esto no es una advertencia de extrapolacion.")
    if datos.get("X3", 0.0) is not None and not (0.0 <= float(datos.get("X3", 0.0)) <= 100.0):
        raise ValueError(
            f"X3 (Finos = {datos['X3']}%) es fisicamente invalido: debe estar "
            "entre 0% y 100% (porcentaje que pasa el tamiz N200).")
    if datos.get("X9", 0.0) is not None and float(datos.get("X9", 0.0)) < 0:
        raise ValueError(
            f"X9 (Cemento = {datos['X9']}%) es fisicamente invalido: la "
            "dosificacion de cemento no puede ser negativa.")

    x = np.array([float(datos[f]) for f in feats])

    y1 = _predecir_uno(bY1, x)
    # El modelo Y2 es una regresion lineal (Ridge): en dosificaciones altas
    # puede extrapolar a valores negativos, fisicamente imposibles (no se
    # puede perder masa negativa). Se limita a 0 -- es un piso fisico, NO
    # un ajuste de calibracion sobre el valor predicho.
    y2 = max(0.0, _predecir_uno(bY2, x))

    clasif = clasificar_aashto(datos["X3"], datos.get("X4", 0.0), datos.get("X6", 0.0))
    umbral = clasif["exigencia_durham"]

    avisos = _avisos_rango(bY1, datos)
    if clasif["categoria"] != "granular":
        avisos.append(
            f"Suelo {clasif['categoria']} (grupo AASHTO estimado {clasif['grupo']}). "
            f"El modelo se entreno casi exclusivamente con suelos granulares "
            f"({_SUELOS_FINOS_EN_ENTRENAMIENTO} de {_SUELOS_TOTAL_ENTRENAMIENTO} "
            "suelos del dataset tienen finos >35 %). La prediccion para este "
            "tipo de suelo es referencial: se recomienda ensayo de laboratorio "
            "(E-1103/E-1104) antes de usar el resultado en obra.")

    return {
        "Y1_MPa": round(y1, 3),
        "Y1_confianza": (f"R2 LOGO={bY1['metricas']['R2_LOGO']} (suelo nuevo). "
                         "Para un suelo ya ensayado a 2-3 dosis la curva es "
                         "mucho mas exacta."),
        "clasificacion_aashto": clasif,
        "durham": {
            "Y2_perdida_pct": round(y2, 2),
            "umbral_normativo_pct": umbral,
            "veredicto": "CUMPLE" if y2 < umbral else "NO CUMPLE",
            "exactitud_clasificacion_referencia":
                bY2["metricas"].get("acc_cumple_14pct"),
            "confianza": _confianza_y2(bY2, datos),
        },
        "avisos": avisos,
    }


def _demo(x=None):
    datos = dict(zip(["X1", "X3", "X4", "X6", "X7", "X8", "X9"],
                     x if x else [55.0, 8.0, 16.0, 4.0, 9.0, 2.17, 5.0]))
    print("Entrada:", datos)
    r = predecir(datos)
    c = r["clasificacion_aashto"]
    print(f"  Clasificacion AASHTO estimada: {c['grupo']}  ({c['categoria']})")
    print(f"\n  Resistencia  Y1 = {r['Y1_MPa']} MPa")
    d = r["durham"]
    print(f"  Durabilidad  Y2 = {d['Y2_perdida_pct']} %  ->  {d['veredicto']} "
          f"(exigencia normativa {d['umbral_normativo_pct']}%)")
    if r["avisos"]:
        print("  AVISOS:")
        for a in r["avisos"]:
            print("   -", a)
    print(f"\n  Nota: {r['Y1_confianza']}")


if __name__ == "__main__":
    args = [float(v) for v in sys.argv[1:8]] if len(sys.argv) >= 8 else None
    _demo(args)

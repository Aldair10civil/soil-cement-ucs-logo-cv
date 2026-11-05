# -*- coding: utf-8 -*-
"""
Extension de analisis_Y2.py: matriz de confusion y metricas de
precision/exhaustividad para el clasificador CUMPLE/NO-CUMPLE (Y2<14%),
pedidas por el revisor 2. Reutiliza exactamente la misma logica LOGO
del script original (mismo modelo ganador, misma particion), solo
agrega las metricas de clasificacion que faltaban.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.svm import SVR
from sklearn.metrics import (r2_score, confusion_matrix, precision_score,
                              recall_score, f1_score, accuracy_score)

BASE = Path(r"c:\Users\Diego Tenorio\Desktop\SOFTWARE_ALDAIR")
COL = {"X1_Grava": "X1", "X3_Finos": "X3", "X4_LL": "X4", "X6_IP": "X6",
       "X7_OCH": "X7", "X8_MDS": "X8", "X9_Cemento": "X9", "Y2_Durham": "Y2"}
VS = ["X1", "X3", "X4", "X6", "X7", "X8", "X9"]
UMBRAL = 14.0

df = pd.read_csv(BASE / "dataset_RNA_v7_verificado.csv", sep=";").rename(columns=COL)
d = df[df.Y2.notna()].reset_index(drop=True)
print(f"n={len(d)} filas con Y2 | {d.Suelo.nunique()} suelos")
print(f"Finos (X3) en el subconjunto Y2: min={d.X3.min():.1f}% max={d.X3.max():.1f}%")


def logo(data, model="lineal", seed=0):
    data = data.reset_index(drop=True)
    R, P = [], []
    for g, gi in data.groupby("Suelo").groups.items():
        te, tr = data.loc[gi], data.drop(index=gi)
        if len(tr) < 3:
            continue
        sx = StandardScaler().fit(tr[VS].to_numpy(float))
        sy = StandardScaler().fit(tr[["Y2"]].to_numpy(float))
        Xtr = sx.transform(tr[VS].to_numpy(float))
        ytr = sy.transform(tr[["Y2"]].to_numpy(float)).ravel()
        if model == "lineal":
            m = LinearRegression().fit(Xtr, ytr)
        elif model == "ridge":
            m = Ridge(alpha=10).fit(Xtr, ytr)
        elif model == "mlp":
            m = MLPRegressor(hidden_layer_sizes=(6, 3), activation="relu",
                              max_iter=3000, random_state=seed).fit(Xtr, ytr)
        elif model == "svr":
            m = SVR(kernel="rbf", C=10, gamma="scale").fit(Xtr, ytr)
        p = sy.inverse_transform(
            m.predict(sx.transform(te[VS].to_numpy(float))).reshape(-1, 1)).ravel()
        R += list(te.Y2); P += list(p)
    return r2_score(R, P), np.array(R), np.array(P)


for mdl, nom in [("lineal", "Lineal"), ("ridge", "Ridge(a=10)"),
                  ("mlp", "MLP(6,3)"), ("svr", "SVR-RBF")]:
    if mdl == "mlp":
        runs = [logo(d, mdl, s) for s in range(30)]
        r2 = float(np.mean([r[0] for r in runs]))
    else:
        r2 = logo(d, mdl)[0]
    print(f"{nom:<12} R2_LOGO={r2:+.4f}")

# El modelo reportado/desplegado en el articulo y el software es Ridge(alpha=10),
# no necesariamente el de mejor R2_LOGO entre estos 4 -- se usa ese para que la
# matriz de confusion corresponda exactamente al accuracy de 77% ya publicado.
r2, R, P = logo(d, "ridge")
nombre = "Ridge(a=10)"
print(f"\nModelo usado para la matriz de confusion (el reportado en el articulo): "
      f"{nombre} (R2_LOGO={r2:+.3f})")

y_true = (R < UMBRAL).astype(int)   # 1 = CUMPLE
y_pred = (P < UMBRAL).astype(int)

cm = confusion_matrix(y_true, y_pred, labels=[1, 0])
print("\nMatriz de confusion (filas=real, columnas=predicho; orden CUMPLE, NO-CUMPLE):")
print(pd.DataFrame(cm, index=["Real CUMPLE", "Real NO-CUMPLE"],
                    columns=["Pred CUMPLE", "Pred NO-CUMPLE"]))

acc = accuracy_score(y_true, y_pred)
prec_cumple = precision_score(y_true, y_pred, pos_label=1, zero_division=0)
rec_cumple = recall_score(y_true, y_pred, pos_label=1, zero_division=0)
f1_cumple = f1_score(y_true, y_pred, pos_label=1, zero_division=0)
prec_no = precision_score(y_true, y_pred, pos_label=0, zero_division=0)
rec_no = recall_score(y_true, y_pred, pos_label=0, zero_division=0)
f1_no = f1_score(y_true, y_pred, pos_label=0, zero_division=0)

print(f"\nExactitud global: {acc*100:.1f}% ({int(acc*len(y_true))}/{len(y_true)})")
print(f"CUMPLE     -> precision={prec_cumple:.3f}  exhaustividad={rec_cumple:.3f}  F1={f1_cumple:.3f}  (n={int((y_true==1).sum())})")
print(f"NO-CUMPLE  -> precision={prec_no:.3f}  exhaustividad={rec_no:.3f}  F1={f1_no:.3f}  (n={int((y_true==0).sum())})")

out = pd.DataFrame({
    "clase": ["CUMPLE", "NO-CUMPLE"],
    "n": [int((y_true == 1).sum()), int((y_true == 0).sum())],
    "precision": [prec_cumple, prec_no],
    "exhaustividad": [rec_cumple, rec_no],
    "f1": [f1_cumple, f1_no],
})
out.to_csv(BASE / "ANALISIS_V7" / "Y2_confusion_metrics.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(cm, index=["Real_CUMPLE", "Real_NO_CUMPLE"],
             columns=["Pred_CUMPLE", "Pred_NO_CUMPLE"]).to_csv(
    BASE / "ANALISIS_V7" / "Y2_confusion_matrix.csv", encoding="utf-8-sig")
print("\nGuardado: ANALISIS_V7/Y2_confusion_metrics.csv, Y2_confusion_matrix.csv")

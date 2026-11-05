# -*- coding: utf-8 -*-
"""
Caso representativo de entrada/salida para el apendice del articulo
(observacion 3 del revisor 2): prediccion LOGO-CV real (el suelo
"Cusco KM4+250", fuente HOL, queda COMPLETAMENTE fuera del
entrenamiento) con el modelo Lineal Config A, igual que el reportado
en el articulo. No se elige el caso por que "acierte perfecto" -- se
usa el error real tal como sale del mismo pipeline de validacion.
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

COL = {"X1_Grava": "X1", "X3_Finos": "X3", "X4_LL": "X4", "X6_IP": "X6",
       "X7_OCH": "X7", "X8_MDS": "X8", "X9_Cemento": "X9", "Y1_MPa": "Y1"}
VS = ["X1", "X3", "X4", "X6", "X7", "X8", "X9"]

df = pd.read_csv("dataset_RNA_v7_verificado.csv", sep=";").rename(columns=COL)
d = df[df.Y1.notna()].reset_index(drop=True)

suelo_objetivo = "Cusco KM4+250"
te = d[d.Suelo == suelo_objetivo]
tr = d[d.Suelo != suelo_objetivo]
print(f"Entrenamiento: {len(tr)} filas, {tr.Suelo.nunique()} suelos (sin {suelo_objetivo})")
print(f"Prueba (fuera de entrenamiento): {len(te)} filas de {suelo_objetivo}\n")

sx = StandardScaler().fit(tr[VS].to_numpy(float))
sy = StandardScaler().fit(tr[["Y1"]].to_numpy(float))
m = LinearRegression().fit(sx.transform(tr[VS].to_numpy(float)),
                            sy.transform(tr[["Y1"]].to_numpy(float)).ravel())
pred = sy.inverse_transform(
    m.predict(sx.transform(te[VS].to_numpy(float))).reshape(-1, 1)).ravel()

for (_, row), p in zip(te.iterrows(), pred):
    err = p - row.Y1
    print(f"X9(cemento)={row.X9:>4.1f}%  Y1_real={row.Y1:.3f} MPa  "
          f"Y1_predicho={p:.3f} MPa  error={err:+.3f} MPa")

print(f"\nPropiedades del suelo (constantes en las 4 dosis): "
      f"Grava={te.X1.iloc[0]}%, Finos={te.X3.iloc[0]}%, LL={te.X4.iloc[0]}%, "
      f"IP={te.X6.iloc[0]}%, OCH={te.X7.iloc[0]}%, MDS={te.X8.iloc[0]} g/cm3")

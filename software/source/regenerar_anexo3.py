# -*- coding: utf-8 -*-
"""Regenera el PDF de ejemplo 'Camino Vecinal' (Anexo 3 de la tesis) con el
reporte.py VIGENTE -- el PDF viejo embebido (anexos/reporte_Camino_vecinalok.pdf)
quedo desactualizado: todavia citaba 'MTC CE.020' y referencias PCA con
'[Verificar ano...]', que ya no existen en el codigo actual. No requiere Qt,
solo las funciones puras de calculo + reportlab.
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))

from clasificacion import clasificar_aashto_detallado, verificar_restriccion_usace
from estabilizadores import evaluar_estabilizadores
from curva import curva_dosificacion, encontrar_optimo
from predictor import predecir
from reporte import generar_texto_informe, generar_pdf

# Mismo ejemplo "Camino Vecinal" que el anexo original (suelo granular A-1-a,
# tipico de proyecto de camino vecinal en Ayacucho).
proyecto = {"nombre": "Camino Vecinal - Tramo de ejemplo", "departamento": "Ayacucho",
            "provincia": "Huamanga", "distrito": "Vinchos", "altitud": 3200,
            "region": "Sierra", "imd": 150}
suelo = {"X1": 55.14, "X2": 36.04, "X3": 8.82, "X4": 16.44, "X5": 12.53,
         "X6": 3.91, "X7": 9.0, "X8": 2.173}
X9 = 3.5

clasif = clasificar_aashto_detallado(suelo["X1"], suelo["X2"], suelo["X3"],
                                      suelo["X4"], suelo["X5"], suelo["X6"])
usace = verificar_restriccion_usace(suelo["X1"], suelo["X2"], suelo["X3"],
                                     suelo["X4"], suelo["X6"])
checks_normativa_a = [
    ("Limite Liquido > 40% (Cuadro 9.2)", suelo["X4"] > 40, True, "LL excede el limite MTC"),
    ("Indice de Plasticidad >= 18% (Cuadro 9.2)", suelo["X6"] >= 18, True, "IP excede el limite MTC"),
    ("Materia organica (CMO) < 1.0% (Cuadro 9.2)", None, "amarillo",
     "No verificado -- no mapeado como variable de entrada del modelo RNA "
     "(requiere ensayo de laboratorio independiente; trabajo futuro)."),
    ("Sulfatos (SO4) < 0.2% (Cuadro 9.2)", None, "amarillo",
     "No verificado -- no mapeado como variable de entrada del modelo RNA "
     "(requiere ensayo de laboratorio independiente; trabajo futuro)."),
    ("Abrasion < 50% (Cuadro 9.2)", None, "amarillo",
     "No verificado -- no mapeado como variable de entrada del modelo RNA "
     "(requiere ensayo de laboratorio independiente; trabajo futuro)."),
    (f"Restriccion USACE (Cuadro 9.1, familia {usace['familia']})",
     usace["cumple"], usace["cumple"], usace["restriccion"]),
]

pred = predecir({"X1": suelo["X1"], "X3": suelo["X3"], "X4": suelo["X4"],
                  "X6": suelo["X6"], "X7": suelo["X7"], "X8": suelo["X8"], "X9": X9})

estabs = evaluar_estabilizadores(suelo, clasif["grupo"],
                                  {"CMO": None, "sulfatos": None, "equiv_arena": None,
                                   "abrasion": None, "ph": None})

base_curva = {"X1": suelo["X1"], "X3": suelo["X3"], "X4": suelo["X4"],
              "X6": suelo["X6"], "X7": suelo["X7"], "X8": suelo["X8"]}
df = curva_dosificacion(base_curva, 1.0, 12.0, 0.5)
opt = encontrar_optimo(df)
dosif_practica = ({k: opt[k] for k in ("kg_m3", "bolsas_m3")} if opt else None)

contexto = {
    "proyecto": proyecto,
    "suelo": {**suelo, "X9": X9},
    "clasif": clasif,
    "checks_normativa_a": checks_normativa_a,
    "y1_mpa": pred["Y1_MPa"], "y1_kgcm2": round(pred["Y1_MPa"] * 10.1972, 1),
    "y2": pred["durham"], "avisos": pred["avisos"],
    "optimo": opt, "dosif_practica": dosif_practica,
    "estabilizadores": estabs, "nota_cal": None,
    "fecha": datetime.now().strftime("%d/%m/%Y"),
    "fotos_reporte": [],
}

texto = generar_texto_informe(contexto)
OUT = Path(r"D:\MODELADO ALDAIR\Borrador de tesis Aldair 2026\anexos\reporte_Camino_vecinalok.pdf")
generar_pdf(texto, OUT, proyecto_nombre=proyecto["nombre"], contexto=contexto)
print(f"PDF regenerado: {OUT}  existe={OUT.exists()}  tam={OUT.stat().st_size} bytes")

# Modelo entrenado — el "best" para el software

Equivalente al `best.pt` de una CNN, pero para scikit-learn. **Clave:** el modelo
NO viaja solo — lleva sus *scalers*. Sin ellos la predicción es basura.

## Archivos

| Archivo | Qué es |
|---|---|
| `modelo_Y1_best.joblib` | Modelo de resistencia Y1 + scalers + rangos + métricas |
| `modelo_Y2_best.joblib` | Modelo de durabilidad Durham Y2 (+ veredicto cumple/no) |
| `metadatos.json` | Entradas, salidas, rangos y métricas (legible desde cualquier lenguaje) |
| `predictor.py` | Módulo de inferencia listo para el software |

## Entradas (7 variables, Config A)

| Código | Variable | Rango entrenado |
|---|---|---|
| X1 | Grava (% ret. N°4) | ver metadatos.json |
| X3 | Finos (% pasa N°200) | |
| X4 | Límite Líquido LL | |
| X6 | Índice Plástico IP | |
| X7 | Óptimo Cont. Humedad OCH (%) | |
| X8 | MDS (g/cm³) | |
| X9 | Cemento (%) | |

## Salidas

- **Y1** — resistencia a compresión simple (MPa).
- **Y2** — pérdida Durham (%) + veredicto **CUMPLE / NO CUMPLE**.

### Exigencia Durham: NO es un umbral único

El estabilizado suelo-cemento aplica a **todos** los tipos de suelo AASHTO
(A-1 a A-7) — solo cambia la exigencia de durabilidad, más estricta en suelos
finos/arcillosos (MTC/PCA):

| Grupo AASHTO | Categoría | Pérdida Durham máx. |
|---|---|---|
| A-1, A-2-4, A-2-5, A-3 | Granular | ≤14 % |
| A-2-6, A-2-7, A-4, A-5 | Transición | ≤10 % |
| A-6, A-7 | Arcilla | ≤7 % |

`predictor.py` clasifica automáticamente el suelo de entrada (`clasificar_aashto`,
a partir de X3/X4/X6) y aplica el umbral correcto — **ya no usa 14 % fijo**.

## Cómo usarlo en el software

```python
from predictor import predecir
r = predecir({"X1": 55, "X3": 8, "X4": 16, "X6": 4,
              "X7": 9, "X8": 2.17, "X9": 5})
r["Y1_MPa"]                          # -> 2.33
r["clasificacion_aashto"]["grupo"]   # -> "A-1 / A-2-4 / A-2-5 / A-3"
r["durham"]["veredicto"]             # -> "CUMPLE" (contra el umbral correcto)
r["avisos"]                          # -> [] o advertencias de extrapolación/cobertura
```

## Honestidad que el software DEBE mostrar al usuario

- **R² LOGO Y1 = 0.47** es la exactitud para un suelo **nuevo** (nunca ensayado).
  Sirve como **estimación preliminar / prediseño**, no como reemplazo del ensayo.
- Para completar una dosis faltante de un suelo ya caracterizado por sus propiedades
  (dentro del rango 1-12%), el mismo modelo es más exacto (R² = 0.64, LODO por
  propiedades). **Ojo:** esto NO usa la identidad del suelo ni dosis previas reales
  ya ensayadas de ese suelo específico -- `predictor.py` no implementa ese ajuste;
  solo interpola dentro del rango de propiedades físicas cubierto por el dataset.
  (Existe un modelo experimental de "efectos fijos por suelo" en `camino_r2_090.py`
  que sí llega a R²=0.84 usando la identidad del suelo, pero NO está integrado al
  software -- ver advertencia registrada 2026-08-05.)
- Durham: la clasificación cumple/no-cumple se validó (~77 % acierto) **solo con
  suelos granulares**; el valor exacto de Y2 es siempre referencial.
- Si una entrada sale del `rango_entrenamiento`, el software debe **avisar
  extrapolación** (el módulo ya lo devuelve en `avisos`).
- **Cobertura por tipo de suelo:** el dataset es casi todo granular — solo 1 de
  23 suelos tiene finos >35 % (borde A-6/A-7). Para suelos de transición o
  arcillosos (A-4 a A-7), `predictor.py` ya agrega un aviso explícito
  recomendando ensayo de laboratorio; la predicción ahí es referencial, no una
  limitación normativa (la norma sí permite estabilizar arcillas con cemento),
  sino una limitación de **evidencia empírica** del modelo actual.

## Siguiente paso — envolverlo en interfaz

Tres caminos (todos consumen `predictor.py` sin cambios):
1. **Streamlit** (web local, lo más rápido): `py -3.11 -m pip install streamlit` →
   una página con 7 casillas y un botón. ~40 líneas.
2. **Tkinter** (escritorio, sin instalar nada): formulario nativo de Windows.
3. **Flask/FastAPI** (API): para integrarlo a un sistema mayor.

Pídeme cualquiera de los tres y te lo dejo funcionando.

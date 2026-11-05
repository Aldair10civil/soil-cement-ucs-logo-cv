# Predictor Suelo-Cemento CNP Perú — Software

Aplicación de escritorio (PyQt5) que implementa las 5 capas de los requisitos
(Diego / Aldair — Maestría Geotecnia UNI). También existe una versión web
(Streamlit, `app.py`) previa a la migración, que se mantiene funcional.

## Cómo ejecutarlo (desarrollo)

```
py -3.11 main.py
```

Se abre como ventana de escritorio (PyQt5), con pestañas para cada paso.
Todo corre localmente, sin conexión a internet ni API keys. No requiere GPU
(el modelo es scikit-learn puro: regresión Lineal/Ridge sobre 7 variables,
sin ninguna dependencia de PyTorch/CUDA).

**Versión Streamlit (alternativa web):**
```
py -3.11 -m streamlit run app.py
```

## Compilar a .exe independiente

Ver [BUILD.md](BUILD.md). Resumen: `py -3.11 -m PyInstaller build_exe.spec
--noconfirm`, resultado en `dist/PredictorSueloCemento/` (~300 MB, se
entrega la carpeta completa). Verificado: abre y corre estable sin consola.

## Estructura de carpetas

```
SOFTWARE/
├── main.py              ← entrada de la app de escritorio (PyQt5)
├── app.py                ← version Streamlit (anterior, se mantiene)
├── build_exe.spec         ← receta de PyInstaller
├── assets/                ← logo/imagenes (opcional)
├── models/                ← el "best" entrenado (antes MODELO_ENTRENADO/)
│   ├── modelo_Y1_best.joblib
│   ├── modelo_Y2_best.joblib
│   ├── predictor.py
│   └── metadatos.json
├── output/                ← PDFs generados por el software
├── clasificacion.py / region.py / estabilizadores.py / curva.py / reporte.py
└── requirements.txt
```

Estructura inspirada en la organizacion del software de tesis de un
companero de la UNSCH (assets/, models/, output/, entrada unica) — adaptada
a este proyecto, que no necesita las partes especificas de video/audio de
aquel (es un predictor tabular, no un sistema de vision en tiempo real).

## Archivos de logica (sin cambios entre Streamlit y PyQt5)

| Archivo | Qué hace |
|---|---|
| `clasificacion.py` | AASHTO detallado (A-1-a…A-7-6) + correlación SUCS (Paso 1) |
| `region.py` | Región por altitud (Cuadro N°02) — con selector de confirmación por el solape de rangos |
| `estabilizadores.py` | Aptitud de los 8 estabilizadores (Cuadro 9.2) — nunca asume apto si falta el dato químico |
| `curva.py` | Modo Curva Completa (1-10% cemento) + dosificación práctica (kg/m³, bolsas/m³) |
| `reporte.py` | Informe técnico por plantilla + exportación a PDF (reportlab) |
| `models/predictor.py` | Motor de predicción Y1/Y2 |

La migración a PyQt5 (`main.py`) reutiliza estos 6 módulos **sin tocar su
lógica** — solo cambió la interfaz. `main.py` usa `matplotlib` embebido
(`FigureCanvasQTAgg`) en vez de `plotly` para la curva de dosificación.

## Decisiones tomadas durante la construcción

- **Reporte con plantilla, no LLM real** (confirmado contigo): el texto se
  genera con reglas deterministas, sin costo ni API key. `reporte.py` está
  escrito para que conectar un LLM real después solo requiera reemplazar el
  cuerpo de `generar_texto_informe()`.
- **Región por altitud es ambigua por diseño** (el propio Cuadro N°02 solapa
  Costa/Sierra/Ceja de Selva en ciertas cotas). El software sugiere una
  región y pide confirmación en vez de adivinar en silencio.
- **Parámetros químicos de Capa 0 son opcionales.** Si no se ingresan
  (sulfatos, CMO, equivalente de arena, abrasión, pH), el criterio queda
  "no verificado" (🟡) — nunca se asume que un estabilizador es apto sin el
  dato real.
- **Y2 (Durham) solo se muestra como veredicto**, nunca como valor numérico
  exacto (precisión limitada, ~77% de acierto).
- **No requiere GPU.** El Python 3.11 de este equipo es compartido con otros
  proyectos que sí usan GPU/PyTorch (p.ej. `software_adas`); este software
  no tiene ninguna dependencia de ese tipo. El `.spec` de PyInstaller excluye
  explícitamente esas librerías para que el .exe no las arrastre.

## Verificado antes de entregar

- **PyQt5 (`main.py`):** prueba headless (`QT_QPA_PLATFORM=offscreen`)
  simulando el flujo completo (suelo → estabilizadores → normativa →
  predicción → curva → PDF → bloqueo de alternativas): cero excepciones,
  PDF con gráfica embebida (57 KB).
- **.exe compilado:** lanzado y confirmado corriendo estable vía `tasklist`
  (~150-250 MB de RAM, sin ventana de consola, cierre limpio).
- **Streamlit (`app.py`):** probado con `streamlit.testing.v1.AppTest`,
  cero excepciones.

## Pendiente / próximos pasos posibles

- Módulo de diseño de espesor (USACE/NAASRA, AASHTO 1993) hoy es solo un
  mensaje informativo, no calcula el espesor — lo dice el propio requisito
  ("módulo informativo").
- Conectar un LLM real para el reporte, si más adelante lo decides.
- Ícono personalizado para el .exe (hoy usa el ícono por defecto).

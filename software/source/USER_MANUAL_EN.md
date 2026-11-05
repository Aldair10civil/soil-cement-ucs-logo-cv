# Soil-Cement Predictor for Unpaved Roads in Peru — User Manual (English)

A companion manual for international readers and reviewers of the article
*"Predicting Unconfined Compressive Strength and Wetting-Drying Durability
of Soil-Cement Through Linear Regression with Leave-One-Group-Out
Validation"* (Rojas Fernandez et al., submitted to *Geotechnics*, MDPI).

The software interface itself remains in Spanish, since its intended users
are Peruvian road engineers working under MTC (Ministerio de Transportes y
Comunicaciones) regulations. This manual describes its functioning in
English so that the tool's logic can be inspected and understood without
requiring the reader to operate the Spanish-language interface directly.

## 1. What the tool does, and does not do

The tool estimates, from seven soil index properties and a cement
dosage, the unconfined compressive strength (Y1, MPa, MTC E-1103) and
issues a compliance/non-compliance verdict for the wetting-drying
durability criterion (Y2, MTC E-1104), for **cement-stabilised granular
soils used as a pavement layer** (AASHTO A-1/A-2/A-3, low-to-medium
plasticity), the application for which the underlying dataset and
models were built (see the article's Introduction and Limitations).

**It does not** replace the regulatory laboratory tests, which remain
mandatory before any construction decision. It must not be used for
fine-grained, high-plasticity soils, nor for the subgrade-improvement
application of soil-cement (CBR < 6%), which is outside its training
domain (see the article's Discussion, Section on sampling bias).

**No internet connection, API key or GPU is required.** The deployed
models are plain scikit-learn (Linear Regression for Y1, Ridge for Y2);
the application runs entirely offline on a standard laptop.

## 2. Requirements and how to run it

- Desktop application built with PyQt5 (Python 3.11).
- A standalone Windows executable is provided (`PredictorSueloCemento.exe`,
  ~300 MB, self-contained folder); no Python installation is required to
  run the `.exe`.
- To run from source: `py -3.11 main.py` (see `requirements.txt` for
  dependencies). A previous Streamlit web version (`app.py`) is also
  included and kept functional.

## 3. The six stages (wizard interface)

The interface is organised as a six-step wizard with a lateral timeline.
Each stage's on-screen label (in Spanish) is given alongside its English
description.

| # | Spanish label | Purpose |
|---|---|---|
| 1 | **PROYECTO** (Project) | General project data: name, location, region, road section, date. Used only for the header of the exported report, not as a model input. |
| 2 | **SUELO** (Soil) | Entry of the seven characterisation properties: gravel retained on sieve No. 4 ($X_1$), fines passing sieve No. 200 ($X_3$, MTC E-107), liquid limit ($X_4$) and plasticity index ($X_6$, MTC E-110/E-111), optimum moisture content ($X_7$) and maximum dry density ($X_8$, MTC E-115, Modified Proctor). The tool computes the AASHTO classification and the probable USCS correlation automatically. |
| 3 | **NORMATIVA** (Regulations applied) | Displays the AASHTO group, the soil category (granular or fine), the applicable Durham loss threshold for that group (14%, 10% or 7%, per MTC technical document RD N°003-2015-MTC/14), and an aptitude check for eight possible stabilisers (Cuadro 9.2): a stabiliser is only marked suitable if the chemical data it requires (sulfates, organic matter content, sand equivalent, abrasion, pH) was actually entered — it is never assumed suitable by default when that data is missing. |
| 4 | **PREDICCION** (Prediction) | For a single cement dosage ($X_9$, entered by the user), the tool returns the predicted $Y_1$ (MPa) and, if durability data was requested, the compliance verdict for $Y_2$ (never a numeric weight-loss value — see Section 4 below). |
| 5 | **CURVA COMPLETA** (Full dosage curve) | Sweeps $X_9$ from 1% to 12% and plots the predicted strength curve (embedded Matplotlib figure), together with the practical dosage (kg of cement per m³, bags per m³) and the AASHTO-1993 structural coefficient $a_2$ for the optimum point identified. |
| 6 | **REPORTE** (Report) | Generates a technical report from a deterministic template (not a large language model) and exports it to PDF (via `reportlab`), in an APA-7th-edition-consistent format, consolidating the inputs, the applicable regulation, the prediction and the dosage curve. |

## 4. Important design decisions (and why)

- **The durability classifier ($Y_2$) only ever returns a verdict
  (compliant / non-compliant), never a numerical weight-loss estimate.**
  This is a deliberate restriction: the model was trained on only 22
  records from 14 soils, all granular, and its numeric prediction
  performance under cross-validation was insufficient for a point
  estimate (see the article's Results, confusion matrix in
  Table~2 of the main text). The verdict itself must still be read with
  caution: a recall of zero was measured for the non-compliant class
  during validation, so a "compliant" verdict is not a guarantee.
- **Soil-region assignment by altitude is intentionally left for the
  user to confirm**, rather than decided silently, because the governing
  table (Cuadro N°02) has overlapping altitude ranges between Coast,
  Highlands and high-jungle fringe zones.
- **A stabiliser is marked "not verified"**, not "suitable", whenever the
  chemical test data it requires was not entered, to avoid a false
  positive that could be read as a design recommendation.
- **The report text is generated from a fixed, deterministic template**,
  not from a large language model, so that it carries no usage cost, no
  API dependency and no risk of fabricated content; the function that
  would need to change if a real LLM were connected later is isolated in
  `reporte.py` (`generar_texto_informe()`).

## 5. Worked example (matching Appendix A of the article)

For readers who want to see the tool's input/output behaviour without
running it, the case reported in Appendix A of the article corresponds
to soil "Cusco KM4+250" (source code HOL):

**Inputs** (Stage 2, SUELO): gravel $X_1=64.0\%$, fines $X_3=9.3\%$,
liquid limit $X_4=28.0\%$, plasticity index $X_6=8.0\%$, optimum
moisture content $X_7=8.0\%$, maximum dry density
$X_8=2.159\ \text{g/cm}^3$.

**Output** (Stage 4, PREDICCION, at a cement dosage of $X_9=3.2\%$):
predicted $Y_1 \approx 2.24$~MPa. The technical file for this soil
reports an observed value of $2.11$~MPa at that same dosage (error
$+0.13$~MPa), consistent with the model's leave-one-group-out error
when this soil is excluded entirely from training (Appendix A gives
the full four-dosage curve and situates this error within the range
observed across all 23 soils in the dataset).

## 6. Where to find everything

See the Data Availability Statement of the article for the public
repository containing the dataset, the analysis scripts (leave-one-group-out
cross-validation, SHAP, group-level bootstrap) and this software's
source code and compiled executable.

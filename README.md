# Soil-Cement UCS and Durability Prediction (LOGO-CV)

Data, analysis code and design-tool software supporting the article:

> Rojas Fernández, A.H.; Lizarbe-Alarcón, H.; Berrocal Argumedo, K.; Gutiérrez Palomino, R.J.; Aldana, C.; Saavedra, Y.; Portal Quicaña, E.; Moncada, W.; Portal Quicaña, V.; Lagos, M.; Pereda Medina, A.M.; Lezama Cuellar, C.; Retamozo Fernández, S.W.; Canchari Gutiérrez, E.
> **"Predicting Unconfined Compressive Strength and Wetting-Drying Durability of Soil-Cement Through Linear Regression with Leave-One-Group-Out Validation: Evidence of an Informational Ceiling in Unpaved Roads of Peru."**
> Submitted to *Geotechnics* (MDPI).

## Repository contents

```
dataset/            Verified dataset (84 specimens, 23 soils, CSV, semicolon-separated)
analysis_code/       Python scripts: SHAP + group-level bootstrap, Y2 confusion matrix,
                      illustrative LOGO-CV example (Appendix A of the article)
software/source/     Source code of the "Predictor Suelo-Cemento CNP Perú" design tool
                      (PyQt5 desktop app + legacy Streamlit version)
docs/                English-language user manual for the design tool (its interface
                      is in Spanish; see manual for why)
```

The compiled, standalone Windows executable of the design tool is published as a
[GitHub Release](../../releases) of this repository (not committed to the git
history directly, to keep the repository itself lightweight).

## Dataset

`dataset/dataset_RNA_v7_verificado.csv` (semicolon-separated, UTF-8 with BOM).
Columns: `Fuente;Suelo;Departamento;X1_Grava;X2_Arena;X3_Finos;X4_LL;X5_LP;X6_IP;X7_OCH;X8_MDS;X9_Cemento;X10_CBR;Y1_MPa;Y2_Durham;Verificado;Trazabilidad`.
84 rows, 23 unique soils, 78 rows with strength ($Y_1$), 22 rows from 14 soils with
durability ($Y_2$). See the article's Methods section for the full data-curation
protocol and inclusion criteria.

## Reproducing the results

```bash
pip install -r software/source/requirements.txt
python analysis_code/analisis_shap_bootstrap.py    # SHAP values + group-level bootstrap
python analysis_code/analisis_Y2_confusion.py      # Y2 confusion matrix (Table 2 of the article)
python analysis_code/caso_representativo_apendice.py  # Appendix A worked example
```

All scripts read `dataset/dataset_RNA_v7_verificado.csv` directly; no external
services or API keys are required, and no GPU is needed (the deployed models are
plain scikit-learn).

## Design tool

See `docs/USER_MANUAL_EN.md` for a description of the tool's six stages, its design
decisions and the Appendix A worked example reproduced through its interface. The
interface itself is in Spanish; its intended users are Peruvian road engineers
working under MTC (Ministerio de Transportes y Comunicaciones) regulations.

## License

Code is released under the MIT License (see `LICENSE`). The dataset is released
under CC BY 4.0: reuse is permitted with attribution to the article above.

## Contact

Corresponding author: aldair.rojas.16@unsch.edu.pe

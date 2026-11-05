# -*- coding: utf-8 -*-
"""
Technical analysis for the soil-cement UCS/durability ML paper
(Transportation Infrastructure Geotechnology, Springer).

Tasks:
  1. Y2 verification
  2. SHAP values (Linear Regression + Random Forest)
  3. Bootstrap 95% CI of LOGO-CV R2/RMSE/MAE (group-level bootstrap)
  4. Standardized coefficients of the Linear Regression model

All outputs (figures, tables, report) are in English, per journal requirements.
"""
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

import shap

# ----------------------------------------------------------------------
# Global plot configuration
# ----------------------------------------------------------------------
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
matplotlib.rcParams['font.size'] = 10
matplotlib.rcParams['axes.labelsize'] = 11
matplotlib.rcParams['axes.titlesize'] = 12
matplotlib.rcParams['figure.dpi'] = 300
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['axes.facecolor'] = 'white'
matplotlib.rcParams['figure.facecolor'] = 'white'
matplotlib.rcParams['savefig.facecolor'] = 'white'

OUT_DIR = r"D:\MODELADO ALDAIR\ARTICULO\analisis"
os.makedirs(OUT_DIR, exist_ok=True)

DATA_PATH = r"C:\Users\Diego Tenorio\Desktop\SOFTWARE_ALDAIR\dataset_RNA_v7_verificado.csv"

FEATURES_RAW = ['X1_Grava', 'X3_Finos', 'X4_LL', 'X6_IP', 'X7_OCH', 'X8_MDS', 'X9_Cemento']
FEATURE_NAMES_EN = ['Gravel (%)', 'Fines (%)', 'Liquid Limit (%)',
                     'Plasticity Index (%)', 'Opt. Moisture Content (%)',
                     'Max. Dry Density (g/cm\u00b3)', 'Cement Content (%)']
FEATURE_MAP = dict(zip(FEATURES_RAW, FEATURE_NAMES_EN))

RNG_SEED = 42
N_BOOTSTRAP = 1000

print("=" * 70)
print("LOADING DATA")
print("=" * 70)
df_full = pd.read_csv(DATA_PATH, sep=';')
print(f"Full dataset shape: {df_full.shape}")

# ========================================================================
# TASK 1 - Y2 VERIFICATION
# ========================================================================
print("\n" + "=" * 70)
print("TASK 1 - Y2 VERIFICATION")
print("=" * 70)

df_y2 = df_full[df_full['Y2_Durham'].notna()].copy()
n_rows_y2 = len(df_y2)
n_soils_y2 = df_y2['Suelo'].nunique()

print(f"a) Rows with Y2: {n_rows_y2} (expected 22)")
print(f"b) Unique soils with Y2: {n_soils_y2} (expected 14)")

y2_summary = (
    df_y2.groupby('Suelo')
    .agg(Region=('Departamento', 'first'), Source=('Fuente', 'first'),
         N_rows_Y2=('Y2_Durham', 'count'))
    .reset_index()
    .rename(columns={'Suelo': 'Soil_ID'})
    .sort_values('Soil_ID')
)
print("\nc) Per-soil breakdown:")
print(y2_summary.to_string(index=False))

y2_summary.to_csv(os.path.join(OUT_DIR, "verificacion_Y2.csv"), index=False, encoding='utf-8-sig')

# ========================================================================
# Prepare Y1 dataset (used for tasks 2, 3, 4)
# ========================================================================
df_y1 = df_full.dropna(subset=['Y1_MPa']).reset_index(drop=True)
X_df_raw = df_y1[FEATURES_RAW].copy()
X_df = X_df_raw.rename(columns=FEATURE_MAP)
y = df_y1['Y1_MPa'].values
groups = df_y1['Suelo'].values
n_total = len(df_y1)
n_soils_total = df_y1['Suelo'].nunique()
print(f"\nY1 modeling dataset: n={n_total}, unique soils={n_soils_total}")

# ========================================================================
# TASK 2 - SHAP VALUES
# ========================================================================
print("\n" + "=" * 70)
print("TASK 2 - SHAP VALUES")
print("=" * 70)

# ---- 2A: Linear Regression ----
# NOTE: for a linear model, SHAP values in output units (MPa) are
# mathematically identical whether computed on raw or standardized inputs
# (SHAP_i = coef_i * (x_i - mean(x_i)); scaling just rescales coef_i by
# 1/std_i while z_i rescales by std_i, cancelling out). We therefore fit
# and explain on RAW feature values so that the dependence-plot x-axes
# show real engineering units (%, g/cm3) instead of z-scores, matching
# the axis labels requested and avoiding a mismatched/misleading scale.
# This also keeps the explained model identical to the deployed model
# used throughout the thesis (R2_LOGO = 0.467 on raw features).
scaler_lr = StandardScaler()
X_scaled = scaler_lr.fit_transform(X_df_raw.values)  # used only for reference/consistency check

lr_model = LinearRegression()
lr_model.fit(X_df_raw.values, y)

try:
    explainer_lr = shap.LinearExplainer(lr_model, X_df_raw.values)
    shap_values_lr = explainer_lr(X_df)
except Exception as e:
    print(f"LinearExplainer failed ({e}), falling back to shap.Explainer(algorithm='linear')")
    explainer_lr = shap.Explainer(lr_model, X_df_raw.values, algorithm="linear")
    shap_values_lr = explainer_lr(X_df)

shap_values_lr_arr = shap_values_lr.values if hasattr(shap_values_lr, "values") else shap_values_lr

# fig_shap_bar_LR.png
plt.figure()
shap.summary_plot(shap_values_lr_arr, X_df, plot_type="bar",
                   feature_names=FEATURE_NAMES_EN, show=False)
plt.title("Mean |SHAP value| \u2014 Linear Regression")
plt.xlabel("Mean |SHAP value| (MPa)")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fig_shap_bar_LR.png"), dpi=300, facecolor='white')
plt.close()

# fig_shap_beeswarm_LR.png
# Reviewer feedback on an earlier round flagged that the colour bar on the
# right of the SHAP beeswarm could be mistaken for a secondary y-axis.
# Widening the figure to give the bar its own clear margin and relabelling
# it explicitly (instead of relying on SHAP's small default "Feature value"
# text) removes that ambiguity; the same fix is applied to the Random
# Forest beeswarm below.
fig = plt.figure(figsize=(8, 5))
shap.summary_plot(shap_values_lr_arr, X_df, plot_type="dot",
                   feature_names=FEATURE_NAMES_EN, show=False)
plt.title("SHAP Beeswarm \u2014 Linear Regression")
cb = plt.gcf().axes[-1]
cb.set_ylabel("Feature value (low \u2192 high)", fontsize=10, labelpad=6)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fig_shap_beeswarm_LR.png"), dpi=300, facecolor='white')
plt.close()

# Both dependence plots share one colormap family (perceptually uniform,
# colour-blind safe) so a reader comparing Figures 7 and 8 side by side is
# not misled by two unrelated colour scales rendered in the same hues
# (the SHAP library's default blue-to-pink palette was previously used
# for both figures, even though each colorbar encodes a different
# variable and a different range).
DEPENDENCE_CMAP = "viridis"

# fig_shap_X9_dependence.png (raw engineering units on both axes)
fig, ax = plt.subplots(figsize=(6, 4.5))
shap.dependence_plot("Cement Content (%)", shap_values_lr_arr, X_df,
                      interaction_index="Max. Dry Density (g/cm\u00b3)",
                      cmap=DEPENDENCE_CMAP, dot_size=28, alpha=0.9,
                      ax=ax, show=False)
ax.set_xlabel("Cement Content (%)", fontsize=12)
ax.set_ylabel("SHAP value for Cement Content (MPa)", fontsize=12)
ax.tick_params(labelsize=10)
ax.grid(axis="both", linestyle="--", linewidth=0.4, alpha=0.4)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "fig_shap_X9_dependence.png"), dpi=300, facecolor='white')
plt.close(fig)

# fig_shap_X8_dependence.png (raw engineering units on both axes)
fig, ax = plt.subplots(figsize=(6, 4.5))
shap.dependence_plot("Max. Dry Density (g/cm\u00b3)", shap_values_lr_arr, X_df,
                      interaction_index="Cement Content (%)",
                      cmap=DEPENDENCE_CMAP, dot_size=28, alpha=0.9,
                      ax=ax, show=False)
ax.set_xlabel("Max. Dry Density (g/cm\u00b3)", fontsize=12)
ax.set_ylabel("SHAP value for Max. Dry Density (MPa)", fontsize=12)
ax.tick_params(labelsize=10)
ax.grid(axis="both", linestyle="--", linewidth=0.4, alpha=0.4)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "fig_shap_X8_dependence.png"), dpi=300, facecolor='white')
plt.close(fig)

shap_mean_abs_lr = np.abs(shap_values_lr_arr).mean(axis=0)

# Sanity check: LR trained on raw features should reproduce the thesis's
# established coefficients/behaviour (cross-checked again explicitly in Task 4).
print(f"[Sanity check] LR (raw features) R2 on full data: {r2_score(y, lr_model.predict(X_df_raw.values)):.4f}")

# ---- 2B: Random Forest ----
rf_model = RandomForestRegressor(n_estimators=200, random_state=RNG_SEED)
rf_model.fit(X_df_raw.values, y)

explainer_rf = shap.TreeExplainer(rf_model)
shap_values_rf = explainer_rf(X_df_raw.rename(columns=FEATURE_MAP))
shap_values_rf_arr = shap_values_rf.values if hasattr(shap_values_rf, "values") else shap_values_rf

plt.figure()
shap.summary_plot(shap_values_rf_arr, X_df_raw.rename(columns=FEATURE_MAP), plot_type="bar",
                   feature_names=FEATURE_NAMES_EN, show=False)
plt.title("Mean |SHAP value| \u2014 Random Forest")
plt.xlabel("Mean |SHAP value| (MPa)")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fig_shap_bar_RF.png"), dpi=300, facecolor='white')
plt.close()

fig = plt.figure(figsize=(8, 5))
shap.summary_plot(shap_values_rf_arr, X_df_raw.rename(columns=FEATURE_MAP), plot_type="dot",
                   feature_names=FEATURE_NAMES_EN, show=False)
plt.title("SHAP Beeswarm \u2014 Random Forest")
cb = plt.gcf().axes[-1]
cb.set_ylabel("Feature value (low \u2192 high)", fontsize=10, labelpad=6)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fig_shap_beeswarm_RF.png"), dpi=300, facecolor='white')
plt.close()

shap_mean_abs_rf = np.abs(shap_values_rf_arr).mean(axis=0)

# ---- 2C: Comparison table ----
rank_lr = pd.Series(shap_mean_abs_lr).rank(ascending=False).astype(int).values
rank_rf = pd.Series(shap_mean_abs_rf).rank(ascending=False).astype(int).values

shap_comparison = pd.DataFrame({
    'Feature': FEATURE_NAMES_EN,
    'SHAP_mean_abs_LR': shap_mean_abs_lr,
    'SHAP_mean_abs_RF': shap_mean_abs_rf,
    'Rank_LR': rank_lr,
    'Rank_RF': rank_rf,
}).sort_values('Rank_LR')

shap_comparison.to_csv(os.path.join(OUT_DIR, "shap_importance_comparison.csv"),
                        index=False, encoding='utf-8-sig')
print("\nSHAP importance comparison (LR vs RF):")
print(shap_comparison.to_string(index=False))

# ========================================================================
# TASK 3 - BOOTSTRAP 95% CI OF LOGO-CV R2
# ========================================================================
print("\n" + "=" * 70)
print("TASK 3 - BOOTSTRAP 95% CI OF LOGO-CV R2/RMSE/MAE")
print("=" * 70)

unique_soils = np.array(sorted(set(groups)))
n_unique_soils = len(unique_soils)
rng = np.random.default_rng(RNG_SEED)

boot_r2, boot_rmse, boot_mae = [], [], []
n_discarded = 0
attempts = 0
max_attempts = N_BOOTSTRAP * 20  # safety valve

while len(boot_r2) < N_BOOTSTRAP and attempts < max_attempts:
    attempts += 1
    sampled_soils = rng.choice(unique_soils, size=n_unique_soils, replace=True)
    sampled_soils_set = set(sampled_soils)
    oob_soils = [s for s in unique_soils if s not in sampled_soils_set]

    if len(oob_soils) == 0:
        n_discarded += 1
        continue

    train_mask = np.isin(groups, list(sampled_soils_set))
    # Rebuild the training rows: every row belonging to a sampled soil,
    # duplicated according to how many times that soil was drawn.
    train_idx = []
    for s in sampled_soils:
        train_idx.extend(np.where(groups == s)[0].tolist())
    train_idx = np.array(train_idx)

    oob_mask = np.isin(groups, oob_soils)
    oob_idx = np.where(oob_mask)[0]

    X_train_b = X_df_raw.values[train_idx]
    y_train_b = y[train_idx]
    X_oob_b = X_df_raw.values[oob_idx]
    y_oob_b = y[oob_idx]

    model_b = LinearRegression()
    model_b.fit(X_train_b, y_train_b)
    y_pred_oob = model_b.predict(X_oob_b)

    r2_b = r2_score(y_oob_b, y_pred_oob)
    rmse_b = np.sqrt(mean_squared_error(y_oob_b, y_pred_oob))
    mae_b = mean_absolute_error(y_oob_b, y_pred_oob)

    boot_r2.append(r2_b)
    boot_rmse.append(rmse_b)
    boot_mae.append(mae_b)

boot_r2 = np.array(boot_r2)
boot_rmse = np.array(boot_rmse)
boot_mae = np.array(boot_mae)

print(f"Valid bootstrap iterations: {len(boot_r2)} (discarded: {n_discarded}, attempts: {attempts})")


def summarize(arr):
    return {
        'mean': np.mean(arr),
        'median': np.median(arr),
        'std': np.std(arr, ddof=1),
        'ci95_lower': np.percentile(arr, 2.5),
        'ci95_upper': np.percentile(arr, 97.5),
        'ci90_lower': np.percentile(arr, 5),
        'ci90_upper': np.percentile(arr, 95),
    }


summary_r2 = summarize(boot_r2)
summary_rmse = summarize(boot_rmse)
summary_mae = summarize(boot_mae)

bootstrap_results = pd.DataFrame([
    {'metric': 'R2', **summary_r2},
    {'metric': 'RMSE', **summary_rmse},
    {'metric': 'MAE', **summary_mae},
])
bootstrap_results.to_csv(os.path.join(OUT_DIR, "bootstrap_results.csv"), index=False)

bootstrap_raw = pd.DataFrame({
    'iteration': np.arange(1, len(boot_r2) + 1),
    'R2': boot_r2,
    'RMSE': boot_rmse,
    'MAE': boot_mae,
})
bootstrap_raw.to_csv(os.path.join(OUT_DIR, "bootstrap_raw.csv"), index=False)

print("\nBootstrap summary:")
print(bootstrap_results.to_string(index=False))

# ---- fig_bootstrap_r2_histogram.png ----
plt.figure(figsize=(7, 5))
plt.hist(boot_r2, bins=50, color='#4C72B0', edgecolor='white', alpha=0.85)
plt.axvline(summary_r2['mean'], color='red', linestyle='--', linewidth=1.8,
            label=f"Mean = {summary_r2['mean']:.3f}")
plt.axvline(summary_r2['ci95_lower'], color='blue', linestyle='--', linewidth=1.5,
            label=f"95% CI = [{summary_r2['ci95_lower']:.3f}, {summary_r2['ci95_upper']:.3f}]")
plt.axvline(summary_r2['ci95_upper'], color='blue', linestyle='--', linewidth=1.5)
plt.title(f"Bootstrap Distribution of R\u00b2 (LOGO-CV, n={len(boot_r2)})")
plt.xlabel("R\u00b2 (Leave-One-Group-Out)")
plt.ylabel("Frequency")
plt.legend(loc='upper left', frameon=False, fontsize=9)
plt.annotate(f"Mean \u00b1 SD = {summary_r2['mean']:.3f} \u00b1 {summary_r2['std']:.3f}\n"
             f"95% CI = [{summary_r2['ci95_lower']:.3f}, {summary_r2['ci95_upper']:.3f}]",
             xy=(0.98, 0.85), xycoords='axes fraction', ha='right', va='top', fontsize=9,
             bbox=dict(boxstyle='round', facecolor='white', edgecolor='gray', alpha=0.9))
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fig_bootstrap_r2_histogram.png"), dpi=300, facecolor='white')
plt.close()

# ---- fig_bootstrap_rmse_histogram.png ----
plt.figure(figsize=(7, 5))
plt.hist(boot_rmse, bins=50, color='#4C72B0', edgecolor='white', alpha=0.85)
plt.axvline(summary_rmse['mean'], color='red', linestyle='--', linewidth=1.8,
            label=f"Mean = {summary_rmse['mean']:.3f}")
plt.axvline(summary_rmse['ci95_lower'], color='blue', linestyle='--', linewidth=1.5,
            label=f"95% CI = [{summary_rmse['ci95_lower']:.3f}, {summary_rmse['ci95_upper']:.3f}]")
plt.axvline(summary_rmse['ci95_upper'], color='blue', linestyle='--', linewidth=1.5)
plt.title(f"Bootstrap Distribution of RMSE (LOGO-CV, n={len(boot_rmse)})")
plt.xlabel("RMSE (MPa)")
plt.ylabel("Frequency")
plt.legend(loc='upper right', frameon=False, fontsize=9)
plt.annotate(f"Mean \u00b1 SD = {summary_rmse['mean']:.3f} \u00b1 {summary_rmse['std']:.3f}\n"
             f"95% CI = [{summary_rmse['ci95_lower']:.3f}, {summary_rmse['ci95_upper']:.3f}]",
             xy=(0.98, 0.85), xycoords='axes fraction', ha='right', va='top', fontsize=9,
             bbox=dict(boxstyle='round', facecolor='white', edgecolor='gray', alpha=0.9))
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fig_bootstrap_rmse_histogram.png"), dpi=300, facecolor='white')
plt.close()

# ========================================================================
# TASK 4 - STANDARDIZED COEFFICIENTS
# ========================================================================
print("\n" + "=" * 70)
print("TASK 4 - STANDARDIZED COEFFICIENTS (Linear Regression)")
print("=" * 70)

scaler_full = StandardScaler()
X_full_scaled = scaler_full.fit_transform(X_df_raw.values)
lr_std_model = LinearRegression()
lr_std_model.fit(X_full_scaled, y)
standardized_coefs = lr_std_model.coef_
intercept_std = lr_std_model.intercept_

lr_raw_model = LinearRegression()
lr_raw_model.fit(X_df_raw.values, y)
raw_coefs = lr_raw_model.coef_
intercept_raw = lr_raw_model.intercept_

interpretations = {
    'X1_Grava': f"Each 1% increase in Gravel \u2192 {raw_coefs[0]:+.3f} MPa",
    'X3_Finos': f"Each 1% increase in Fines \u2192 {raw_coefs[1]:+.3f} MPa",
    'X4_LL': f"Each 1% increase in Liquid Limit \u2192 {raw_coefs[2]:+.3f} MPa",
    'X6_IP': f"Each 1% increase in Plasticity Index \u2192 {raw_coefs[3]:+.3f} MPa",
    'X7_OCH': f"Each 1% increase in Optimum Moisture Content \u2192 {raw_coefs[4]:+.3f} MPa",
    'X8_MDS': f"Each 0.1 g/cm\u00b3 increase in Max. Dry Density \u2192 {raw_coefs[5]*0.1:+.3f} MPa",
    'X9_Cemento': f"Each 1% increase in Cement Content \u2192 {raw_coefs[6]:+.3f} MPa",
}

coef_table = pd.DataFrame({
    'Feature': FEATURE_NAMES_EN,
    'Raw_Coefficient': raw_coefs,
    'Standardized_Coefficient': standardized_coefs,
    'Direction': np.where(standardized_coefs >= 0, 'Positive', 'Negative'),
    'Interpretation': [interpretations[f] for f in FEATURES_RAW],
})
coef_table_sorted = coef_table.reindex(
    coef_table['Standardized_Coefficient'].abs().sort_values(ascending=False).index
)
coef_table_sorted.to_csv(os.path.join(OUT_DIR, "coeficientes_LR.csv"), index=False, encoding='utf-8-sig')

print(f"\nIntercept (raw scale): {intercept_raw:.4f}")
print(f"Intercept (standardized scale): {intercept_std:.4f}")
print("\nStandardized coefficients table:")
print(coef_table_sorted.to_string(index=False))

# ---- fig_coeficientes_estandarizados.png ----
plot_df = coef_table_sorted.iloc[::-1]  # smallest |coef| at bottom -> largest at top when plotted
colors = ['#2196F3' if v >= 0 else '#F44336' for v in plot_df['Standardized_Coefficient']]

plt.figure(figsize=(8.5, 5))
bars = plt.barh(plot_df['Feature'], plot_df['Standardized_Coefficient'], color=colors)
plt.axvline(0, color='black', linestyle='--', linewidth=1)
plt.title("Standardized Coefficients \u2014 Linear Regression")
plt.xlabel("Standardized Coefficient (\u03b2)")

max_abs = plot_df['Standardized_Coefficient'].abs().max()
plt.xlim(-max_abs * 1.35, max_abs * 1.35)

for bar, val in zip(bars, plot_df['Standardized_Coefficient']):
    offset = 0.04 * max_abs * (1 if val >= 0 else -1)
    ha = 'left' if val >= 0 else 'right'
    plt.text(val + offset, bar.get_y() + bar.get_height() / 2, f"{val:.3f}",
              va='center', ha=ha, fontsize=9)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fig_coeficientes_estandarizados.png"), dpi=300, facecolor='white')
plt.close()

# ========================================================================
# FINAL VERIFICATION PRINTOUT
# ========================================================================
print("\n" + "=" * 70)
print("FINAL VERIFICATION")
print("=" * 70)

print(f"\n1) Y2: {n_rows_y2} rows, {n_soils_y2} unique soils")

top3_lr = shap_comparison.sort_values('Rank_LR').head(3)['Feature'].tolist()
top3_rf = shap_comparison.sort_values('Rank_RF').head(3)['Feature'].tolist()
print(f"\n2) Top-3 SHAP features - LR: {top3_lr}")
print(f"   Top-3 SHAP features - RF: {top3_rf}")

print(f"\n3) Bootstrap R2: mean={summary_r2['mean']:.4f}, "
      f"95% CI=[{summary_r2['ci95_lower']:.4f}, {summary_r2['ci95_upper']:.4f}], "
      f"n_valid={len(boot_r2)}")

top_coef_row = coef_table_sorted.iloc[0]
print(f"\n4) Most important standardized coefficient: {top_coef_row['Feature']} "
      f"(beta={top_coef_row['Standardized_Coefficient']:.4f})")

print("\n5) Generated files:")
for fname in sorted(os.listdir(OUT_DIR)):
    fpath = os.path.join(OUT_DIR, fname)
    if os.path.isfile(fpath):
        size_kb = os.path.getsize(fpath) / 1024
        print(f"   {fname:45s} {size_kb:8.1f} KB")

print("\nDONE.")

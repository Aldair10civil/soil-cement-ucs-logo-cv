# -*- mode: python ; coding: utf-8 -*-
"""
build_exe.spec - Empaquetado a .exe del Predictor Suelo-Cemento CNP Peru
Compilar:  py -3.11 -m PyInstaller build_exe.spec --noconfirm
El .exe queda en dist/PredictorSueloCemento/PredictorSueloCemento.exe
"""
from pathlib import Path

BASE = Path(SPECPATH)
MODELS = BASE / "models"
ASSETS = BASE / "assets"
MINIATURAS = ASSETS / "miniaturas"

block_cipher = None

datas_miniaturas = [(str(p), "assets/miniaturas") for p in MINIATURAS.glob("*.png")]

a = Analysis(
    ['main.py'],
    pathex=[str(BASE), str(MODELS)],
    binaries=[],
    datas=[
        (str(MODELS / "modelo_Y1_best.joblib"), "models"),
        (str(MODELS / "modelo_Y2_best.joblib"), "models"),
        (str(MODELS / "metadatos.json"), "models"),
        (str(ASSETS / "logo.png"), "assets"),
        (str(ASSETS / "icono.ico"), "assets"),
    ] + datas_miniaturas,
    hiddenimports=[
        'sklearn.linear_model', 'sklearn.linear_model._base',
        'sklearn.linear_model._ridge', 'sklearn.preprocessing',
        'sklearn.preprocessing._data', 'sklearn.utils._param_validation',
        'matplotlib.backends.backend_qt5agg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        # Librerias de OTROS proyectos instaladas en el mismo entorno Python
        # 3.11 (p.ej. software_adas / YOLO) que PyInstaller detecta de forma
        # conservadora pero que este software NO usa. Sin esto, el paquete
        # pasa de ~450 MB a varios GB innecesariamente.
        'torch', 'torchvision', 'torchaudio', 'tensorflow', 'onnxruntime',
        'cv2', 'ultralytics', 'transformers', 'nltk', 'pyarrow', 'llvmlite',
        'numba', 'av', 'grpc', 'jedi', 'IPython', 'notebook', 'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PredictorSueloCemento',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,         # sin ventana de consola (build final, profesional)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "icono.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PredictorSueloCemento',
)

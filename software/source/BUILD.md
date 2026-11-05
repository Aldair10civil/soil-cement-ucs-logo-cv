# Compilar el .exe (PyInstaller)

## Requisitos

Todo ya deberia estar instalado en el Python 3.11 de este equipo
(`C:\Program Files\Python311\python.exe`): PyQt5, matplotlib, scikit-learn,
pandas, joblib, reportlab, kaleido, y PyInstaller.

Si falta algo:
```
py -3.11 -m pip install -r requirements.txt
py -3.11 -m pip install pyinstaller
```

## Compilar

Desde la carpeta `SOFTWARE/`:
```
py -3.11 -m PyInstaller build_exe.spec --noconfirm
```

Tarda varios minutos (no esta "colgado" — esta copiando y analizando las
librerias de Qt5/scipy/sklearn, no instalando nada). El resultado queda en:

```
dist/PredictorSueloCemento/PredictorSueloCemento.exe
```

**Para entregar el software a alguien: copia toda la carpeta**
`dist/PredictorSueloCemento/` (no solo el .exe — necesita la carpeta
`_internal/` que va al lado). Puede comprimirse en un .zip para enviarla.

## Tamaño esperado

~300 MB. Es normal para esta combinacion de librerias (Qt5 + scipy +
scikit-learn + matplotlib empaquetados sin depender de que el usuario
instale Python). No requiere GPU: el modelo es scikit-learn puro (regresion
lineal/Ridge), no usa PyTorch/CUDA en ningun punto del codigo.

**Importante — este equipo comparte el Python 3.11 con otros proyectos**
(p.ej. `software_adas`, que usa PyTorch/YOLO). El `.spec` ya excluye
explicitamente esas librerias (`torch`, `tensorflow`, `onnxruntime`, `cv2`,
`ultralytics`, etc.) porque PyInstaller las detecta de forma conservadora
aunque este software no las use — sin esa exclusion el paquete pesa varios
GB en lugar de ~300 MB. Si en el futuro instalas una libreria nueva en ese
mismo entorno y el .exe vuelve a inflarse, revisa `excludes=[...]` en
`build_exe.spec`.

## Depurar un build que falla

Si el .exe no abre o se cierra solo, cambia temporalmente en
`build_exe.spec`:
```python
console=True,
```
Recompila y ejecutalo desde una consola (`PredictorSueloCemento.exe`) para
ver el traceback. Vuelve a `console=False` para el build final.

## Verificacion ya realizada

- Prueba headless (`QT_QPA_PLATFORM=offscreen`) del flujo completo: suelo ->
  estabilizadores -> normativa -> prediccion -> curva -> PDF -> bloqueo de
  alternativas. Cero excepciones.
- El .exe compilado se lanzo y se verifico corriendo estable (tasklist,
  ~150-250 MB de RAM) antes de cerrarlo.

# -*- coding: utf-8 -*-
"""Regenera las capturas de pantalla del software embebidas en la tesis
(PATRICIA/*.png), que habian quedado desactualizadas tras los fixes de hoy
(LL/IP invertido, lenguaje "aceptable para diseno" -> "estimacion preliminar").
Usa QT_QPA_PLATFORM=offscreen -- no requiere pantalla.

Ejemplo usado en TODAS las capturas: mismo suelo (granular A-1-a, canonico del
propio codigo -- el mismo de curva.py __main__), mismo proyecto, variando solo
X9 (dosificacion) para los 3 escenarios de Prediccion.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "models"))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)

import main as M

OUT = Path(r"D:\MODELADO ALDAIR\Borrador de tesis Aldair 2026\PATRICIA")

win = M.MainWindow()
# NO sobreescribir el tamano -- MainWindow.__init__ ya hace self.resize(1400, 880),
# que es el tamano para el que estan calibrados los factores \includegraphics
# scale=... del .tex. Cambiarlo (p.ej. a 1600x950) corta contenido por el borde
# derecho de la pagina al compilar.
win.move(-3000, -3000)  # fuera de la pantalla visible, pero ventana real
win.show()
app.processEvents()

# ---- Proyecto (coincide con la narrativa del cuerpo: Vilcashuaman, Ayacucho, 3200msnm) ----
e1 = win.etapa1
e1.nombre.setText("Camino vecinal Saurma-Carhuanca-Belen-Chalcos-Chilcayocc")
e1.departamento.setText("Ayacucho")
e1.provincia.setText("Vilcas Huaman")
e1.distrito.setText("Vilcas Huaman")
e1.altitud.setValue(3200)
e1.imd.setValue(0)
e1._actualizar()

# ---- Suelo (canonico, A-1-a granular, igual que curva.py __main__) ----
e2 = win.etapa2
e2.X1.setValue(55.14)
e2.X2.setValue(36.04)
e2.X3.setValue(8.82)
e2.X4.setValue(16.44)
e2.X5.setValue(12.53)   # => IP = X4-X5 = 3.91
e2.X7.setValue(9.0)
e2.X8.setValue(2.173)
e2._actualizar()
win._al_cambiar_suelo()


def grab(widget_etapa, nombre):
    win._ir_a_etapa(win.etapas.index(widget_etapa))
    app.processEvents()
    pix = win.grab()
    destino = OUT / nombre
    pix.save(str(destino))
    print(f"  guardado: {destino}  ({pix.width()}x{pix.height()})")


# ---- Etapa 1: Proyecto ----
grab(win.etapa1, "3333.png")

# ---- Etapa 2: Suelo ----
grab(win.etapa2, "2307.png")

# ---- Etapa 3: Normativa ----
grab(win.etapa3, "2308.png")

# ---- Etapa 4: Prediccion, 3 escenarios (naranja, verde, economia) ----
e4 = win.etapa4
for x9, nombre in [(2.0, "2313.png"), (3.5, "2309.png"), (8.0, "2311.png")]:
    e4.X9.setValue(x9)
    e4._predecir()
    app.processEvents()
    grab(win.etapa4, nombre)

# ---- Etapa 5: Curva completa (deja X9 en 3.5 para la marca del usuario) ----
e4.X9.setValue(3.5)
e4._predecir()
win._ir_a_etapa(win.etapas.index(win.etapa5))
app.processEvents()
win.etapa5._generar()  # genera y dibuja la curva completa 1-12% (el boton real)
app.processEvents()
win.etapa5.refrescar_marca_usuario(win.estado)
app.processEvents()
grab(win.etapa5, "2392.png")
grab(win.etapa5, "2321.png")

# ---- Etapa 6: Reporte (vista previa, SIN llamar a _generar() -- ese metodo
# abre un QFileDialog.getSaveFileName modal que se queda esperando un clic
# que nunca llega bajo offscreen; replicamos aqui solo la parte de armar el
# texto de previsualizacion) ----
from reporte import generar_texto_informe
from curva import curva_dosificacion, encontrar_optimo
e6 = win.etapa6
e = win.estado
s = e.suelo
base = {"X1": s["X1"], "X3": s["X3"], "X4": s["X4"], "X6": s["X6"],
       "X7": s["X7"], "X8": s["X8"]}
df = curva_dosificacion(base, 1.0, 12.0, 0.5)
opt = encontrar_optimo(df)
dosif_practica = ({k: opt[k] for k in ("kg_m3", "bolsas_m3")} if opt else None)
estabs, nota_cal = e6._evaluar_estabilizadores_y_cal(e)
checks_normativa_a = M._checks_normativa_a(e)
contexto = {
    "proyecto": e.proyecto, "suelo": {**e.suelo, "X9": e.entrada_actual["X9"]},
    "clasif": e.clasif, "checks_normativa_a": checks_normativa_a,
    "y1_mpa": e.prediccion["Y1_MPa"],
    "y1_kgcm2": round(e.prediccion["Y1_MPa"] * M.MPA_A_KGCM2, 1),
    "y2": e.prediccion["durham"], "avisos": e.prediccion["avisos"],
    "optimo": opt, "dosif_practica": dosif_practica,
    "estabilizadores": estabs, "nota_cal": nota_cal,
    "fecha": "28/10/2026", "fotos_reporte": [],
}
texto = generar_texto_informe(contexto)
e6.preview.setPlainText(texto)
win._ir_a_etapa(win.etapas.index(win.etapa6))
app.processEvents()
grab(win.etapa6, "2314.png")

print("\nListo.")

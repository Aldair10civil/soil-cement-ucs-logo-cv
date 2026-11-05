# -*- coding: utf-8 -*-
"""
================================================================================
main.py - SUELO-CEMENTO CNP PERU (aplicacion de escritorio PyQt5)
================================================================================
Interfaz tipo wizard de 6 etapas con timeline lateral. Reutiliza sin cambios
de logica de negocio: models/predictor.py (motor RNA), clasificacion.py,
region.py, estabilizadores.py, curva.py, reporte.py, tooltips.py.

Ejecutar en desarrollo:  py -3.11 main.py
Compilar a .exe:         ver build_exe.spec (PyInstaller)
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
from PyQt5.QtCore import Qt, QLocale, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGridLayout, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QMessageBox, QFileDialog, QScrollArea, QFrame,
    QListWidget, QListWidgetItem, QInputDialog,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

_DIR = Path(__file__).resolve().parent
_MODELO_DIR = _DIR / "models"
if not getattr(sys, "frozen", False):
    for p in (_DIR, _MODELO_DIR):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

from predictor import predecir                                        # noqa: E402
from clasificacion import (clasificar_aashto_detallado, SIGNIFICADO_SUCS,  # noqa: E402
                           verificar_restriccion_usace)
from region import REGIONES, sugerir_region                            # noqa: E402
from estabilizadores import evaluar_estabilizadores, APTO, NO_APTO, NO_VERIFICADO  # noqa: E402
from curva import (curva_dosificacion, encontrar_optimo, rango_fhwa,   # noqa: E402
                   Y1_MIN_MPA, MPA_A_KGCM2, evaluar_escenario,
                   mensaje_ninguna_dosis_cumple, coeficiente_estructural_a2)
from reporte import generar_texto_informe, generar_pdf                 # noqa: E402
from tooltips import TEXTO_E1103, TEXTO_E1104                          # noqa: E402

APP_TITLE = "SUELO-CEMENTO CNP PERU"
if getattr(sys, "frozen", False):
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
    OUTPUT_DIR = Path(sys.executable).resolve().parent / "output"
else:
    ASSETS_DIR = _DIR / "assets"
    OUTPUT_DIR = _DIR / "output"

RANGO_MTC_CEMENTO = (2.0, 12.0)   # Cuadro 9.2 MTC: rango universal de cemento Portland

# ============================================================================
# ESTILO
# ============================================================================
STYLE_SHEET = """
QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: #1c2530; }
QMainWindow { background: #f4f6f9; }
QScrollArea { border: none; }
QGroupBox {
    font-weight: 600; border: 1px solid #d4dae2; border-radius: 6px;
    margin-top: 12px; padding-top: 12px; background: #fbfcfd;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #2a5d9f; }
QPushButton {
    background: #2a5d9f; color: white; border: none; border-radius: 5px;
    padding: 8px 16px; font-weight: 600;
}
QPushButton:hover { background: #23508a; }
QPushButton:disabled { background: #a9b4c0; }
QPushButton#botonHerramienta {
    background: #eef1f5; color: #2a3441; padding: 6px 10px; font-weight: 500; font-size: 9pt;
}
QPushButton#botonHerramienta:hover { background: #d3dce6; }
QLineEdit, QComboBox {
    border: 1px solid #c3cbd4; border-radius: 4px; padding: 4px 6px; background: white;
}
/* QDoubleSpinBox/QSpinBox se dejan SIN estilo de caja propio A PROPOSITO:
   se confirmo visualmente (captura de pantalla) que CUALQUIER CSS sobre
   estos controles (incluso solo border/padding, sin tocar los botones)
   degrada o elimina las flechas nativas +/- en este entorno Qt/Fusion.
   Un intento anterior de dibujarlas a mano con bordes-triangulo causo
   ademas un crash nativo (0xc0000005 en msvcp140.dll). En vez de pelear
   con las flechas nativas, cada spinbox va acompanado de botones +/-
   explicitos (ver _con_flechas() mas abajo) que llaman a stepUp()/
   stepDown() -- mismo resultado, cero riesgo, visibilidad garantizada. */
QPushButton#botonSpin {
    background: #eef1f5; color: #2a3441; border: 1px solid #c3cbd4;
    border-radius: 4px; padding: 2px 0; font-weight: 700; min-width: 24px; max-width: 26px;
}
QPushButton#botonSpin:hover { background: #d3dce6; }
QPushButton#botonSpin:pressed { background: #b9c6d3; }
QTableWidget { border: 1px solid #d4dae2; gridline-color: #e7ebf0; }
QHeaderView::section {
    background: #eef1f5; color: #2a3441; padding: 6px; border: none;
    border-bottom: 2px solid #2a5d9f; font-weight: 600;
}
"""

C_VERDE = QColor("#d7f4e8")
C_ROJO = QColor("#fbdede")
C_AMARILLO = QColor("#fff3cd")
C_OPTIMO = QColor("#cfe3ff")

ETAPAS_INFO = [
    ("PROYECTO", "", "01_proyecto.png"),
    ("SUELO", "", "02_suelo.png"),
    ("NORMATIVA", "", "03_normativa.png"),
    ("PREDICCION", "", "04_prediccion.png"),
    ("CURVA\nCOMPLETA", "", "05_curva.png"),
    ("REPORTE", "", "06_reporte.png"),
]


# ============================================================================
# ESTADO COMPARTIDO ENTRE ETAPAS
# ============================================================================
class EstadoApp:
    def __init__(self):
        self.proyecto = {}
        self.suelo = {}            # X1..X8
        self.clasif = None
        self.entrada_actual = None
        self.prediccion = None
        self.curva_df = None
        self.curva_base = None
        self.optimo = None
        self.dosif_practica = None
        self.figura_curva = None
        self.x9_usuario = 5.0
        self.fotos_reporte = []    # lista de {"ruta": str, "leyenda": str}


# ---------------------------------------------------------------- helpers
class _DoubleSpinBoxSeleccionable(QDoubleSpinBox):
    """QDoubleSpinBox que selecciona todo el texto al recibir foco, para que
    escribir un numero nuevo lo REEMPLACE en vez de insertarse en medio del
    valor anterior (p.ej. click en '2' + escribir '3' -> '23' en vez de
    '3', lo que confundia resultados al re-predecir con otra dosificacion)."""

    def focusInEvent(self, ev):
        super().focusInEvent(ev)
        self.selectAll()


def _dspin(minv, maxv, val, step=0.1, decimals=1, suffix=""):
    w = _DoubleSpinBoxSeleccionable()
    w.setLocale(QLocale(QLocale.C))
    w.setRange(minv, maxv)
    w.setDecimals(decimals)
    w.setSingleStep(step)
    w.setValue(val)
    if suffix:
        w.setSuffix(" " + suffix)
    return w


def _ispin(minv, maxv, val, step=1):
    w = QSpinBox()
    w.setLocale(QLocale(QLocale.C))
    w.setRange(minv, maxv)
    w.setSingleStep(step)
    w.setValue(val)
    return w


def _con_flechas(spin):
    """Envuelve un spinbox con botones +/- EXPLICITOS y visibles. El objeto
    'spin' en si NO cambia (sigue siendo el mismo QDoubleSpinBox/QSpinBox,
    con su .value()/.setValue()/.valueChanged de siempre) -- solo se agregan
    botones al lado que llaman stepUp()/stepDown(). Devuelve un QWidget
    contenedor listo para insertar en un layout o QFormLayout.addRow(...)."""
    cont = QWidget()
    h = QHBoxLayout(cont)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(2)
    h.addWidget(spin, 1)
    btn_menos = QPushButton("−"); btn_mas = QPushButton("+")
    for b, fn in ((btn_menos, spin.stepDown), (btn_mas, spin.stepUp)):
        b.setObjectName("botonSpin")
        b.setFixedWidth(26)
        b.clicked.connect(fn)
        h.addWidget(b)
    return cont


def _item(texto, ok=None, negrita=False):
    it = QTableWidgetItem(str(texto))
    it.setTextAlignment(Qt.AlignCenter)
    if ok is True:
        it.setBackground(C_VERDE)
    elif ok is False:
        it.setBackground(C_ROJO)
    elif ok == "amarillo":
        it.setBackground(C_AMARILLO)
    elif ok == "optimo":
        it.setBackground(C_OPTIMO)
    if negrita:
        f = it.font(); f.setBold(True); it.setFont(f)
    return it


def _pintar_estado(label: QLabel, ok, texto: str):
    paletas = {True: ("#0b5a35", "#d7f4e8"), False: ("#7a1414", "#fbdede"),
              "amarillo": ("#6b4c00", "#fff3cd"),
              "verde": ("#0b5a35", "#d7f4e8"), "naranja": ("#7a3c00", "#ffe4c4"),
              "rojo": ("#7a1414", "#fbdede"), "rojo_oscuro": ("#ffffff", "#7a1414")}
    fg, bg = paletas.get(ok, ("#1c2530", "#eef1f5"))
    label.setStyleSheet(f"color:{fg}; background:{bg}; border-radius:5px; "
                        f"padding:8px; font-weight:600;")
    label.setText(texto)
    label.setWordWrap(True)


ESTADO_TXT = {APTO: "Apto", NO_APTO: "No apto", NO_VERIFICADO: "No verificado"}


def _dibujar_curva_en_ejes(ax, df, opt, punto_usuario=None):
    """Dibuja la curva de dosificacion: eje izquierdo Y1 (MPa, con eje
    secundario en kg/cm2 -- son la MISMA magnitud, no datos independientes),
    eje derecho Y2 (perdida Durham %). Se reutiliza en la etapa interactiva
    (Curva Completa) y al exportar el PDF (Reporte)."""
    ax.clear()
    ax2_previo = getattr(ax, "_ax2_gemelo", None)
    if ax2_previo is not None and ax2_previo in ax.figure.axes:
        ax2_previo.remove()
    ax2 = ax.twinx()
    ax._ax2_gemelo = ax2
    ax3 = ax.secondary_yaxis(
        "left", functions=(lambda mpa: mpa * MPA_A_KGCM2, lambda kg: kg / MPA_A_KGCM2))
    ax3.spines["left"].set_position(("outward", 42))
    ax3.set_ylabel("kg/cm2", color="#e67e22", fontsize=8)
    ax3.tick_params(axis="y", labelcolor="#e67e22", labelsize=8)

    l1, = ax.plot(df.cemento, df.Y1_MPa, "o-", color="#2a5d9f", lw=2, ms=4,
                 label="Y1 - Resistencia (MPa)")
    hl1 = ax.axhline(Y1_MIN_MPA, color="#d03b3b", ls="--", lw=1.4,
                     label=f"Minimo Y1 {Y1_MIN_MPA:.3f} MPa")
    l2, = ax2.plot(df.cemento, df.Y2_pct, "s--", color="#8a5fc2", lw=1.6, ms=4,
                  label="Y2 - Perdida Durham (%)")
    lineas_extra = []
    limite_durham = df.exigencia_durham.iloc[0] if len(df) else None
    if limite_durham is not None:
        hl2 = ax2.axhline(limite_durham, color="#5b8fd6", ls=":", lw=1.6,
                          label=f"Limite Y2 {limite_durham:.0f}%")
        lineas_extra.append(hl2)
    if opt:
        m1, = ax.plot([opt["cemento"]], [opt["Y1_MPa"]], "*", color="#1baf7a", ms=18,
                     label=f"Optimo automatico ({opt['cemento']:.1f}%)", zorder=5)
        lineas_extra.append(m1)
    if punto_usuario:
        x9u, y1u = punto_usuario
        m2, = ax.plot([x9u], [y1u], "D", color="#d03b3b", ms=10,
                     markeredgecolor="white", markeredgewidth=1,
                     label=f"Su diseno ({x9u:.1f}%)", zorder=6)
        lineas_extra.append(m2)

    ax.set_xlabel("Cemento (%)")
    ax.set_ylabel("Y1 - Resistencia (MPa)", color="#2a5d9f")
    ax2.set_ylabel("Y2 - Perdida Durham (%)", color="#8a5fc2")
    ax.tick_params(axis="y", labelcolor="#2a5d9f")
    ax2.tick_params(axis="y", labelcolor="#8a5fc2")
    ax.set_title("Curva de dosificacion suelo-cemento")
    ax.grid(alpha=.3)
    ax.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)

    lineas = [l1, hl1, l2] + lineas_extra
    ax.legend(lineas, [ln.get_label() for ln in lineas], fontsize=7,
             loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2,
             frameon=False, handletextpad=0.5, columnspacing=1.2)
    ax.figure.subplots_adjust(bottom=0.34, right=0.86)


# ============================================================================
# BARRA DE CONTEXTO PERSISTENTE (se muestra en las 6 etapas)
# ============================================================================
class BarraContexto(QFrame):
    def __init__(self, estado: EstadoApp):
        super().__init__()
        self.estado = estado
        self.setStyleSheet("background:#fbfcfd; border:1px solid #d4dae2; border-radius:6px;")
        lay = QHBoxLayout(self)
        self.valores = {}
        for clave, titulo in [("proyecto", "Proyecto"), ("ubicacion", "Ubicacion"),
                              ("clasificacion", "Clasificacion del Suelo"),
                              ("normativa", "Normativa de Ensayo")]:
            col = QVBoxLayout()
            t = QLabel(titulo); t.setStyleSheet("color:#2a5d9f; font-weight:700; font-size:8.5pt;")
            v = QLabel("-"); v.setWordWrap(True); v.setStyleSheet("font-size:8.5pt;")
            v.setTextFormat(Qt.RichText)
            col.addWidget(t); col.addWidget(v)
            lay.addLayout(col)
            self.valores[clave] = v
        self.valores["normativa"].setText("Resistencia: MTC E-1103<br>Durabilidad: MTC E-1104")

    def refrescar(self):
        e = self.estado
        p = e.proyecto or {}
        self.valores["proyecto"].setText(p.get("nombre") or "(sin nombre)")
        self.valores["ubicacion"].setText(
            f"{p.get('distrito','')} / {p.get('provincia','')}<br>"
            f"Altitud: {p.get('altitud','?')} msnm")
        if e.clasif:
            self.valores["clasificacion"].setText(
                f"AASHTO: {e.clasif['grupo']}<br>"
                f"SUCS: {', '.join(e.clasif['sucs_probable']) or '-'}")
        else:
            self.valores["clasificacion"].setText("-")


# ============================================================================
# SIDEBAR - TIMELINE DE 6 ETAPAS
# ============================================================================
class ItemEtapa(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, indice, titulo, icono, imagen_nombre=None):
        super().__init__()
        self.indice = indice
        self.completo = False
        self._activo = False
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        fila_sup = QHBoxLayout()
        self.lbl_circulo = QLabel()
        self.lbl_circulo.setFixedSize(26, 26)
        self.lbl_circulo.setAlignment(Qt.AlignCenter)
        fila_sup.addWidget(self.lbl_circulo)
        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setWordWrap(True)
        fila_sup.addWidget(self.lbl_titulo, 1)
        self.lbl_icono = QLabel(icono)
        self.lbl_icono.setStyleSheet("font-size:13pt;")
        fila_sup.addWidget(self.lbl_icono)
        lay.addLayout(fila_sup)

        self.lbl_miniatura = QLabel()
        self.lbl_miniatura.setAlignment(Qt.AlignCenter)
        self.lbl_miniatura.setFixedHeight(72)
        ruta_img = ASSETS_DIR / "miniaturas" / imagen_nombre if imagen_nombre else None
        if ruta_img and ruta_img.exists():
            pix = QPixmap(str(ruta_img))
            self.lbl_miniatura.setPixmap(pix.scaledToHeight(70, Qt.SmoothTransformation))
            self.lbl_icono.hide()
        lay.addWidget(self.lbl_miniatura)

        self._refrescar_estilo()

    def mousePressEvent(self, ev):
        self.clicked.emit(self.indice)

    def set_activo(self, activo):
        self._activo = activo
        self._refrescar_estilo()

    def set_completo(self, completo):
        self.completo = completo
        self._refrescar_estilo()

    def _refrescar_estilo(self):
        if self._activo:
            bg, fg, circ_bg, circ_fg, simbolo = "#e67e22", "white", "white", "#e67e22", str(self.indice + 1)
        elif self.completo:
            bg, fg, circ_bg, circ_fg, simbolo = "transparent", "#2a3441", "#1baf7a", "white", ""
        else:
            bg, fg, circ_bg, circ_fg, simbolo = "transparent", "#8a96a3", "#e7ebf0", "#8a96a3", str(self.indice + 1)
        self.setStyleSheet(f"ItemEtapa {{ background:{bg}; border-radius:8px; }}")
        self.lbl_titulo.setStyleSheet(f"font-weight:600; font-size:8.5pt; color:{fg}; background:transparent;")
        self.lbl_circulo.setText(simbolo)
        self.lbl_circulo.setStyleSheet(
            f"background:{circ_bg}; color:{circ_fg}; border-radius:15px; font-weight:700;")


class SidebarTimeline(QWidget):
    etapaSeleccionada = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(196)
        lay = QVBoxLayout(self)
        lay.setSpacing(2)
        self.items = []
        for i, (titulo, icono, imagen) in enumerate(ETAPAS_INFO):
            it = ItemEtapa(i, titulo, icono, imagen)
            it.clicked.connect(self.etapaSeleccionada.emit)
            lay.addWidget(it)
            self.items.append(it)
        lay.addStretch()
        self.set_activo(0)

    def set_activo(self, indice):
        for i, it in enumerate(self.items):
            it.set_activo(i == indice)

    def set_completos(self, lista_bool):
        for it, c in zip(self.items, lista_bool):
            it.set_completo(c)


# ============================================================================
# ETAPA 1 — PROYECTO (ubicacion)
# ============================================================================
class Etapa1Proyecto(QWidget):
    actualizado = pyqtSignal()

    def __init__(self, estado: EstadoApp):
        super().__init__()
        self.estado = estado
        lay = QVBoxLayout(self)

        gb = QGroupBox("Ubicacion y contexto del proyecto")
        form = QFormLayout()
        self.departamento = QLineEdit("Ayacucho")
        self.provincia = QLineEdit("Huamanga")
        self.distrito = QLineEdit("")
        self.nombre = QLineEdit("Camino vecinal")
        self.altitud = _ispin(0, 6000, 3200, 50)
        self.imd = _ispin(0, 99999, 0, 10)
        form.addRow("Nombre del proyecto:", self.nombre)
        form.addRow("Departamento:", self.departamento)
        form.addRow("Provincia:", self.provincia)
        form.addRow("Distrito:", self.distrito)
        form.addRow("Altitud (m.s.n.m.):", _con_flechas(self.altitud))
        form.addRow("IMD - Indice Medio Diario (veh/dia):", _con_flechas(self.imd))
        gb.setLayout(form)
        lay.addWidget(gb)

        self.region_combo = QComboBox()
        self.region_combo.addItems(list(REGIONES.keys()))
        self.lbl_ambiguo = QLabel(); self.lbl_ambiguo.setWordWrap(True)
        self.lbl_altitud_alta = QLabel(); self.lbl_altitud_alta.setWordWrap(True)

        gb2 = QGroupBox("Region (Cuadro N02 MTC)")
        v2 = QVBoxLayout()
        v2.addWidget(self.region_combo)
        v2.addWidget(self.lbl_ambiguo)
        v2.addWidget(self.lbl_altitud_alta)
        self.lbl_cuadro = QLabel(); self.lbl_cuadro.setWordWrap(True)
        self.lbl_cuadro.setStyleSheet("padding:6px;")
        v2.addWidget(self.lbl_cuadro)
        gb2.setLayout(v2)
        lay.addWidget(gb2)
        lay.addStretch()

        self.altitud.valueChanged.connect(self._sugerir_region)
        self.region_combo.currentTextChanged.connect(self._actualizar)
        for w in (self.departamento, self.provincia, self.distrito, self.nombre):
            w.textChanged.connect(self._actualizar)
        self.imd.valueChanged.connect(self._actualizar)
        self._sugerir_region()

    def _sugerir_region(self):
        sug, ambiguo, cand = sugerir_region(self.altitud.value())
        self.region_combo.blockSignals(True)
        self.region_combo.setCurrentText(sug)
        self.region_combo.blockSignals(False)
        if ambiguo:
            self.lbl_ambiguo.setText(
                f"ℹA {self.altitud.value()} m.s.n.m. la region no es unica por "
                f"altitud (el Cuadro N02 MTC solapa cotas). Candidatas: "
                f"{', '.join(cand)}. Confirme segun la vertiente de su proyecto.")
        else:
            self.lbl_ambiguo.setText("")
        if self.altitud.value() > 3000:
            self.lbl_altitud_alta.setText(
                "Altitud > 3000 msnm: aplicar consideraciones especiales de "
                "climas frios en curado y tiempos de compactacion.")
        else:
            self.lbl_altitud_alta.setText("")
        self._actualizar()

    def _actualizar(self):
        region = self.region_combo.currentText()
        info = REGIONES[region]
        self.lbl_cuadro.setText(
            f"<b>Suelos predominantes:</b> {info['suelos']}<br>"
            f"<b>Estabilizadores aplicables:</b> {', '.join(info['estabilizadores'])}")
        self.estado.proyecto = {
            "nombre": self.nombre.text() or "Proyecto", "departamento": self.departamento.text(),
            "provincia": self.provincia.text(), "distrito": self.distrito.text(),
            "altitud": self.altitud.value(), "region": region,
            "imd": self.imd.value() or "no especificado",
        }
        self.actualizado.emit()

    def cargar(self, p: dict):
        self.nombre.setText(p.get("nombre", "")); self.departamento.setText(p.get("departamento", ""))
        self.provincia.setText(p.get("provincia", "")); self.distrito.setText(p.get("distrito", ""))
        self.altitud.setValue(int(p.get("altitud", 3200)))
        imd = p.get("imd", 0)
        self.imd.setValue(int(imd) if isinstance(imd, (int, float)) else 0)


# ============================================================================
# ETAPA 2 — SUELO (granulometria + Atterberg + Proctor + clasificacion)
# ============================================================================
class Etapa2Suelo(QWidget):
    actualizado = pyqtSignal()

    def __init__(self, estado: EstadoApp):
        super().__init__()
        self.estado = estado
        lay = QVBoxLayout(self)

        fila = QHBoxLayout()
        gbG = QGroupBox("Granulometria (MTC E-107)")
        f1 = QFormLayout()
        self.X1 = _dspin(0, 100, 55.0, 0.1, 2, "%")
        self.X2 = _dspin(0, 100, 30.0, 0.1, 2, "%")
        self.X3 = _dspin(0, 100, 15.0, 0.1, 2, "%")
        f1.addRow("X1 - Grava (% ret. N4):", _con_flechas(self.X1))
        f1.addRow("X2 - Arena (% pasa N4, ret. N200):", _con_flechas(self.X2))
        f1.addRow("X3 - Finos (% pasa N200):", _con_flechas(self.X3))
        self.lbl_suma = QLabel()
        f1.addRow(self.lbl_suma)
        self.Cu = _dspin(0, 100, 0.0, 0.1, 2)
        self.Cc = _dspin(0, 10, 0.0, 0.1, 2)
        f1.addRow("Cu - Coef. Uniformidad (opcional):", _con_flechas(self.Cu))
        f1.addRow("Cc - Coef. Curvatura (opcional):", _con_flechas(self.Cc))
        lbl_cu_cc_info = QLabel(
            "<i>Deje ambos en 0.0 si no los tiene. Con Cu y Cc (de la curva "
            "granulometrica D10/D30/D60 de su ensayo) y finos &lt; 5%, la "
            "correlacion SUCS deja de ser una lista de posibles simbolos y "
            "se vuelve exacta (GW/GP/SW/SP).</i>")
        lbl_cu_cc_info.setWordWrap(True)
        lbl_cu_cc_info.setStyleSheet("color:#6c7a89; font-size:8pt;")
        f1.addRow(lbl_cu_cc_info)
        gbG.setLayout(f1)
        fila.addWidget(gbG)

        gbA = QGroupBox("Atterberg (MTC E-110 / E-111)")
        f2 = QFormLayout()
        self.np_check = QCheckBox("Suelo No Plastico (NP)")
        self.X4 = _dspin(0, 100, 20.0, 0.1, 2, "%")
        self.X5 = _dspin(0, 100, 15.0, 0.1, 2, "%")
        self.lbl_ip = QLabel("0.0 %")
        f2.addRow(self.np_check)
        f2.addRow("X4 - Limite Liquido LL:", _con_flechas(self.X4))
        f2.addRow("X5 - Limite Plastico LP:", _con_flechas(self.X5))
        f2.addRow("X6 - Indice de Plasticidad IP:", self.lbl_ip)
        gbA.setLayout(f2)
        fila.addWidget(gbA)

        gbC = QGroupBox("Compactacion (Proctor Modificado, MTC E-115)")
        f3 = QFormLayout()
        self.X7 = _dspin(0, 40, 9.0, 0.1, 1, "%")
        self.X8 = _dspin(1.0, 3.0, 2.10, 0.001, 3, "g/cm3")
        f3.addRow("X7 - OCH:", _con_flechas(self.X7))
        f3.addRow("X8 - MDS:", _con_flechas(self.X8))
        self.lbl_mds = QLabel()
        f3.addRow(self.lbl_mds)
        gbC.setLayout(f3)
        fila.addWidget(gbC)
        lay.addLayout(fila)

        fila2 = QHBoxLayout()
        gbR = QGroupBox("Clasificacion AASHTO / SUCS")
        gr = QGridLayout()
        self.lbl_grupo = QLabel(); self.lbl_grupo.setStyleSheet("font-size:14pt; font-weight:700; color:#2a5d9f;")
        self.lbl_categoria = QLabel()
        self.lbl_durham = QLabel()
        self.lbl_sucs = QLabel(); self.lbl_sucs.setWordWrap(True)
        self.lbl_advertencia = QLabel(); self.lbl_advertencia.setWordWrap(True)
        gr.addWidget(QLabel("Grupo AASHTO:"), 0, 0); gr.addWidget(self.lbl_grupo, 0, 1)
        gr.addWidget(QLabel("Categoria:"), 1, 0); gr.addWidget(self.lbl_categoria, 1, 1)
        gr.addWidget(QLabel("Exigencia Durham:"), 2, 0); gr.addWidget(self.lbl_durham, 2, 1)
        gr.addWidget(self.lbl_sucs, 3, 0, 1, 2)
        gr.addWidget(self.lbl_advertencia, 4, 0, 1, 2)
        gbR.setLayout(gr)
        fila2.addWidget(gbR, 1)

        gbP = QGroupBox("Curva Proctor (ilustrativa)")
        vp = QVBoxLayout()
        self.figura = Figure(figsize=(4.2, 2.6), dpi=100, facecolor="white")
        self.ax_proctor = self.figura.add_subplot(111)
        self.canvas = FigureCanvas(self.figura)
        self.canvas.setMinimumHeight(210)
        vp.addWidget(self.canvas)
        lbl_nota = QLabel("<i>Esquematica, centrada en OCH/MDS ingresados -- "
                          "no representa multiples ensayos reales.</i>")
        lbl_nota.setWordWrap(True)
        vp.addWidget(lbl_nota)
        gbP.setLayout(vp)
        fila2.addWidget(gbP, 1)
        lay.addLayout(fila2)
        lay.addStretch()

        for w in (self.X1, self.X2, self.X3, self.X4, self.X5, self.X7, self.X8,
                 self.Cu, self.Cc):
            w.valueChanged.connect(self._actualizar)
        self.np_check.stateChanged.connect(self._toggle_np)
        self._toggle_np()
        self._actualizar()

    def _toggle_np(self):
        np_on = self.np_check.isChecked()
        self.X4.setEnabled(not np_on); self.X5.setEnabled(not np_on)
        if np_on:
            self.X4.setValue(0.0); self.X5.setValue(0.0)
        self._actualizar()

    def _dibujar_proctor(self, och, mds):
        x = np.linspace(max(0.1, och - 5), och + 6, 60)
        k = 0.012
        y = mds - k * (x - och) ** 2
        self.ax_proctor.clear()
        self.ax_proctor.plot(x, y, "-", color="#2a5d9f", lw=2)
        self.ax_proctor.plot([och], [mds], "o", color="#e67e22", ms=8, zorder=5)
        self.ax_proctor.annotate(
            f"OCH={och:.1f}%\nMDS={mds:.3f}", (och, mds),
            xytext=(8, 14), textcoords="offset points", fontsize=7.5,
            arrowprops=dict(arrowstyle="-", color="#8a96a3", lw=0.8))
        self.ax_proctor.set_xlabel("Humedad (%)", fontsize=8)
        self.ax_proctor.set_ylabel("Densidad seca (g/cm3)", fontsize=8)
        self.ax_proctor.tick_params(labelsize=7.5)
        self.ax_proctor.grid(alpha=.3)
        self.ax_proctor.margins(y=0.22)
        for sp in ("top", "right"):
            self.ax_proctor.spines[sp].set_visible(False)
        self.figura.tight_layout(pad=0.6)
        self.canvas.draw()

    def _actualizar(self):
        X1, X2, X3 = self.X1.value(), self.X2.value(), self.X3.value()
        X4, X5 = self.X4.value(), self.X5.value()
        X6 = max(0.0, X4 - X5)
        X7, X8 = self.X7.value(), self.X8.value()
        self.lbl_ip.setText(f"{X6:.2f} %")

        suma = X1 + X2 + X3
        if abs(suma - 100) > 2:
            _pintar_estado(self.lbl_suma, False, f"Granulometria no suma 100% (suma = {suma:.1f}%)")
        else:
            _pintar_estado(self.lbl_suma, True, f"Granulometria OK (suma = {suma:.1f}%)")

        if X8 <= 1.5:
            _pintar_estado(self.lbl_mds, "amarillo", "Verificar dato de compactacion (MDS <= 1.5 g/cm3)")
        else:
            self.lbl_mds.setText(""); self.lbl_mds.setStyleSheet("")

        self._dibujar_proctor(X7, X8)

        cu, cc = self.Cu.value(), self.Cc.value()
        clasif = clasificar_aashto_detallado(X1, X2, X3, X4, X5, X6, cu or None, cc or None)
        self.lbl_grupo.setText(clasif["grupo"])
        self.lbl_categoria.setText(clasif["categoria"])
        self.lbl_durham.setText(f"<= {clasif['exigencia_durham']:.0f} %")
        if clasif["sucs_exacto"]:
            self.lbl_sucs.setText(
                f"<b>SUCS (exacto, segun Cu={cu:.1f}/Cc={cc:.1f}):</b> {clasif['sucs_exacto']}")
        else:
            self.lbl_sucs.setText(
                f"<b>SUCS probable:</b> {', '.join(clasif['sucs_probable']) or '-'}<br>"
                f"<b>SUCS posible:</b> {', '.join(clasif['sucs_posible']) or '-'}<br>"
                f"<b>SUCS posible pero improbable:</b> {', '.join(clasif['sucs_improbable']) or '-'}")
        if clasif["grupo"] in ("A-4", "A-5", "A-6", "A-7-5", "A-7-6"):
            _pintar_estado(self.lbl_advertencia, "amarillo",
                          f"Suelo arcilloso/limoso ({clasif['grupo']}). Suelo-cemento es "
                          "tecnicamente posible pero economicamente no recomendable para CNP. "
                          "Considere cal o evalue otra cantera granular.")
        else:
            _pintar_estado(self.lbl_advertencia, True,
                          "Suelo granular apto para estabilizacion con cemento Portland.")

        self.estado.suelo = {"X1": X1, "X2": X2, "X3": X3, "X4": X4, "X5": X5,
                             "X6": X6, "X7": X7, "X8": X8}
        self.estado.clasif = clasif
        self.actualizado.emit()

    def cargar(self, s: dict):
        self.X1.setValue(s.get("X1", 55.0)); self.X2.setValue(s.get("X2", 30.0))
        self.X3.setValue(s.get("X3", 15.0))
        if s.get("X4", 0) == 0 and s.get("X6", 0) == 0:
            self.np_check.setChecked(True)
        else:
            self.np_check.setChecked(False)
            self.X4.setValue(s.get("X4", 20.0)); self.X5.setValue(s.get("X5", 15.0))
        self.X7.setValue(s.get("X7", 9.0)); self.X8.setValue(s.get("X8", 2.10))
        self.Cu.setValue(s.get("Cu", 0.0)); self.Cc.setValue(s.get("Cc", 0.0))


def _checks_normativa_a(estado: EstadoApp):
    """Version COMPLETA de la Seccion A (para el reporte PDF): todos los
    criterios que el Cuadro 9.2 exige como obligatorios para cemento Portland,
    incluyendo CMO/Sulfatos/Abrasion -- exigencias reales del Cuadro 9.2 que
    este software NO mide (no hay ensayo quimico/mecanico en el modelo RNA,
    no se mapearon como variables de entrada X1..X9 por falta de datos en el
    dataset de entrenamiento). Se marcan NO VERIFICADO, nunca se asume que
    cumplen -- quedan documentadas en el PDF como limitacion/trabajo futuro,
    sin saturar la pantalla principal (ver _checks_normativa_a_pantalla)."""
    s = estado.suelo
    usace = verificar_restriccion_usace(s["X1"], s["X2"], s["X3"], s["X4"], s["X6"])
    return [
        ("Limite Liquido > 40% (Cuadro 9.2)", s["X4"] > 40, s["X4"] > 40,
         "LL no supera el limite minimo del Cuadro 9.2 (debe ser > 40%)"),
        ("Indice de Plasticidad >= 18% (Cuadro 9.2)", s["X6"] >= 18, s["X6"] >= 18,
         "IP no alcanza el limite minimo del Cuadro 9.2 (debe ser >= 18%)"),
        ("Materia organica (CMO) < 1.0% (Cuadro 9.2)", None, "amarillo",
         "No verificado -- no mapeado como variable de entrada del modelo RNA "
         "(requiere ensayo de laboratorio independiente; trabajo futuro si se "
         "dispone de suficiente data)"),
        ("Sulfatos (SO4) < 0.2% (Cuadro 9.2)", None, "amarillo",
         "No verificado -- no mapeado como variable de entrada del modelo RNA "
         "(requiere ensayo de laboratorio independiente; trabajo futuro si se "
         "dispone de suficiente data)"),
        ("Abrasion < 50% (Cuadro 9.2)", None, "amarillo",
         "No verificado -- no mapeado como variable de entrada del modelo RNA "
         "(requiere ensayo de laboratorio independiente; trabajo futuro si se "
         "dispone de suficiente data)"),
        (f"Restriccion USACE (Cuadro 9.1, familia {usace['familia']})",
         usace["cumple"], usace["cumple"], usace["restriccion"]),
    ]


def _checks_normativa_a_pantalla(estado: EstadoApp):
    """Version de PANTALLA de la Seccion A (Etapa3Normativa): solo lo que
    el software puede verificar/calcular con los datos ingresados. Encabeza
    con el limite Durham aplicable a ESTE suelo (Cuadro N01) -- es el dato
    fundamental para decidir si conviene o no estabilizar con cemento, mas
    relevante en pantalla que CMO/Sulfatos/Abrasion (que no son verificables
    aqui y solo se documentan en el reporte PDF, ver _checks_normativa_a)."""
    s, c = estado.suelo, estado.clasif
    usace = verificar_restriccion_usace(s["X1"], s["X2"], s["X3"], s["X4"], s["X6"])
    return [
        ("Limite Liquido > 40% (Cuadro 9.2)", s["X4"] > 40, s["X4"] > 40,
         "LL no supera el limite minimo del Cuadro 9.2 (debe ser > 40%)", None),
        ("Indice de Plasticidad >= 18% (Cuadro 9.2)", s["X6"] >= 18, s["X6"] >= 18,
         "IP no alcanza el limite minimo del Cuadro 9.2 (debe ser >= 18%)", None),
        (f"Perdida Durham maxima admisible (MTC E-1104, Cuadro N01) para "
         f"suelo {c['grupo']} ({c['categoria']})", True, "optimo",
         f"<= {c['exigencia_durham']:.0f}% -- criterio fundamental para decidir "
         "si conviene estabilizar con cemento. Vea la Y2 predicha en la "
         "Etapa 4 (Prediccion) o Etapa 5 (Curva Completa).", "ℹ"),
        (f"Restriccion USACE (Cuadro 9.1, familia {usace['familia']})",
         usace["cumple"], usace["cumple"], usace["restriccion"], None),
    ]


# ============================================================================
# ETAPA 3 — NORMATIVA (Seccion A: requisitos MTC obligatorios / Seccion B:
# criterios de calidad del modelo RNA, recomendaciones)
# ============================================================================
class Etapa3Normativa(QWidget):
    def __init__(self, estado: EstadoApp):
        super().__init__()
        self.estado = estado
        lay = QVBoxLayout(self)

        gbA = QGroupBox("Seccion A — Requisitos normativos MTC (obligatorios, Cuadro 9.2)")
        va = QVBoxLayout()
        lbl_nota_suelo = QLabel(
            "ℹSegun el Cuadro 9.2 MTC, el cemento Portland es aplicable a suelos "
            "A-1, A-2, A-3, A-4, A-5, A-6 y A-7 -- TODOS los grupos AASHTO son "
            "aceptables. No es un requisito restrictivo por tipo de suelo.")
        lbl_nota_suelo.setWordWrap(True)
        lbl_nota_suelo.setStyleSheet("color:#2a5d9f; font-style:italic; padding:4px;")
        va.addWidget(lbl_nota_suelo)
        self.tabla_a = QTableWidget(0, 3)
        self.tabla_a.setHorizontalHeaderLabels(["Criterio", "Estado", "Observacion"])
        self.tabla_a.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_a.setEditTriggers(QTableWidget.NoEditTriggers)
        va.addWidget(self.tabla_a)
        gbA.setLayout(va)
        lay.addWidget(gbA)

        gbB = QGroupBox("Seccion B — Criterios de calidad del modelo RNA (recomendaciones)")
        vb = QVBoxLayout()
        self.tabla_b = QTableWidget(0, 3)
        self.tabla_b.setHorizontalHeaderLabels(["Criterio", "Estado", "Observacion"])
        self.tabla_b.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_b.setEditTriggers(QTableWidget.NoEditTriggers)
        vb.addWidget(self.tabla_b)
        gbB.setLayout(vb)
        lay.addWidget(gbB)
        lay.addStretch()

    def refrescar(self, estado: EstadoApp):
        if not estado.suelo or not estado.clasif:
            return
        s, c = estado.suelo, estado.clasif
        suma = s["X1"] + s["X2"] + s["X3"]

        checks_a = _checks_normativa_a_pantalla(estado)
        checks_b = [
            ("Finos <= 35% (filtro del modelo, mantiene suelos granulares)",
             s["X3"] <= 35, s["X3"] <= 35, "Exceso de finos para el modelo entrenado", None),
            ("MDS > 1.5 g/cm3 (filtro del modelo, excluye suelos organicos/livianos)",
             s["X8"] > 1.5, s["X8"] > 1.5, "Verificar dato de compactacion", None),
            ("Granulometria suma 100% +-2% (consistencia de datos)",
             abs(suma - 100) <= 2, abs(suma - 100) <= 2, "Granulometria no suma 100%", None),
        ]
        for tabla, checks in ((self.tabla_a, checks_a), (self.tabla_b, checks_b)):
            tabla.setRowCount(len(checks))
            for r, (crit, ok, color, msg, simbolo_forzado) in enumerate(checks):
                simbolo = simbolo_forzado or ("" if ok is None else ("" if ok else ""))
                tabla.setItem(r, 0, _item(crit))
                tabla.setItem(r, 1, _item(simbolo, color))
                tabla.setItem(r, 2, _item("-" if (ok and not simbolo_forzado) else msg))
            tabla.resizeRowsToContents()


# ============================================================================
# ETAPA 4 — PREDICCION (Y1 numerico + Y2 numerico con advertencia de precision)
# ============================================================================
class CajaY2(QFrame):
    """Caja de durabilidad Durham -- valor NUMERICO estimado (no solo un
    veredicto cualitativo), con advertencia de precision limitada (77% de
    acierto en clasificacion cumple/no-cumple, dataset de 22 filas)."""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Box)
        v = QVBoxLayout(self)
        self.titulo = QLabel("DURABILIDAD DURHAM (MTC E-1104)")
        self.titulo.setStyleSheet("font-weight:700; font-size:10.5pt;")
        v.addWidget(self.titulo)
        self.valor = QLabel(); self.valor.setStyleSheet("font-size:15pt; font-weight:700;")
        v.addWidget(self.valor)
        self.estado_txt = QLabel(); self.estado_txt.setWordWrap(True)
        v.addWidget(self.estado_txt)
        self.aviso = QLabel()
        self.aviso.setStyleSheet("color:#6b4c00; font-size:8.5pt;")
        self.aviso.setWordWrap(True)
        v.addWidget(self.aviso)
        self._neutro()

    def _neutro(self):
        self.valor.setText("—")
        self.estado_txt.setText("")
        self.aviso.setText(
            "Prediccion numerica con precision limitada (dataset de 22 "
            "filas). Se requiere ensayo MTC E-1104 para confirmacion.")
        self.setStyleSheet("QFrame { border: 2px solid #d4dae2; border-radius: 8px; padding: 6px; }")

    def actualizar(self, y2_pct: float, limite: float, grupo: str, confianza: dict = None):
        cumple = y2_pct <= limite
        self.valor.setText(f"Perdida Durham estimada = {y2_pct:.1f}%")
        if cumple:
            self.estado_txt.setText(f"Maximo admisible: {limite:.0f}% (suelo {grupo}). CUMPLE ")
            self.estado_txt.setStyleSheet("color:#0b5a35; font-weight:700;")
            self.setStyleSheet("QFrame { border: 2px solid #1baf7a; border-radius: 8px; "
                              "padding: 6px; background:#f3fbf7; }")
        else:
            self.estado_txt.setText(f"Maximo admisible: {limite:.0f}% (suelo {grupo}). "
                                    "NO CUMPLE — Aumente % de cemento.")
            self.estado_txt.setStyleSheet("color:#7a1414; font-weight:700;")
            self.setStyleSheet("QFrame { border: 2px solid #d03b3b; border-radius: 8px; "
                              "padding: 6px; background:#fdf5f5; }")
        if confianza:
            colores_txt = {"verde": "#0b5a35", "amarillo": "#6b4c00", "rojo": "#7a1414"}
            self.aviso.setStyleSheet(
                f"color:{colores_txt.get(confianza['color'], '#6b4c00')}; font-size:8.5pt; font-weight:600;")
            self.aviso.setText(confianza["mensaje"])


class Etapa4Prediccion(QWidget):
    x9_cambiado = pyqtSignal(float)

    def __init__(self, estado: EstadoApp):
        super().__init__()
        self.estado = estado
        lay = QVBoxLayout(self)

        fx9 = QHBoxLayout()
        fx9.addWidget(QLabel("X9 - Cemento (%, en peso de suelo seco):"))
        self.X9 = _dspin(0.5, 15.0, 5.0, 0.1, 1)
        self.X9.valueChanged.connect(self._on_x9_cambiado)
        fx9.addWidget(_con_flechas(self.X9))
        fx9.addStretch()
        lay.addLayout(fx9)
        self.lbl_rango_aviso = QLabel(); self.lbl_rango_aviso.setWordWrap(True)
        lay.addWidget(self.lbl_rango_aviso)
        self.lbl_rango_info = QLabel(); self.lbl_rango_info.setWordWrap(True)
        lay.addWidget(self.lbl_rango_info)

        self.btn_predecir = QPushButton("PREDECIR")
        self.btn_predecir.clicked.connect(self._predecir)
        lay.addWidget(self.btn_predecir)

        self.lbl_escenario = QLabel(); self.lbl_escenario.setWordWrap(True)
        lay.addWidget(self.lbl_escenario)

        cols = QHBoxLayout()
        gb1 = QGroupBox("Resistencia Y1 (MTC E-1103)")
        v1 = QVBoxLayout()
        fila_titulo1 = QHBoxLayout()
        fila_titulo1.addStretch()
        self.btn_ayuda_y1 = QPushButton("?"); self.btn_ayuda_y1.setFixedWidth(28)
        self.btn_ayuda_y1.clicked.connect(lambda: self._mostrar_ayuda("Ensayo MTC E-1103", TEXTO_E1103))
        fila_titulo1.addWidget(self.btn_ayuda_y1)
        v1.addLayout(fila_titulo1)
        self.lbl_y1_valor = QLabel("—"); self.lbl_y1_valor.setStyleSheet("font-size:16pt; font-weight:700;")
        self.lbl_y1_estado = QLabel(); self.lbl_y1_estado.setWordWrap(True)
        self.lbl_y1_caption = QLabel(); self.lbl_y1_caption.setStyleSheet("color:#6c7a89; font-size:9pt;")
        self.lbl_y1_a2 = QLabel(); self.lbl_y1_a2.setWordWrap(True)
        self.lbl_y1_a2.setStyleSheet("color:#2a5d9f; font-size:8.5pt;")
        v1.addWidget(self.lbl_y1_valor); v1.addWidget(self.lbl_y1_estado); v1.addWidget(self.lbl_y1_caption)
        v1.addWidget(self.lbl_y1_a2)
        gb1.setLayout(v1)
        cols.addWidget(gb1)

        gb2 = QGroupBox("Durabilidad Y2 (MTC E-1104, Durham)")
        v2b = QVBoxLayout()
        fila_titulo2 = QHBoxLayout()
        fila_titulo2.addStretch()
        self.btn_ayuda_y2 = QPushButton("?"); self.btn_ayuda_y2.setFixedWidth(28)
        self.btn_ayuda_y2.clicked.connect(lambda: self._mostrar_ayuda("Ensayo MTC E-1104 (Durham)", TEXTO_E1104))
        fila_titulo2.addWidget(self.btn_ayuda_y2)
        v2b.addLayout(fila_titulo2)
        self.caja_y2 = CajaY2()
        v2b.addWidget(self.caja_y2)
        gb2.setLayout(v2b)
        cols.addWidget(gb2)
        lay.addLayout(cols)
        lay.addStretch()

        self.refrescar_contexto(estado)

    def _mostrar_ayuda(self, titulo, html):
        box = QMessageBox(self)
        box.setWindowTitle(titulo)
        box.setTextFormat(Qt.RichText)
        box.setText(html)
        box.setIcon(QMessageBox.Information)
        box.exec_()

    def refrescar_contexto(self, estado: EstadoApp):
        self._chequear_rango()

    def _chequear_rango(self):
        c = self.estado.clasif
        x9 = self.X9.value()
        lo, hi = RANGO_MTC_CEMENTO
        if x9 < lo or x9 > hi:
            _pintar_estado(self.lbl_rango_aviso, False,
                          f"Dosificacion fuera del rango normativo MTC Cuadro 9.2 "
                          f"({lo:.0f}-{hi:.0f}%).")
        else:
            self.lbl_rango_aviso.setText(""); self.lbl_rango_aviso.setStyleSheet("")

        texto = (f"Rango normativo MTC (Cuadro 9.2): <b>{lo:.0f}% - {hi:.0f}%</b> "
                "(obligatorio, valido para todos los grupos AASHTO).")
        if c:
            rf = rango_fhwa(c["grupo"])
            if rf:
                texto += (f" Rango referencial FHWA para suelo {c['grupo']}: "
                         f"{rf[0]}-{rf[1]}% (orientativo, complementario).")
        self.lbl_rango_info.setText(texto)

    def _on_x9_cambiado(self, valor):
        self.estado.x9_usuario = valor
        self._chequear_rango()
        self.x9_cambiado.emit(valor)

    def _predecir(self):
        s = self.estado.suelo
        if not s:
            QMessageBox.warning(self, "Falta informacion", "Complete primero la Etapa 2 (Suelo).")
            return
        entrada = {"X1": s["X1"], "X3": s["X3"], "X4": s["X4"], "X6": s["X6"],
                  "X7": s["X7"], "X8": s["X8"], "X9": self.X9.value()}
        r = predecir(entrada)
        self.estado.prediccion = r
        self.estado.entrada_actual = entrada

        y1 = r["Y1_MPa"]; y1kg = round(y1 * MPA_A_KGCM2, 1)
        self.lbl_y1_valor.setText(f"{y1:.2f} MPa  ({y1kg:.1f} kg/cm2)")
        criterio = f"(criterio: minimo normativo Cuadro N01 MTC = {Y1_MIN_MPA:.3f} MPa = 18.0 kg/cm2)"
        if y1 < Y1_MIN_MPA:
            _pintar_estado(self.lbl_y1_estado, False,
                          f"ESTIMACION PRELIMINAR: NO alcanza el umbral {criterio}. "
                          "Aumentar % cemento o evaluar otra cantera; confirmar con "
                          "ensayo de laboratorio.")
        elif y1 < 2.0:
            _pintar_estado(self.lbl_y1_estado, "amarillo",
                          f"ESTIMACION PRELIMINAR: alcanzaria el umbral {criterio}, con "
                          f"margen reducido (+{y1 - Y1_MIN_MPA:.2f} MPa). Pendiente de "
                          "verificar con ensayo MTC E-1103.")
        elif y1 < 3.0:
            _pintar_estado(self.lbl_y1_estado, True,
                          f"ESTIMACION PRELIMINAR: alcanzaria el umbral {criterio}, con "
                          f"margen adecuado (+{y1 - Y1_MIN_MPA:.2f} MPa). Pendiente de "
                          "verificacion experimental; no constituye aprobacion para diseno.")
        else:
            _pintar_estado(self.lbl_y1_estado, True,
                          f"ESTIMACION PRELIMINAR: alcanzaria el umbral {criterio}, "
                          f"holgadamente (+{y1 - Y1_MIN_MPA:.2f} MPa). Evaluar reducir % "
                          "cemento por economia; pendiente de verificacion experimental.")
        self.lbl_y1_caption.setText("R2 LOGO (suelo nuevo) = 0.467 · R2 LODO (dosis faltante del mismo suelo) = 0.64")
        a2 = coeficiente_estructural_a2(y1kg)
        self.lbl_y1_a2.setText(
            f"Coeficiente estructural a2 (AASHTO 1993) estimado: <b>{a2:.3f}</b>. "
            "Uselo junto con el CBR de subrasante y los ejes equivalentes de su "
            "proyecto en su plantilla AASHTO 1993 (SN = a2 x D2) para calcular el "
            "espesor -- este software no calcula espesor de pavimento ni costos, "
            "porque esos dos datos son especificos de cada proyecto.")

        y2 = r["durham"]
        grupo = self.estado.clasif["grupo"] if self.estado.clasif else "-"
        self.caja_y2.actualizar(y2["Y2_perdida_pct"], y2["umbral_normativo_pct"], grupo,
                                y2.get("confianza"))

        escenario = evaluar_escenario(y1, y2["Y2_perdida_pct"], y2["umbral_normativo_pct"])
        _pintar_estado(self.lbl_escenario, escenario["color"], escenario["mensaje"])


# ============================================================================
# ETAPA 5 — CURVA COMPLETA (matplotlib embebido)
# ============================================================================
class Etapa5Curva(QWidget):
    def __init__(self, estado: EstadoApp):
        super().__init__()
        self.estado = estado
        lay = QVBoxLayout(self)

        self.btn_curva = QPushButton("Generar Curva Completa (1% a 12% cemento)")
        self.btn_curva.clicked.connect(self._generar)
        lay.addWidget(self.btn_curva)

        fila_central = QHBoxLayout()
        col_izq = QVBoxLayout()
        self.figura = Figure(figsize=(7, 3.6), dpi=100, facecolor="white")
        self.ax = self.figura.add_subplot(111)
        self.canvas = FigureCanvas(self.figura)
        self.canvas.setMinimumHeight(300)
        col_izq.addWidget(self.canvas)
        fila_central.addLayout(col_izq, 3)

        col_der = QVBoxLayout()
        gbo = QGroupBox("Evaluacion optima")
        vo = QVBoxLayout()
        self.lbl_opt_titulo = QLabel("—"); self.lbl_opt_titulo.setStyleSheet("font-weight:700;")
        vo.addWidget(self.lbl_opt_titulo)
        caja_res_opt = QFrame(); caja_res_opt.setFrameShape(QFrame.Box)
        vres = QVBoxLayout(caja_res_opt)
        vres.addWidget(QLabel("<b>Resistencia (MTC E-1103)</b>"))
        self.lbl_opt_y1 = QLabel("—"); self.lbl_opt_y1.setStyleSheet("font-size:14pt; font-weight:700;")
        vres.addWidget(self.lbl_opt_y1)
        self.lbl_opt_y1_estado = QLabel(); vres.addWidget(self.lbl_opt_y1_estado)
        self.lbl_opt_a2 = QLabel(); self.lbl_opt_a2.setWordWrap(True)
        self.lbl_opt_a2.setStyleSheet("color:#2a5d9f; font-size:8.5pt;")
        vres.addWidget(self.lbl_opt_a2)
        vo.addWidget(caja_res_opt)
        caja_dur_opt = QFrame(); caja_dur_opt.setFrameShape(QFrame.Box)
        vdur = QVBoxLayout(caja_dur_opt)
        vdur.addWidget(QLabel("<b>Durabilidad (MTC E-1104)</b>"))
        self.lbl_opt_y2_estado = QLabel(); self.lbl_opt_y2_estado.setWordWrap(True)
        vdur.addWidget(self.lbl_opt_y2_estado)
        vo.addWidget(caja_dur_opt)
        gbo.setLayout(vo)
        col_der.addWidget(gbo)

        gbn = QGroupBox("Notas importantes")
        vn = QVBoxLayout()
        lbl_notas = QLabel(
            "• La dosificacion optima cumple resistencia y durabilidad.\n"
            "• Iniciar compactacion: MAXIMO 2 horas despues de mezclar.\n"
            "• Curado minimo 7 dias (se recomienda 14 en zonas criticas).\n"
            "• Control de calidad segun Cuadro N01 MTC y Cuadro 9.2 MTC.\n"
            "• Resultados obtenidos con Modelo RNA v7.0 entrenado con 84 datos verificados.")
        lbl_notas.setWordWrap(True)
        vn.addWidget(lbl_notas)
        gbn.setLayout(vn)
        col_der.addWidget(gbn)
        col_der.addStretch()
        fila_central.addLayout(col_der, 2)
        lay.addLayout(fila_central)

        self.tabla = QTableWidget(0, 9)
        self.tabla.setHorizontalHeaderLabels(
            ["% Cemento", "Y1 (MPa)", "Y1 (kg/cm2)", "Cumple Y1", "Y2 (%)",
             "Cumple Y2", "kg cemento/m3", "bolsas/m3", "Coef. a2 (AASHTO 93)"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.tabla)

        fila_botones = QHBoxLayout()
        self.btn_exportar_png = QPushButton("Exportar Curva (PNG)")
        self.btn_exportar_png.clicked.connect(self._exportar_png)
        fila_botones.addWidget(self.btn_exportar_png)
        fila_botones.addStretch()
        lay.addLayout(fila_botones)

        self._dibujar_vacio()

    def _dibujar_vacio(self):
        self.ax.clear()
        self.ax.set_xlabel("Cemento (%)"); self.ax.set_ylabel("Y1 (MPa)")
        self.ax.set_title("Curva de dosificacion suelo-cemento")
        self.ax.grid(alpha=.3)
        for sp in ("top", "right"):
            self.ax.spines[sp].set_visible(False)
        self.canvas.draw()

    def refrescar_si_corresponde(self, estado: EstadoApp):
        if estado.curva_base is None:
            return
        base_actual = {k: estado.suelo.get(k) for k in estado.curva_base}
        if base_actual != estado.curva_base:
            self._generar()

    def _punto_usuario(self, estado: EstadoApp):
        if estado.x9_usuario is None or not estado.suelo:
            return None
        s = estado.suelo
        entrada = {"X1": s["X1"], "X3": s["X3"], "X4": s["X4"], "X6": s["X6"],
                  "X7": s["X7"], "X8": s["X8"], "X9": estado.x9_usuario}
        try:
            return (estado.x9_usuario, predecir(entrada)["Y1_MPa"])
        except Exception:
            return None

    def refrescar_marca_usuario(self, estado: EstadoApp):
        if estado.curva_df is None:
            return
        _dibujar_curva_en_ejes(self.ax, estado.curva_df, estado.optimo,
                               self._punto_usuario(estado))
        self.canvas.draw()
        self.estado.figura_curva = self.figura

    def _generar(self):
        s = self.estado.suelo
        if not s:
            QMessageBox.warning(self, "Falta informacion", "Complete primero la Etapa 2 (Suelo).")
            return
        base = {"X1": s["X1"], "X3": s["X3"], "X4": s["X4"], "X6": s["X6"],
               "X7": s["X7"], "X8": s["X8"]}
        df = curva_dosificacion(base, 1.0, 12.0, 0.5)
        self.estado.curva_df = df
        self.estado.curva_base = base
        opt = encontrar_optimo(df)
        self.estado.optimo = opt

        _dibujar_curva_en_ejes(self.ax, df, opt, self._punto_usuario(self.estado))
        self.canvas.draw()
        self.estado.figura_curva = self.figura

        self.tabla.setRowCount(len(df))
        for r, row in df.iterrows():
            es_opt = bool(opt) and row.cemento == opt["cemento"]
            marca = "optimo" if es_opt else None
            self.tabla.setItem(r, 0, _item(f"{row.cemento:.1f}", marca, es_opt))
            self.tabla.setItem(r, 1, _item(f"{row.Y1_MPa:.2f}", marca))
            self.tabla.setItem(r, 2, _item(f"{row.Y1_kgcm2:.1f}", marca))
            self.tabla.setItem(r, 3, _item("" if row.cumple_Y1 else "", row.cumple_Y1))
            self.tabla.setItem(r, 4, _item(f"{row.Y2_pct:.1f}", marca))
            self.tabla.setItem(r, 5, _item("" if row.cumple_Y2 else "", row.cumple_Y2))
            self.tabla.setItem(r, 6, _item(f"{row.kg_m3:.1f}", marca))
            self.tabla.setItem(r, 7, _item(f"{row.bolsas_m3:.2f}", marca))
            self.tabla.setItem(r, 8, _item(f"{row.a2:.3f}", marca))
        self.tabla.resizeRowsToContents()

        if opt:
            self.estado.dosif_practica = {k: opt[k] for k in ("kg_m3", "bolsas_m3")}
            self.lbl_opt_titulo.setText(f"EVALUACION OPTIMA ({opt['cemento']:.1f}% cemento)")
            self.lbl_opt_y1.setText(f"{opt['Y1_MPa']:.2f} MPa\n{opt['Y1_kgcm2']:.1f} kg/cm2")
            _pintar_estado(self.lbl_opt_y1_estado, True, "CUMPLE (> 1.765 MPa)")
            self.lbl_opt_a2.setText(
                f"Coeficiente estructural a2 (AASHTO 1993): <b>{opt['a2']:.3f}</b>. "
                "Uselo con el CBR de subrasante y ejes equivalentes de su proyecto "
                "para calcular el espesor en su plantilla AASHTO 1993.")
            _pintar_estado(self.lbl_opt_y2_estado, True,
                          f"CUMPLE ({opt['Y2_pct']:.1f}% < {opt['exigencia_durham']:.0f}% max.)")
        else:
            self.estado.dosif_practica = None
            self.lbl_opt_titulo.setText("Sin dosificacion optima")
            self.lbl_opt_y1.setText("—")
            self.lbl_opt_a2.setText("")
            escenario5 = mensaje_ninguna_dosis_cumple()
            _pintar_estado(self.lbl_opt_y1_estado, escenario5["color"], escenario5["mensaje"])
            self.lbl_opt_y2_estado.setText("")

    def _exportar_png(self):
        if self.estado.curva_df is None:
            QMessageBox.warning(self, "Falta informacion", "Genere primero la curva completa.")
            return
        OUTPUT_DIR.mkdir(exist_ok=True)
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar curva como PNG", str(OUTPUT_DIR / "curva_dosificacion.png"),
            "Imagen PNG (*.png)")
        if not ruta:
            return
        self.figura.savefig(ruta, dpi=200, bbox_inches="tight")
        QMessageBox.information(self, "Exportado", f"Curva guardada en:\n{ruta}")


# ============================================================================
# ETAPA 6 — REPORTE (incluye seccion de estabilizadores como respaldo normativo)
# ============================================================================
class Etapa6Reporte(QWidget):
    def __init__(self, estado: EstadoApp):
        super().__init__()
        self.estado = estado
        lay = QVBoxLayout(self)
        lbl_info_espesor = QLabel(
            "<i>Este software calcula el coeficiente estructural a2 (AASHTO "
            "1993, 0.15-0.25 segun resistencia) de la capa de suelo-cemento "
            "como dato de salida (Etapa 4 y Etapa 5) -- pero NO calcula el "
            "espesor de pavimento ni el costo, porque eso requiere el CBR de "
            "subrasante y los ejes equivalentes de cada proyecto especifico, "
            "datos que el software no tiene. Use el a2 en su propia plantilla "
            "AASHTO 1993. No se usa USACE/NAASRA porque esos metodos son para "
            "afirmado granular sin tratar, no para una capa tratada como el "
            "suelo-cemento. El reporte incluye la evaluacion de los 8 "
            "estabilizadores del Cuadro 9.2 MTC como informacion de respaldo "
            "normativo.</i>")
        lbl_info_espesor.setWordWrap(True)
        lay.addWidget(lbl_info_espesor)
        gb_fotos = QGroupBox("Fotos del proyecto (opcional -- se incluyen en el PDF como "
                             "Registro Fotografico)")
        v_fotos = QVBoxLayout()
        lbl_fotos_info = QLabel(
            "Adjunte fotos de campo (calicata, ensayo, obra, etc.). No son "
            "obligatorias: el reporte se genera igual sin fotos.")
        lbl_fotos_info.setWordWrap(True)
        lbl_fotos_info.setStyleSheet("color:#5a6472; font-size:8.5pt;")
        v_fotos.addWidget(lbl_fotos_info)
        self.lista_fotos = QListWidget()
        self.lista_fotos.setMaximumHeight(120)
        v_fotos.addWidget(self.lista_fotos)
        f_botones = QHBoxLayout()
        self.btn_agregar_foto = QPushButton("Agregar foto(s)")
        self.btn_agregar_foto.clicked.connect(self._agregar_fotos)
        f_botones.addWidget(self.btn_agregar_foto)
        self.btn_editar_leyenda = QPushButton("Editar leyenda")
        self.btn_editar_leyenda.clicked.connect(self._editar_leyenda_foto)
        f_botones.addWidget(self.btn_editar_leyenda)
        self.btn_quitar_foto = QPushButton("Quitar")
        self.btn_quitar_foto.clicked.connect(self._quitar_foto)
        f_botones.addWidget(self.btn_quitar_foto)
        f_botones.addStretch()
        v_fotos.addLayout(f_botones)
        gb_fotos.setLayout(v_fotos)
        lay.addWidget(gb_fotos)

        self.btn_pdf = QPushButton("Generar Reporte (PDF)")
        self.btn_pdf.clicked.connect(self._generar)
        self.btn_pdf.setMinimumWidth(260)
        fila_btn_pdf = QHBoxLayout()
        fila_btn_pdf.addStretch()
        fila_btn_pdf.addWidget(self.btn_pdf)
        fila_btn_pdf.addStretch()
        lay.addLayout(fila_btn_pdf)
        self.preview = QTextEdit(); self.preview.setReadOnly(True)
        lay.addWidget(self.preview)

    def _agregar_fotos(self):
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Agregar fotos del proyecto", str(Path.home()),
            "Imagenes (*.png *.jpg *.jpeg)")
        for ruta in rutas:
            self.estado.fotos_reporte.append({"ruta": ruta, "leyenda": Path(ruta).stem})
        self._refrescar_lista_fotos()

    def _quitar_foto(self):
        fila = self.lista_fotos.currentRow()
        if fila < 0:
            return
        del self.estado.fotos_reporte[fila]
        self._refrescar_lista_fotos()

    def _editar_leyenda_foto(self):
        fila = self.lista_fotos.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccione una foto",
                                   "Primero seleccione una foto de la lista.")
            return
        actual = self.estado.fotos_reporte[fila]["leyenda"]
        texto, ok = QInputDialog.getText(self, "Editar leyenda",
                                         "Leyenda de la foto (aparece debajo en el PDF):",
                                         text=actual)
        if ok and texto.strip():
            self.estado.fotos_reporte[fila]["leyenda"] = texto.strip()
            self._refrescar_lista_fotos()

    def _refrescar_lista_fotos(self):
        self.lista_fotos.clear()
        for foto in self.estado.fotos_reporte:
            nombre = Path(foto["ruta"]).name
            self.lista_fotos.addItem(QListWidgetItem(f"{nombre}  --  \"{foto['leyenda']}\""))

    def _evaluar_estabilizadores_y_cal(self, e: EstadoApp):
        quimico_vacio = {"CMO": None, "sulfatos": None, "equiv_arena": None,
                         "abrasion": None, "ph": None}
        if not e.clasif:
            return None, None
        estabs = evaluar_estabilizadores(e.suelo, e.clasif["grupo"], quimico_vacio)
        nota_cal = None
        cal = next((r for r in estabs if r["nombre"] == "Cal"), None)
        region = (e.proyecto or {}).get("region")
        cal_apta_por_suelo = cal and all(est == APTO for _, est in cal["criterios"][:2])
        if cal_apta_por_suelo and region and "Cal" not in REGIONES[region]["estabilizadores"]:
            ip = e.suelo.get("X6", 0)
            grupo = e.clasif["grupo"]
            nota_cal = (
                f"Nota: Cal no esta listada para la region {region} en el Cuadro N02 "
                f"MTC. Sin embargo, segun el Cuadro 9.2 la cal es tecnicamente "
                f"aplicable para este tipo de suelo (IP={ip:.1f}, clasificacion "
                f"{grupo}). La omision del Cuadro N02 se debe a que en sierra/costa "
                "predominan suelos granulares donde la cal no es efectiva. Si su "
                "suelo especifico es arcilloso, la cal podria ser una alternativa "
                "valida -- consulte con el especialista.")
        return estabs, nota_cal

    def _generar(self):
        e = self.estado
        if not e.prediccion:
            QMessageBox.warning(self, "Falta informacion",
                               "Primero prediga en la Etapa 4 (Prediccion).")
            return
        s = e.suelo
        base = {"X1": s["X1"], "X3": s["X3"], "X4": s["X4"], "X6": s["X6"],
               "X7": s["X7"], "X8": s["X8"]}
        df = curva_dosificacion(base, 1.0, 12.0, 0.5)
        opt = encontrar_optimo(df)
        dosif_practica = ({k: opt[k] for k in ("kg_m3", "bolsas_m3")} if opt else None)
        e.curva_df, e.curva_base, e.optimo, e.dosif_practica = df, base, opt, dosif_practica

        estabs, nota_cal = self._evaluar_estabilizadores_y_cal(e)
        checks_normativa_a = _checks_normativa_a(e)

        contexto = {
            "proyecto": e.proyecto,
            "suelo": {**e.suelo, "X9": e.entrada_actual["X9"]},
            "clasif": e.clasif,
            "checks_normativa_a": checks_normativa_a,
            "y1_mpa": e.prediccion["Y1_MPa"],
            "y1_kgcm2": round(e.prediccion["Y1_MPa"] * MPA_A_KGCM2, 1),
            "y2": e.prediccion["durham"], "avisos": e.prediccion["avisos"],
            "optimo": opt, "dosif_practica": dosif_practica,
            "estabilizadores": estabs, "nota_cal": nota_cal,
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "fotos_reporte": e.fotos_reporte,
        }
        texto = generar_texto_informe(contexto)
        self.preview.setPlainText(texto)

        punto_usuario = (e.entrada_actual["X9"], e.prediccion["Y1_MPa"])
        OUTPUT_DIR.mkdir(exist_ok=True)
        imagen_curva = str(OUTPUT_DIR / "_curva_tmp.png")
        figura = Figure(figsize=(7, 3.6), dpi=150, facecolor="white")
        ax = figura.add_subplot(111)
        _dibujar_curva_en_ejes(ax, df, opt, punto_usuario)
        try:
            figura.savefig(imagen_curva, dpi=150, bbox_inches="tight")
            e.figura_curva = figura
        except Exception:
            imagen_curva = None

        nombre_archivo = f"reporte_{(e.proyecto.get('nombre') or 'proyecto').replace(' ', '_')}.pdf"
        ruta_defecto = str(OUTPUT_DIR / nombre_archivo)
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte (PDF)", ruta_defecto,
                                              "Archivos PDF (*.pdf)")
        if not ruta:
            return
        logo_path = ASSETS_DIR / "logo.png"
        generar_pdf(texto, ruta, imagen_curva, e.proyecto.get("nombre", "Proyecto"),
                   contexto=contexto, logo_path=str(logo_path) if logo_path.exists() else None)
        resp = QMessageBox.information(
            self, "Reporte generado", f"Reporte guardado en:\n{ruta}\n\n¿Abrir la carpeta?",
            QMessageBox.Yes | QMessageBox.No)
        if resp == QMessageBox.Yes:
            try:
                os.startfile(str(Path(ruta).parent))
            except Exception:
                pass


# ============================================================================
# ENCABEZADO (logo, titulo, toolbar, badge normativa, bandera)
# ============================================================================
class Encabezado(QWidget):
    accion = pyqtSignal(str)   # "nuevo"

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        self.logo = QLabel()
        pix = QPixmap(str(ASSETS_DIR / "logo.png"))
        if not pix.isNull():
            self.logo.setPixmap(pix.scaledToHeight(52, Qt.SmoothTransformation))
        lay.addWidget(self.logo)

        col = QVBoxLayout()
        titulo = QLabel(
            '<span style="font-size:18pt; font-weight:800; color:#2a5d9f;">SUELO-CEMENTO</span> '
            '<span style="font-size:18pt; font-weight:800; color:#e67e22;">CNP PERU</span>')
        col.addWidget(titulo)
        subt = QLabel("Suelos Estabilizados con Cemento para Carreteras No Pavimentadas según MTC")
        subt.setStyleSheet("color:#6c7a89;")
        col.addWidget(subt)
        lay.addLayout(col)

        b_nuevo = QPushButton("🆕 Nuevo Proyecto")
        b_nuevo.setObjectName("botonHerramienta")
        b_nuevo.setToolTip("Reinicia todos los campos a los valores por defecto.")
        b_nuevo.clicked.connect(lambda: self.accion.emit("nuevo"))
        lay.addWidget(b_nuevo)
        lay.addStretch()

        badge_col = QVBoxLayout()
        badge_col.setSpacing(2)
        lbl_t = QLabel("Normativa Aplicada")
        lbl_t.setStyleSheet("color:#8a96a3; font-size:8pt;")
        lbl_t.setAlignment(Qt.AlignRight)
        badge_col.addWidget(lbl_t)
        # Las 3 normativas fuente identificadas (ver reporte.py, MARCO_NORMATIVO):
        # el "Documento Tecnico" es donde estan los Cuadros 9.1/9.2/9.4/N01/N02
        # que este software usa mas; los otros dos son la fuente de los
        # procedimientos de ensayo y de la clasificacion de suelos.
        for texto, tooltip in [
            ("RD-003-2015-MTC/14", "Aprueba el 'Documento Tecnico: Soluciones Basicas en "
                                   "Carreteras No Pavimentadas' (MTC, feb-2015) -- fuente de "
                                   "los Cuadros 9.1, 9.2, 9.4, N01 y N02 usados por este software."),
            ("Manual de Ensayo de Materiales (2016)", "Fuente de los procedimientos E-1101, "
                                                       "E-1103, E-1104 y E-115."),
            ("Manual de Carreteras: Suelos, Geología,\nGeotecnia y Pavimentos (2013)",
             "Clasificacion de suelos (AASHTO/SUCS) y marco de diseno estructural."),
        ]:
            lbl_v = QLabel(texto)
            lbl_v.setToolTip(tooltip)
            lbl_v.setStyleSheet("background:#2a5d9f; color:white; padding:2px 8px; "
                               "border-radius:4px; font-weight:700; font-size:7.5pt;")
            lbl_v.setAlignment(Qt.AlignCenter)
            badge_col.addWidget(lbl_v)
        lay.addLayout(badge_col)

        bandera = QLabel("PERU")
        bandera.setStyleSheet("font-weight:700; font-size:10pt; padding-left:8px; color:#2a5d9f;")
        lay.addWidget(bandera)


# ============================================================================
# VENTANA PRINCIPAL
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        icono = ASSETS_DIR / "icono.ico"
        if icono.exists():
            self.setWindowIcon(QIcon(str(icono)))
        self.resize(1400, 880)
        self.estado = EstadoApp()

        central = QWidget()
        self.setCentralWidget(central)
        lay_principal = QVBoxLayout(central)

        self.encabezado = Encabezado()
        self.encabezado.accion.connect(self._accion_toolbar)
        lay_principal.addWidget(self.encabezado)

        self.barra_contexto = BarraContexto(self.estado)
        lay_principal.addWidget(self.barra_contexto)

        cuerpo = QHBoxLayout()
        self.sidebar = SidebarTimeline()
        self.sidebar.etapaSeleccionada.connect(self._ir_a_etapa)
        cuerpo.addWidget(self.sidebar)

        self.etapa1 = Etapa1Proyecto(self.estado)
        self.etapa2 = Etapa2Suelo(self.estado)
        self.etapa3 = Etapa3Normativa(self.estado)
        self.etapa4 = Etapa4Prediccion(self.estado)
        self.etapa5 = Etapa5Curva(self.estado)
        self.etapa6 = Etapa6Reporte(self.estado)
        self.etapas = [self.etapa1, self.etapa2, self.etapa3, self.etapa4,
                       self.etapa5, self.etapa6]

        self.stack = QStackedWidget()
        for et in self.etapas:
            scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(et)
            self.stack.addWidget(scroll)
        cuerpo.addWidget(self.stack, 1)
        lay_principal.addLayout(cuerpo, 1)

        self.statusBar().showMessage(
            "Modelo RNA v7.0 | 84 datos verificados | R2 LODO = 0.64 | "
            "Normativa: RD-003-2015 MTC | Modo: Local (sin conexion)")

        # --- wiring ---
        self.etapa1.actualizado.connect(self.barra_contexto.refrescar)
        self.etapa2.actualizado.connect(self._al_cambiar_suelo)
        self.etapa4.x9_cambiado.connect(
            lambda v: self.etapa5.refrescar_marca_usuario(self.estado))

        self.etapa1._actualizar()
        # Etapa2 ya corrio su propio _actualizar() durante su __init__ (antes
        # de que la señal quedara conectada arriba), asi que Etapa3/4/5 nunca
        # se refrescaban con el suelo por defecto hasta que el usuario tocara
        # un campo de Etapa2 -- se dispara aqui una vez a mano para que
        # arranquen ya con la informacion del suelo por defecto.
        self._al_cambiar_suelo()
        self._ir_a_etapa(0)

    # -------------------------------------------------------------- sidebar
    def _ir_a_etapa(self, indice):
        self.stack.setCurrentIndex(indice)
        self.sidebar.set_activo(indice)
        self._actualizar_completitud()

    def _actualizar_completitud(self):
        e = self.estado
        completos = [
            bool(e.proyecto),
            e.clasif is not None,
            e.clasif is not None,
            e.prediccion is not None,
            e.curva_df is not None,
            False,
        ]
        self.sidebar.set_completos(completos)

    # -------------------------------------------------------------- wiring
    def _al_cambiar_suelo(self):
        self.barra_contexto.refrescar()
        self.etapa3.refrescar(self.estado)
        self.etapa4.refrescar_contexto(self.estado)
        self.etapa5.refrescar_si_corresponde(self.estado)
        self._actualizar_completitud()

    # -------------------------------------------------------------- toolbar
    def _accion_toolbar(self, clave):
        if clave == "nuevo":
            self._nuevo_proyecto()

    def _nuevo_proyecto(self):
        resp = QMessageBox.question(self, "Nuevo proyecto",
                                    "¿Reiniciar todos los campos a los valores por defecto?",
                                    QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        self.etapa1.cargar({"nombre": "Camino vecinal", "departamento": "Ayacucho",
                            "provincia": "Huamanga", "distrito": "", "altitud": 3200, "imd": 0})
        self.etapa2.cargar({"X1": 55.0, "X2": 30.0, "X3": 15.0, "X4": 20.0, "X5": 15.0,
                            "X6": 5.0, "X7": 9.0, "X8": 2.10})
        self.etapa4.X9.setValue(5.0)
        self.estado.prediccion = None; self.estado.curva_df = None
        self.estado.curva_base = None; self.estado.optimo = None
        self.estado.fotos_reporte = []
        self.etapa6._refrescar_lista_fotos()
        self._ir_a_etapa(0)


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE_SHEET)
    icono = ASSETS_DIR / "icono.ico"
    if icono.exists():
        app.setWindowIcon(QIcon(str(icono)))
    ventana = MainWindow()
    ventana.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

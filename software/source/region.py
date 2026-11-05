# -*- coding: utf-8 -*-
"""
================================================================================
region.py - Region por altitud + alternativas de estabilizador (Cuadro N02 MTC)
Software predictor suelo-cemento CNP Peru
================================================================================
NOTA IMPORTANTE: los rangos de altitud del Cuadro N02 se SOLAPAN entre si
(Costa <=500, Sierra 500-4800, Ceja de Selva/Selva Alta 400-1000). La altitud
sola NO basta para distinguir, por ejemplo, 450 msnm en la costa arida de
450 msnm en la ceja de selva -- depende de la vertiente (Pacifico vs
Amazonica), no solo de la cota. Por eso este modulo devuelve una SUGERENCIA
y, cuando hay solape, la marca como ambigua para que la interfaz pida
confirmacion al usuario en vez de asumir en silencio.
"""
from __future__ import annotations

REGIONES = {
    "Costa": {
        "altitud_txt": "hasta 500 msnm",
        "suelos": "Granulares, nula a baja plasticidad (A-1 a A-5)",
        "estabilizadores": ["Sales", "Cemento Portland/Ceniza/Puzolana",
                            "Emulsion asfaltica", "Productos quimicos"],
    },
    "Sierra": {
        "altitud_txt": "500 a 4800 msnm",
        "suelos": "Granulares, nula a plasticidad media (A-1 a A-5)",
        "estabilizadores": ["Cemento Portland/Ceniza/Puzolana",
                            "Emulsion asfaltica", "Productos quimicos"],
    },
    "Ceja de Selva y Selva Alta": {
        "altitud_txt": "400 a 1000 msnm",
        "suelos": "Granulares, nula a plasticidad alta (A-1 a A-7)",
        "estabilizadores": ["Cemento Portland/Ceniza/Puzolana",
                            "Emulsion asfaltica", "Cal", "Productos quimicos"],
    },
    "Selva Baja": {
        "altitud_txt": "menor a 400 msnm",
        "suelos": "Limo-arcillosos, arcillas (A-2-4, A-3, A-6, A-7)",
        "estabilizadores": ["Cemento Portland/Ceniza/Puzolana",
                            "Emulsion asfaltica", "Cal", "Productos quimicos"],
    },
}

NOTA_SALES_CAL = (
    "Sales solo aplica en Costa. Segun Cuadro N02 MTC, Cal se recomienda para "
    "Ceja de Selva y Selva Baja. En Costa y Sierra puede aplicarse si IP >= 10% "
    "(Cuadro 9.2), pero no es primera opcion para suelos granulares."
)


def sugerir_region(altitud: float):
    """
    Devuelve (sugerencia, ambiguo, candidatas).
    candidatas = lista de regiones geograficamente posibles a esa altitud
    (segun el solape del Cuadro N02); ambiguo=True si hay mas de una.
    """
    candidatas = []
    if altitud < 400:
        candidatas.append("Selva Baja")
    if 0 <= altitud <= 500:
        candidatas.append("Costa")
    if 400 <= altitud <= 1000:
        candidatas.append("Ceja de Selva y Selva Alta")
    if 500 <= altitud <= 4800:
        candidatas.append("Sierra")
    if not candidatas:
        candidatas = ["Sierra"] if altitud > 4800 else ["Costa"]

    ambiguo = len(candidatas) > 1
    # sugerencia por defecto: la primera regla que aplica en el orden natural
    sugerencia = candidatas[0]
    return sugerencia, ambiguo, candidatas


if __name__ == "__main__":
    for alt in [50, 450, 700, 2000, 4900, 300]:
        s, amb, cand = sugerir_region(alt)
        print(f"{alt:>6} msnm -> sugerida={s:<28} ambiguo={amb}  candidatas={cand}")

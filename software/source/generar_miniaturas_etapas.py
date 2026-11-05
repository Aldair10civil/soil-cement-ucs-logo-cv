# -*- coding: utf-8 -*-
"""Genera assets/miniaturas/*.png (placeholders) con PIL -- una miniatura por
cada una de las 6 etapas del sidebar, para reemplazar los iconos de emoji.
Reemplazar estos 6 archivos por fotografias/imagenes reales cuando esten
disponibles -- main.py los carga por nombre de archivo, no hace falta tocar
el codigo. Tamano recomendado: 480x224 px (proporcion ~2.14:1), JPG o PNG,
sin texto superpuesto (el titulo ya lo pone el software debajo del icono
numerado)."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "assets" / "miniaturas"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 480, 224
RADIO = 22

AZUL = (42, 93, 159)
AZUL_OSCURO = (30, 68, 117)
NARANJA = (230, 126, 34)
BLANCO = (255, 255, 255)
BEIGE = (196, 164, 122)
BEIGE_OSCURO = (150, 120, 85)


def _lienzo():
    """Rectangulo redondeado de fondo azul, con mascara alfa para las esquinas."""
    img = Image.new("RGBA", (W, H), AZUL)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H // 2], fill=AZUL_OSCURO)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=RADIO, fill=255)
    salida = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    salida.paste(img, (0, 0), mask)
    return salida, ImageDraw.Draw(salida)


def _guardar(nombre, img):
    img.save(OUT / nombre)
    print(f"  {nombre}")


def mini_proyecto():
    img, d = _lienzo()
    d.polygon([(60, 170), (170, 60), (250, 140), (330, 50), (420, 170)], fill=BLANCO)
    d.rectangle([0, 170, W, 200], fill=NARANJA)
    d.line([(20, 185), (W - 20, 185)], fill=BLANCO, width=4)
    _guardar("01_proyecto.png", img)


def mini_suelo():
    img, d = _lienzo()
    capas = [(60, BEIGE), (105, BEIGE_OSCURO), (150, (120, 95, 65)), (195, (90, 70, 50))]
    y0 = 40
    for y1, color in capas:
        d.rectangle([40, y0, W - 40, y1], fill=color)
        y0 = y1
    d.line([(W // 2, 10), (W // 2, 210)], fill=NARANJA, width=6)
    d.ellipse([W // 2 - 10, 0, W // 2 + 10, 20], fill=NARANJA)
    _guardar("02_suelo.png", img)


def mini_normativa():
    img, d = _lienzo()
    d.rounded_rectangle([150, 30, 330, 200], radius=10, fill=BLANCO)
    for i, y in enumerate(range(60, 170, 25)):
        ancho = 140 if i % 2 == 0 else 100
        d.rectangle([170, y, 170 + ancho, y + 10], fill=AZUL)
    d.ellipse([255, 150, 315, 210], fill=NARANJA)
    d.line([(268, 180), (280, 195), (302, 165)], fill=BLANCO, width=6, joint="curve")
    _guardar("03_normativa.png", img)


def mini_prediccion():
    img, d = _lienzo()
    capa1 = [(90, 60), (90, 112), (90, 164)]
    capa2 = [(240, 45), (240, 90), (240, 135), (240, 180)]
    capa3 = [(390, 112)]
    for x1, y1 in capa1:
        for x2, y2 in capa2:
            d.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 110), width=2)
    for x2, y2 in capa2:
        for x3, y3 in capa3:
            d.line([(x2, y2), (x3, y3)], fill=(255, 255, 255, 110), width=2)
    for x, y in capa1:
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=BLANCO)
    for x, y in capa2:
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=NARANJA)
    for x, y in capa3:
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=BLANCO)
    _guardar("04_prediccion.png", img)


def mini_curva():
    img, d = _lienzo()
    ox, oy = 60, 190
    d.line([(ox, 30), (ox, oy)], fill=BLANCO, width=3)
    d.line([(ox, oy), (W - 30, oy)], fill=BLANCO, width=3)
    puntos = [(ox, 175), (140, 150), (200, 110), (270, 95), (340, 60), (420, 45)]
    d.line(puntos, fill=NARANJA, width=5, joint="curve")
    for x, y in puntos:
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=BLANCO)
    _guardar("05_curva.png", img)


def mini_reporte():
    img, d = _lienzo()
    esquina = 26
    d.polygon([(150, 25), (300, 25), (330, 55), (330, 200), (150, 200)], fill=BLANCO)
    d.polygon([(300, 25), (330, 55), (300, 55)], fill=(210, 220, 232))
    for y in range(75, 180, 22):
        d.rectangle([170, y, 310, y + 9], fill=AZUL)
    d.rectangle([150, 165, 330, 200], fill=NARANJA)
    _guardar("06_reporte.png", img)


if __name__ == "__main__":
    print("Generando miniaturas de etapas...")
    mini_proyecto()
    mini_suelo()
    mini_normativa()
    mini_prediccion()
    mini_curva()
    mini_reporte()
    print(f"Listo en: {OUT}")

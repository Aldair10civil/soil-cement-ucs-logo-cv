# -*- coding: utf-8 -*-
"""Genera assets/icono.ico y assets/logo.png (placeholder) con PIL.
Reemplazar estos archivos por el logo real cuando este disponible -- main.py
los carga por nombre de archivo, no hace falta tocar el codigo."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(exist_ok=True)

AZUL = (42, 93, 159)
NARANJA = (230, 126, 34)
BLANCO = (255, 255, 255)


def dibujar_logo(tam):
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, tam - 1, tam - 1], fill=AZUL)
    m = tam * 0.12
    # montaña estilizada (triangulo) en la mitad superior
    d.polygon([(tam * 0.15, tam * 0.62), (tam * 0.42, tam * 0.28), (tam * 0.60, tam * 0.50),
              (tam * 0.75, tam * 0.30), (tam * 0.90, tam * 0.62)], fill=BLANCO)
    # carretera (linea naranja) en la base
    d.rectangle([0, tam * 0.68, tam, tam * 0.82], fill=NARANJA)
    d.line([(tam * 0.1, tam * 0.75), (tam * 0.9, tam * 0.75)], fill=BLANCO,
          width=max(1, int(tam * 0.02)))
    return img


logo_grande = dibujar_logo(512)
logo_grande.save(OUT / "logo.png")

tamanos = [16, 24, 32, 48, 64, 128, 256]
imgs = [dibujar_logo(t) for t in tamanos]
imgs[-1].save(OUT / "icono.ico", format="ICO",
             sizes=[(t, t) for t in tamanos])

print(f"Generados: {OUT / 'logo.png'}  y  {OUT / 'icono.ico'}")

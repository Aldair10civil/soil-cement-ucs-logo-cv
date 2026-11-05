# -*- coding: utf-8 -*-
"""
================================================================================
reporte.py - Informe tecnico (texto por plantilla) + exportacion a PDF
Software predictor suelo-cemento CNP Peru
================================================================================
Genera el informe tecnico de forma DETERMINISTA por plantilla (sin costo, sin
API key, funciona offline). Para conectar un LLM real (Qwen/GPT) mas adelante:
reemplazar el CUERPO de generar_texto_informe() por una llamada a la API,
pasando 'contexto' como el JSON de entrada/contexto del prompt -- la firma de
la funcion (recibe contexto, devuelve str) no tiene que cambiar, por lo que
app.py no requiere modificaciones.
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from curva import evaluar_escenario, mensaje_ninguna_dosis_cumple

AVISO_LEGAL = (
    "Este software es una herramienta de estimacion preliminar de prediseno "
    "basada en un modelo de regresion entrenado con datos de expedientes "
    "tecnicos peruanos verificados (R2 LODO = 0.64 para Y1). Los resultados "
    "NO reemplazan los ensayos de laboratorio MTC E-1103 y MTC E-1104 "
    "requeridos por la normativa vigente (RD-003-2015-MTC/14). El diseno "
    "final de la mezcla suelo-cemento debe ser validado mediante ensayos de "
    "laboratorio por un profesional habilitado. La prediccion de durabilidad "
    "Durham (Y2) tiene precision limitada (77% acierto) y requiere "
    "confirmacion obligatoria mediante ensayo MTC E-1104."
)

EXPLICACION_DURHAM = (
    "Ensayo Durham (MTC E-1104): 12 ciclos consecutivos de aproximadamente 48 "
    "horas cada uno (5 horas de inmersion en agua + 42 horas de secado en "
    "horno a 71 grados C), finalizando con un cepillado normalizado de 18 a "
    "20 pasadas (fuerza de 13.3 N). Mide la perdida de peso de la probeta "
    "como indicador de durabilidad frente a humedecimiento y secado."
)

PROCESO_CONSTRUCTIVO = """
Paso 1. Preparación
- Escarificar y pulverizar el suelo hasta que >=80% pase la malla N4.
- Eliminar piedras mayores a 2 pulgadas (50 mm) y restos vegetales.
- Espesor por capa: 6 a 8 pulgadas (15-20 cm).

Paso 2. Aplicación del cemento
- Cemento Portland Tipo I o IP.
- Esparcir uniformemente sobre el suelo pulverizado.
- Mezclar con motoniveladora o recicladora de suelos.

Paso 3. Agua y mezclado
- Agua potable o sin materia organica.
- Agregar agua hasta alcanzar el OCH de la mezcla.
- Mezclado hasta lograr homogeneidad completa.

Paso 4. Compactación
- Iniciar compactacion: MAXIMO 2 horas despues de agregar agua al cemento.
- Terminar compactacion: entre 2 y 4 horas segun clima.
- Densidad minima: >=98% del MDS de la Formula de Trabajo.
- Humedad de compactacion: entre OCH-2% y OCH (rama seca del Proctor Modificado).
- Si la mezcla no se compacta a tiempo: retirar y reemplazar (no reutilizable).

Paso 5. Curado
- Minimo 7 dias de curado humedo con riego de agua.
- Aplicar membrana de curado asfaltico (emulsion de rotura rapida).
- NO abrir al transito antes de los 7 dias.
- En zonas calurosas (costa, selva baja): el curado es CRITICO para evitar fisuramiento.
- En zonas de heladas: proteger la mezcla fresca.

Coeficientes estructurales (referencia AASHTO 1993)
- Suelo-cemento: a2 = 0.15 - 0.25 (segun resistencia 30-65 kg/cm2).
- Metodo de diseno de espesor: AASHTO 1993, usando el coeficiente estructural
  a2 de la capa de suelo-cemento. USACE/NAASRA (metodos basados en CBR) NO
  aplica aqui: fueron desarrollados para afirmado granular sin tratar, un
  material de comportamiento friccionante muy distinto al suelo-cemento, que
  es una capa tratada y semi-rigida con aporte estructural propio (por eso
  AASHTO 1993 le asigna el coeficiente a2).
- Periodo de diseno y frecuencia de mantenimiento: a definir por el
  proyectista segun el nivel de servicio y el transito proyectado del
  tramo especifico. Este software no analiza vida util ni mantenimiento;
  solo predice resistencia y durabilidad de la mezcla suelo-cemento.
""".strip()

CRITERIOS_ACEPTACION_OBRA = [
    ("Densidad de compactacion", ">=98% de la Formula de Trabajo", "Minimo absoluto"),
    ("Humedad de compactacion", "Entre OCH-2% y OCH (rama seca)", "-"),
    ("Espesor de capa", "Segun diseno", "+-10 mm"),
    ("Lisura superficial", "Regla de 3 metros", "Maximo 10 mm de flecha"),
]

# Normativa efectivamente usada por el modulo predictivo (Y1/Y2), la
# clasificacion de suelos y el diseno de espesor -- NO incluye las normas
# de estabilizadores alternativos (Cal, Sales, Emulsion, etc.), que ya se
# citan aparte en la Seccion 3 (Evaluacion de Alternativas) junto a cada
# estabilizador.
#
# Documentos fuente (segun portadas verificadas, jul-2026): los
# Cuadros 9.1/9.2/9.4/N01/N02 provienen del "Documento Tecnico: Soluciones
# Basicas en Carreteras No Pavimentadas" (MTC, Lima, feb-2015), aprobado por
# RD-003-2015-MTC/14 -- de ahi el nombre del proyecto. Los procedimientos
# E-11xx/E-1xx vienen del "Manual de Ensayo de Materiales" (MTC, ed.
# may-2016). El "Manual de Carreteras: Suelos, Geologia, Geotecnia y
# Pavimentos" (2013) es la fuente de la clasificacion AASHTO/SUCS y el marco
# general de diseno estructural.
MARCO_NORMATIVO = [
    ("RD-003-2015-MTC/14", "Resolucion que aprueba el 'Documento Tecnico: "
                           "Soluciones Basicas en Carreteras No Pavimentadas' "
                           "(MTC, Lima, feb-2015). Marco general -- exige "
                           "evaluar minimo tres estabilizadores y cuatro dosificaciones."),
    ("Manual de Ensayo de Materiales (MTC, ed. 2016)", "Documento fuente de "
                       "todos los procedimientos de ensayo E-1101, E-1103, "
                       "E-1104 y E-115 citados en este informe."),
    ("Manual de Carreteras: Suelos, Geologia, Geotecnia y Pavimentos (MTC, 2013)",
                       "Clasificacion de suelos (AASHTO/SUCS) y marco general "
                       "de diseno estructural de pavimentos."),
    ("Cuadro 9.1 MTC", "Restriccion USACE de aplicabilidad por familia de suelo."),
    ("Cuadro 9.2 MTC", "Aplicabilidad de estabilizadores por tipo de suelo y "
                       "parametros de control (incluye CMO, sulfatos, abrasion)."),
    ("Cuadro 9.4 MTC", "Rango de dosificacion de cemento (FHWA) por grupo AASHTO."),
    ("Cuadro N01 MTC", "Parametros de control por tipo de estabilizador "
                       "(resistencia y durabilidad exigidas)."),
    ("Cuadro N02 MTC", "Regiones geograficas y estabilizadores aplicables segun "
                       "altitud."),
    ("MTC E-1101", "Compactacion de probetas de suelo-cemento."),
    ("MTC E-1103 / ASTM D-1633 / AASHTO T-22", "Resistencia a la compresion "
                                               "simple (variable Y1 del modelo)."),
    ("MTC E-1104 / ASTM D-559 / AASHTO T-135", "Humedecimiento y secado, ensayo "
                                               "Durham (variable Y2 del modelo)."),
    ("MTC E-115 / ASTM D1557 / AASHTO T-180", "Proctor Modificado (OCH y MDS de "
                                              "la mezcla)."),
    ("AASHTO M145", "Clasificacion de suelos y mezclas suelo-agregado para "
                    "vias (usada para estimar el grupo AASHTO del suelo)."),
    ("AASHTO 1993", "Coeficiente estructural (a2 = 0.15-0.25) para diseno de "
                    "espesor de la capa de suelo-cemento."),
]


def generar_texto_informe(contexto: dict) -> str:
    """
    contexto: dict con 'proyecto' (nombre, departamento, provincia, distrito,
    altitud, region, imd), 'suelo' (X1..X9), 'clasif' (grupo, categoria,
    sucs_probable...), 'y1_mpa', 'y1_kgcm2', 'y2' (dict de predictor.py),
    'avisos' (list), 'optimo' (dict de curva.encontrar_optimo o None, incluye
    'a2'), 'dosif_practica' (dict kg_m3/bolsas_m3) opcional, 'ingeniero'
    (str opcional).
    """
    p = contexto["proyecto"]
    s = contexto["suelo"]
    c = contexto["clasif"]
    y1 = contexto["y1_mpa"]; y1kg = contexto["y1_kgcm2"]
    y2 = contexto["y2"]
    escenario = evaluar_escenario(y1, y2["Y2_perdida_pct"], y2["umbral_normativo_pct"])
    opt = contexto.get("optimo")
    fecha = contexto.get("fecha") or datetime.now().strftime("%d/%m/%Y")

    L = []
    L.append(f"INFORME TECNICO DE PREDISEÑO - ESTABILIZACION SUELO-CEMENTO")
    L.append(f"Proyecto: {p.get('nombre', '(sin nombre)')}")
    L.append(f"Fecha: {fecha}")
    L.append("=" * 78)

    L.append("\n1. DESCRIPCIÓN DEL PROYECTO Y UBICACIÓN\n")
    L.append(f"El proyecto se ubica en {p.get('distrito','')}, "
             f"{p.get('provincia','')}, departamento de {p.get('departamento','')}, "
             f"a una altitud de {p.get('altitud','?')} m.s.n.m. Segun esta altitud, "
             f"el proyecto se clasifica dentro de la region **{p.get('region','?')}**. "
             f"El transito estimado (IMD) es de {p.get('imd','no especificado')} "
             "vehiculos/dia.")

    L.append("\n2. CLASIFICACIÓN DEL SUELO Y VERIFICACIÓN NORMATIVA\n")
    if c.get("sucs_exacto"):
        sucs_txt = f"clasificacion SUCS **{c['sucs_exacto']}** (exacta, segun Cu/Cc ingresados)"
    else:
        sucs_txt = ("correlacion SUCS probable "
                    f"{', '.join(c['sucs_probable']) or '(no determinada)'}")
    L.append(f"Segun los ensayos de clasificacion (granulometria y limites de "
             f"Atterberg), el suelo se clasifica AASHTO como **{c['grupo']}** "
             f"(categoria {c['categoria']}), con {sucs_txt}, siguiendo el Manual "
             f"de Carreteras: Suelos, Geologia, Geotecnia y Pavimentos (MTC, 2013). "
             f"{'Este es un suelo IDEAL para estabilizacion con cemento.' if c.get('ideal_para_cemento') else 'Este suelo no esta en el rango ideal para cemento; se recomienda verificacion adicional.'}")
    if contexto.get("avisos"):
        L.append("\nAvisos del sistema:")
        for a in contexto["avisos"]:
            L.append(f"  - {a}")

    checks_a = contexto.get("checks_normativa_a")
    if checks_a:
        L.append("\nRequisitos normativos MTC obligatorios (Cuadro 9.2, MTC, 2015):")
        for crit, ok, _color, msg in checks_a:
            simbolo = "[NO VERIFICADO]" if ok is None else ("[CUMPLE]" if ok else "[NO CUMPLE]")
            detalle = msg if ok is None else ("-" if ok else msg)
            L.append(f"  - {simbolo} {crit}: {detalle}")
        L.append("\nNota: el cemento Portland aplica a suelos AASHTO A-1 a A-7 "
                 "segun el Cuadro 9.2 (MTC, 2015) (no es una restriccion por tipo de suelo). "
                 "Los parametros de materia organica (CMO), sulfatos y abrasion "
                 "son exigencias reales del Cuadro 9.2 que este modelo RNA NO mide: "
                 "no se mapearon como variables de entrada (X1..X9) porque el "
                 "dataset de entrenamiento no registra esos ensayos quimicos/"
                 "mecanicos para un numero suficiente de suelos. Requieren ensayo "
                 "de laboratorio independiente antes de la ejecucion de obra. "
                 "Trabajo futuro: incorporarlos como variables adicionales si se "
                 "recopila suficiente data verificada.")

    if c["grupo"] not in ("A-1-a", "A-1-b", "A-2-4", "A-2-5", "A-2-6", "A-2-7"):
        L.append("\nNota sobre la confianza del modelo: el modelo RNA esta "
                 f"entrenado casi exclusivamente con suelos granulares (grupos "
                 f"AASHTO A-1/A-2). El suelo de este proyecto ({c['grupo']}) esta "
                 "fuera de ese rango de mejor evidencia empirica -- la prediccion "
                 "es referencial, no un requisito normativo, y se recomienda mayor "
                 "verificacion con ensayo de laboratorio.")

    estabs = contexto.get("estabilizadores")
    if estabs:
        L.append("\n3. EVALUACIÓN DE ALTERNATIVAS DE ESTABILIZADOR (Cuadro 9.2 MTC)")
        L.append("Informacion de respaldo normativo (RD-003-2015 MTC exige evaluar "
                 "minimo tres estabilizadores). El modelo predictivo RNA solo esta "
                 "entrenado para Cemento Portland; las demas alternativas se listan "
                 "con sus parametros de referencia. Estado [APTO]: cumple todos los "
                 "criterios evaluables del Cuadro 9.2 para este suelo. [NO_APTO]: "
                 "incumple al menos uno. [NO_VERIFICADO]: al menos un criterio "
                 "requiere un dato de laboratorio (materia organica, sulfatos, "
                 "abrasion, equivalente de arena o pH) que este software no mide "
                 "para NINGUN estabilizador -- no significa que el estabilizador no "
                 "se haya evaluado, sino que ese dato en particular queda pendiente "
                 "de ensayo de laboratorio.")
        for r in estabs:
            L.append(f"\n- **{r['nombre']}** [{r['estado']}]: dosificacion "
                     f"{r['dosificacion']}, curado {r['curado']}. Normas: {r['normas']}. "
                     f"Parametro de control (Cuadro N01): {r.get('control', '-')}")
            if r["nombre"] == "Cemento Portland" and r["estado"] == "NO_VERIFICADO":
                L.append("  [NO_VERIFICADO se refiere UNICAMENTE a materia organica, "
                        "sulfatos y abrasion (Cuadro 9.2), que este software no mide. "
                        "La resistencia (Y1) y la durabilidad Durham (Y2) del Cemento "
                        "Portland SI fueron evaluadas mediante el modelo RNA -- ver "
                        "Seccion 4 (Resultados de Prediccion) para el valor numerico "
                        "obtenido con la dosificacion de este proyecto.]")
        nota_cal = contexto.get("nota_cal")
        if nota_cal:
            L.append(f"\n{nota_cal}")

    L.append("\n4. RESULTADOS DE PREDICCIÓN\n")
    L.append("(Estimacion preliminar del modelo predictivo, NO sustituye el "
             "ensayo de laboratorio -- ver Seccion 9: ADVERTENCIA.)")
    L.append(f"\nResistencia a compresion simple (Y1, ensayo E-1103 del Manual de "
             f"Ensayo de Materiales; MTC, 2016) a {s.get('X9','?')}% "
             f"de cemento: **{y1:.2f} MPa ({y1kg:.1f} kg/cm2)**.")
    L.append(f"\nDurabilidad Durham (Y2, MTC E-1104): perdida estimada = "
             f"**{y2['Y2_perdida_pct']:.1f}%** [valor REFERENCIAL, no "
             f"confiable numericamente: bajo validacion rigurosa por suelo "
             f"(LOGO-CV) ningun modelo de regresion probado para Y2 supero "
             f"el desempeno de un modelo trivial] (maximo admisible <= "
             f"{y2['umbral_normativo_pct']}% para suelos {c['categoria']}). "
             f"**{y2['veredicto']}** (veredicto de clasificacion CUMPLE/NO "
             f"CUMPLE, metrica con mayor respaldo que el valor numerico "
             f"anterior).")
    confianza = y2.get("confianza")
    if confianza:
        L.append(f"\n{confianza['mensaje']}")
    L.append(f"\nEvaluacion combinada (resistencia + durabilidad): {escenario['mensaje']}")
    L.append(f"\n{EXPLICACION_DURHAM}")

    if opt:
        L.append("\n5. CURVA DE DOSIFICACIÓN - ESTIMACIÓN PRELIMINAR\n")
        L.append("(Resultado basado en el modelo predictivo, NO sustituye el "
                 "ensayo de laboratorio -- ver Seccion 9: ADVERTENCIA.)")
        L.append(f"\nEvaluando de 1% a 12% de cemento, el porcentaje con la "
                 f"ESTIMACION PRELIMINAR mas baja que alcanza los umbrales de "
                 f"resistencia y durabilidad (pendiente de verificacion "
                 f"experimental y de los demas requisitos del Cuadro 9.2 no "
                 f"evaluados por este software) es **{opt['cemento']}%**, con "
                 f"Y1 estimado = {opt['Y1_MPa']:.2f} MPa "
                 f"({opt['Y1_kgcm2']:.1f} kg/cm2) y Durham "
                 f"{opt['Y2_veredicto']} (estimado, no verificado).")
        dp = contexto.get("dosif_practica")
        if dp:
            L.append(f"\nDosificacion: {opt['cemento']}% en peso de suelo seco "
                     f"= {dp['kg_m3']} kg/m3 de mezcla = {dp['bolsas_m3']} "
                     "bolsas/m3 (bolsa de 42.5 kg).")
            L.append(f"- MDS = {s.get('X8','?')} g/cm3, OCH = {s.get('X7','?')}% "
                     "(Proctor Modificado, MTC E-115).")
            L.append("- Grado de compactacion exigido: >=98% del MDS de esta "
                     "Formula de Trabajo.")
            L.append(f"- Coeficiente estructural **a2 = {opt['a2']:.3f}** (AASHTO "
                     "1993, estimado desde Y1). Este software NO calcula espesor "
                     "de pavimento ni costo por m2 -- eso requiere el CBR de "
                     "subrasante y los ejes equivalentes del proyecto especifico, "
                     "datos fuera del alcance de este modelo. Use a2 junto con "
                     "esos dos datos en su propia plantilla AASHTO 1993 "
                     "(SN = a2 x D2 x m2) para calcular el espesor.")
    else:
        L.append("\n5. CURVA DE DOSIFICACIÓN\n")
        L.append(mensaje_ninguna_dosis_cumple()["mensaje"])

    L.append("\n6. PROCESO CONSTRUCTIVO\n")
    L.append(PROCESO_CONSTRUCTIVO)

    L.append("\n7. CRITERIOS DE ACEPTACIÓN EN OBRA")
    for param, req, tol in CRITERIOS_ACEPTACION_OBRA:
        L.append(f"- {param}: {req} (tolerancia: {tol})")

    L.append("\n8. MARCO NORMATIVO APLICADO")
    for norma, uso in MARCO_NORMATIVO:
        L.append(f"- {norma}: {uso}")

    L.append("\n9. ADVERTENCIA")
    L.append(AVISO_LEGAL)

    return "\n".join(L)


_AZUL = "#2a5d9f"          # acento SOLO en el logo de portada -- ya no en
                            # titulos/tablas (APA 7 no usa cajas de color)
_NARANJA = "#e67e22"
_GRIS_TEXTO = "#444444"
_GRIS_LINEA = "#000000"    # reglas de tabla APA: negro, no gris de marca
_VERDE_BG = "#eafaf1"      # -- estos 3 colores se conservan UNICAMENTE en la
_ROJO_BG = "#fdeaea"       #    columna "Estado" de las tablas de criterios/
_AMARILLO_BG = "#fff6e0"   #    estabilizadores: es informacion funcional de
                            #    campo (apto/no apto/no verificado), no
                            #    decoracion. Decision registrada con Diego
                            #    (2026-08-05): formato APA 7 hibrido -- todo
                            #    lo demas (fuente, margenes, interlineado,
                            #    titulos, tablas, figuras, referencias) sigue
                            #    APA 7 estricto; el color de estado se
                            #    mantiene por ser una excepcion deliberada.

FUENTE = "Times-Roman"
FUENTE_NEGRITA = "Times-Bold"
FUENTE_CURSIVA = "Times-Italic"
FUENTE_NEGRITA_CURSIVA = "Times-BoldItalic"


def _tabla_criterios(filas, encabezados, anchos, styles, usar_color_estado=True):
    """Tabla APA 7 (3 lineas horizontales: arriba del encabezado, debajo del
    encabezado y al final de la tabla -- SIN lineas verticales, sin sombreado
    de encabezado). `filas` es una lista de (col0, col1, col2, estado) donde
    estado in (True, False, None). El fondo de color en la columna de Estado
    (col. 1) solo se aplica si usar_color_estado=True -- son APTO/NO_APTO/
    NO_VERIFICADO reales (ej. Cuadro 9.2); para tablas donde el estado es
    siempre el mismo valor decorativo (ej. Criterios de Aceptacion en Obra)
    se pasa False, porque ahi el color no aporta informacion funcional y
    APA 7 no shading."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors

    data = [[Paragraph(f"<b>{h}</b>", styles["Celda"]) for h in encabezados]]
    for c0, c1, c2, _estado in filas:
        data.append([Paragraph(c0, styles["Celda"]), Paragraph(str(c1), styles["Celda"]),
                    Paragraph(c2, styles["Celda"])])

    estilo = [
        ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if usar_color_estado:
        for i, (_c0, _c1, _c2, estado) in enumerate(filas, start=1):
            if estado is None:
                bg = _AMARILLO_BG
            elif estado:
                bg = _VERDE_BG
            else:
                bg = _ROJO_BG
            estilo.append(("BACKGROUND", (1, i), (1, i), colors.HexColor(bg)))

    t = Table(data, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle(estilo))
    return t


def _lista_referencias(filas, styles):
    """Lista de referencias en formato APA 7: sangria francesa (la 1ra linea
    de cada entrada sin sangria, las siguientes con 1.27cm), ordenada
    alfabeticamente. NO es una tabla -- APA no formatea la lista de
    referencias como tabla, es una lista de parrafos con sangria."""
    from reportlab.platypus import Paragraph
    filas_ordenadas = sorted(filas, key=lambda x: x[0].upper())
    return [Paragraph(f"{norma}. {uso}", styles["Referencia"]) for norma, uso in filas_ordenadas]


def _banner_seccion(texto, styles):
    """Titulo de seccion Nivel 1 APA 7: centrado, negrita, sin caja de color
    (el nombre de la funcion se conserva por compatibilidad con los muchos
    puntos de llamada en generar_pdf(), aunque ya no dibuja un "banner")."""
    from reportlab.platypus import Paragraph
    return Paragraph(texto.replace("*", ""), styles["Nivel1"])


def _titulo_nivel2(texto, styles):
    """Subtitulo Nivel 2 APA 7: alineado a la izquierda, negrita."""
    from reportlab.platypus import Paragraph
    return Paragraph(texto, styles["Nivel2"])


def _tabla_estabilizadores(estabs, styles):
    """Tabla APA 7 de la Seccion 3 (Evaluacion de Alternativas de
    Estabilizador, Cuadro 9.2 MTC): una fila por estabilizador. El color de
    fondo se conserva UNICAMENTE en la columna "Estado" (APTO=verde,
    NO_APTO=rojo, NO_VERIFICADO=amarillo) -- informacion funcional para el
    ingeniero en campo, ver nota de color al inicio del modulo."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import cm

    ESTADO_TXT = {"APTO": "Apto", "NO_APTO": "No apto", "NO_VERIFICADO": "No verificado"}
    encabezados = [Paragraph(f"<b>{h}</b>", styles["Celda"])
                  for h in ("Estabilizador", "Estado", "Dosificacion", "Curado",
                           "Normas de referencia", "Parametro de control (Cuadro N01)")]
    data = [encabezados]
    for r in estabs:
        nombre = r["nombre"]
        if nombre == "Cemento Portland" and r["estado"] == "NO_VERIFICADO":
            nombre += " [1]"
        data.append([
            Paragraph(f"<b>{nombre}</b>", styles["Celda"]),
            ESTADO_TXT.get(r["estado"], r["estado"]),
            Paragraph(r["dosificacion"], styles["Celda"]),
            Paragraph(r["curado"], styles["Celda"]),
            Paragraph(r["normas"], styles["Celda"]),
            Paragraph(r.get("control", "-"), styles["Celda"]),
        ])

    anchos = [2.7*cm, 1.85*cm, 2.3*cm, 2.0*cm, 3.3*cm, 3.72*cm]
    t = Table(data, colWidths=anchos, repeatRows=1)
    estilo = [
        ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i, r in enumerate(estabs, start=1):
        bg = {"APTO": _VERDE_BG, "NO_APTO": _ROJO_BG, "NO_VERIFICADO": _AMARILLO_BG}.get(r["estado"])
        if bg:
            estilo.append(("BACKGROUND", (1, i), (1, i), colors.HexColor(bg)))
    t.setStyle(TableStyle(estilo))
    return t


def _figura_foto(ruta, ancho, styles):
    """Imagen de una fotografia de campo, sin marco de color (APA 7: las
    figuras no llevan caja decorativa; el titulo/leyenda va DEBAJO, en
    cursiva y numerado -- ver _con_titulo_figura() en generar_pdf())."""
    from reportlab.platypus import Image, Paragraph
    from reportlab.lib.units import cm
    from PIL import Image as PILImage
    try:
        with PILImage.open(ruta) as im:
            iw, ih = im.size
        alto = ancho * ih / iw
        alto_max = 9 * cm
        if alto > alto_max:
            alto = alto_max
            ancho = alto * iw / ih
        return Image(ruta, width=ancho, height=alto)
    except Exception:
        return Paragraph("(Imagen no disponible)", styles["Celda"])


def _encabezado_pie_pagina(nombre_proyecto, titulo_abreviado="PREDISEÑO SUELO-CEMENTO"):
    """Encabezado de pagina APA 7 (running head): titulo abreviado en
    mayusculas a la izquierda, numero de pagina a la derecha, arriba de la
    pagina. Se mantiene ademas un pie de pagina minimo (nombre del proyecto)
    -- util para identificar impresiones sueltas en campo; APA no lo prohibe,
    solo exige el encabezado con numero de pagina."""
    def _dibujar(canvas, doc):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        canvas.saveState()
        canvas.setFont(FUENTE, 10)
        canvas.setFillColor(colors.black)
        y_header = A4[1] - 1.6 * cm
        canvas.drawString(2.54 * cm, y_header, titulo_abreviado.upper())
        canvas.drawRightString(A4[0] - 2.54 * cm, y_header, str(doc.page))
        canvas.setFont(FUENTE_CURSIVA, 8)
        canvas.setFillColor(colors.HexColor(_GRIS_TEXTO))
        canvas.drawCentredString(A4[0] / 2, 1.1 * cm,
                                 f"Software SUELO-CEMENTO CNP PERU -- {nombre_proyecto}")
        canvas.restoreState()
    return _dibujar


def generar_pdf(texto_informe: str, ruta_salida, imagen_curva: str | None = None,
                proyecto_nombre: str = "Proyecto", contexto: dict | None = None,
                logo_path: str | None = None):
    """Exporta el informe a PDF usando reportlab, en formato APA 7ma edicion
    HIBRIDO: fuente Times New Roman 12pt, interlineado doble, margenes de
    2.54cm, jerarquia de titulos (Nivel 1 centrado negrita / Nivel 2
    izquierda negrita / Nivel 3 izquierda negrita cursiva), tablas de 3
    lineas horizontales sin lineas verticales ni sombreado de encabezado,
    tablas y figuras numeradas con titulo en cursiva, referencias con
    sangria francesa ordenadas alfabeticamente, y encabezado de pagina
    (titulo abreviado + numero). UNICA excepcion deliberada a APA 7 estricto:
    se conserva el color de fondo en la columna "Estado" de las tablas de
    criterios/estabilizadores (APTO/NO_APTO/NO_VERIFICADO), por ser
    informacion funcional de campo -- ver nota de color al inicio del
    modulo. imagen_curva: ruta a PNG opcional. contexto: el mismo dict
    pasado a generar_texto_informe -- si se omite, el PDF cae de vuelta al
    modo simple (solo texto), por compatibilidad."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                    PageBreak, Table, TableStyle)
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib import colors

    ANCHO_UTIL = 21.0 * cm - 2 * 2.54 * cm    # A4 (21cm) menos margenes APA de 2.54cm c/lado
    LEADING_DOBLE = 24                        # interlineado doble para cuerpo de 12pt (APA 7 SS 7.2)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Cuerpo", parent=styles["Normal"],
                              fontName=FUENTE, fontSize=12, leading=LEADING_DOBLE,
                              alignment=TA_LEFT, spaceAfter=0))
    styles.add(ParagraphStyle(name="Nivel1", parent=styles["Cuerpo"],
                              fontName=FUENTE_NEGRITA, alignment=TA_CENTER,
                              spaceBefore=16, spaceAfter=10))
    styles.add(ParagraphStyle(name="Nivel2", parent=styles["Cuerpo"],
                              fontName=FUENTE_NEGRITA, alignment=TA_LEFT,
                              spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle(name="Nivel3", parent=styles["Cuerpo"],
                              fontName=FUENTE_NEGRITA_CURSIVA, alignment=TA_LEFT,
                              spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="TituloTablaFigura", parent=styles["Cuerpo"],
                              fontName=FUENTE_NEGRITA, fontSize=11, leading=13,
                              spaceBefore=10, spaceAfter=0))
    styles.add(ParagraphStyle(name="CaptionCursiva", parent=styles["Cuerpo"],
                              fontName=FUENTE_CURSIVA, fontSize=11, leading=13,
                              spaceAfter=3))
    styles.add(ParagraphStyle(name="NotaTabla", parent=styles["Cuerpo"],
                              fontName=FUENTE, fontSize=9.5, leading=12, spaceBefore=3))
    styles.add(ParagraphStyle(name="Referencia", parent=styles["Cuerpo"],
                              fontSize=11, leading=16,
                              leftIndent=1.27*cm, firstLineIndent=-1.27*cm, spaceAfter=8))
    styles.add(ParagraphStyle(name="Celda", parent=styles["Normal"],
                              fontName=FUENTE, fontSize=10, leading=12.5))
    styles.add(ParagraphStyle(name="CeldaNegrita", parent=styles["Celda"],
                              fontName=FUENTE_NEGRITA))
    styles.add(ParagraphStyle(name="TituloPortada", parent=styles["Cuerpo"],
                              fontName=FUENTE_NEGRITA, fontSize=14, alignment=TA_CENTER,
                              leading=18))
    styles.add(ParagraphStyle(name="SubtituloPortada", parent=styles["Cuerpo"],
                              fontSize=12, alignment=TA_CENTER, leading=16, spaceBefore=4))
    styles.add(ParagraphStyle(name="Aviso", parent=styles["Cuerpo"], fontSize=11))

    # Contadores de "Tabla N" / "Figura N" (APA 7: numeracion secuencial en
    # todo el documento, con titulo en cursiva arriba de la tabla / debajo
    # de la figura).
    contador = {"tabla": 0, "figura": 0}

    def _con_titulo_tabla(titulo, tabla, nota=None):
        contador["tabla"] += 1
        bloques_out = [Paragraph(f"Tabla {contador['tabla']}", styles["TituloTablaFigura"]),
                      Paragraph(titulo, styles["CaptionCursiva"]),
                      Spacer(1, 3), tabla]
        if nota:
            bloques_out.append(Paragraph(f"<i>Nota.</i> {nota}", styles["NotaTabla"]))
        bloques_out.append(Spacer(1, 12))
        return bloques_out

    def _con_titulo_figura(titulo, figura):
        contador["figura"] += 1
        return [figura, Spacer(1, 3),
               Paragraph(f"Figura {contador['figura']}", styles["TituloTablaFigura"]),
               Paragraph(titulo, styles["CaptionCursiva"]), Spacer(1, 12)]

    doc = SimpleDocTemplate(str(ruta_salida), pagesize=A4,
                            topMargin=2.54*cm, bottomMargin=2.54*cm,
                            leftMargin=2.54*cm, rightMargin=2.54*cm,
                            title=f"Informe {proyecto_nombre}")
    story = []

    # -------------------------------------------------- encabezado / portada
    fecha = (contexto or {}).get("fecha") or datetime.now().strftime("%d/%m/%Y")
    p = (contexto or {}).get("proyecto") or {}
    celda_titulo = [
        Paragraph("INFORME TECNICO DE PREDISEÑO", styles["TituloPortada"]),
        Paragraph("Estabilizacion de suelos con cemento Portland", styles["SubtituloPortada"]),
    ]
    if logo_path and Path(logo_path).exists():
        img_logo = Image(logo_path, width=1.6*cm, height=1.6*cm)
        fila_encabezado = [[img_logo, celda_titulo]]
        anchos_encabezado = [2*cm, ANCHO_UTIL - 2*cm]
    else:
        fila_encabezado = [[celda_titulo]]
        anchos_encabezado = [ANCHO_UTIL]
    tabla_encabezado = Table(fila_encabezado, colWidths=anchos_encabezado)
    tabla_encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -1), 1.0, colors.black),
    ]))
    story.append(tabla_encabezado)
    story.append(Spacer(1, 8))

    if contexto:
        # Los valores van envueltos en Paragraph (no texto plano) para que
        # reportlab los ajuste (word-wrap) al ancho de su columna -- un
        # string plano no se ajusta y, si es largo (p.ej. una ubicacion con
        # distrito+provincia+departamento), se dibuja por encima de la
        # columna vecina ("Altitud") en vez de bajar de linea.
        ubicacion_txt = ", ".join(v for v in
                                  (p.get("distrito"), p.get("provincia"), p.get("departamento"))
                                  if v) or "-"
        # Las etiquetas (columnas 0 y 2) tambien van en Paragraph -- "Clasificacion
        # AASHTO" es mas ancho que su columna (3.2cm) y, como texto plano, se
        # dibujaba pegado directo al valor de la celda vecina sin espacio.
        def _et(txt):
            return Paragraph(txt, styles["CeldaNegrita"])
        datos_proyecto = [
            [_et("Proyecto"), Paragraph(p.get("nombre", "(sin nombre)"), styles["Celda"]),
             _et("Fecha"), fecha],
            [_et("Ubicacion"), Paragraph(ubicacion_txt, styles["Celda"]), _et("Altitud"),
             f"{p.get('altitud','?')} msnm"],
        ]
        c = contexto.get("clasif") or {}
        if c:
            datos_proyecto.append([_et("Clasificacion AASHTO"), c.get("grupo", "?"),
                                   _et("SUCS probable"),
                                   Paragraph(", ".join(c.get("sucs_probable", [])) or "-",
                                             styles["Celda"])])
        tabla_proy = Table(datos_proyecto, colWidths=[3.0*cm, 4.96*cm, 2.62*cm, 5.34*cm])
        tabla_proy.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tabla_proy)
        story.append(Spacer(1, 10))

    # -------------------------------------------------- cuerpo del informe
    checks_a = (contexto or {}).get("checks_normativa_a")
    estabs = (contexto or {}).get("estabilizadores")
    prefijos_estabilizador = tuple(f"- **{r['nombre']}**" for r in (estabs or []))
    bloques = texto_informe.split("\n\n")
    # el primer bloque (titulo/proyecto/fecha en texto plano) ya se reemplazo
    # por el encabezado de arriba -- se omite para no duplicar informacion.
    if bloques and bloques[0].strip().upper().startswith("INFORME TECNICO"):
        bloques = bloques[1:]

    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        primera = bloque.split("\n")[0]
        # "N. TITULO..." (numeral + punto + espacio) es SIEMPRE un titulo de
        # seccion, sin importar el largo -- antes se exigia largo < 60, lo
        # que fallaba justo con "3. EVALUACION DE ALTERNATIVAS DE
        # ESTABILIZADOR (Cuadro 9.2 MTC)" (65 caracteres) y esa seccion nunca
        # se pintaba como banner azul como las demas.
        es_titulo = bool(re.match(r"^\d+\.\s", primera)) or (
            len(primera) < 60 and primera.isupper())

        # Los bloques "- **Nombre del estabilizador** [...]" se renderizan
        # como tabla (mas abajo, al detectar el titulo de la Seccion 3) --
        # aqui se descartan para no duplicarlos como parrafos sueltos.
        if estabs and bloque.startswith(prefijos_estabilizador):
            continue
        nota_cal_ctx = (contexto or {}).get("nota_cal")
        if nota_cal_ctx and bloque.strip() == nota_cal_ctx.strip():
            continue    # ya se imprime junto a la tabla de estabilizadores, mas abajo

        if es_titulo and "EVALUACIÓN DE ALTERNATIVAS DE ESTABILIZADOR" in primera.upper() and estabs:
            story.append(_banner_seccion(primera.replace("*", ""), styles))
            resto = "\n".join(bloque.split("\n")[1:])
            if resto.strip():
                story.append(Spacer(1, 4))
                story.append(Paragraph(resto.replace("\n", "<br/>").replace("**", "<b>").replace("**", "</b>"),
                                       styles["Cuerpo"]))
            story.append(Spacer(1, 6))
            story.extend(_con_titulo_tabla(
                "Evaluacion de estabilizadores segun el Cuadro 9.2 (MTC, 2015)",
                _tabla_estabilizadores(estabs, styles),
                nota=("[1] Para Cemento Portland, \"No verificado\" se refiere "
                     "UNICAMENTE a materia organica, sulfatos y abrasion (Cuadro "
                     "9.2), que este software no mide. La resistencia (Y1) y la "
                     "durabilidad Durham (Y2) del Cemento Portland SI fueron "
                     "evaluadas mediante el modelo RNA -- ver Seccion 4 (Resultados "
                     "de Prediccion)."
                     if any(r["nombre"] == "Cemento Portland" and r["estado"] == "NO_VERIFICADO"
                           for r in estabs) else None)))
            nota_cal = (contexto or {}).get("nota_cal")
            if nota_cal:
                story.append(Paragraph(nota_cal, styles["Cuerpo"]))
                story.append(Spacer(1, 8))
            continue

        if bloque.startswith("Requisitos normativos MTC obligatorios") and checks_a:
            filas = []
            for crit, ok, _color, msg in checks_a:
                estado_txt = "No verificado" if ok is None else ("Cumple" if ok else "No cumple")
                detalle = msg if ok is None else ("-" if ok else msg)
                filas.append((crit, estado_txt, detalle, ok))
            story.extend(_con_titulo_tabla(
                "Requisitos normativos obligatorios, Cuadro 9.2 (MTC, 2015)",
                _tabla_criterios(filas, ["Criterio (Cuadro 9.2 MTC)", "Estado", "Observacion"],
                                 [7.0*cm, 2.5*cm, 6.42*cm], styles, usar_color_estado=True)))
            continue

        if es_titulo and "CRITERIOS DE ACEPTACIÓN EN OBRA" in primera.upper():
            story.append(_banner_seccion(primera.replace("*", ""), styles))
            story.append(Spacer(1, 6))
            filas = [(param, tol, req, True) for param, req, tol in CRITERIOS_ACEPTACION_OBRA]
            story.extend(_con_titulo_tabla(
                "Criterios de aceptacion en obra",
                _tabla_criterios(filas, ["Parametro", "Tolerancia", "Requisito"],
                                 [5.3*cm, 3.3*cm, 7.32*cm], styles, usar_color_estado=False)))
            continue

        if es_titulo and "MARCO NORMATIVO APLICADO" in primera.upper():
            story.append(_banner_seccion(primera.replace("*", ""), styles))
            story.append(Spacer(1, 8))
            story.extend(_lista_referencias(MARCO_NORMATIVO, styles))
            story.append(Spacer(1, 8))
            continue

        if es_titulo and "ADVERTENCIA" in primera.upper():
            story.append(_banner_seccion(primera.replace("*", ""), styles))
            resto = "\n".join(bloque.split("\n")[1:]).strip()
            story.append(Spacer(1, 4))
            texto_aviso = resto.replace("\n", "<br/>").replace("**", "")
            story.append(Table([[Paragraph(texto_aviso, styles["Aviso"])]],
                                colWidths=[ANCHO_UTIL],
                                style=TableStyle([
                                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_AMARILLO_BG)),
                                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                ])))
            story.append(Spacer(1, 8))
            continue

        # Subtitulos Nivel 2 APA: los pasos del proceso constructivo ("Paso 1.
        # Preparacion", etc., dentro de la Seccion 6) y el bloque de
        # coeficientes estructurales. Se detectan ANTES del caso generico
        # es_titulo -- no empiezan con "N." asi que nunca calzan con ese
        # patron (a proposito: si usaran "1. Preparacion" tal como antes,
        # el regex de titulo de seccion los ascendia por error a Nivel 1,
        # con el mismo peso visual que "6. PROCESO CONSTRUCTIVO").
        if re.match(r"^Paso \d+\.\s", primera) or primera == "Coeficientes estructurales (referencia AASHTO 1993)":
            story.append(_titulo_nivel2(primera, styles))
            resto = "\n".join(bloque.split("\n")[1:])
            if resto.strip():
                story.append(Paragraph(resto.replace("\n", "<br/>"), styles["Cuerpo"]))
        elif es_titulo:
            story.append(_banner_seccion(primera.replace("*", ""), styles))
            resto = "\n".join(bloque.split("\n")[1:])
            if resto.strip():
                story.append(Spacer(1, 4))
                story.append(Paragraph(resto.replace("\n", "<br/>").replace("**", "<b>").replace("**", "</b>"),
                                       styles["Cuerpo"]))
        else:
            texto_html = bloque.replace("\n", "<br/>")
            partes = texto_html.split("**")
            texto_html = "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(partes))
            story.append(Paragraph(texto_html, styles["Cuerpo"]))
        story.append(Spacer(1, 8))

    if imagen_curva and Path(imagen_curva).exists():
        story.append(PageBreak())
        story.append(_banner_seccion("5. CURVA DE DOSIFICACIÓN", styles))
        story.append(Spacer(1, 6))
        # Respetar la proporcion real del PNG (evita estirar/distorsionar la
        # imagen): se calcula el alto a partir del ancho maximo disponible.
        from PIL import Image as PILImage
        with PILImage.open(imagen_curva) as im:
            iw, ih = im.size
        ancho = ANCHO_UTIL
        alto = ancho * ih / iw
        alto_max = 18 * cm
        if alto > alto_max:
            alto = alto_max
            ancho = alto * iw / ih
        story.extend(_con_titulo_figura(
            "Curva de dosificacion: resistencia (Y1) y durabilidad Durham (Y2) "
            "predichas en funcion del porcentaje de cemento",
            Image(imagen_curva, width=ancho, height=alto)))

    fotos = [f for f in ((contexto or {}).get("fotos_reporte") or [])
            if Path(f.get("ruta", "")).exists()]
    if fotos:
        story.append(PageBreak())
        story.append(_banner_seccion("REGISTRO FOTOGRÁFICO", styles))
        story.append(Spacer(1, 8))
        for f in fotos:
            imagen_foto = _figura_foto(f["ruta"], 11*cm, styles)
            story.extend(_con_titulo_figura(f.get("leyenda") or "Fotografia de campo.",
                                            imagen_foto))

    encabezado_pie = _encabezado_pie_pagina(proyecto_nombre)
    doc.build(story, onFirstPage=encabezado_pie, onLaterPages=encabezado_pie)
    return str(ruta_salida)


if __name__ == "__main__":
    ctx = {
        "proyecto": {"nombre": "Prueba", "departamento": "Ayacucho",
                     "provincia": "Huamanga", "distrito": "Vinchos",
                     "altitud": 3200, "region": "Sierra", "imd": 150},
        "suelo": {"X9": 3.5, "X7": 9.0, "X8": 2.17},
        "clasif": {"grupo": "A-1-a", "categoria": "granular",
                   "sucs_probable": ["GW", "GP"], "ideal_para_cemento": True},
        "y1_mpa": 2.33, "y1_kgcm2": 23.8,
        "y2": {"veredicto": "CUMPLE", "Y2_perdida_pct": 7.1,
               "umbral_normativo_pct": 14.0, "exactitud_clasificacion_referencia": 0.77},
        "avisos": [],
        "optimo": {"cemento": 3.5, "Y1_MPa": 1.86, "Y1_kgcm2": 18.9,
                  "Y2_veredicto": "CUMPLE", "a2": 0.18},
        "dosif_practica": {"kg_m3": 76.1, "bolsas_m3": 1.79},
    }
    txt = generar_texto_informe(ctx)
    print(txt)
    out = Path(__file__).parent / "_prueba_informe.pdf"
    generar_pdf(txt, out, proyecto_nombre="Prueba")
    print(f"\nPDF generado: {out}  existe={out.exists()}  tam={out.stat().st_size} bytes")

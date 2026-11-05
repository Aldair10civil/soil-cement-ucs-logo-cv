# -*- coding: utf-8 -*-
"""
================================================================================
estabilizadores.py - Capa 0: aptitud de estabilizadores (Cuadro 9.2 MTC)
Software predictor suelo-cemento CNP Peru
================================================================================
Evalua los 8 estabilizadores del Cuadro 9.2 contra el suelo del proyecto.
Parametros quimicos (CMO, sulfatos, equivalente de arena, abrasion, pH) NO
estan en el dataset de entrenamiento del modelo RNA -- son insumos
INDEPENDIENTES que el usuario puede ingresar opcionalmente en Capa 0. Si no
se ingresan, el criterio queda 'no verificado' (None), NUNCA se asume que
pasa. Solo si TODOS los criterios evaluables son aptos Y ninguno esta marcado
explicitamente no apto, se considera 'APTO'.
"""
from __future__ import annotations

APTO, NO_APTO, NO_VERIFICADO = "APTO", "NO_APTO", "NO_VERIFICADO"


def _chk(cond):
    """cond puede ser True/False (criterio evaluable) o None (dato no ingresado)."""
    if cond is None:
        return NO_VERIFICADO
    return APTO if cond else NO_APTO


def _peor(estados):
    """NO_APTO domina; si no hay NO_APTO pero hay NO_VERIFICADO, es NO_VERIFICADO."""
    if NO_APTO in estados:
        return NO_APTO
    if NO_VERIFICADO in estados:
        return NO_VERIFICADO
    return APTO


def evaluar_estabilizadores(suelo: dict, grupo_aashto: str, quimico: dict) -> list:
    """
    suelo: dict con X1..X6 (grava, arena, finos, LL, LP, IP)
    grupo_aashto: p.ej. "A-2-6" (de clasificacion.clasificar_aashto_detallado)
    quimico: dict OPCIONAL con claves CMO, sulfatos, equiv_arena, abrasion, ph
             (valores None si no se ingresaron)
    Retorna lista de dicts: nombre, estado, restricciones (lista de
    (descripcion, estado)), dosificacion, curado, normas.
    """
    X3, ip = suelo["X3"], suelo.get("X6") or 0.0
    cmo = quimico.get("CMO")
    so4 = quimico.get("sulfatos")
    ea = quimico.get("equiv_arena")
    abr = quimico.get("abrasion")
    ph = quimico.get("ph")

    es_A1_A2_A3 = grupo_aashto in ("A-1-a", "A-1-b", "A-3", "A-2-4", "A-2-5",
                                   "A-2-6", "A-2-7")
    es_A1_A2 = grupo_aashto in ("A-1-a", "A-1-b", "A-2-4", "A-2-5", "A-2-6", "A-2-7")
    es_A26_A27_A6_A7 = grupo_aashto in ("A-2-6", "A-2-7", "A-6", "A-7-5", "A-7-6")
    ll = suelo.get("X4") or 0.0

    resultados = []

    # 1. CEMENTO PORTLAND
    crit = [("Suelo A-1 a A-7", True),
            ("LL > 40%", ll > 40), ("IP >= 18%", ip >= 18),
            ("Materia organica < 1.0%", None if cmo is None else cmo < 1.0),
            ("Sulfatos < 0.2%", None if so4 is None else so4 < 0.2),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Cemento Portland", crit, "2-12%", "7 dias",
                            "EG-CBT-2008 Sec. 3068, ASTM C150, AASHTO M85",
                            control=("Resistencia compresion simple >= 1.8 MPa "
                                    "(18.0 kg/cm2) - MTC E-1103. Humedecimiento-"
                                    "secado (MTC E-1104): <=14% (A-1/A-2-4/A-2-5/"
                                    "A-3), <=10% (A-2-6/A-2-7/A-4/A-5), <=7% "
                                    "(A-6/A-7).")))

    # 2. EMULSION ASFALTICA
    crit = [("Suelo A-1, A-2 o A-3", grupo_aashto in
            ("A-1-a", "A-1-b", "A-3", "A-2-4", "A-2-5", "A-2-6", "A-2-7")),
            ("Pasa N200 <= 10%", X3 <= 10), ("IP <= 8%", ip <= 8),
            ("Equiv. arena >= 40%", None if ea is None else ea >= 40),
            ("Materia organica < 1.0%", None if cmo is None else cmo < 1.0),
            ("Sulfatos < 0.6%", None if so4 is None else so4 < 0.6),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Emulsion asfaltica", crit, "4-8%", "min. 24 horas",
                            "ASTM D2397, AASHTO M208",
                            control=("Estabilidad Marshall >= 230 kg - MTC E-504. "
                                    "Perdida estabilidad saturado <= 50%. "
                                    "Recubrimiento y trabajabilidad: 50-100%.")))

    # 3. CAL
    crit = [("Suelo A-2-6/A-2-7/A-6/A-7", es_A26_A27_A6_A7),
            ("10% <= IP <= 50%", 10 <= ip <= 50),
            ("Materia organica < 3.0%", None if cmo is None else cmo < 3.0),
            ("Sulfatos < 0.2%", None if so4 is None else so4 < 0.2),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Cal", crit, "2-8%", "min. 72 horas",
                            "EG-CBT-2008 Sec. 3078, AASHTO M216, ASTM C977",
                            nota="Para IP > 50% aplicar en dos etapas (ASTM D6276)"
                            if ip > 50 else None,
                            control="CBR (0.1\") >= 100% - MTC E-115/E-132. Expansion <= 0.5%."))

    # 4. CLORURO DE CALCIO
    crit = [("Suelo A-1, A-2 o A-3", es_A1_A2_A3), ("IP <= 15%", ip <= 15),
            ("Materia organica < 3.0%", None if cmo is None else cmo < 3.0),
            ("Sulfatos < 0.2%", None if so4 is None else so4 < 0.2),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Cloruro de Calcio", crit, "1-3% en peso", "24 horas",
                            "ASTM D98, ASTM D345, ASTM E449, MTC E-1109",
                            control="CBR no saturado (0.1\") >= 100% - MTC E-115/E-132."))

    # 5. CLORURO DE SODIO
    crit = [("Suelo A-2-4 a A-2-7", grupo_aashto in ("A-2-4", "A-2-5", "A-2-6", "A-2-7")),
            ("8% <= IP <= 15%", 8 <= ip <= 15),
            ("Materia organica < 3.0%", None if cmo is None else cmo < 3.0),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Cloruro de Sodio", crit, "50-80 kg/m3", "7 dias",
                            "EG-CBT-2008 Sec. 309B, ASTM E534, MTC E-1109",
                            control="CBR no saturado (0.1\") >= 100% - MTC E-115/E-132."))

    # 6. CLORURO DE MAGNESIO
    crit = [("Suelo A-1, A-2 o A-3", es_A1_A2_A3), ("IP <= 15%", ip <= 15),
            ("pH >= 5", None if ph is None else ph >= 5),
            ("Materia organica < 3.0%", None if cmo is None else cmo < 3.0),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Cloruro de Magnesio", crit, "50-80 kg/m3", "48 horas",
                            "MTC E-1109",
                            control="CBR no saturado (0.1\") >= 100% - MTC E-115/E-132."))

    # 7. ENZIMAS
    crit = [("Suelo A-2-4 a A-2-7", grupo_aashto in ("A-2-4", "A-2-5", "A-2-6", "A-2-7")),
            ("6% <= IP <= 15%", 6 <= ip <= 15),
            ("4.5 < pH < 8.5", None if ph is None else 4.5 < ph < 8.5),
            ("CMO = 0 (no debe contener)", None if cmo is None else cmo == 0),
            ("Pasa N200 entre 10-35%", 10 <= X3 <= 35),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Enzimas", crit, "1L / 30-33 m3", "segun fabricante",
                            "EG-CBT-2008 Sec. 308B, MTC E-1109",
                            control="CBR (0.1\") >= 100% - MTC E-115/E-132. Expansion <= 0.5%."))

    # 8. ACEITES SULFONADOS
    crit = [("Finos limosos o arcillosos, LL bajo", X3 > 10),
            ("Materia organica < 1.0%", None if cmo is None else cmo < 1.0),
            ("Abrasion < 50%", None if abr is None else abr < 50)]
    resultados.append(_fila("Aceites sulfonados", crit, "segun fabricante",
                            "segun fabricante", "MTC E-1109",
                            control="CBR (0.1\") >= 100% - MTC E-115/E-132. Expansion <= 0.5%."))

    return resultados


def _fila(nombre, criterios, dosificacion, curado, normas, nota=None, control=None):
    estados = [_chk(c) for _, c in criterios]
    r = {"nombre": nombre, "estado": _peor(estados),
         "criterios": [(desc, _chk(c)) for desc, c in criterios],
         "dosificacion": dosificacion, "curado": curado, "normas": normas,
         "control": control or "-"}
    if nota:
        r["nota"] = nota
    return r


if __name__ == "__main__":
    suelo = {"X1": 55, "X2": 30, "X3": 15, "X4": 20, "X5": 15, "X6": 5}
    quim = {"CMO": 0.5, "sulfatos": 0.1, "equiv_arena": 45, "abrasion": 30, "ph": 7}
    for r in evaluar_estabilizadores(suelo, "A-2-4", quim):
        print(f"{r['nombre']:<22} {r['estado']:<14} dosif={r['dosificacion']}")
        for desc, est in r["criterios"]:
            if est != APTO:
                print(f"    - {desc}: {est}")

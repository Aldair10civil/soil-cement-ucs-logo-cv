# -*- coding: utf-8 -*-
"""
================================================================================
clasificacion.py - Clasificacion AASHTO detallada + correlacion SUCS
Software predictor suelo-cemento CNP Peru
================================================================================
Clasificacion AASHTO simplificada (segun especificacion del software, no
sustituye AASHTO M145 completo porque el dataset no registra %pasa N10/N40).
Devuelve el grupo detallado (A-1-a, A-1-b, A-3, A-2-4..A-2-7, A-4..A-7-6) y su
correlacion SUCS (probable / posible / improbable) para mostrar al usuario.

La EXIGENCIA DURHAM (umbral normativo Y2) se calcula por separado en
MODELO_ENTRENADO/predictor.clasificar_aashto() usando la misma frontera
finos<=35 / IP>10 -- este modulo NO debe usarse para esa cifra, solo para
mostrar el grupo detallado y el cuadro SUCS al usuario.
"""
from __future__ import annotations

# grupo -> (sucs_probable, sucs_posible, sucs_improbable)
TABLA_SUCS = {
    "A-1-a": (["GW", "GP"], ["SW", "SP"], ["GM", "SM"]),
    "A-1-b": (["SW", "SP", "GM", "SM"], ["GP"], []),
    "A-3":   (["SP"], [], ["SW", "GP"]),
    "A-2-4": (["GM", "SM"], ["GC", "SC"], ["GW", "GP", "SW", "SP"]),
    "A-2-5": (["GM", "SM"], [], ["GW", "GP", "SW", "SP"]),
    "A-2-6": (["GC", "SC"], ["GM", "SM"], ["GW", "GP", "SW", "SP"]),
    "A-2-7": (["GM", "GC", "SM", "SC"], [], ["GW", "GP", "SW", "SP"]),
    "A-4":   (["ML", "OL"], ["CL", "SM", "SC"], ["GM", "GC"]),
    "A-5":   (["OH", "MH"], ["ML", "OL"], ["SM", "GM"]),
    "A-6":   (["CL"], ["ML", "OL", "SC"], ["GC", "GM", "SM"]),
    "A-7-5": (["OH", "MH"], ["ML", "OL", "CH"], ["GM", "SM", "GC", "SC"]),
    "A-7-6": (["CH", "CL"], ["ML", "OL", "SC"], ["OH", "MH", "GC", "GM", "SM"]),
}

# grupo -> categoria / exigencia Durham (debe coincidir con predictor.clasificar_aashto)
_GRANULAR = {"A-1-a", "A-1-b", "A-3", "A-2-4", "A-2-5"}
_TRANSICION = {"A-2-6", "A-2-7", "A-4", "A-5"}
_ARCILLA = {"A-6", "A-7-5", "A-7-6"}

SIGNIFICADO_SUCS = {
    "G": "Grava (>4.75 mm, retenido N4)", "S": "Arena (0.075-4.75 mm)",
    "M": "Limo (finos baja plasticidad)", "C": "Arcilla (finos alta plasticidad)",
    "O": "Organico",
    "W": "Bien graduado", "P": "Mal graduado",
    "H": "Alta plasticidad (LL>50%)", "L": "Baja plasticidad (LL<50%)",
}

SUELOS_IDEALES_CEMENTO = {"A-1-a", "A-1-b", "A-2-4", "A-2-5", "A-2-6", "A-2-7"}


def _sucs_exacto_limpio(X1, X2, cu, cc):
    """Simbolo SUCS EXACTO (ASTM D2487) para suelos LIMPIOS (finos < 5%),
    donde Cu y Cc determinan sin ambiguedad bien graduado (W) vs mal
    graduado (P) -- sin Cu/Cc esto solo se puede acotar a una lista de
    posibles simbolos (ver TABLA_SUCS).
    Cu (D60/D10) minimo: 4 para grava, 6 para arena. Cc ((D30)^2/(D60*D10))
    debe estar entre 1 y 3 en ambos casos."""
    grava_dominante = X1 >= X2
    cu_min = 4.0 if grava_dominante else 6.0
    bien_graduado = cu >= cu_min and 1.0 <= cc <= 3.0
    letra = "G" if grava_dominante else "S"
    return f"{letra}W" if bien_graduado else f"{letra}P"


def clasificar_aashto_detallado(X1, X2, X3, X4, X5, X6, cu=None, cc=None):
    """
    X1 Grava %ret N4, X2 Arena, X3 Finos %pasa N200, X4 LL, X5 LP, X6 IP.
    cu, cc: Coeficiente de Uniformidad (D60/D10) y Curvatura ((D30)^2/(D60*D10))
    -- OPCIONALES, del ensayo granulometrico completo (curva D10/D30/D60). Si
    se proveen ambos y el suelo es limpio (finos < 5%), la correlacion SUCS
    deja de ser una lista de posibles simbolos y se vuelve el simbolo EXACTO
    (sucs_exacto), ya que Cu/Cc son precisamente lo que distingue W de P.
    Retorna dict: grupo, sucs_probable/posible/improbable, sucs_exacto,
    categoria, ideal_para_cemento, exigencia_durham (informativa, ver nota
    de arriba).
    """
    ip = X6 or 0.0
    ll = X4 or 0.0
    es_np = (ll == 0.0 and ip == 0.0)   # No Plastico

    if X1 > 50 and X3 < 15 and ip <= 6:
        grupo = "A-1-a"
    elif X1 < 50 and X3 < 25 and ip <= 6:
        grupo = "A-1-b"
    elif X2 > 50 and X3 < 10 and es_np:
        grupo = "A-3"
    elif X3 < 35:
        if ll <= 40 and ip <= 10:
            grupo = "A-2-4"
        elif ll > 40 and ip <= 10:
            grupo = "A-2-5"
        elif ll <= 40 and ip > 10:
            grupo = "A-2-6"
        else:
            grupo = "A-2-7"
    else:
        if ll <= 40 and ip <= 10:
            grupo = "A-4"
        elif ll > 40 and ip <= 10:
            grupo = "A-5"
        elif ll <= 40 and ip > 10:
            grupo = "A-6"
        else:
            grupo = "A-7-5" if ip <= (ll - 30) else "A-7-6"

    probable, posible, improbable = TABLA_SUCS[grupo]
    if grupo in _GRANULAR:
        categoria, exigencia = "granular", 14.0
    elif grupo in _TRANSICION:
        categoria, exigencia = "transicion", 10.0
    else:
        categoria, exigencia = "arcilla", 7.0

    sucs_exacto = None
    if cu and cc and X3 < 5.0:
        sucs_exacto = _sucs_exacto_limpio(X1, X2, cu, cc)
        probable, posible, improbable = [sucs_exacto], [], []

    return {
        "grupo": grupo,
        "sucs_probable": probable, "sucs_posible": posible,
        "sucs_improbable": improbable, "sucs_exacto": sucs_exacto,
        "categoria": categoria, "exigencia_durham": exigencia,
        "ideal_para_cemento": grupo in SUELOS_IDEALES_CEMENTO,
    }


def verificar_restriccion_usace(X1, X2, X3, X4, X6):
    """
    Restricciones USACE para aptitud a cemento Portland (Cuadro 9.1 MTC).
    Indexadas por familia SUCS (limpio / dual-simbolo / con finos / arcilla),
    inferida aqui a partir de X1 (grava %ret N4), X2 (arena), X3 (finos %pasa
    N200), X4 (LL) y X6 (IP) -- el dataset no registra el simbolo SUCS
    definitivo, solo su banda de finos y dominancia grava/arena.

    Retorna dict: familia, restriccion (texto), cumple (bool).
    """
    ip = X6 or 0.0
    ll = X4 or 0.0
    grava_dominante = X1 >= X2   # mas retenido N4 que arena -> familia "G"

    if X3 <= 5:
        return {"familia": "SW, SP, GW, GP (limpios)",
               "restriccion": "Sin restriccion adicional", "cumple": True}

    if X3 <= 12:
        ip_ok = ip <= 30
        n4_ok = (X1 <= 55) if grava_dominante else True
        detalle = "IP <= 30" + (" y minimo 45% pasa N4 (X1<=55%)" if grava_dominante else "")
        familia = ("GW-GM/GP-GM/GW-GC/GP-GC" if grava_dominante
                  else "SW-SM/SP-SM/SW-SC/SP-SC")
        return {"familia": familia, "restriccion": detalle, "cumple": ip_ok and n4_ok}

    if X3 < 36:
        umbral_ip = (50 - X3) / 4 + 20
        ip_ok = ip <= umbral_ip
        n4_ok = (X1 <= 55) if grava_dominante else True
        detalle = f"IP <= {umbral_ip:.1f} (formula (50-finos)/4+20)" + (
            " y minimo 45% pasa N4 (X1<=55%)" if grava_dominante else "")
        familia = "GM/GC/GM-GC" if grava_dominante else "SM/SC/SM-SC"
        return {"familia": familia, "restriccion": detalle, "cumple": ip_ok and n4_ok}

    cumple = ll > 40 and ip >= 18
    return {"familia": "CH, CL, MH, ML",
           "restriccion": "LL > 40 e IP >= 18", "cumple": cumple}


if __name__ == "__main__":
    casos = [
        ("Grava limpia", 60, 35, 5, 0, 0, 0),
        ("Colombia Zofia", 55.14, 36.04, 8.82, 16.44, 12.52, 3.91),
        ("Vallejo Caceres", 63.8, 20.2, 16.0, 26.0, 20.4, 5.6),
        ("Arcilla A-6/7", 20, 20, 60, 45, 25, 20),
    ]
    for nom, *x in casos:
        r = clasificar_aashto_detallado(*x)
        print(f"{nom:<18} -> {r['grupo']:<8} ({r['categoria']:<10}) "
              f"SUCS probable={r['sucs_probable']}  Durham<={r['exigencia_durham']}%  "
              f"ideal_cemento={r['ideal_para_cemento']}")

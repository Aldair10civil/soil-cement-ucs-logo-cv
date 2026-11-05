# -*- coding: utf-8 -*-
"""
================================================================================
tooltips.py - Ayuda contextual: metodologia de ensayos MTC E-1103 / E-1104
Software predictor suelo-cemento CNP Peru
================================================================================
Contenido tecnico para los botones "?" junto a Y1 y Y2. Se muestra en un
QMessageBox (informativo, HTML simple) al hacer clic.
"""
from __future__ import annotations

FACTOR_CORRECCION_HD = [
    (2.00, 1.000), (1.75, 0.980), (1.50, 0.960), (1.25, 0.930), (1.00, 0.870),
]

TEXTO_E1103 = """
<h3>Resistencia a la Compresion de Probetas de Suelo-Cemento</h3>
<p><b>MTC E-1103 / ASTM D-1633 / AASHTO T-22</b></p>

<p>Se fabrican probetas cilindricas de suelo-cemento (diametro 101.6 mm)
compactadas al 100% de la MDS con el OCH de la mezcla. Se curan 7 dias en
camara humeda a 21 grados C. Antes de la rotura se sumergen 4 horas en agua.
Se rompen en prensa a velocidad de 1.4 kg/cm2/segundo.</p>

<p><b>Resistencia = Carga maxima / Area de la seccion x Factor de correccion H/D</b></p>

<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Relacion H/D</th><th>Factor de correccion</th></tr>
{filas_hd}
</table>

<p><b>Control de calidad:</b> si una probeta difiere mas del 10% del promedio
de las demas, se descarta y se promedia con las restantes.</p>

<p><b>Requisito minimo:</b> &gt;= 1.8 MPa (18.0 kg/cm2) segun Cuadro N01 MTC</p>

<h4>Probeta de compactacion (MTC E-1101)</h4>
<ul>
<li>Molde cilindrico: 101.6 mm diametro x 116.4 mm altura</li>
<li>Compactacion: 5 capas, 25 golpes/capa</li>
<li>Pison: 4.54 kg de peso, caida de 457 mm</li>
<li>Metodo: Proctor Modificado (MTC E-115 / ASTM D1557 / AASHTO T-180)</li>
<li>Se compacta al 100% MDS con el OCH de la mezcla suelo-cemento</li>
</ul>
""".format(filas_hd="\n".join(
    f"<tr><td>{hd:.2f}</td><td>{f:.3f}</td></tr>" for hd, f in FACTOR_CORRECCION_HD))

TEXTO_E1104 = """
<h3>Humedecimiento y Secado de Mezclas de Suelo-Cemento Compactadas</h3>
<p><b>MTC E-1104 / ASTM D-559 / AASHTO T-135</b></p>

<p>Simula las condiciones climaticas extremas que sufrira la carretera durante
su vida util. Se fabrican 2 probetas compactadas al 100% MDS con OCH. Se
curan 7 dias en camara humeda a 21 grados C. Luego se someten a <b>12
ciclos</b>, cada uno de 48 horas:</p>

<ol>
<li><b>Inmersion en agua: 5 horas</b> -- simula lluvia intensa, inundacion, napa freatica alta</li>
<li><b>Secado en horno a 71 grados C: 42 horas</b> -- simula calor extremo, sol intenso</li>
<li><b>Reposo a temperatura ambiente: 1 hora</b></li>
<li><b>Cepillado normalizado: 18-20 pasadas</b> con cepillo de cerdas de alambre a 13.3 N de fuerza -- simula erosion mecanica del trafico</li>
</ol>

<p>Duracion total: 12 ciclos x 48 horas = ~24 dias de ensayo continuo.</p>

<p>Al final del ciclo 12, se seca la probeta a 110 grados C y se pesa. La
<b>perdida de peso (%)</b> respecto al peso original es el valor Y2.</p>

<h4>Limites maximos de perdida segun tipo de suelo</h4>
<ul>
<li>A-1, A-2-4, A-2-5, A-3 (granulares): &lt;= 14%</li>
<li>A-2-6, A-2-7, A-4, A-5 (transicion): &lt;= 10%</li>
<li>A-6, A-7 (arcillas): &lt;= 7%</li>
</ul>

<p><i>Por que es importante:</i> una mezcla suelo-cemento puede tener buena
resistencia a compresion (Y1 &gt;= 1.8 MPa) pero desintegrarse con el clima.
El ensayo Durham verifica que la mezcla es durable -- que no se deshara con
las lluvias y el sol. Un camino en la sierra a 3500 msnm sufre lluvia intensa
en epoca humeda y sol con heladas en epoca seca, exactamente lo que este
ensayo simula.</p>

<p><b>Dosificaciones a ensayar:</b> el ensayo E-1104 en si NO establece que
porcentajes de cemento probar -- solo describe el procedimiento (12 ciclos) y
como calcular la perdida de peso. El Cuadro 9.2 MTC exige unicamente "emplear
como minimo 4 dosificaciones diferentes"; el ingeniero elige cuales, usando
como referencia el rango FHWA (Cuadro 9.4) y la curva de dosificacion de este
software (que predice Y2 para todo el rango 1%-12%, no solo para 3 puntos
fijos).</p>
""".strip()

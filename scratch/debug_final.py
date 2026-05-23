# -*- coding: utf-8 -*-
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

import app as webapp

real_text = """\xa0\xa0\xa0\xa0\xa0\xa0\xa0 Art.
38. A base de c\u00e1lculo do imposto \u00e9 o valor venal dos bens ou direitos transmitidos.

\u00a7 1\u00ba
Considera-se valor venal, para fins do *caput* deste artigo, o valor pelo
qual o bem ou direito seria negociado \u00e0 vista, em condi\u00e7\u00f5es normais de mercado.
\xa0(Inclu\u00eddo
pela Lei Complementar n\u00ba 227, de 2026)

\u00a7 2\u00ba O
valor pelo qual o bem ou direito seria negociado \u00e0 vista, em condi\u00e7\u00f5es normais
de mercado, a que se refere o \u00a7\xa01\u00ba deste artigo, ser\u00e1 estimado por meio de
crit\u00e9rios t\u00e9cnicos, considerando pelo menos um dos seguintes:
\xa0(Inclu\u00eddo
pela Lei Complementar n\u00ba 227, de 2026)

I
an\u00e1lise de pre\u00e7os praticados no mercado imobili\u00e1rio;
\xa0(Inclu\u00eddo
pela Lei Complementar n\u00ba 227, de 2026)
"""

print("=== Raw input ===")
for i, line in enumerate(real_text.splitlines(), 1):
    print(f"  {i}: {repr(line)}")

print("\n=== format_pdf_markdown_model2 ===")
result1 = webapp.format_pdf_markdown_model2(real_text)
for i, line in enumerate(result1.splitlines(), 1):
    if line.strip():
        print(f"  {i}: {repr(line)}")

print("\n=== polish_legal_markdown_model2 ===")
result2 = webapp.polish_legal_markdown_model2(result1)
for i, line in enumerate(result2.splitlines(), 1):
    if line.strip():
        print(f"  {i}: {repr(line)}")

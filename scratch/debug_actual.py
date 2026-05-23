# -*- coding: utf-8 -*-
"""Test with actual raw text from the Planalto MarkItDown output for Art. 38 area."""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

import app as webapp

# Simulate the ACTUAL raw MarkItDown output format for the problem section
# In the raw output, articles are split across lines with indentation
raw_text = """        Art. 38. A base de c\u00e1lculo do imposto \u00e9 o valor venal dos bens ou direitos transmitidos.

\u00a7 1\u00ba Considera-se valor venal, para fins do *caput* deste artigo, o valor pelo qual o bem ou direito seria negociado \u00e0 vista, em condi\u00e7\u00f5es normais de mercado. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 2\u00ba O valor pelo qual o bem ou direito seria negociado \u00e0 vista, em condi\u00e7\u00f5es normais de mercado, a que se refere o \u00a7 1\u00ba deste artigo, ser\u00e1 estimado por meio de crit\u00e9rios t\u00e9cnicos, considerando pelo menos um dos seguintes: (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

I an\u00e1lise de pre\u00e7os praticados no mercado imobili\u00e1rio; (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

II informa\u00e7\u00f5es prestadas pelos servi\u00e7os notariais e registrais e por agentes financeiros; (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

III localiza\u00e7\u00e3o, tipologia, destina\u00e7\u00e3o, padr\u00e3o e \u00e1rea de terreno e constru\u00e7\u00e3o, entre outras caracter\u00edsticas do bem im\u00f3vel; e (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

IV outros par\u00e2metros t\u00e9cnicos usualmente observados na avalia\u00e7\u00e3o de im\u00f3veis. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 3\u00ba As administra\u00e7\u00f5es tribut\u00e1rias dos Munic\u00edpios e do Distrito Federal dever\u00e3o divulgar os crit\u00e9rios utilizados. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 4\u00ba Os servi\u00e7os registrais e notariais dever\u00e3o compartilhar as informa\u00e7\u00f5es. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

Art. 39. (Revogado pela Lei Complementar n\u00ba 227, de 2026)"""

print("=== Raw input ===")
for i, line in enumerate(raw_text.splitlines(), 1):
    if line.strip():
        print(f"  {i}: {line[:120]}")

print()
result = webapp.format_pdf_markdown_model2(raw_text)
print("=== After format_pdf_markdown_model2 ===")
for i, line in enumerate(result.splitlines(), 1):
    if line.strip():
        print(f"  {i}: {line[:140]}")

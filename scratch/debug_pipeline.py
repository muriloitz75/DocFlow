# -*- coding: utf-8 -*-
"""Trace the pipeline step-by-step to find where inline § splits get re-merged."""
import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

import app as webapp

# Extract a problem section from the raw MarkItDown output
# This is from Art. 38 area where §1, §2, §3, §4 get concatenated
test_input = """Art. 38. A base de c\u00e1lculo do imposto \u00e9 o valor venal dos bens ou direitos transmitidos.

\u00a7 1\u00ba Considera-se valor venal, para fins do *caput* deste artigo, o valor pelo qual o bem ou direito seria negociado \u00e0 vista, em condi\u00e7\u00f5es normais de mercado. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 2\u00ba O valor pelo qual o bem ou direito seria negociado \u00e0 vista, em condi\u00e7\u00f5es normais de mercado, a que se refere o \u00a7 1\u00ba deste artigo, ser\u00e1 estimado por meio de crit\u00e9rios t\u00e9cnicos. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

I an\u00e1lise de pre\u00e7os praticados no mercado imobili\u00e1rio; (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

II informa\u00e7\u00f5es prestadas pelos servi\u00e7os notariais e registrais e por agentes financeiros; (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

III localiza\u00e7\u00e3o, tipologia, destina\u00e7\u00e3o, padr\u00e3o e \u00e1rea de terreno e constru\u00e7\u00e3o, entre outras caracter\u00edsticas do bem im\u00f3vel; e (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

IV outros par\u00e2metros t\u00e9cnicos usualmente observados na avalia\u00e7\u00e3o de im\u00f3veis. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 3\u00ba As administra\u00e7\u00f5es tribut\u00e1rias dever\u00e3o divulgar os crit\u00e9rios. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 4\u00ba Os servi\u00e7os registrais e notariais dever\u00e3o compartilhar as informa\u00e7\u00f5es. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)"""

print("=== STEP 1: Raw input ===")
print(test_input[:500])
print(f"...(lines: {len(test_input.splitlines())})")

print("\n=== STEP 2: After split_inline_legal_elements ===")
step2 = webapp.split_inline_legal_elements(test_input)
for i, line in enumerate(step2.splitlines(), 1):
    if line.strip():
        print(f"  {i}: {line[:120]}")

print("\n=== STEP 3: After compact_markdown ===")
step3 = webapp.compact_markdown(step2)
for i, line in enumerate(step3.splitlines(), 1):
    if line.strip():
        print(f"  {i}: {line[:120]}")

print("\n=== STEP 4: After format_pdf_markdown_model2 (full pipeline) ===")
step4 = webapp.format_pdf_markdown_model2(test_input)
for i, line in enumerate(step4.splitlines(), 1):
    if line.strip():
        print(f"  {i}: {line[:120]}")

# -*- coding: utf-8 -*-
"""Debug why inline § splitting fails for some cases."""
import re

# Test case from line 246
test = 'Considera-se valor venal, para fins do *caput* deste artigo, o valor pelo qual o bem ou direito seria negociado \u00e0 vista, em condi\u00e7\u00f5es normais de mercado. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) **\u00a7 2\u00ba** O valor pelo qual...'

print("Test input:")
print(repr(test[:200]))
print()

# The boundary pattern
boundary = r'(?:[).;]|Produ[\u00e7c][\u00e3a]o\s+de\s+efeitos|Vig[\u00eae]ncia|Vide\b)'

# Split § pattern
pattern = rf'({boundary}\s*)([*_]*\u00a7\s*\d+)'
matches = list(re.finditer(pattern, test))
print(f"Matches found: {len(matches)}")
for m in matches:
    print(f"  Match: {repr(m.group(0))}")
    print(f"  Group 1 (boundary): {repr(m.group(1))}")
    print(f"  Group 2 (§): {repr(m.group(2))}")

result = re.sub(pattern, r'\1\n\n\2', test)
print(f"\nResult:")
print(result[:300])

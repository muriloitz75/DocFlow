# -*- coding: utf-8 -*-
"""Test the ACTUAL failing pattern from the live output."""
import re

# This is EXACTLY what appears in the formatted output at line 246
test = '**\u00a7 1\u00ba** Considera-se valor venal. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) **\u00a7 2\u00ba** O valor pelo qual.'

print("Test input:")
print(repr(test))
print()

boundary = r'(?:[).;]|Produ[\u00e7c][\u00e3a]o\s+de\s+efeitos|Vig[\u00eae]ncia|Vide\b)'

# Pattern from split_inline_legal_elements for §
pattern = rf'({boundary}\s*)([*_]*\u00a7\s*\d+)'
matches = list(re.finditer(pattern, test))
print(f"Matches: {len(matches)}")
for m in matches:
    print(f"  {repr(m.group(0))}")

result = re.sub(pattern, r'\1\n\n\2', test)
print(f"\nResult:")
print(result)

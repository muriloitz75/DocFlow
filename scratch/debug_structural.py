# -*- coding: utf-8 -*-
"""Debug _starts_structural_block for § lines."""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

import app as webapp

test_lines = [
    "\u00a7 2\u00ba O valor pelo qual...",
    "\u00a7 3\u00ba As administra\u00e7\u00f5es...",
    "Art. 39. (Revogado)",
    "I an\u00e1lise de pre\u00e7os...",
    "LIVRO PRIMEIRO",
]

for line in test_lines:
    normalized = webapp._normalize_text_line(line)
    starts = webapp._starts_structural_block(normalized)
    print(f"  Line: {repr(line[:60])}")
    print(f"    Normalized: {repr(normalized[:60])}")
    print(f"    _starts_structural_block: {starts}")
    
    # Also check each structural pattern individually
    import re
    clean = re.sub(r"^[\*_]+|[\*_]+$", "", normalized).strip()
    for i, pat in enumerate(webapp.STRUCTURAL_LINE_PATTERNS):
        if pat.match(clean):
            print(f"    Matches STRUCTURAL_LINE_PATTERNS[{i}]: {pat.pattern}")
    print()

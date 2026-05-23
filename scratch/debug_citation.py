# -*- coding: utf-8 -*-
"""Check if § 2º line matches CITATION_PATTERN."""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

import app as webapp

test_lines = [
    "\u00a7 2\u00ba O valor pelo qual o bem",
    "\u00a7 3\u00ba As administra\u00e7\u00f5es tribut\u00e1rias",
    "\u00a7 4\u00ba Os servi\u00e7os registrais",
    "\u00a7 1\u00ba deste artigo",  # This IS a citation
    "\u00a7 1\u00ba Considera-se valor",  # This is NOT a citation
]

for line in test_lines:
    citation = webapp.CITATION_PATTERN.match(line)
    structural = webapp._starts_structural_block(line)
    print(f"  {repr(line[:60])}")
    print(f"    CITATION_PATTERN match: {bool(citation)}")
    print(f"    _starts_structural_block: {structural}")
    print()

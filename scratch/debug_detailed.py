# -*- coding: utf-8 -*-
"""Detailed step-by-step trace inside format_pdf_markdown_model2."""
import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

import app as webapp

test_input = """\u00a7 1\u00ba Considera-se valor venal. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 2\u00ba O valor pelo qual. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

I an\u00e1lise de pre\u00e7os praticados. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026)

IV outros par\u00e2metros t\u00e9cnicos. (Inclu\u00eddo pela Lei Complementar n\u00ba 227, de 2026) \u00a7 3\u00ba As administra\u00e7\u00f5es. (Inclu\u00eddo) \u00a7 4\u00ba Os servi\u00e7os registrais. (Inclu\u00eddo)"""

print("=== INPUT ===")
print(test_input)
print()

# Step 1: split_inline
step1 = webapp.split_inline_legal_elements(test_input)
print("=== AFTER split_inline_legal_elements ===")
for i, line in enumerate(step1.splitlines(), 1):
    print(f"  {i}: {repr(line[:100])}")
print()

# Step 2: compact_markdown
step2 = webapp.compact_markdown(step1)
print("=== AFTER compact_markdown ===")
for i, line in enumerate(step2.splitlines(), 1):
    print(f"  {i}: {repr(line[:100])}")
print()

# Step 3: walk through the lines as format_pdf_markdown_model2 does
source_lines = step2.splitlines()
index = 0
print("=== WALKING LINES ===")
while index < len(source_lines):
    line = webapp._normalize_text_line(source_lines[index])
    if not line:
        print(f"  [{index}] (empty)")
        index += 1
        continue
        
    is_art_or_par = (
        re.match(r"^Art\.?\s*\d+", line, flags=re.I)
        or re.match(r"^\u00a7\s*\d+", line)
    )
    is_citation = webapp.CITATION_PATTERN.match(line)
    
    print(f"  [{index}] is_art_or_par={is_art_or_par}, is_citation={is_citation}, line={repr(line[:80])}")
    
    if is_art_or_par and not is_citation:
        # This is the paragraph collection loop
        paragraph_lines = [line]
        index += 1
        while index < len(source_lines):
            next_line = webapp._normalize_text_line(source_lines[index])
            if not next_line:
                index += 1
                break
            is_structural = webapp._starts_structural_block(next_line)
            print(f"    -> [{index}] structural={is_structural}, line={repr(next_line[:80])}")
            if is_structural:
                break
            paragraph_lines.append(next_line)
            index += 1
        paragraph = webapp._join_wrapped_lines(paragraph_lines)
        print(f"    => Joined paragraph: {repr(paragraph[:100])}")
    else:
        index += 1

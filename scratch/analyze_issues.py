# -*- coding: utf-8 -*-
"""Analyze all formatting issues in the live output."""
import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

output_path = os.path.join(BASE_DIR, "scratch", "live_output.md")
with open(output_path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()

print("=== ISSUE 1: Bold-only structural blocks that should be headings ===")
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    # Bold text that looks like a legal structural heading
    clean = re.sub(r'^[\*_]+|[\*_]+$', '', stripped).strip()
    if re.match(r'^\*\*', stripped) and stripped.endswith('**'):
        if re.match(r'^(?:DISPOSI[ÇC][ÃA]O|DISPOSI[ÇC][ÕO]ES)\s', clean, re.I):
            print(f"  L{i}: {stripped[:100]}")

print("\n=== ISSUE 2: Broken bold inside headings ===")
for i, line in enumerate(lines, 1):
    if line.startswith('#') and '**' in line:
        print(f"  L{i}: {line[:120]}")

print("\n=== ISSUE 3: Multiple paragraphs concatenated inline (§ stuck to preceding text) ===")
count = 0
for i, line in enumerate(lines, 1):
    # Look for cases where a § is preceded by text without a linebreak
    if re.search(r'[a-zA-ZÀ-ÿ.)\]]\s+\*\*§\s*\d+', line):
        count += 1
        if count <= 10:
            # Show context
            pos = re.search(r'\*\*§\s*\d+', line).start()
            print(f"  L{i}: ...{line[max(0,pos-50):pos+30]}")
print(f"  Total inline § concatenations: {count}")

print("\n=== ISSUE 4: Art. not bolded (missing **Art.**) ===")
count = 0
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if re.match(r'^Art\.\s+\d+', stripped) and not stripped.startswith('**'):
        count += 1
        if count <= 5:
            print(f"  L{i}: {stripped[:100]}")
print(f"  Total un-bolded articles: {count}")

print("\n=== ISSUE 5: Headings with DISPOSIÇÃO/DISPOSIÇÕES that are NOT heading-marked ===")
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if not stripped.startswith('#') and re.match(r'^\*\*(?:DISPOSI|Das\s|Dos\s|Do\s|Da\s)', stripped):
        print(f"  L{i}: {stripped[:100]}")

print("\n=== ISSUE 6: Lines starting with 'DISPOSIÇ' not as headings ===")
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    clean = re.sub(r'^[\*_]+|[\*_]+$', '', stripped).strip()
    if re.match(r'^DISPOSI[ÇC]', clean, re.I) and not stripped.startswith('#'):
        print(f"  L{i}: {stripped[:100]}")
        
print("\n=== Summary of heading levels ===")
levels = {}
for line in lines:
    if line.startswith('#'):
        level = len(line.split(' ')[0])
        levels[level] = levels.get(level, 0) + 1
for level in sorted(levels):
    print(f"  H{level} ({'#'*level}): {levels[level]} occurrences")

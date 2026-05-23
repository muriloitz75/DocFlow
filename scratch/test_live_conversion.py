# -*- coding: utf-8 -*-
"""Test the live conversion pipeline to see actual output quality."""
import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

import app as webapp

webapp.app.config["TESTING"] = True
client = webapp.app.test_client()

# Simulate URL conversion using the mock approach - fetch real page
import requests
import re
import tempfile

url = "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("Downloading page...")
response = requests.get(url, headers=headers, timeout=15)
response.raise_for_status()

# Replicate exact server logic
html_str = response.content.decode("cp1252", errors="replace")
if "<head>" in html_str.lower():
    html_str = re.sub(r'(<head\b[^>]*>)', r'\1<meta charset="utf-8">', html_str, flags=re.I)
else:
    html_str = '<meta charset="utf-8">' + html_str

# Save to temp
from markitdown import MarkItDown
temp_path = os.path.join(BASE_DIR, "scratch", "temp_live_test.html")
with open(temp_path, "w", encoding="utf-8") as f:
    f.write(html_str)

print("Converting with MarkItDown...")
md_converter = MarkItDown(enable_plugins=False)
result = md_converter.convert(temp_path)
content = result.text_content

print(f"\n=== RAW MARKITDOWN OUTPUT (first 2000 chars) ===")
print(content)
print(f"\n=== END RAW ===\n")

# Apply planalto pipeline
is_planalto = "presid" in content.lower() and ("casa civil" in content.lower() or "subchefia" in content.lower())
print(f"is_planalto detected: {is_planalto}")

if is_planalto:
    content = webapp.clean_planalto_encoding_glitches(content)
    content = webapp.strip_relative_and_internal_links(content)
    header_text, body_text = webapp.split_planalto_document(content)
    premium_header = webapp.generate_premium_header(header_text)
    body_text = webapp.clean_pdf_headers_footers(body_text)
    formatted_body = webapp.format_pdf_markdown_model2(body_text)
    content = premium_header + "\n\n" + formatted_body

# Save live output
output_path = os.path.join(BASE_DIR, "scratch", "live_output.md")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n=== FORMATTED OUTPUT (first 3000 chars) ===")
print(content[:3000])
print(f"\n=== END FORMATTED ===\n")

# Count headings
heading_count = 0
for line in content.splitlines():
    if line.startswith("#"):
        heading_count += 1
        
print(f"Total heading lines (starting with #): {heading_count}")

# Count bold-only structural elements (should be 0 for good output)
bold_structural = 0
for line in content.splitlines():
    stripped = line.strip()
    if re.match(r'^\*\*(?:LIVRO|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O|DISPOSI[ÇC][ÃA]O)\b', stripped, re.I):
        bold_structural += 1
        print(f"  BOLD-ONLY structural: {stripped[:80]}")

print(f"Bold-only structural elements (missing heading markers): {bold_structural}")

# Cleanup
if os.path.exists(temp_path):
    os.remove(temp_path)

print("\nDone!")

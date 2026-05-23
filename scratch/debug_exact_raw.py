# -*- coding: utf-8 -*-
"""Get the EXACT raw MarkItDown text for Art. 38 area to test splitting."""
import os
import sys
import re
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

from markitdown import MarkItDown
import app as webapp

url = "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers, timeout=15)
html_str = response.content.decode("cp1252", errors="replace")
if "<head>" in html_str.lower():
    html_str = re.sub(r'(<head\b[^>]*>)', r'\1<meta charset="utf-8">', html_str, flags=re.I)
else:
    html_str = '<meta charset="utf-8">' + html_str

temp_path = os.path.join(BASE_DIR, "scratch", "temp_debug.html")
with open(temp_path, "w", encoding="utf-8") as f:
    f.write(html_str)

md_converter = MarkItDown(enable_plugins=False)
result = md_converter.convert(temp_path)
content = result.text_content

# Clean and strip as the planalto path does
content = webapp.clean_planalto_encoding_glitches(content)
content = webapp.strip_relative_and_internal_links(content)
_, body_text = webapp.split_planalto_document(content)
body_text = webapp.clean_pdf_headers_footers(body_text)

# Find the Art. 38 section
lines = body_text.splitlines()
start = None
end = None
for i, line in enumerate(lines):
    if 'Art. 38' in line and 'base de cálculo' in line.lower():
        start = max(0, i - 2)
    if start and 'Art. 40' in line:
        end = i + 2
        break

if start and end:
    section = '\n'.join(lines[start:end])
    print("=== RAW BODY TEXT for Art. 38 section ===")
    for i, line in enumerate(section.splitlines(), start+1):
        print(f"  {i}: {repr(line[:130])}")
    
    print("\n=== AFTER split_inline_legal_elements ===")
    split = webapp.split_inline_legal_elements(section)
    for i, line in enumerate(split.splitlines(), 1):
        if line.strip():
            print(f"  {i}: {repr(line[:130])}")
    
    print("\n=== AFTER format_pdf_markdown_model2 ===")
    formatted = webapp.format_pdf_markdown_model2(section)
    for i, line in enumerate(formatted.splitlines(), 1):
        if line.strip():
            print(f"  {i}: {line[:140]}")
else:
    print("Art. 38 section not found!")

os.remove(temp_path)

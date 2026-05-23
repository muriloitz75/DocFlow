# -*- coding: utf-8 -*-
"""Find Art. 38 in the actual body text."""
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

temp_path = os.path.join(BASE_DIR, "scratch", "temp_debug2.html")
with open(temp_path, "w", encoding="utf-8") as f:
    f.write(html_str)

md_converter = MarkItDown(enable_plugins=False)
result = md_converter.convert(temp_path)
content = result.text_content

content = webapp.clean_planalto_encoding_glitches(content)
content = webapp.strip_relative_and_internal_links(content)
_, body_text = webapp.split_planalto_document(content)
body_text = webapp.clean_pdf_headers_footers(body_text)

# Search more broadly
lines = body_text.splitlines()
for i, line in enumerate(lines):
    if 'Art.' in line and '38' in line:
        print(f"Found at line {i}: {repr(line[:120])}")

# Also find by §1 with "valor venal"
for i, line in enumerate(lines):
    if 'valor venal' in line.lower():
        start = max(0, i - 3)
        end = min(len(lines), i + 20)
        print(f"\n=== Context around 'valor venal' at line {i} ===")
        for j in range(start, end):
            print(f"  {j}: {repr(lines[j][:130])}")
        break

os.remove(temp_path)

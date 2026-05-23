import os
import sys
import requests
import re

# Add markitdown to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))
sys.path.insert(0, BASE_DIR)

from markitdown import MarkItDown
import app as webapp

url = "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
print("Downloading Planalto page...")
response = requests.get(url, headers=headers, timeout=15)
response.raise_for_status()

# Decode as cp1252
html_str = response.content.decode("cp1252", errors="replace")

# Inject meta utf-8
if "<head>" in html_str.lower():
    html_str = re.sub(r'(<head\b[^>]*>)', r'\1<meta charset="utf-8">', html_str, flags=re.I)
else:
    html_str = '<meta charset="utf-8">' + html_str

# Save to temp htm file
temp_path = os.path.join(BASE_DIR, "scratch", "temp_l5172.html")
os.makedirs(os.path.dirname(temp_path), exist_ok=True)
with open(temp_path, "w", encoding="utf-8") as f:
    f.write(html_str)

print("Converting HTML to Markdown using MarkItDown...")
md_converter = MarkItDown(enable_plugins=False)
result = md_converter.convert(temp_path)
content = result.text_content

print("Applying premium legal styling and cleaning pipeline...")
# Clean, format, and reconstruct
content = webapp.clean_planalto_encoding_glitches(content)
content = webapp.strip_relative_and_internal_links(content)
header_text, body_text = webapp.split_planalto_document(content)
premium_header = webapp.generate_premium_header(header_text)
body_text = webapp.clean_pdf_headers_footers(body_text)
formatted_body = webapp.format_pdf_markdown_model2(body_text)
content = premium_header + "\n\n" + formatted_body

# Clean up temp file
if os.path.exists(temp_path):
    os.remove(temp_path)

# Save to output path
output_path = os.path.join(BASE_DIR, "teste", "l5172compilado.md")
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Regeneration completed successfully! Saved to:", output_path)

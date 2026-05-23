import os
import sys
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))

from markitdown import MarkItDown

url = "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
print("Downloading...")
response = requests.get(url, headers=headers, timeout=15)
html_str = response.content.decode("cp1252", errors="replace")

temp_path = os.path.join(BASE_DIR, "scratch", "raw_temp.html")
with open(temp_path, "w", encoding="utf-8") as f:
    f.write(html_str)

md_converter = MarkItDown(enable_plugins=False)
result = md_converter.convert(temp_path)
raw_md = result.text_content

# Save first 10000 characters of raw md to a scratch file
output_path = os.path.join(BASE_DIR, "scratch", "raw_output_prefix.txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(raw_md[:20000])

if os.path.exists(temp_path):
    os.remove(temp_path)

print("Done! Saved to:", output_path)

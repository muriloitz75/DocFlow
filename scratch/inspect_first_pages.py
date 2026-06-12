# -*- coding: utf-8 -*-
import pdfplumber
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://diariooficial.imperatriz.ma.gov.br/upload/diario_oficial/49A1CC9DC3825ED239661C18FAA60F9D3B23AD490.pdf"
pdf_path = "scratch/temp_inspect.pdf"

print("Baixando...")
response = requests.get(url, headers={"User-Agent": "Mozilla"}, verify=False)
with open(pdf_path, "wb") as f:
    f.write(response.content)

print("Analisando páginas...")
with pdfplumber.open(pdf_path) as pdf:
    for i in range(min(5, len(pdf.pages))):
        print(f"\n--- PÁGINA {i+1} ---")
        text = pdf.pages[i].extract_text() or ""
        print(text[:800])
        print("--------------------")

import os
if os.path.exists(pdf_path):
    os.remove(pdf_path)

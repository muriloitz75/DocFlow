import requests
import pdfplumber
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app as webapp

def main():
    url = "https://diariooficial.imperatriz.ma.gov.br/upload/diario_oficial/5B7EE2EABE7C52293F4591DC7A985C88A26FD8AD0.pdf"
    pdf_path = "scratch/debug_gazette_slice.pdf"
    
    if not os.path.exists(pdf_path):
        print("Downloading PDF...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(response.content)
        print("Downloaded.")
        
    print("Extracting pages 3-5...")
    with pdfplumber.open(pdf_path) as pdf:
        for p in [3, 4, 5]: # pages are 1-indexed (page 3, 4, 5 are indices 2, 3, 4)
            print(f"\n--- PAGE {p} ---")
            text = webapp.extract_text_with_layout_and_columns(pdf.pages[p-1])
            print(text[:2000] if text else "[empty]")
            print(f"--- END PAGE {p} ---")

if __name__ == "__main__":
    main()

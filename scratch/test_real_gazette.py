# -*- coding: utf-8 -*-
import sys
import os
import requests
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as webapp
from markitdown.converters._pdf_converter import extract_text_with_layout_and_columns

def is_index_page(text):
    dots_pattern = re.compile(r"\.\.\.+\s*\d+\s*$")
    matches = dots_pattern.findall(text)
    if len(matches) >= 2:
        return True
    if re.search(r"^\s*(Índice|Sumário|Sumario)\b", text, re.IGNORECASE | re.MULTILINE):
        return True
    return False

def scan_gazette_index_v3(pdf_path):
    import pdfplumber
    
    norms = []
    total_pages = 0
    seen_norms = set() # Para de-duplicar
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages):
            page_num = page_idx + 1
            
            text = extract_text_with_layout_and_columns(page) or ""
            
            if is_index_page(text):
                print(f"Página {page_num} identificada como índice. Pulando...")
                continue
                
            for match in webapp.GAZETTE_NORM_RE.finditer(text):
                tipo = match.group(1).strip().upper()
                numero = match.group(2).strip()
                
                # Chave única para de-duplicar na mesma página ou no diário
                norm_key = (tipo, numero)
                if norm_key in seen_norms:
                    continue
                seen_norms.add(norm_key)
                
                # Extrair ementa
                start_pos = match.end()
                rest_of_text = text[start_pos:].strip()
                rest_of_text = re.sub(r'\s+', ' ', rest_of_text)
                
                ementa = rest_of_text[:150]
                if len(rest_of_text) > 150:
                    ementa += "..."
                    
                norms.append({
                    "id": len(norms),
                    "tipo": tipo,
                    "numero": numero,
                    "ementa": ementa,
                    "start_page": page_num,
                    "end_page": page_num
                })
                
    # Ajustar end_page
    for i in range(len(norms)):
        if i < len(norms) - 1:
            norms[i]["end_page"] = norms[i+1]["start_page"]
        else:
            norms[i]["end_page"] = total_pages
            
    return {
        "total_pages": total_pages,
        "norms": norms
    }

def main():
    url = "https://diariooficial.imperatriz.ma.gov.br/upload/diario_oficial/49A1CC9DC3825ED239661C18FAA60F9D3B23AD490.pdf"
    pdf_path = "scratch/real_gazette.pdf"
    
    print("Baixando PDF real...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(url, headers=headers, timeout=30, verify=False)
    response.raise_for_status()
    
    with open(pdf_path, "wb") as f:
        f.write(response.content)
    print("PDF baixado com sucesso.")
    
    print("\nEscanenando índice com V3...")
    result = scan_gazette_index_v3(pdf_path)
    print(f"Total de páginas: {result['total_pages']}")
    print(f"Total de normas encontradas: {len(result['norms'])}")
    
    # Exibir as primeiras 15 normas para conferir
    for norm in result["norms"][:15]:
        print(f"- [{norm['id']}] {norm['tipo']} Nº {norm['numero']} (Págs. {norm['start_page']}-{norm['end_page']})")
        print(f"  Ementa: {norm['ementa']}")
        
    if result["norms"]:
        print("\nTestando fatiamento da primeira norma com V3...")
        first_norm = result["norms"][0]
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        
        for p in range(first_norm["start_page"] - 1, min(first_norm["end_page"], len(reader.pages))):
            writer.add_page(reader.pages[p])
            
        temp_pdf = "scratch/temp_extracted.pdf"
        with open(temp_pdf, "wb") as f:
            writer.write(f)
            
        print("Convertendo PDF fatiado usando extract_text_with_layout_and_columns diretamente...")
        import pdfplumber
        content_parts = []
        with pdfplumber.open(temp_pdf) as pdf:
            for page in pdf.pages:
                content_parts.append(extract_text_with_layout_and_columns(page))
        content = "\n\n".join(content_parts)
        
        content = webapp.clean_pdf_headers_footers(content)
        content = webapp.format_pdf_markdown_model2(content)
        
        # Testar nova regex de busca de título
        curr_pat = r"(?m)^\s*(?:#+\s*|\*\*|___)?\s*" + r"\s+".join(re.escape(w) for w in first_norm["tipo"].split()) + r"\s+(?:Nº|N[°ºo]\.?)\s*" + re.escape(first_norm["numero"])
        next_pat = None
        if len(result["norms"]) > 1:
            next_norm = result["norms"][1]
            next_pat = r"(?m)^\s*(?:#+\s*|\*\*|___)?\s*" + r"\s+".join(re.escape(w) for w in next_norm["tipo"].split()) + r"\s+(?:Nº|N[°ºo]\.?)\s*" + re.escape(next_norm["numero"])
            
        sliced_content = webapp.slice_norm_markdown(content, curr_pat, next_pat)
        
        print("\n--- INÍCIO DO MARKDOWN FATIADO ---")
        print(sliced_content[:1500])
        print("--- FIM DO PREVIEW ---")
        
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
            
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

if __name__ == "__main__":
    main()

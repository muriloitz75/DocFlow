import sys
import os
import requests
import pdfplumber

def main():
    url = "https://diariooficial.imperatriz.ma.gov.br/upload/diario_oficial/49A1CC9DC3825ED239661C18FAA60F9D3B23AD490.pdf"
    pdf_path = "scratch/debug_gazette.pdf"
    
    if not os.path.exists(pdf_path):
        print("Baixando PDF...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(response.content)
            
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[2] # Página 3
        print(f"Page width: {page.width}, height: {page.height}")
        
        # Analisar linhas verticais
        lines = page.lines
        print(f"Linhas verticais: {len([l for l in lines if l['x0'] == l['x1']])}")
        for l in lines:
            if abs(l['x0'] - l['x1']) < 1: # Vertical
                print(f"Linha vertical em x={l['x0']}, y0={l['top']}, y1={l['bottom']}")
                
        # Analisar palavras no meio
        words = page.extract_words()
        mid_start = page.width * 0.40
        mid_end = page.width * 0.60
        middle_words = [w for w in words if w["top"] > page.height * 0.08 and w["bottom"] < page.height * 0.92]
        
        spans = sorted([(w["x0"], w["x1"]) for w in middle_words])
        union_intervals = []
        for s in spans:
            if not union_intervals:
                union_intervals.append(s)
            else:
                prev_s = union_intervals[-1]
                if s[0] <= prev_s[1]:
                    union_intervals[-1] = (prev_s[0], max(prev_s[1], s[1]))
                else:
                    union_intervals.append(s)
                    
        print(f"Intervalos unificados na horizontal:")
        for ui in union_intervals:
            if ui[1] > mid_start and ui[0] < mid_end:
                print(f"  Overlap com o meio: {ui}")
                
        # Listar gaps
        gaps = []
        for idx in range(len(union_intervals) - 1):
            gap_start = union_intervals[idx][1]
            gap_end = union_intervals[idx + 1][0]
            if gap_start < mid_end and gap_end > mid_start:
                overlap_start = max(gap_start, mid_start)
                overlap_end = min(gap_end, mid_end)
                gaps.append((overlap_start, overlap_end, overlap_end - overlap_start))
        print("Gaps encontrados no meio:")
        for g in gaps:
            print(f"  Gap: {g[0]:.2f} a {g[1]:.2f} (largura: {g[2]:.2f})")

if __name__ == "__main__":
    main()

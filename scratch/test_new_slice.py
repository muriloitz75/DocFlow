import sys
import os
import re
import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app as webapp

def new_slice_norm_markdown(markdown, norm_title_pattern, next_norm_title_pattern=None):
    """Novo fatiamento com detecção de Código Identificador."""
    match_start = re.search(norm_title_pattern, markdown, re.IGNORECASE | re.MULTILINE)
    if not match_start:
        return None
        
    start_pos = match_start.start()
    
    # 1. Tentar encontrar o Código Identificador que encerra a publicação
    match_code = re.search(
        r'(?:C[óo]d\.?\s*Identificador|C[óo]digo\s+[iI]dentificador)\s*:\s*([A-Za-z0-9$]+)',
        markdown[match_start.end():],
        re.IGNORECASE
    )
    
    end_pos = None
    if match_code:
        end_pos = match_start.end() + match_code.end()
        
    # 2. Se houver padrão da próxima norma, usar a menor posição entre o Código e o início da próxima norma
    if next_norm_title_pattern:
        match_end = re.search(next_norm_title_pattern, markdown[match_start.end():], re.IGNORECASE | re.MULTILINE)
        if match_end:
            next_norm_pos = match_start.end() + match_end.start()
            if end_pos is None or next_norm_pos < end_pos:
                end_pos = next_norm_pos
                
    if end_pos is not None:
        return markdown[start_pos:end_pos].strip()
        
    return markdown[start_pos:].strip()

def main():
    pdf_path = "scratch/debug_gazette_slice.pdf"
    
    if not os.path.exists(pdf_path):
        print("Error: debug_gazette_slice.pdf not found. Run debug_slice.py first.")
        sys.exit(1)
        
    print("Extracting pages 3-5...")
    content_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in [3, 4, 5]:
            text = webapp.extract_text_with_layout_and_columns(pdf.pages[p-1]) or ""
            content_parts.append(text.strip())
    content = "\n\n".join(content_parts)
    
    # Limpeza padrão do backend
    content = webapp.clean_pdf_headers_footers(content)
    content = webapp.format_pdf_markdown_model2(content)
    
    # Patterns para PORTARIA 5.777 (atual) e PORTARIA 51 (próxima)
    curr_pat = webapp.get_norm_title_pattern("PORTARIA", "5.777")
    next_pat = webapp.get_norm_title_pattern("PORTARIA", "51")
    
    print("\n--- TESTANDO FATIAMENTO ANTIGO ---")
    old_sliced = webapp.slice_norm_markdown(content, curr_pat, next_pat)
    if old_sliced:
        print(f"Comprimento: {len(old_sliced)} caracteres")
        print("Últimos 300 caracteres:")
        print(old_sliced[-300:])
    else:
        print("Não localizado.")
        
    print("\n--- TESTANDO NOVO FATIAMENTO ---")
    new_sliced = new_slice_norm_markdown(content, curr_pat, next_pat)
    if new_sliced:
        print(f"Comprimento: {len(new_sliced)} caracteres")
        print("Últimos 300 caracteres:")
        print(new_sliced[-300:])
    else:
        print("Não localizado.")

if __name__ == "__main__":
    main()

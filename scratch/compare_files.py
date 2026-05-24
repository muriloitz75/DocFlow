# -*- coding: utf-8 -*-
import os
import sys
import pdfplumber
import re

# Add local packages to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "packages", "markitdown", "src"))
from markitdown import MarkItDown

def analyze_conversion():
    pdf_path = r"c:\Users\muril\Desktop\Projetos\DocFlow\teste\CODIGO TRIBUTARIO MUNICIPAL LEI 5.2022.pdf"
    old_md_path = r"c:\Users\muril\Desktop\Projetos\DocFlow\teste\CODIGO TRIBUTARIO MUNICIPAL LEI 5.2022.md"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    print("Opening PDF...")
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        print(f"Total pages in PDF: {num_pages}")
        
        # Check first page dimensions
        first_page = pdf.pages[0]
        print(f"Page 1 size: {first_page.width}x{first_page.height}")
        
    print("\nConverting PDF using upgraded engine (this might take a moment since it has many pages)...")
    md_converter = MarkItDown(enable_plugins=False)
    result = md_converter.convert(pdf_path)
    new_md_content = result.text_content
    print(f"Converted successfully! New MD size: {len(new_md_content)} chars.")
    
    # Run the Flask app's post-processing clean_pdf_headers_footers
    sys.path.insert(0, PROJECT_ROOT)
    import app as webapp
    new_md_content = webapp.clean_pdf_headers_footers(new_md_content)
    print(f"Post-processed new MD size: {len(new_md_content)} chars.")
    
    # Read old MD
    if os.path.exists(old_md_path):
        with open(old_md_path, "r", encoding="utf-8", errors="ignore") as f:
            old_md_content = f.read()
        print(f"Old MD size: {len(old_md_content)} chars.")
        
        # Extract top 8% to see headers in PDF
        headers_found = []
        with pdfplumber.open(pdf_path) as pdf:
            # Check a few pages for header noise
            for page in pdf.pages[:10]:
                top_crop = page.crop((0, 0, page.width, page.height * 0.08))
                text = top_crop.extract_text()
                if text and text.strip():
                    headers_found.append(text.strip().replace("\n", " "))
        
        print("\n=== Detected headers in first 10 pages of PDF ===")
        for idx, h in enumerate(headers_found[:5]):
            print(f"Page {idx+1}: {h}")
            
        print("\n=== Header Occurrences Analysis ===")
        for h in set(headers_found):
            cleaned_h = h.strip()
            if len(cleaned_h) > 8:
                # Use a smaller snippet to avoid minor extraction differences
                snippet = cleaned_h[:20]
                old_count = len(re.findall(re.escape(snippet), old_md_content))
                new_count = len(re.findall(re.escape(snippet), new_md_content))
                print(f"Header snippet '{snippet}...':")
                print(f"  - Count in old MD: {old_count}")
                print(f"  - Count in new MD: {new_count}")

        # Check for column layout detection
        columns_pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for idx, page in enumerate(pdf.pages):
                width = page.width
                mid_start = width * 0.40
                mid_end = width * 0.60
                words = page.extract_words()
                spans = sorted([(w["x0"], w["x1"]) for w in words])
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
                gaps = []
                for g_idx in range(len(union_intervals) - 1):
                    gap_start = union_intervals[g_idx][1]
                    gap_end = union_intervals[g_idx + 1][0]
                    if gap_start < mid_end and gap_end > mid_start:
                        overlap_start = max(gap_start, mid_start)
                        overlap_end = min(gap_end, mid_end)
                        if overlap_end - overlap_start > 15:
                            gaps.append((overlap_start, overlap_end))
                if gaps:
                    columns_pages.append(idx + 1)
        print(f"\nTwo-column layouts detected on pages (1-based index): {columns_pages}")
        
        # Check if there are any hyphens merged
        # We can look for common hyphenated Portuguese words in the PDF compared to the converted text
        hyphen_checks = ["constitu-", "tribu-", "muni-", "decreto-"]
        print("\n=== Hyphenation check in new MD ===")
        for hc in hyphen_checks:
            hc_clean = hc.replace("-", "")
            count_hyphen = len(re.findall(re.escape(hc), new_md_content))
            count_merged = len(re.findall(re.escape(hc_clean), new_md_content))
            print(f"'{hc}' count: {count_hyphen} | '{hc_clean}' count: {count_merged}")

        # Check some sample lines of the old MD compared to the new MD
        print("\n=== Sample comparison of old vs new MD ===")
        print("Old MD snippet:")
        print("\n".join(old_md_content.splitlines()[:10]))
        print("\nNew MD snippet:")
        print("\n".join(new_md_content.splitlines()[:10]))
        
    else:
        print(f"Old MD file not found at {old_md_path}")

if __name__ == "__main__":
    analyze_conversion()

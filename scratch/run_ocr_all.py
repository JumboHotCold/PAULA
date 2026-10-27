"""Run RapidOCR on all 16 rendered pages and save raw text outputs."""
import os
import re
from rapidocr_onnxruntime import RapidOCR

BASE = r"c:\Users\ADMIN\OneDrive\DEX CAPSTONE 2026\paulibot"
SCRATCH = os.path.join(BASE, "scratch")
OUT_DIR = os.path.join(BASE, "knowledge_base", "office_documents", "extracted")
os.makedirs(OUT_DIR, exist_ok=True)

engine = RapidOCR()

docs = {
    "PBMO_FAQs": {
        "office": "PBMO",
        "title": "PBMO Frequently Asked Questions",
        "pages": ["PBMO_FAQs_p0.png", "PBMO_FAQs_p1.png", "PBMO_FAQs_p2.png"]
    },
    "PBMO_PROCEDURES": {
        "office": "PBMO",
        "title": "PBMO Online Posting and Media Procedures",
        "pages": ["PBMO_PROCEDURES_p0.png", "PBMO_PROCEDURES_p1.png"]
    },
    "PBMO_SPUS_BRANDING": {
        "office": "PBMO",
        "title": "PBMO SPUS University Branding and Identity Guide",
        "pages": [f"PBMO_SPUS_BRANDING_p{i}.png" for i in range(7)]
    },
    "REGISTRAR_ENROLLMENT_PROCEDURES": {
        "office": "Registrar",
        "title": "Registrar Enrollment, Adding, Dropping, and Changing of Subjects Procedures",
        "pages": [f"REGISTRAR_ENROLLMENT_PROCEDURES_p{i}.png" for i in range(4)]
    }
}

for doc_key, doc_info in docs.items():
    print(f"\n{'='*60}")
    print(f"PROCESSING: {doc_info['title']} ({len(doc_info['pages'])} pages)")
    print(f"{'='*60}")
    
    doc_lines = []
    for p_idx, page_file in enumerate(doc_info["pages"]):
        img_path = os.path.join(SCRATCH, page_file)
        if not os.path.exists(img_path):
            print(f"  Missing image: {img_path}")
            continue
            
        result, elapse = engine(img_path)
        page_boxes = len(result) if result else 0
        print(f"  Page {p_idx + 1} ({page_file}): {page_boxes} text boxes detected in {sum(elapse):.2f}s")
        
        doc_lines.append(f"--- PAGE {p_idx + 1} ---")
        if result:
            # Sort boxes primarily top-to-bottom (y), secondarily left-to-right (x)
            # result item: [ [ [x1,y1],[x2,y2],[x3,y3],[x4,y4] ], text, score ]
            # sort by y_min roughly rounded to line buckets (e.g. 20px) to maintain left-to-right reading order
            sorted_boxes = sorted(result, key=lambda b: (round(b[0][0][1] / 25), b[0][0][0]))
            for b in sorted_boxes:
                text = b[1].strip()
                score = b[2]
                if text:
                    doc_lines.append(text)
        doc_lines.append("")

    full_text = "\n".join(doc_lines)
    txt_out = os.path.join(OUT_DIR, f"{doc_key}_raw.txt")
    with open(txt_out, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"  Saved raw text to: {txt_out} ({len(full_text)} chars)")

print("\nALL OCR EXTRACTION COMPLETE!")

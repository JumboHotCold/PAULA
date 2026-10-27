"""
Management command to ingest office-submitted FAQs and procedures into PauliBot's Knowledge Base.

Supports softcopies submitted by university offices (Registrar, Finance, CEIT, CHS, etc.)
in .docx (Word), .pdf, .txt, .json, and .csv formats.

Entries are tagged with source_type='office' and source_office=<office_name>, giving them
Tier 1 priority (highest authority) in PauliBot's RAG search pipeline.

Usage examples:
    python manage.py ingest_office_faqs --file registrar_faqs.docx --office Registrar
    python manage.py ingest_office_faqs --file finance_procedures.pdf --office Finance
    python manage.py ingest_office_faqs --file ceit_curriculum.txt --office CEIT --category "Academics"
    python manage.py ingest_office_faqs --file registrar_faqs.docx --office Registrar --clear-existing
"""
import os
import re
import csv
import json
import logging
from django.core.management.base import BaseCommand
from chatbot.models import FAQ

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ingest office-submitted FAQs and procedures into PauliBot Knowledge Base (Tier 1 Priority)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to the document file (.docx, .pdf, .txt, .json, .csv)'
        )
        parser.add_argument(
            '--office',
            type=str,
            required=True,
            help="Name of the office or department (e.g. 'Registrar', 'Finance', 'CEIT', 'CHS', 'Guidance')"
        )
        parser.add_argument(
            '--category',
            type=str,
            default=None,
            help="Category name (default: '<Office> Office')"
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=800,
            help='Target chunk size in characters for unstructured text (default: 800)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Delete existing FAQs from this office before ingesting new entries'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Extract and display entries without saving to the database'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        office = options['office'].strip()
        category = options['category'] or f"{office} Office"
        chunk_size = options['chunk_size']
        clear_existing = options['clear_existing']
        dry_run = options['dry_run']

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        ext = os.path.splitext(file_path)[1].lower()
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"INGESTING OFFICE DOCUMENT: {office}")
        self.stdout.write(f"  File:     {file_path} ({ext})")
        self.stdout.write(f"  Office:   {office}")
        self.stdout.write(f"  Category: {category}")
        self.stdout.write(f"  Priority: Tier 1 (Office-Submitted)")
        self.stdout.write(f"{'='*60}\n")

        # Extract items (list of dicts with 'question' and 'answer')
        try:
            if ext == '.json':
                items = self._parse_json(file_path, office)
            elif ext == '.csv':
                items = self._parse_csv(file_path, office)
            elif ext == '.docx':
                raw_text = self._read_docx(file_path)
                items = self._parse_text(raw_text, office, chunk_size)
            elif ext == '.pdf':
                raw_text = self._read_pdf(file_path)
                items = self._parse_text(raw_text, office, chunk_size)
            elif ext in ('.txt', '.md'):
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    raw_text = f.read()
                items = self._parse_text(raw_text, office, chunk_size)
            else:
                self.stderr.write(self.style.ERROR(f"Unsupported file format: {ext}"))
                return
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error reading file {file_path}: {e}"))
            return

        if not items:
            self.stderr.write(self.style.WARNING("No Q&A or procedure entries could be parsed from the document."))
            return

        self.stdout.write(f"Extracted {len(items)} items from document.\n")

        if clear_existing and not dry_run:
            deleted_count, _ = FAQ.objects.filter(source_office=office).delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing FAQ entries for office: {office}"))

        saved_count = 0
        for idx, item in enumerate(items, 1):
            q = item['question'].strip()
            a = item['answer'].strip()

            if not q or not a:
                continue

            if dry_run:
                self.stdout.write(f"[{idx}] [DRY-RUN] {q}")
                preview = a[:120].replace('\n', ' ')
                self.stdout.write(f"    Preview: {preview}...\n")
                saved_count += 1
            else:
                faq, created = FAQ.objects.update_or_create(
                    question=q,
                    defaults={
                        'category': category,
                        'answer': a,
                        'source_type': 'office',
                        'source_office': office
                    }
                )
                action = "CREATED" if created else "UPDATED"
                self.stdout.write(f"[{idx}] [{action}] {q}")
                saved_count += 1

        if not dry_run and saved_count > 0:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write("Generating vector embeddings for newly ingested entries...")
            try:
                from chatbot.rag import RAGSearcher
                rag = RAGSearcher()
                rag.ensure_embeddings()
                self.stdout.write(self.style.SUCCESS("Vector embeddings updated successfully!"))
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"Embeddings generation deferred: {e}"))

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(
            f"Successfully processed {saved_count} entries for {office} (Tier 1 Priority)."
        ))
        self.stdout.write(f"{'='*60}\n")

    # ── Document Readers ──

    def _read_docx(self, path):
        import docx
        doc = docx.Document(path)
        parts = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                parts.append(txt)
        for table in doc.tables:
            for row in table.rows:
                row_txt = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_txt:
                    parts.append(" | ".join(row_txt))
        return "\n\n".join(parts)

    def _read_pdf(self, path):
        import fitz
        doc = fitz.open(path)
        parts = []
        for page in doc:
            txt = page.get_text()
            if txt.strip():
                parts.append(txt.strip())

        combined = "\n\n".join(parts)
        # If PDF is scanned or image-based (no digital text), fall back to RapidOCR
        if len(combined.strip()) < 50:
            self.stdout.write(self.style.WARNING("  PDF has no digital text. Running OCR extraction..."))
            try:
                from rapidocr_onnxruntime import RapidOCR
                engine = RapidOCR()
                ocr_parts = []
                for p_idx, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    result, _ = engine(img_bytes)
                    if result:
                        sorted_boxes = sorted(result, key=lambda b: (round(b[0][0][1] / 25), b[0][0][0]))
                        page_text = "\n".join(b[1].strip() for b in sorted_boxes if b[1].strip())
                        if page_text:
                            ocr_parts.append(page_text)
                doc.close()
                return "\n\n".join(ocr_parts)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"  OCR fallback failed: {e}"))

        doc.close()
        return combined

    def _parse_json(self, path, office):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get('faqs') or data.get('procedures') or data.get('items') or [data]
        items = []
        for entry in data:
            q = entry.get('question') or entry.get('title') or entry.get('topic')
            a = entry.get('answer') or entry.get('content') or entry.get('procedure') or entry.get('steps')
            if q and a:
                if isinstance(a, list):
                    a = "\n".join(f"{i+1}. {step}" if not step.startswith(tuple("0123456789-")) else step for i, step in enumerate(a))
                items.append({'question': f"[{office}] {q}", 'answer': str(a)})
        return items

    def _parse_csv(self, path, office):
        items = []
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                q = (row.get('question') or row.get('Question') or row.get('title') or row.get('Title') or '').strip()
                a = (row.get('answer') or row.get('Answer') or row.get('content') or row.get('Procedure') or '').strip()
                if q and a:
                    items.append({'question': f"[{office}] {q}", 'answer': a})
        return items

    # ── Text Parser (Q&A detection + structured chunks) ──

    def _parse_text(self, text, office, chunk_size):
        items = []

        # 1. Look for explicit Q&A patterns (Q: ... A: ... or Question: ... Answer: ...)
        qa_pattern = re.compile(
            r'(?:^|\n)(?:Q(?:uestion)?[\s\d\.\:]+)(.+?)\n(?:A(?:nswer)?[\s\d\.\:]+)(.+?)(?=\n(?:Q(?:uestion)?[\s\d\.\:]+)|\Z)',
            re.DOTALL | re.IGNORECASE
        )
        matches = qa_pattern.findall(text)
        if matches and len(matches) >= 2:
            for q, a in matches:
                q_clean = q.strip()
                a_clean = a.strip()
                if q_clean and a_clean:
                    items.append({
                        'question': f"[{office}] {q_clean}",
                        'answer': a_clean
                    })
            if items:
                return items

        # 2. Look for numbered procedure/section headers (e.g., "1. How to Request TOR", "STEP 1: ...", "### Section")
        section_pattern = re.compile(r'(?:^|\n)(#{1,3}\s+.+?|(?:\d+[\.\)]\s+[A-Z].+?)|(?:STEP\s+\d+[:\s].+?))\n', re.IGNORECASE)
        splits = section_pattern.split(text)
        if len(splits) > 3:
            curr_title = None
            for part in splits:
                part = part.strip()
                if not part:
                    continue
                if section_pattern.match('\n' + part + '\n') or (len(part) < 100 and ('\n' not in part) and any(part.startswith(p) for p in ['#', 'STEP', 'Step', 'Procedure', '1.', '2.', '3.', '4.', '5.'])):
                    curr_title = part.lstrip('#').strip()
                elif curr_title:
                    items.append({
                        'question': f"[{office}] {curr_title}",
                        'answer': part
                    })
                    curr_title = None
            if items:
                return items

        # 3. Fallback: Split into paragraph chunks with detected titles
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_chunk = ""
        chunk_idx = 1
        current_title = f"{office} Procedures"

        for p in paragraphs:
            # Check if this paragraph looks like a heading
            if len(p) < 90 and not p.endswith('.') and ('\n' not in p):
                if current_chunk:
                    items.append({
                        'question': f"[{office}] {current_title} (Part {chunk_idx})",
                        'answer': current_chunk
                    })
                    chunk_idx += 1
                    current_chunk = ""
                current_title = p
                continue

            if current_chunk and len(current_chunk) + len(p) + 2 > chunk_size:
                items.append({
                    'question': f"[{office}] {current_title} (Part {chunk_idx})",
                    'answer': current_chunk
                })
                chunk_idx += 1
                current_chunk = p
            else:
                if current_chunk:
                    current_chunk += "\n\n" + p
                else:
                    current_chunk = p

        if current_chunk:
            title_suffix = f" (Part {chunk_idx})" if chunk_idx > 1 else ""
            items.append({
                'question': f"[{office}] {current_title}{title_suffix}",
                'answer': current_chunk
            })

        return items

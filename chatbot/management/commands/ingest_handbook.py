"""
Management command to ingest Handbook.pdf into the Knowledge Base.

Since the PDF is a scanned document (CamScanner - images only, no text),
this uses Gemini Vision API to OCR each page, then stores the extracted
text as FAQ entries with vector embeddings for RAG search.

Windows Compatibility: Uses PIL Image objects sent directly to Gemini
instead of genai.upload_file() to avoid file-locking issues on Windows.
"""
import io
import os
import re
import time
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

import fitz  # PyMuPDF
from PIL import Image
import google.generativeai as genai

from chatbot.models import FAQ

logger = logging.getLogger(__name__)

# Gemini Vision prompt to extract text from a scanned handbook page
EXTRACTION_PROMPT = """You are reading a scanned page from the St. Paul University Surigao (SPUS) Student Handbook.

INSTRUCTIONS:
1. Extract ALL text from this scanned page image accurately.
2. The page may have a two-column layout (two book pages side by side). Read the LEFT column first completely, then the RIGHT column.
3. Preserve section headers and titles by putting them on their own line in UPPERCASE.
4. Preserve numbered lists, bullet points, and paragraph breaks.
5. Skip any watermarks, page numbers, or "Scanned with CamScanner" text.
6. If there is an image or logo with no text, write: [IMAGE: brief description]
7. Return ONLY the extracted text, nothing else. No commentary or explanation.
8. If the page is blank or contains only images with no readable text, return: [BLANK PAGE]"""


class Command(BaseCommand):
    help = 'Ingest Handbook.pdf into the Knowledge Base using Gemini Vision OCR'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pdf-path',
            type=str,
            default='Handbook.pdf',
            help='Path to the Handbook PDF file (default: Handbook.pdf in project root)'
        )
        parser.add_argument(
            '--start-page',
            type=int,
            default=1,
            help='Start processing from this page number (1-indexed, default: 1)'
        )
        parser.add_argument(
            '--end-page',
            type=int,
            default=None,
            help='Stop processing at this page number (inclusive, default: last page)'
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=900,
            help='Target chunk size in characters (default: 900)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.5,
            help='Delay in seconds between Gemini API calls (default: 1.5)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Extract text but do not save to database'
        )

    def handle(self, *args, **options):
        pdf_path = options['pdf_path']
        start_page = options['start_page']
        end_page = options['end_page']
        chunk_size = options['chunk_size']
        delay = options['delay']
        dry_run = options['dry_run']

        # Validate PDF exists
        if not os.path.exists(pdf_path):
            self.stderr.write(self.style.ERROR(f"PDF file not found: {pdf_path}"))
            return

        # Configure Gemini
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            self.stderr.write(self.style.ERROR(
                "GEMINI_API_KEY is not set in .env. Cannot perform OCR without it."
            ))
            return

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Open the PDF
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        self.stdout.write(f"Opened '{pdf_path}' — {total_pages} pages")

        if end_page is None:
            end_page = total_pages

        # Validate page range
        start_page = max(1, start_page)
        end_page = min(total_pages, end_page)

        self.stdout.write(f"Processing pages {start_page} to {end_page}...")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — will not save to database"))

        all_chunks = []
        failed_pages = []

        for page_num in range(start_page - 1, end_page):
            page_display = page_num + 1
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"  Processing page {page_display}/{end_page}...")

            try:
                # Step 1: Convert page to PIL Image in memory (no temp files!)
                page = doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_bytes))

                # Step 2: Send PIL Image directly to Gemini Vision for OCR
                self.stdout.write(f"  Sending to Gemini Vision...")
                response = model.generate_content([EXTRACTION_PROMPT, pil_image])
                extracted_text = response.text.strip()

                # Step 3: Skip blank pages
                if not extracted_text or extracted_text == "[BLANK PAGE]":
                    self.stdout.write(self.style.WARNING(f"  Page {page_display}: BLANK — skipped"))
                    time.sleep(delay)
                    continue

                # Step 4: Chunk the extracted text
                chunks = self._chunk_text(extracted_text, chunk_size, page_display)
                self.stdout.write(
                    f"  Page {page_display}: Extracted {len(extracted_text)} chars -> {len(chunks)} chunk(s)"
                )

                for chunk_info in chunks:
                    all_chunks.append(chunk_info)

                    if not dry_run:
                        # Step 5: Save to database with source_type='handbook'
                        obj, created = FAQ.objects.get_or_create(
                            category="Student Handbook",
                            question=chunk_info['question'],
                            defaults={
                                'answer': chunk_info['answer'],
                                'source_type': 'handbook',
                                'source_office': 'Student Affairs'
                            }
                        )
                        if not created and (obj.source_type != 'handbook' or not obj.source_office):
                            obj.source_type = 'handbook'
                            obj.source_office = 'Student Affairs'
                            obj.save(update_fields=['source_type', 'source_office'])
                        status = "CREATED" if created else "EXISTS"
                        self.stdout.write(f"    [{status}] {chunk_info['question']}")
                    else:
                        self.stdout.write(f"    [DRY] {chunk_info['question']}")
                        preview = chunk_info['answer'][:150].replace('\n', ' ')
                        self.stdout.write(f"           Preview: {preview}...")

                # Rate limit delay
                time.sleep(delay)

            except Exception as e:
                failed_pages.append(page_display)
                self.stderr.write(self.style.ERROR(
                    f"  Page {page_display}: FAILED — {str(e)}"
                ))
                # Still delay to avoid hammering the API after an error
                time.sleep(delay)
                continue

        doc.close()

        # Step 6: Generate embeddings for new entries
        if not dry_run and all_chunks:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write("Generating vector embeddings for new entries...")
            try:
                from chatbot.rag import RAGSearcher
                rag = RAGSearcher()
                rag.ensure_embeddings()
                self.stdout.write(self.style.SUCCESS("Embeddings generated successfully!"))
            except Exception as e:
                self.stderr.write(self.style.WARNING(
                    f"Could not generate embeddings (you can do this later): {e}"
                ))

        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"INGESTION COMPLETE")
        self.stdout.write(f"  Pages processed: {end_page - start_page + 1}")
        self.stdout.write(f"  Chunks created:  {len(all_chunks)}")
        self.stdout.write(f"  Failed pages:    {len(failed_pages)}")
        if failed_pages:
            self.stdout.write(f"  Failed page numbers: {failed_pages}")

        total_handbook = FAQ.objects.filter(category="Student Handbook").count()
        self.stdout.write(f"  Total handbook FAQs in DB: {total_handbook}")
        self.stdout.write(self.style.SUCCESS("\nDone! The handbook is now part of PauliBot's knowledge base."))

    def _chunk_text(self, text, target_size, page_num):
        """
        Split extracted text into meaningful chunks.

        Strategy:
        - Split by paragraphs (double newlines)
        - If chunks are still too large, they get split at paragraph boundaries
        - Each chunk gets a descriptive question/title based on the first line
        """
        chunks = []

        # Try to detect a page title from the first non-empty line
        lines = text.split('\n')
        page_title = None
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) > 3:
                # Use the first substantial line as the page title
                page_title = stripped[:80]
                break

        if not page_title:
            page_title = f"Page {page_num}"

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_chunk = ""
        chunk_idx = 1

        for para in paragraphs:
            # If adding this paragraph exceeds target, save current and start new
            if current_chunk and len(current_chunk) + len(para) + 2 > target_size:
                chunks.append({
                    'question': f"Handbook: {page_title} (Page {page_num}, Part {chunk_idx})",
                    'answer': current_chunk.strip()
                })
                chunk_idx += 1
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk.strip():
            if chunk_idx == 1:
                # Only one chunk for this page — no need for "Part X"
                question = f"Handbook: {page_title} (Page {page_num})"
            else:
                question = f"Handbook: {page_title} (Page {page_num}, Part {chunk_idx})"
            chunks.append({
                'question': question,
                'answer': current_chunk.strip()
            })

        return chunks

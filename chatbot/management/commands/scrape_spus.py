"""
Management command to scrape the official SPUS website (https://spus.edu.ph)
and ingest verified information into the WebResource Knowledge Base.

Pages are scraped, stripped of scripts/nav boilerplate, segmented into semantic chunks,
and saved with pgvector embeddings for RAG retrieval with verified source URLs.
"""
import re
import logging
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import requests

from django.core.management.base import BaseCommand
from chatbot.models import WebResource

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Core verified SPUS pages with high-value institutional knowledge
CORE_SPUS_PAGES = [
    {
        'title': 'College Admission Requirements',
        'url': 'https://spus.edu.ph/college-admission/',
        'category': 'Admissions',
    },
    {
        'title': 'Basic Education Admission Requirements',
        'url': 'https://spus.edu.ph/basic-education-admission/',
        'category': 'Admissions',
    },
    {
        'title': 'SPUS Contact Information and Office Hours',
        'url': 'https://spus.edu.ph/contact-us-2/',
        'category': 'Contact',
    },
    {
        'title': 'About SPUS & Paulinian Core Values',
        'url': 'https://spus.edu.ph/about-us-2/',
        'category': 'About',
    },
    {
        'title': 'TESDA Programs & TVET Assessment Center',
        'url': 'https://spus.edu.ph/tesda-program/',
        'category': 'TVET',
    },
    {
        'title': 'University Administration & Faculty',
        'url': 'https://spus.edu.ph/administrator/',
        'category': 'Administration',
    },
    {
        'title': 'SPUS Quality Policy',
        'url': 'https://spus.edu.ph/quality-policy/',
        'category': 'Academics',
    },
    {
        'title': 'Pillars and Formative Compasses',
        'url': 'https://spus.edu.ph/the-pillars-and-formative-compasses/',
        'category': 'About',
    },
    {
        'title': 'SPUS University Seal & Insignia',
        'url': 'https://spus.edu.ph/school-seal/',
        'category': 'About',
    },
    {
        'title': 'College Department Overview & Academic Programs',
        'url': 'https://spus.edu.ph/college-department/',
        'category': 'Academics',
    },
    {
        'title': 'College of Health Sciences - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-health-sciences/',
        'category': 'Academics',
    },
    {
        'title': 'College of Business Management and Accountancy - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-business-management-and-accountancy/',
        'category': 'Academics',
    },
    {
        'title': 'College of Education, Arts and Sciences - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-education-arts-and-sciences/',
        'category': 'Academics',
    },
    {
        'title': 'College of Engineering and Information Technology - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-engineering-and-information-technology/',
        'category': 'Academics',
    },
    {
        'title': 'College of Criminal Justice Education - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-criminal-justice-education/',
        'category': 'Academics',
    },
    {
        'title': 'Graduate School and Professional Studies (GSPS) Programs',
        'url': 'https://spus.edu.ph/graduate-school/',
        'category': 'Academics',
    },
    {
        'title': 'Basic Education Department (Grade School, JHS, SHS)',
        'url': 'https://spus.edu.ph/basic-education/',
        'category': 'Academics',
    },
    {
        'title': 'SPUS Online Services Portal',
        'url': 'https://spus.edu.ph/online-services/',
        'category': 'Services',
    },
    {
        'title': 'SPUS Research, Innovations & Publications',
        'url': 'https://spus.edu.ph/research/',
        'category': 'Research',
    },
    {
        'title': 'Office of the Vice President for Academic Services (OVPaCS)',
        'url': 'https://sites.google.com/spus.edu.ph/spusovpacs/home',
        'category': 'Academics',
    },
    {
        'title': 'SPUS Finance Services Portal & Payment Guidelines',
        'url': 'https://sites.google.com/spus.edu.ph/spusfinanceservices/home',
        'category': 'Finance',
    },
    {
        'title': 'St. Paul University Surigao Library Portal',
        'url': 'https://library.spus.edu.ph/',
        'category': 'Academics',
    },
    {
        'title': 'Data Privacy Policy',
        'url': 'https://spus.edu.ph/data-privacy-policy/',
        'category': 'Policy',
    },
    {
        'title': 'SPUS Official Homepage & Campus Overview',
        'url': 'https://spus.edu.ph/',
        'category': 'General',
    },
]


class SPUSHTMLCleaner(HTMLParser):
    """Strips boilerplate, navigation, and formatting to yield clean readable text."""
    def __init__(self):
        super().__init__()
        self.chunks = []
        self.in_ignored = False
        self.ignored_tags = {'script', 'style', 'noscript', 'nav', 'footer', 'header'}
        self.heading_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

    def handle_starttag(self, tag, attrs):
        if tag in self.ignored_tags:
            self.in_ignored = True
        elif tag in self.heading_tags:
            self.chunks.append("\n\n### ")
        elif tag in ('p', 'li', 'br', 'tr', 'div'):
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self.ignored_tags:
            self.in_ignored = False
        elif tag in self.heading_tags or tag in ('p', 'li', 'tr'):
            self.chunks.append("\n")

    def handle_data(self, data):
        if not self.in_ignored:
            text = data.strip()
            if text:
                self.chunks.append(text + " ")

    def get_clean_text(self):
        full = "".join(self.chunks)
        # Remove typical Elementor / WordPress boilerplate
        boilerplate = [
            "Skip to content",
            "Scroll to Top",
            "© All Rights Reserved. St. Paul University Surigao",
            "ENROLL NOW",
            "admission-col",
            "admission-basic",
            "SLIDER2 (1)",
            "Get In Touch",
            "[email protected]"
        ]
        for bp in boilerplate:
            full = full.replace(bp, "")

        # Collapse whitespace lines
        lines = [line.strip() for line in full.split("\n")]
        cleaned = [l for l in lines if l]
        return "\n".join(cleaned)


def chunk_text(text, max_chunk_chars=1200, overlap=150):
    """Splits a document text into overlapping chunks, preferring heading/paragraph boundaries."""
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para)
        if current_length + para_len > max_chunk_chars and current_chunk:
            combined = "\n".join(current_chunk)
            chunks.append(combined)
            # Retain last few lines for context overlap
            current_chunk = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk
            current_length = sum(len(p) for p in current_chunk)

        current_chunk.append(para)
        current_length += para_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks if chunks else [text]


class Command(BaseCommand):
    help = 'Scrape official SPUS website and ingest verified content into WebResource knowledge base'

    def add_arguments(self, parser):
        parser.add_argument(
            '--discover',
            action='store_true',
            help='Also crawl and discover additional internal links from the homepage'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Starting SPUS Official Website Scraper ==="))
        
        pages_to_scrape = list(CORE_SPUS_PAGES)
        scraped_urls = {p['url'] for p in pages_to_scrape}

        if options['discover']:
            self.stdout.write("Discovering additional internal links from https://spus.edu.ph/...")
            try:
                resp = requests.get('https://spus.edu.ph/', headers=HEADERS, timeout=15)
                raw_links = re.findall(r'href=["\'](.*?)["\']', resp.text)
                for l in raw_links:
                    full = urljoin('https://spus.edu.ph/', l)
                    parsed = urlparse(full)
                    if parsed.netloc == 'spus.edu.ph' and not any(parsed.path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.svg', '.pdf', '.webp']):
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
                        if clean_url and clean_url not in scraped_urls and len(clean_url) > 20:
                            scraped_urls.add(clean_url)
                            slug = parsed.path.strip('/').replace('-', ' ').title()
                            pages_to_scrape.append({
                                'title': slug if slug else 'SPUS Page',
                                'url': clean_url,
                                'category': 'Discovered',
                            })
                self.stdout.write(f"Total pages queued for ingestion: {len(pages_to_scrape)}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not discover links: {e}"))

        total_saved = 0

        for page in pages_to_scrape:
            url = page['url']
            title = page['title']
            category = page['category']
            
            self.stdout.write(f"\nScraping: {title} ({url})...")
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"  HTTP {resp.status_code} - Skipping."))
                    continue

                cleaner = SPUSHTMLCleaner()
                cleaner.feed(resp.text)
                clean_text = cleaner.get_clean_text()

                if len(clean_text) < 100:
                    self.stdout.write(self.style.WARNING(f"  Content too short ({len(clean_text)} chars) - Skipping."))
                    continue

                chunks = chunk_text(clean_text)
                self.stdout.write(f"  Extracted {len(clean_text)} characters -> {len(chunks)} chunk(s).")

                for i, chunk in enumerate(chunks):
                    chunk_title = title if len(chunks) == 1 else f"{title} (Part {i + 1})"
                    
                    obj, created = WebResource.objects.update_or_create(
                        url=url,
                        title=chunk_title,
                        defaults={
                            'category': category,
                            'content': chunk,
                        }
                    )
                    status_text = "CREATED" if created else "UPDATED"
                    self.stdout.write(f"    [{status_text}] {chunk_title}")
                    total_saved += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error scraping {url}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nScraping complete! Ingested/updated {total_saved} web resources."))
        
        # Trigger RAG embedding generation
        self.stdout.write("Generating vector embeddings for new web resources...")
        try:
            from chatbot.rag import RAGSearcher
            rag = RAGSearcher()
            rag.ensure_embeddings()
            self.stdout.write(self.style.SUCCESS("Vector embeddings generated and stored in pgvector!"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not automatically generate embeddings: {e}"))

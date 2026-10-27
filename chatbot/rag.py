"""
PauliBot RAG (Retrieval-Augmented Generation) Engine
=====================================================
Phase 2: Database-backed vector search using PostgreSQL + pgvector.

This module reads knowledge from the database (Location, StaffMember, FAQ),
generates embeddings, and performs semantic search against pgvector.
"""
import logging
from sentence_transformers import SentenceTransformer
from pgvector.django import L2Distance

logger = logging.getLogger(__name__)


class RAGSearcher:
    """Manages semantic search using PostgreSQL pgvector."""

    def __init__(self):
        logger.info("Initializing RAG Searcher (pgvector mode)...")
        logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("RAG Searcher ready.")

    def _generate_embedding(self, text):
        """Generate a 384-dimension embedding for a text string."""
        return self.model.encode(text).tolist()

    def ensure_embeddings(self):
        """
        Generate embeddings for any Knowledge Base entries that don't have one yet.
        Called when a staff member adds new data via the admin panel.
        """
        from chatbot.models import Location, StaffMember, FAQ, WebResource

        updated = 0

        for loc in Location.objects.filter(embedding__isnull=True):
            text = f"Location: {loc.name}. {loc.description}"
            loc.embedding = self._generate_embedding(text)
            loc.save(update_fields=['embedding'])
            updated += 1

        for staff in StaffMember.objects.filter(embedding__isnull=True):
            text = f"Staff: {staff.name}, {staff.position}. Office located at {staff.office}."
            staff.embedding = self._generate_embedding(text)
            staff.save(update_fields=['embedding'])
            updated += 1

        for faq in FAQ.objects.filter(embedding__isnull=True):
            text = f"FAQ about {faq.category}: {faq.question} - {faq.answer}"
            faq.embedding = self._generate_embedding(text)
            faq.save(update_fields=['embedding'])
            updated += 1

        for wr in WebResource.objects.filter(embedding__isnull=True):
            text = f"{wr.category} - {wr.title}: {wr.content}"
            wr.embedding = self._generate_embedding(text)
            wr.save(update_fields=['embedding'])
            updated += 1

        if updated:
            logger.info(f"Generated embeddings for {updated} new knowledge entries.")

    def live_scrape_query(self, query):
        """
        On-demand live fallback: If information is missing from the database,
        searches spus.edu.ph live using its search endpoint, extracts the top article,
        and saves it to WebResource with an embedding for immediate citation.
        """
        import requests
        import re
        from html.parser import HTMLParser
        from urllib.parse import quote_plus
        from chatbot.models import WebResource

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }

        search_url = f"https://spus.edu.ph/?s={quote_plus(query)}"
        logger.info(f"Triggering live SPUS web scrape fallback for: '{query}' -> {search_url}")

        try:
            resp = requests.get(search_url, headers=headers, timeout=8)
            if resp.status_code != 200:
                return []

            # Extract article links from WordPress search result page
            article_links = re.findall(r'<h[23][^>]*class=[\'"][^\'"]*entry-title[^\'"]*[\'"][^>]*>\s*<a\s+href=[\'"]([^\'"]+)[\'"]', resp.text, re.IGNORECASE)
            if not article_links:
                # Fallback link pattern
                article_links = re.findall(r'href=[\'"](https://spus\.edu\.ph/[^\'"\s#]+)[\'"]', resp.text)
                article_links = [l for l in article_links if not any(l.endswith(ext) for ext in ['.jpg', '.png', '.css', '.js', '/feed', '/comments/feed'])]

            if not article_links:
                return []

            target_url = article_links[0]
            logger.info(f"Live scrape found target URL on SPUS website: {target_url}")

            # Check if we already have it
            existing = WebResource.objects.filter(url=target_url).first()
            if existing:
                return [{
                    'text': existing.content,
                    'document_title': f"{existing.title} (SPUS Official Website)",
                    'source_url': existing.url
                }]

            # Fetch target page
            page_resp = requests.get(target_url, headers=headers, timeout=8)
            if page_resp.status_code != 200:
                return []

            # Extract clean text
            text = re.sub(r'<script[^>]*>.*?</script>', '', page_resp.text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()

            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', page_resp.text, re.IGNORECASE)
            page_title = title_match.group(1).split('-')[0].strip() if title_match else "SPUS Official Article"

            if len(text) > 100:
                # Save into WebResource so future queries hit DB instantly
                obj = WebResource.objects.create(
                    title=page_title,
                    url=target_url,
                    category="Live Web Search",
                    content=text[:2000],
                    embedding=self._generate_embedding(f"{page_title}: {text[:1000]}")
                )
                logger.info(f"Successfully live-scraped and saved '{page_title}' to WebResource.")
                return [{
                    'text': text[:1500],
                    'document_title': f"{page_title} (SPUS Official Website)",
                    'source_url': target_url
                }]
        except Exception as e:
            logger.warning(f"Live scrape fallback failed: {e}")

        return []

    def search(self, query, limit=5):
        """
        Perform semantic vector search across all Knowledge Base tables:
        Locations, StaffDirectory, FAQs, and WebResource (official website).
        Returns the top matching text chunks ordered by actual L2 distance.
        """
        from chatbot.models import Location, StaffMember, FAQ, WebResource
        from pgvector.django import L2Distance

        # Ensure all entries have embeddings before searching
        self.ensure_embeddings()

        query_vector = self._generate_embedding(query)
        all_results = []
        pool_size = max(15, limit * 3)

        # Search Locations
        locations = Location.objects.exclude(embedding__isnull=True).annotate(
            distance=L2Distance('embedding', query_vector)
        ).order_by('distance')[:pool_size]
        
        for loc in locations:
            all_results.append({
                'text': f"Location: {loc.name}. {loc.description}",
                'title': f"Location: {loc.name}",
                'url': None,
                'source_type': 'campus_map',
                'source_office': None,
                'question': f"Where is {loc.name}?",
                'answer': loc.description,
                'distance': loc.distance
            })

        # Search Staff
        staff_members = StaffMember.objects.exclude(embedding__isnull=True).annotate(
            distance=L2Distance('embedding', query_vector)
        ).order_by('distance')[:pool_size]
        
        for staff in staff_members:
            all_results.append({
                'text': f"{staff.name} is the {staff.position}.",
                'title': f"Staff Directory: {staff.position}",
                'url': None,
                'source_type': 'staff_directory',
                'source_office': staff.office,
                'question': f"Who is the {staff.position}?",
                'answer': f"{staff.name} is the {staff.position}. Office located at {staff.office}.",
                'distance': staff.distance
            })

        # Search FAQs
        faqs = FAQ.objects.exclude(embedding__isnull=True).annotate(
            distance=L2Distance('embedding', query_vector)
        ).order_by('distance')[:pool_size]
        
        for faq in faqs:
            st = faq.source_type or ('handbook' if faq.category == 'Student Handbook' else 'curated')
            all_results.append({
                'text': f"FAQ about {faq.category}: {faq.question} - {faq.answer}",
                'title': f"FAQ ({faq.category}): {faq.question}",
                'url': None,
                'source_type': st,
                'source_office': faq.source_office,
                'question': faq.question,
                'answer': faq.answer,
                'distance': faq.distance
            })

        # Search Official SPUS Web Resources
        web_resources = WebResource.objects.exclude(embedding__isnull=True).annotate(
            distance=L2Distance('embedding', query_vector)
        ).order_by('distance')[:pool_size]

        for wr in web_resources:
            all_results.append({
                'text': f"{wr.title}: {wr.content}",
                'title': f"{wr.title} (SPUS Official Website)",
                'url': wr.url,
                'source_type': 'website',
                'source_office': None,
                'question': wr.title,
                'answer': wr.content,
                'distance': wr.distance
            })

        # --- Keyword Boost Logic ---
        query_lower = query.lower()
        boost_keywords = []
        if 'tesda' in query_lower or 'tvet' in query_lower:
            boost_keywords.extend(['tesda', 'tvet'])
        if 'admission' in query_lower or 'enroll' in query_lower or 'requirement' in query_lower:
            boost_keywords.extend(['admission', 'enrol', 'requirement', 'report card', 'birth certificate'])
        if 'contact' in query_lower or 'phone' in query_lower or 'email' in query_lower:
            boost_keywords.extend(['contact', 'phone', '826 4325', 'office hours'])
        if any(kw in query_lower for kw in ['scholarship', 'scholarships', 'financial aid', 'grant', 'grants', 'subsidy', 'subsidies', 'ssap', 'voucher']):
            boost_keywords.extend(['scholarship', 'scholarships', 'subsidy', 'esc', 'voucher', 'guidance office', 'assistance'])
            for res in all_results:
                t_low = res['text'].lower()
                if 'scholarship' in t_low or 'subsidy' in t_low or 'ssap' in t_low or 'voucher' in t_low:
                    res['distance'] -= 0.60
                if 'across five' in t_low or ('college of health sciences' in t_low and 'college of engineering' in t_low):
                    res['distance'] += 0.80  # Heavily penalize program catalog for scholarship queries

        if any(kw in query_lower for kw in ['tuition', 'fee', 'fees', 'magkano', 'how much', 'downpayment', 'installment']):
            boost_keywords.extend(['tuition', 'fee', 'fees', 'finance', 'accounting', 'payment'])
            for res in all_results:
                t_low = res['text'].lower()
                if 'across five' in t_low:
                    res['distance'] += 0.80

        # Calendar / school events / activities boost
        if any(kw in query_lower for kw in ['calendar', 'school calendar', 'academic calendar', 'school activities', 'school events', 'important dates', 'semester schedule', 'intramurals', 'foundation day', 'paulinian week', 'commencement', 'exam schedule', 'academic year']):
            boost_keywords.extend(['academic calendar', 'semester', 'first semester', 'second semester', 'enrollment period', 'intramurals', 'foundation day', 'commencement', 'graduation'])
            for res in all_results:
                t_low = res['text'].lower()
                # Boost calendar-specific content
                if any(ck in t_low for ck in ['academic calendar', 'first semester', 'second semester', 'preliminary exam', 'midterm exam', 'final exam', 'intramurals', 'foundation day', 'paulinian week', 'commencement']):
                    res['distance'] -= 0.80  # Strong boost for calendar content
                # Penalize PBMO publication procedures
                if 'pbmo' in t_low or 'submit materials' in t_low or 'reporting school events for publication' in t_low:
                    res['distance'] += 1.00  # Heavy penalty to push irrelevant PBMO out

        if any(kw in query_lower for kw in ['program', 'programs', 'course', 'courses', 'degree', 'degrees', 'bachelor', 'undergraduate', 'curriculum', 'available programs', 'available courses']):
            if not any(sk in query_lower for sk in ['scholarship', 'scholarships', 'tuition', 'fee', 'fees']):
                boost_keywords.extend(['college of', 'bachelor of', 'programs offered', 'undergraduate', 'curriculum'])
            
        for res in all_results:
            text_lower = res['text'].lower()
            for kw in boost_keywords:
                if kw in text_lower:
                    res['distance'] -= 0.4  # Keyword boost

        # --- Source Priority Hierarchy Boost ---
        # Tier 1: Office-Submitted (highest authority, direct from office)
        # Tier 2: SPUS Official Website & Staff Directory (updated current facts)
        # Tier 3: Student Handbook & Curated Baseline (foundational policies)
        for res in all_results:
            st = res.get('source_type')
            if st == 'office':
                res['distance'] -= 0.30  # Tier 1: Strongest boost
            elif st in ('website', 'staff_directory'):
                res['distance'] -= 0.15  # Tier 2: Freshness boost over handbook

        # Specific boost for unified all-programs catalog on broad program queries
        # Ensures that a student asking "What programs are offered?" gets all 5 colleges instead of 1 random college
        is_broad_program = any(kw in query_lower for kw in [
            'what program', 'what course', 'programs offered', 'courses offered',
            'available program', 'available course', 'all program', 'all course',
            'list of program', 'undergraduate program', 'degrees offered', 'what are the program',
            'what are the course', 'mga programa', 'mga kurso', 'departments', 'programs are offered',
            'courses are available'
        ])
        if is_broad_program:
            for res in all_results:
                t_low = res['text'].lower()
                if 'across five' in t_low or 'across 5' in t_low or ('college of health sciences' in t_low and 'college of engineering' in t_low and 'college of business' in t_low):
                    res['distance'] -= 0.80  # Definitive win for unified catalog

        # Sort all results by distance
        all_results.sort(key=lambda x: x['distance'])

        # If best match distance is weak or no results, attempt live web scrape fallback
        if not all_results or (len(all_results) > 0 and all_results[0]['distance'] > 1.25):
            live_results = self.live_scrape_query(query)
            if live_results:
                return live_results

        # Filter out weak matches — only keep entries with distance below calibrated threshold
        relevance_threshold = 1.05
        all_results = [r for r in all_results if r['distance'] <= relevance_threshold]

        final_results = [{
            "text": r['text'],
            "document_title": r['title'],
            "source_url": r['url'],
            "source_type": r.get('source_type', 'curated'),
            "source_office": r.get('source_office'),
            "question": r.get('question'),
            "answer": r.get('answer'),
            "distance": r['distance'],
        } for r in all_results[:limit]]
        
        logger.info(f"Top RAG results count for query '{query}': {len(final_results)}")
        return final_results


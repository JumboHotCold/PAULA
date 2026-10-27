import os
import logging
from groq import Groq
from django.conf import settings
from .rag import RAGSearcher

logger = logging.getLogger(__name__)

# ==============================================================================
# SYSTEM PROMPT — PauliBot Identity & Behavior Rules
# ==============================================================================
# Separated from user context for better instruction-following on chat APIs.

PAULIBOT_SYSTEM_PROMPT = """You are PAULA, which stands for Paulinian Artificial User Support and Learning Assistant. You are the official AI campus assistant for Saint Paul University Surigao (SPUS).
You are a warm, friendly, and knowledgeable virtual guide created to help students, parents, and visitors with university-related inquiries.

CORE RULES:
1. You must ONLY answer based on the verified SPUS knowledge base provided in each user message. NEVER use outside knowledge or make up information.
2. If the requested information is NOT in the provided context or is not covered in the official SPUS knowledge base, student handbook, or website, respond with a friendly message: "I'm sorry, but I don't have that specific information in my current SPUS knowledge base. For further assistance, you may inquire directly at the Information Desk located near the Main Entrance, visit the campus administration, or check the official SPUS website (https://spus.edu.ph)." (in the student's language)
3. You are NOT a general-purpose AI. Politely decline non-SPUS topics.

ANSWER PRECISION:
- The knowledge base context may contain MULTIPLE entries. You MUST carefully select ONLY the entry or entries that DIRECTLY answer the question.
- DO NOT include entries that are merely similar or tangentially related. For example, if asked "Who is the VP Academic?", answer ONLY with the VP for Academics — do NOT also mention the VP for PRISM, VP for Finance, etc. just because they appear in the context.
- When answering "who is" or "sino ang" questions about a specific role, provide ONLY the person holding that exact role.
- Keep your answer focused: one question = one precise answer. Quality over quantity.

KNOWLEDGE SOURCE HIERARCHY & PRIORITY:
The context entries are prefixed with their source type:
1. [OFFICIAL OFFICE: <NAME> (2026-2027)]: Tier 1 (HIGHEST AUTHORITY) — Official procedures, requirements, FAQs, and forms submitted directly by university offices (Registrar, Finance, Guidance, CEIT, CHS, etc.). ALWAYS prefer this over all other sources when it answers the question.
2. [SPUS OFFICIAL WEBSITE (2027)] & [STAFF DIRECTORY (2027)]: Tier 2 (CURRENT FACTS) — Current university website and directory. Authoritative for active administrators, officials, contact info, admissions, tuition fees, and recent announcements. Overrides older handbook information for factual data.
3. [STUDENT HANDBOOK (2022)]: Tier 3 (FOUNDATIONAL POLICIES) — Authoritative for institutional policies, grading system, student code of conduct, dress code, disciplinary procedures, graduation honors, and student rights.

CONFLICT RESOLUTION RULES:
- If an Office source contradicts a Website or Handbook source regarding that office's procedures, requirements, or policies, ALWAYS follow the Office source.
- If the Website or Staff Directory contradicts the 2022 Student Handbook on factual data (e.g., current administrators, fees, contacts), ALWAYS use the Website/Directory data.
- For institutional rules and policies not updated by the website or offices, rely on the Student Handbook.

LANGUAGE GUIDELINES:
- Detect the language of the CURRENT message ONLY. Ignore previous messages.
- If the message is in Filipino, respond entirely in Filipino.
- If the message is in English, respond entirely in English.
- If the message mixes Filipino and English (Taglish), respond in Taglish.
- Always keep a warm, friendly, and approachable tone — like a helpful campus guide.

GREETING & IDENTITY:
- Introduce yourself as PAULA (Paulinian Artificial User Support and Learning Assistant) ONLY in the very first message of a conversation or when explicitly asked "Who are you?", "What is your name?", or "What does PAULA stand for?".
- When asked what PAULA stands for, state clearly: "PAULA stands for Paulinian Artificial User Support and Learning Assistant."
- For regular follow-up questions, jump straight to the answer without restating your name or giving a generic welcome.
- For greetings (hi, hello, kamusta, hey, good morning), respond with a friendly greeting in the SAME language. If it's the start of the chat, introduce yourself as PAULA. If it's midway, just greet back naturally.

ANSWER STYLE:
- Be thorough but concise. Avoid redundant preambles.
- Maintain a professional and academic tone.
- Use bullet points or numbered lists when listing multiple items.
- When mentioning staff, include their name and position. Only mention their office location if the user specifically asks where to find them.

COMPREHENSIVE LISTING:
- When the question asks for ALL available programs, courses, colleges, or degrees, you MUST list ALL items from the knowledge base — do NOT truncate, abbreviate, or summarize to fewer items.
- If the knowledge base lists 5 colleges, list all 5 colleges. If it lists 20 programs, list all 20 programs.
- Use the term "programs" instead of "courses" when referring to academic degree programs.

FOLLOW-UP SUGGESTIONS:
After EVERY answer, provide exactly 3 short follow-up questions the student might want to ask next.
Write them on the LAST line in this EXACT format:
[SUGGESTIONS: "Question 1?" | "Question 2?" | "Question 3?"]
The suggestions must be in the SAME language as your response and relevant to SPUS topics."""



class PauliBotLogic:
    """
    PauliBot v2 — AI Logic Engine powered by Groq (Llama 3.3 70B) or Google Gemini.
    Uses Retrieval-Augmented Generation (RAG) with pgvector for context retrieval.
    Includes smart RAG fallback when LLM API keys are offline or invalid.
    """

    def __init__(self):
        # Priority: os.environ → Django settings
        self.groq_key = (os.environ.get('GROQ_API_KEY') or getattr(settings, 'GROQ_API_KEY', '')).strip()
        self.openai_key = (os.environ.get('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', '')).strip()
        self.gemini_key = (os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', '')).strip()

        # Ignore placeholder values
        if self.groq_key in ('your_groq_api_key_here', ''):
            self.groq_key = None
        if self.openai_key in ('your_openai_api_key_here', ''):
            self.openai_key = None
        if self.gemini_key in ('your_gemini_api_key_here', ''):
            self.gemini_key = None

        self.client = None
        self.openai_client = None
        self.gemini_model = None

        if self.groq_key:
            try:
                self.client = Groq(api_key=self.groq_key)
                # Auto-discover the best available chat model on this Groq account
                self.model_name = self._discover_groq_model()
                if self.model_name:
                    logger.info(f"PauliBot v2 initialized with Groq model: {self.model_name}")
                else:
                    logger.warning("Groq client initialized but no chat model available.")
                    self.client = None
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")

        if self.openai_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_key)
                logger.info("PauliBot v2 initialized with OpenAI fallback client.")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")

        if not self.client and not self.openai_client and self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("PauliBot v2 initialized with Gemini model: gemini-1.5-flash")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

        # Initialize the RAG searcher engine
        self.rag = RAGSearcher()

    def _build_context(self, query):
        """Perform semantic search to fetch relevant context chunks and return context string + sources list."""
        results = self.rag.search(query, limit=5)
        if not results:
            return "No relevant knowledge base entries found for this query.", []
        
        context = "Here is the relevant verified knowledge base for Saint Paul University Surigao (SPUS):\n\n"
        sources = []
        seen_source_keys = set()
        for i, res in enumerate(results):
            st = res.get('source_type', 'curated')
            so = res.get('source_office')
            if st == 'office' and so:
                prefix = f"[OFFICIAL OFFICE: {so.upper()} (2026-2027)]"
            elif st == 'office':
                prefix = "[OFFICIAL OFFICE SUBMISSION]"
            elif st == 'website':
                prefix = "[SPUS OFFICIAL WEBSITE (2027)]"
            elif st == 'staff_directory':
                prefix = f"[STAFF DIRECTORY (2027){f' - {so}' if so else ''}]"
            elif st == 'handbook':
                prefix = "[STUDENT HANDBOOK (2022)]"
            elif st == 'campus_map':
                prefix = "[CAMPUS MAP DIRECTORY]"
            else:
                prefix = "[VERIFIED KNOWLEDGE BASE]"

            context += f"- {prefix} {res['text']}\n"

            raw_title = res.get('document_title', '')
            url = res.get('source_url')

            display_title = raw_title
            if st == 'office' and so:
                clean_q = raw_title
                for pfx in ("FAQ (Academics): ", "FAQ (Registrar's Office): ", "FAQ (Courses): ", "FAQ: ", "FAQ (Admissions): "):
                    clean_q = clean_q.replace(pfx, "")
                clean_q = clean_q.split('?')[0].strip() + '?' if '?' in clean_q else clean_q.strip()
                display_title = f"Office of the {so}: {clean_q}"
            elif st == 'website' and not raw_title.endswith('(SPUS Official Website)'):
                display_title = f"{raw_title} (SPUS Official Website)"

            source_key = url if url else " ".join(display_title.lower().split()[:6])
            if source_key not in seen_source_keys:
                seen_source_keys.add(source_key)
                sources.append({
                    "title": display_title,
                    "page": None,
                    "url": url,
                    "source_type": st,
                    "source_office": so
                })
            
        return context, sources

    # ── Location keyword → campus node ID mapping ──
    LOCATION_KEYWORDS = {
        'registrar': 'registrar_office',
        'registration': 'registrar_office',
        'finance': 'finance_office',
        'cashier': 'finance_office',
        'accounting': 'finance_office',
        'guidance': 'guidance_office',
        'counselor': 'guidance_office',
        'cafeteria': 'cafeteria',
        'canteen': 'cafeteria',
        'cathedral': 'cathedral',
        'church': 'cathedral',
        'chapel': 'cathedral',
        'clinic': 'clinic',
        'infirmary': 'clinic',
        'nurse': 'clinic',
        'sao': 'sao',
        'student affairs': 'sao',
        'ict': 'ict_office',
        'music room': 'music_room',
        'president': 'presidents_office',
        'boardroom': 'presidents_boardroom',
        'hr': 'hr_office',
        'human resource': 'hr_office',
        'science building': 'science_building',
        'science lab': 'science_building',
        'laboratory': 'science_building',
        'court': 'open_court',
        'basketball': 'open_court',
        'lounge': 'student_lounge_upper',
        'cfo': 'cfo',
        'front office': 'cfo',
        'ccje': 'ccje',
        'criminal justice': 'ccje',
        'criminology': 'ccje',
        'engineering': 'ceit',
        'information technology': 'ceit',
        'ceit': 'ceit',
        'community development': 'community_dev',
        'community': 'community_dev',
        'dean': 'dean_graduate',
        'graduate school': 'dean_graduate',
        'entrance': 'main_entrance',
        'gate': 'main_entrance',
        'main gate': 'main_entrance',
        'visitor': 'visitors_lodge',
        'lodge': 'visitors_lodge',
        'snb': 'snb_building',
        'inspire': 'inspire',
        'ins pire': 'inspire',
        'scholarship': 'inspire',
        'education': 'college_education',
        'college of education': 'college_education',
        'san nicolas': 'san_nicolas_bldg',
        'restroom': 'restroom_left',
        'sp building': 'sp_building',
        'st paul building': 'sp_building',
    }

    def _extract_destination(self, message):
        """Extract destination node ID from a user's location query."""
        msg_lower = message.lower()
        sorted_keywords = sorted(self.LOCATION_KEYWORDS.keys(), key=len, reverse=True)
        for keyword in sorted_keywords:
            if keyword in msg_lower:
                return self.LOCATION_KEYWORDS[keyword]
        return None

    def _discover_groq_model(self):
        """Query Groq API to verify and find an available active chat model."""
        preferred_models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
        try:
            available_models = [m.id for m in self.client.models.list().data if getattr(m, 'active', True)]
            # Check if any preferred model is usable (verify not blocked by project limits)
            for pref in preferred_models:
                if pref in available_models:
                    try:
                        self.client.chat.completions.create(
                            model=pref,
                            messages=[{"role": "user", "content": "ping"}],
                            max_tokens=2
                        )
                        return pref
                    except Exception:
                        continue
            # Try any available chat model
            for m in available_models:
                try:
                    self.client.chat.completions.create(
                        model=m,
                        messages=[{"role": "user", "content": "ping"}],
                        max_tokens=2
                    )
                    return m
                except Exception:
                    continue
            return None
        except Exception as e:
            logger.warning(f"Could not discover working Groq model: {e}")
            return None

    def _extract_relevant_blocks(self, text, query, max_blocks=2):
        """
        Extract only the discrete entity blocks (e.g. staff card, section, paragraph)
        from a long text chunk that directly answer or match the query.
        Prevents returning long lists or catalogs of unrelated staff/sections.
        """
        import re
        stopwords = {'what', 'is', 'the', 'who', 'are', 'a', 'an', 'of', 'for', 'in', 'to', 'and', 'or', 'how', 'do', 'i', 'does', 'can', 'saan', 'ano', 'sino', 'ang', 'ng', 'sa', 'at'}
        query_words = [w for w in re.findall(r'\b\w+\b', query.lower()) if w not in stopwords and len(w) > 1]
        if not query_words:
            query_words = query.lower().split()

        # Split text into distinct logical blocks by ### headers or double newlines
        lines = text.split('\n')
        blocks = []
        curr = []
        for line in lines:
            line_str = line.strip()
            if (line_str.startswith('###') or line_str.startswith('## ')) and curr:
                block_content = '\n'.join(curr).strip()
                if block_content:
                    blocks.append(block_content)
                curr = [line_str]
            elif not line_str and curr:
                block_content = '\n'.join(curr).strip()
                if len(block_content) > 30:
                    blocks.append(block_content)
                    curr = []
            else:
                if line_str:
                    curr.append(line_str)
        if curr:
            block_content = '\n'.join(curr).strip()
            if block_content:
                blocks.append(block_content)

        if not blocks:
            blocks = [text]

        # Score blocks by keyword matches and density
        scored_blocks = []
        for b in blocks:
            # Skip pure category banners
            b_lower = b.lower()
            if 'top management graduate school faculty' in b_lower:
                continue
            
            # Count matches
            hits = sum(1 for kw in query_words if kw in b_lower)
            if hits > 0:
                # Extra weight for exact match of role/term
                score = hits
                if '###' in b:
                    score += 0.5
                scored_blocks.append((score, b))

        scored_blocks.sort(key=lambda x: -x[0])

        if not scored_blocks:
            # If no blocks match the user query words at all, do NOT hallucinate or return random faculty
            return []

        # Keep top distinct blocks
        top_score = scored_blocks[0][0]
        results = []
        seen = set()
        for score, b in scored_blocks:
            # Only include blocks that are competitive with the top match
            if score < top_score * 0.7:
                break
            
            # Clean display formatting
            clean_b = b.replace('### ', '**').replace('\n', '**\n', 1) if b.startswith('### ') else b
            if clean_b not in seen:
                seen.add(clean_b)
                results.append(clean_b)
            if len(results) >= max_blocks:
                break

        return results

    def _generate_rag_fallback(self, msg, sources, action, action_data):
        """
        Generates a direct, accurate, and complete response using retrieved knowledge base
        entries when an LLM is offline or unconfigured. Preserves complete FAQ answers
        (e.g., all colleges and programs) without arbitrary 4-line truncation.
        """
        import re
        identity_keywords = [
            'who are you', 'what is your name', 'what is paula', 'what does paula stand for',
            'who is paula', 'ano ang paula', 'sino ka', 'sino si paula', 'about paula',
            'meaning of paula', 'ano pangalan mo', 'introduce yourself', 'what are you'
        ]
        if any(ik in msg.lower() for ik in identity_keywords):
            resp = (
                "Hello! I am **PAULA**, which stands for **Paulinian Artificial User Support and Learning Assistant**.\n\n"
                "I am the official AI campus assistant for Saint Paul University Surigao (SPUS), designed to assist students, parents, faculty, and visitors with university information, including:\n\n"
                "- **Academic Programs**: Undergraduate colleges, Graduate School, and TVET/TESDA offerings\n"
                "- **Admissions & Enrollment**: Procedures, deadlines, and requirements for incoming freshmen and transferees\n"
                "- **Scholarships & Grants**: Academic/athletic scholarships, ESC grants, Senior High vouchers, and SSAP\n"
                "- **Tuition Fees & Payments**: Assessment policies and Finance Office procedures\n"
                "- **Campus Navigation**: 2D campus maps and interactive directions to offices and facilities\n"
                "- **University Directory**: Administrators, deans, faculty, and office contact information\n\n"
                "How may I assist you today?\n\n"
                '[SUGGESTIONS: "What programs are offered at SPUS?" | "Does SPUS offer scholarships?" | "Where is the Registrar\'s Office?"]'
            )
            return resp, [], action, action_data

        results = self.rag.search(msg, limit=5)
        if not results:
            fallback_text = (
                "I'm sorry, but I don't have that specific information in my current SPUS knowledge base, student handbook, or website directory.\n\n"
                "For further assistance or inquiries:\n"
                "- **Information Desk**: You may visit the Information Desk located near the **Main Entrance** (Gate 1).\n"
                "- **Campus Administration**: Inquire at the Administration Building on campus.\n"
                "- **Official Website**: Visit [spus.edu.ph](https://spus.edu.ph) for official university announcements.\n\n"
                "Feel free to ask me about academic programs, admissions, tuition fees, scholarships, or campus office locations!"
                '\n\n[SUGGESTIONS: "What programs are offered at SPUS?" | "Does SPUS offer scholarships?" | "Where is the Registrar\'s Office?"]'
            )
            return fallback_text, [], action, action_data

        stopwords = {'what', 'is', 'the', 'who', 'are', 'a', 'an', 'of', 'for', 'in', 'to', 'and', 'or', 'how', 'do', 'i', 'does', 'can', 'saan', 'ano', 'sino', 'ang', 'ng', 'sa', 'at'}
        query_words = [w for w in re.findall(r'\b\w+\b', msg.lower()) if w not in stopwords and len(w) > 1]
        if not query_words:
            query_words = msg.lower().split()

        person_keywords = {'who', 'sino', 'vp', 'president', 'dean', 'director', 'principal', 'chair', 'head', 'moderator', 'officer', 'faculty'}
        is_person_query = any(pk in msg.lower() for pk in person_keywords)

        is_scholarship_query = any(kw in msg.lower() for kw in ['scholarship', 'scholarships', 'financial aid', 'grant', 'grants', 'subsidy', 'subsidies', 'ssap', 'voucher'])
        is_tuition_query = any(kw in msg.lower() for kw in ['tuition', 'fee', 'fees', 'magkano', 'how much', 'downpayment', 'installment'])

        calendar_keywords = [
            'calendar', 'school calendar', 'academic calendar', 'school activities',
            'school events', 'important dates', 'semester schedule', 'when does class start',
            'when do classes start', 'intramurals', 'foundation day', 'paulinian week',
            'graduation date', 'commencement', 'enrollment period', 'exam schedule',
            'academic year', 'school year schedule'
        ]
        is_calendar_query = any(ck in msg.lower() for ck in calendar_keywords)

        program_keywords = [
            'what program', 'what course', 'programs offered', 'courses offered',
            'available program', 'available course', 'all program', 'all course',
            'list of program', 'undergraduate program', 'degrees offered', 'what are the program',
            'what are the course', 'mga programa', 'mga kurso', 'academic programs', 'courses are available',
            'programs are offered', 'college courses'
        ]
        is_program_query = any(pk in msg.lower() for pk in program_keywords) and not is_scholarship_query and not is_tuition_query and not is_calendar_query

        all_candidate_blocks = []
        for res in results:
            txt = res['text']
            source_url = res.get('source_url', '')

            q = res.get('question')
            a = res.get('answer')

            if q and a and (txt.startswith("FAQ about ") or res.get('source_type') in ('curated', 'handbook', 'office')):
                clean_question = q.split('?')[0].strip() + '?' if '?' in q else q.strip()
                answer_body = a.strip()
                all_candidate_blocks.append({
                    'title': clean_question,
                    'text': f"**{clean_question}**\n\n{answer_body}",
                    'answer_body': answer_body,
                    'url': source_url,
                    'is_faq': True
                })
            elif txt.startswith("FAQ about "):
                parts = txt.split(" - ", 1)
                if len(parts) == 2:
                    raw_title = parts[0]
                    for prefix in ("FAQ about Location: ", "FAQ about Process: ", "FAQ about Academic: ", "FAQ about Academics: ", "FAQ about Academics - ", "FAQ about "):
                        raw_title = raw_title.replace(prefix, "")
                    clean_question = raw_title.split('?')[0].strip() + '?' if '?' in raw_title else raw_title.strip()
                    answer_body = parts[1].strip()
                    all_candidate_blocks.append({
                        'title': clean_question,
                        'text': f"**{clean_question}**\n\n{answer_body}",
                        'answer_body': answer_body,
                        'url': source_url,
                        'is_faq': True
                    })
            elif txt.startswith("Location: ") or 'is the' in txt.split('.')[0]:
                all_candidate_blocks.append({
                    'title': txt.split('.')[0],
                    'text': txt.strip(),
                    'answer_body': txt.strip(),
                    'url': source_url,
                    'is_faq': False
                })
            else:
                extracted = self._extract_relevant_blocks(txt, msg, max_blocks=2)
                for item in extracted:
                    all_candidate_blocks.append({
                        'title': res.get('document_title', ''),
                        'text': item.strip(),
                        'answer_body': item.strip(),
                        'url': source_url,
                        'is_faq': False
                    })

        scored_candidates = []
        for cand in all_candidate_blocks:
            t = cand['text']
            t_lower = t.lower()
            match_count = sum(1 for kw in query_words if kw in t_lower)

            score = match_count
            if cand['is_faq']:
                score += 2  # Strong baseline preference for curated/official FAQs

            # Program query boost: heavily prioritize comprehensive "All Programs" FAQ
            if is_program_query:
                if 'across five' in t_lower or 'all programs' in t_lower or 'undergraduate programs across' in t_lower:
                    score += 15
                elif 'college of' in t_lower and 'curriculum' in t_lower:
                    score += 5
            else:
                # Never show the all-programs catalog unless the user specifically asked for programs
                if 'across five' in t_lower or 'undergraduate programs across' in t_lower:
                    score -= 15

            # Scholarship query boost
            if is_scholarship_query:
                if 'scholarship' in t_lower or 'subsidy' in t_lower or 'esc' in t_lower or 'voucher' in t_lower or 'ssap' in t_lower:
                    score += 15

            # Tuition query boost
            if is_tuition_query:
                if 'tuition' in t_lower or 'fee' in t_lower or 'downpayment' in t_lower:
                    score += 15

            # Calendar / school events query boost
            if is_calendar_query:
                if any(ck in t_lower for ck in ['academic calendar', 'semester', 'enrollment period', 'first semester', 'second semester', 'preliminary exam', 'midterm exam', 'final exam', 'intramurals', 'foundation day', 'paulinian week', 'commencement', 'important dates', 'school calendar']):
                    score += 15
                # Penalize PBMO submission procedures (publication/reporting rules)
                if 'pbmo' in t_lower or 'publication' in t_lower or 'submit materials' in t_lower or 'reporting school events for publication' in t_lower:
                    score -= 20

            # Person query boost
            if is_person_query:
                is_person_card = (
                    ('is the' in t_lower.split('.')[0]) or
                    any(title in t_lower for title in ['vp for', 'president', 'director', 'dean', 'principal', 'head,']) or
                    any(honorific in t for honorific in ['Dr.', 'Sr.', 'Mr.', 'Ms.', 'Mrs.', 'Engr.', 'Fr.', 'Prof.'])
                )
                if is_person_card:
                    score += 5
                else:
                    score -= 3

            # Only consider candidates that actually match the user query words (or are boosted relevant FAQs)
            if match_count > 0 or cand['is_faq']:
                if score > 0:
                    scored_candidates.append((score, cand))

        scored_candidates.sort(key=lambda x: -x[0])

        # If no verified candidates match the user's specific query, provide a friendly fallback
        if not scored_candidates or scored_candidates[0][0] <= 0:
            fallback_text = (
                "I'm sorry, but I don't have that specific information in my current SPUS knowledge base, student handbook, or website directory.\n\n"
                "For further assistance or inquiries:\n"
                "- **Information Desk**: You may visit the Information Desk located near the **Main Entrance** (Gate 1).\n"
                "- **Campus Administration**: Inquire at the Administration Building on campus.\n"
                "- **Official Website**: Visit [spus.edu.ph](https://spus.edu.ph) for official university announcements.\n\n"
                "Feel free to ask me about academic programs, admissions, tuition fees, scholarships, or campus office locations!"
                '\n\n[SUGGESTIONS: "What programs are offered at SPUS?" | "Does SPUS offer scholarships?" | "Where is the Registrar\'s Office?"]'
            )
            return fallback_text, [], action, action_data

        top_candidates = scored_candidates

        final_blocks = []
        seen = set()
        seen_bodies = set()

        for score, cand in top_candidates:
            clean_txt = cand['text']
            
            # For non-FAQ long text walls, safely truncate while preserving bullet lists
            if not cand['is_faq'] and len(clean_txt) > 1500:
                lines = clean_txt.split('\n')
                clean_txt = '\n'.join(lines[:12]).strip()

            first_line = clean_txt.split('\n')[0].strip()
            body = cand.get('answer_body', clean_txt)
            norm_body = ' '.join(body.lower().split()[:15])

            if first_line not in seen and norm_body not in seen_bodies:
                seen.add(first_line)
                seen_bodies.add(norm_body)
                url = cand.get('url')
                if url:
                    final_blocks.append(f"{clean_txt}\n\n*(Source: {url})*")
                else:
                    final_blocks.append(clean_txt)

            # If the candidate is an authoritative FAQ or has substantial content, it is already a complete answer!
            # Do NOT append secondary fragments that cause duplication.
            if cand['is_faq'] or len(body) > 200:
                break

            if len(final_blocks) >= 2:
                break

        response_text = "\n\n".join(final_blocks)

        # Dynamic follow-up suggestions
        if is_scholarship_query:
            response_text += '\n\n[SUGGESTIONS: "What programs are offered at SPUS?" | "How much is the tuition fee?" | "Where is the Guidance Office?"]'
        elif is_tuition_query:
            response_text += '\n\n[SUGGESTIONS: "Does SPUS offer scholarships?" | "What programs are offered at SPUS?" | "Where is the Finance Office?"]'
        elif is_calendar_query:
            response_text += '\n\n[SUGGESTIONS: "How do I enroll at SPUS?" | "What programs are offered at SPUS?" | "Where is the Registrar\'s Office?"]'
        elif is_program_query:
            response_text += '\n\n[SUGGESTIONS: "What are the admission requirements?" | "How much is the tuition fee?" | "Does SPUS offer scholarships?"]'
        elif is_person_query:
            response_text += '\n\n[SUGGESTIONS: "Who are the other university administrators?" | "Where is the Administration office?" | "How do I contact SPUS?"]'
        elif any(k in msg.lower() for k in ['admission', 'enroll', 'enrol', 'requirement', 'fee', 'tuition']):
            response_text += '\n\n[SUGGESTIONS: "What programs are offered?" | "How much is the tuition fee?" | "Where is the Registrar\'s Office?"]'
        else:
            response_text += '\n\n[SUGGESTIONS: "What programs are offered at SPUS?" | "How do I enroll at SPUS?" | "Where is the Registrar\'s Office?"]'

        return response_text, sources, action, action_data

    def process_query(self, user_message, history=None):
        """
        Takes the user message, retrieves RAG context, and generates a response via LLM or RAG fallback.
        Returns a tuple of (response_text, sources_list, action, action_data).
        """
        import re
        raw_msg = user_message.strip()
        if not raw_msg:
            return "Please type a message.", [], None, None

        # Normalize concatenated typos like "theVP" -> "the VP"
        msg = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw_msg)
        msg = re.sub(r'\s+', ' ', msg)
        
        # Procedural check
        procedural_keywords = ['enroll', 'enrollment', 'how do i', 'how to', 'steps to', 'process for', 'requirements for', 'apply', 'deadline', 'loa', 'leave of absence', 'scholarship', 'add/drop']
        is_procedural = any(kw in msg.lower() for kw in procedural_keywords)

        # Mapping / Navigation Intention check
        mapping_keywords = ['where is', 'where are', 'location of', 'find', 'map of', 'how to get to', 'directions to', 'navigate to', 'way to', 'nasaan', 'saan ang']
        action = None
        action_data = None

        if any(kw in msg.lower() for kw in mapping_keywords):
            action = 'navigate_map'
            destination = self._extract_destination(msg)
            action_data = {'destination': destination}

        # Step 1: Retrieve context from the knowledge base (RAG)
        context, sources = self._build_context(msg)
        
        # If no LLM client is configured, use direct RAG knowledge fallback
        if not self.client and not self.openai_client and not self.gemini_model:
            return self._generate_rag_fallback(msg, sources, action, action_data)

        # Step 2: Build the user message with embedded context
        user_content = (
            f"--- VERIFIED SPUS KNOWLEDGE ---\n"
            f"{context}\n"
            f"--- END KNOWLEDGE ---\n\n"
            f"Student Question: {msg}\n"
            f"Helpful Answer:"
        )

        system_prompt = PAULIBOT_SYSTEM_PROMPT
        if is_procedural:
            system_prompt += "\n\nPROCEDURAL OVERRIDE: The user is asking a procedural question. You are an academic advisor. Answer using ONLY the provided handbook excerpts/knowledge base. Format procedural answers strictly as a numbered Markdown list. Ensure it is easy to read."

        # Step 3: Try Groq API
        if self.client:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": user_content})

            try:
                chat_completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.6,
                    max_tokens=2048,
                    top_p=0.9,
                    stream=False,
                )
                response_text = chat_completion.choices[0].message.content.strip()
                logger.info(f"Groq response generated successfully for query: '{msg[:50]}...'")
                return response_text, sources, action, action_data
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Groq API error or rate limit: {error_msg}. Attempting OpenAI fallback...")

        # Step 4: Try OpenAI API if Groq was unavailable or reached limits/tokens
        if self.openai_client:
            try:
                messages = [{"role": "system", "content": system_prompt}]
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": user_content})

                completion = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.6,
                    max_tokens=2048,
                )
                response_text = completion.choices[0].message.content.strip()
                logger.info(f"OpenAI fallback response generated successfully for query: '{msg[:50]}...'")
                return response_text, sources, action, action_data
            except Exception as e:
                logger.warning(f"OpenAI API fallback error: {e}. Falling back to next tier...")

        # Step 5: Try Gemini API if Groq and OpenAI were unavailable or failed
        if self.gemini_model:
            try:
                full_prompt = f"{system_prompt}\n\n{user_content}"
                response = self.gemini_model.generate_content(full_prompt)
                return response.text.strip(), sources, action, action_data
            except Exception as e:
                logger.error(f"Gemini API error: {e}")

        # Step 6: If all LLM calls fail (e.g. rate limit, quota, offline), fallback to direct RAG answer!
        return self._generate_rag_fallback(msg, sources, action, action_data)

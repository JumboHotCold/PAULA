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

PAULIBOT_SYSTEM_PROMPT = """You are PauliBot, the official AI campus assistant for Saint Paul University Surigao (SPUS).
You are a warm, friendly, and knowledgeable virtual guide created to help students, parents, and visitors with university-related inquiries.

CORE RULES:
1. You must ONLY answer based on the verified SPUS knowledge base provided in each user message. NEVER use outside knowledge or make up information.
2. If information is NOT in the provided context, respond: "I'm sorry, but I don't have that specific information in my current knowledge base for SPUS. For further assistance, please contact the university administration." (in the student's language)
3. You are NOT a general-purpose AI. Politely decline non-SPUS topics.

LANGUAGE GUIDELINES:
- Detect the language of the CURRENT message ONLY. Ignore previous messages.
- If the message is in Filipino, respond entirely in Filipino.
- If the message is in English, respond entirely in English.
- If the message mixes Filipino and English (Taglish), respond in Taglish.
- Always keep a warm, friendly, and approachable tone — like a helpful campus guide.

GREETING & IDENTITY:
- Introduce yourself as PauliBot ONLY in the very first message of a conversation or when explicitly asked "Who are you?".
- For regular follow-up questions, jump straight to the answer without restating your name or giving a generic welcome.
- For greetings (hi, hello, kamusta, hey, good morning), respond with a friendly greeting in the SAME language. If it's the start of the chat, introduce yourself. If it's midway, just greet back naturally.

ANSWER STYLE:
- Be thorough but concise. Avoid redundant preambles.
- Maintain a professional and academic tone.
- Use bullet points or numbered lists when listing multiple items.

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
        self.gemini_key = (os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', '')).strip()

        # Ignore placeholder values
        if self.groq_key in ('your_groq_api_key_here', ''):
            self.groq_key = None
        if self.gemini_key in ('your_gemini_api_key_here', ''):
            self.gemini_key = None

        self.client = None
        self.gemini_model = None

        if self.groq_key:
            try:
                self.client = Groq(api_key=self.groq_key)
                self.model_name = "llama-3.3-70b-versatile"
                logger.info(f"PauliBot v2 initialized with Groq model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")

        if not self.client and self.gemini_key:
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
        results = self.rag.search(query, limit=8)
        if not results:
            return "No relevant knowledge base entries found for this query.", []
        
        context = "Here is the relevant verified knowledge base for Saint Paul University Surigao (SPUS):\n\n"
        sources = []
        for i, res in enumerate(results):
            context += f"- {res['text']}\n"
            sources.append({
                "title": res['document_title'],
                "page": None,
                "url": res['source_url']
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

    def _generate_rag_fallback(self, msg, sources, action, action_data):
        """Generates a direct response using retrieved knowledge base entries when LLM is unavailable."""
        results = self.rag.search(msg, limit=5)
        if not results:
            return (
                "I'm sorry, but I don't have that specific information in my current knowledge base for SPUS. "
                "For further assistance, please contact the university administration."
            ), sources, action, action_data

        ans_lines = []
        for res in results[:3]:
            txt = res['text']
            if txt.startswith("FAQ about "):
                # Format FAQ answer nicely
                parts = txt.split(" - ", 1)
                if len(parts) == 2:
                    txt = f"**{parts[0]}**\n{parts[1]}"
            ans_lines.append(txt)

        response_text = "Here is what I found in the SPUS Knowledge Base regarding your inquiry:\n\n" + "\n\n".join(ans_lines)
        response_text += '\n\n[SUGGESTIONS: "What are the enrollment requirements?" | "Where is the Registrar\'s office?" | "How do I contact SPUS?"]'
        return response_text, sources, action, action_data

    def process_query(self, user_message, history=None):
        """
        Takes the user message, retrieves RAG context, and generates a response via LLM or RAG fallback.
        Returns a tuple of (response_text, sources_list, action, action_data).
        """
        msg = user_message.strip()
        if not msg:
            return "Please type a message.", [], None, None
        
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
        if not self.client and not self.gemini_model:
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
                    max_tokens=1024,
                    top_p=0.9,
                    stream=False,
                )
                response_text = chat_completion.choices[0].message.content.strip()
                logger.info(f"Groq response generated successfully for query: '{msg[:50]}...'")
                return response_text, sources, action, action_data
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Groq API error: {error_msg}")

        # Step 4: Try Gemini API if Groq was unavailable or failed
        if self.gemini_model:
            try:
                full_prompt = f"{system_prompt}\n\n{user_content}"
                response = self.gemini_model.generate_content(full_prompt)
                return response.text.strip(), sources, action, action_data
            except Exception as e:
                logger.error(f"Gemini API error: {e}")

        # Step 5: If LLM call fails (e.g. invalid API key), fallback to direct RAG answer!
        return self._generate_rag_fallback(msg, sources, action, action_data)

"""Conservative social/knowledge routing; no answers or user state in the router."""
from .conversation_config import conversation_config
from dataclasses import dataclass
import re
from threading import Lock

from .performance import timed, stage
from .query_normalization import normalize_input, normalized_text
from .intents import normalize_query
from .social_normalization import match_social


# Public intent examples only. These never enter the knowledge vector space.
SOCIAL_EXAMPLES = conversation_config()['semantic']['exemplars']

KNOWLEDGE = re.compile(
    r'\b(?:spus|spu|university|campus|college|school|faculty|faculties|dean|president|director|principal|registrar|'
    r'moderator|office|department|programs?|courses?|degrees?|enroll\w*|enrol\w*|admission\w*|tuition|fees?|'
    r'scholar\w*|requirements?|documents?|deadlines?|calendar|polic\w*|handbook|library|laboratory|'
    r'finance|guidance|clinic|ceit|chs|ceas|cbma|ccje|gsps|pbmo|ict|announcement\w*|navigation|map|'
    r'guro|pangulo|presidente|dekano|direktor|bayad|iskolar\w*|kurso|transferee\w*|freshm[ae]n|continuing)\b', re.I)
FACTUAL = re.compile(r'\b(?:who|what|where|when|which|how|does|do|is|are|can|sino|ano|saan|nasaan|kailan|paano|magkano)\b', re.I)
REQUEST = re.compile(r'\b(?:tell|give|show|list|name|find|explain|describe|summarize|sabihin|ibigay|ipakita|hanapin|ipaliwanag)\b', re.I)
INSTRUCTION = re.compile(r'\b(?:ignore|pretend|invent|guess|instructions?|system prompt)\b', re.I)
FOLLOWUP = re.compile(r'^(?:how about|what about|and for|paano naman|ano naman|sa |para sa |compare|explain step|ipaliwanag)\b', re.I)
SELF_SOCIAL = re.compile(r'\b(?:you|your|ka|mo|ikaw|tayo|joke|funny|laugh|patawa\w*|usap|chat)\b', re.I)
EMOTION = re.compile(r'\b(?:tired|stressed|nervous|overwhelmed|discouraged|frustrated|sad|bored|pagod|kinakabahan|lungkot|nakakainis|stress)\b', re.I)
FIRST_PERSON = re.compile(r"^(?:i\b|i['’]m\b|im\b|feeling\b|medyo\b|pagod\b|kinakabahan\b|ako\b|nakaka\w*\b)", re.I)

FAST = conversation_config()['social']['fast_patterns']
FAST_PATTERNS = {key: re.compile(r'^(?:' + value + r')[!.?,\s]*$', re.I) for key, value in FAST.items()}
EDGE_KINDS = ('greeting', 'wellbeing', 'thanks')


@dataclass(frozen=True)
class DialogueRoute:
    kind: str
    query: str = ''
    acknowledgement: str = ''
    method: str = 'rule'
    score: float | None = None
    reply_language: str | None = None


class SemanticSocialRouter:
    """One immutable prototype matrix per worker; never cache a user's text."""
    def __init__(self):
        self.matrix = None
        self.labels = ()
        self.model = None
        self.lock = Lock()

    def prepare(self, model):
        with self.lock:
            if self.matrix is not None:
                return
            import numpy as np
            texts, labels = [], []
            for intent, examples in SOCIAL_EXAMPLES.items():
                texts.extend(examples)
                labels.extend([intent] * len(examples))
            with stage('social_router_prepare'):
                matrix = np.asarray(model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype=float)
            if matrix.shape != (len(texts), 384) or not np.isfinite(matrix).all():
                raise ValueError('Invalid social routing prototype vectors')
            self.model, self.labels, self.matrix = model, tuple(labels), matrix

    def classify(self, text):
        if self.matrix is None:
            return None
        import numpy as np
        with stage('social_query_embedding'):
            vector = np.asarray(self.model.encode(text, normalize_embeddings=True, show_progress_bar=False), dtype=float)
        if vector.shape != (384,) or not np.isfinite(vector).all():
            return None
        scores = self.matrix @ vector
        ranked = sorted(((max(float(scores[i]) for i, label in enumerate(self.labels) if label == kind), kind)
                         for kind in SOCIAL_EXAMPLES), reverse=True)
        score, kind = ranked[0]
        # Intent similarity thresholds are independent of the unchanged .45
        # document-retrieval cutoff. Low-margin cases fail toward clarification.
        if kind == 'knowledge' or score < 0.65 or score - ranked[1][0] < 0.08:
            return None
        return kind, round(score, 4)


social_router = SemanticSocialRouter()


def language_for(message, history=(), preference=None):
    preference = preference if preference in ('en', 'fil') else None
    current = language_request(message)
    if current:
        return current
    if preference:
        return preference
    for text in [row.get('content', '') for row in reversed(history) if row.get('role') == 'user']:
        requested = language_request(text)
        if requested:
            return requested
    return 'fil' if re.search(r'\b(?:paano|saan|nasaan|ano|sino|ang|mga|po|naman|salamat|pagod|kinakabahan|'
                              r'gets|musta|kamusta|kumusta|usap|patawa\w*|sige|tulong|ako|bakit|maling|pakilala|magpakilala)\b', message, re.I) else 'en'


def language_request(text):
    value = normalized_text(text)
    if re.fullmatch(r'(?:please )?(?:can we (?:speak|chat|talk) in |let s (?:speak|chat|talk) in |'
                    r'pwede bang |puwede bang |mag |in )?(?:filipino|tagalog|taglish)(?: please| po| tayo)?', value):
        return 'fil'
    if re.fullmatch(r'(?:please )?(?:can we (?:speak|chat|talk) in |let s (?:speak|chat|talk) in |in )?english(?: please| po)?', value):
        return 'en'
    return None


def local_self_intent(text):
    """Whole-command self requests only; extra clauses retain normal retrieval."""
    return next((kind for kind in ('identity', 'capabilities') if FAST_PATTERNS[kind].fullmatch(text)), None)


def task_tail(text):
    return bool(FACTUAL.search(text) or KNOWLEDGE.search(text) or FOLLOWUP.search(text) or local_self_intent(text))


def social_edges(message):
    """Strip only whole social clauses at the edges; preserve the request span."""
    text, ack = message.strip(), ''
    for _ in range(2):
        for kind in EDGE_KINDS:
            match = re.match(r'^(?:' + FAST[kind] + r')(?:[!?,.:;]+\s*|\s+(?:and|at)\s+)(.+)$', text, re.I)
            if match and task_tail(match.group(1)):
                text, ack = match.group(1).strip(), 'greeting' if kind in ('greeting', 'wellbeing') else kind
                break
        else:
            break
    # Remove a closing thank-you only when a substantive request remains.
    match = re.match(r'^(.*?)(?:[!.?,;]\s*|\s+)(?:' + FAST['thanks'] + r')[!.?\s]*$', text, re.I)
    if match and task_tail(match.group(1)):
        text, ack = match.group(1).strip(), ack or 'thanks'
    # Abbreviations/typos may be stripped only as an isolated social edge.
    # Keep the factual span verbatim, including dates, negation, and identifiers.
    match = re.match(r'^([^!?,.:;\n]{1,100})[!?,.:;]+\s*(.+)$', text, re.S)
    if match:
        social = match_social(match.group(1))
        tail = match.group(2).strip()
        if social and social.kind in EDGE_KINDS and task_tail(tail):
            text, ack = tail, 'greeting' if social.kind in ('greeting', 'wellbeing') else social.kind
    match = re.match(r'^(.*)[!?,;.]\s*([^!?,;.]+)[!?.\s]*$', text, re.S)
    if match:
        social = match_social(match.group(2))
        head = match.group(1).strip()
        if social and social.kind == 'thanks' and task_tail(head):
            text, ack = head, ack or 'thanks'
    return text, ack


@timed('dialogue_routing')
def route_turn(message, semantic=True):
    if not isinstance(message, str) or not message.strip():
        return DialogueRoute('knowledge', message if isinstance(message, str) else '')
    text = normalize_query(message)
    if len(text) > 2000:
        return DialogueRoute('knowledge', text)
    if not re.search(r'\w', text, re.UNICODE):
        return DialogueRoute('repair')
    if language_request(text):
        return DialogueRoute('language', method='rule')
    # A comma before a vocative ("Hello, PAULA") is punctuation, not a
    # second request. Do not normalize the substantive retrieval query.
    social_text = re.sub(r'[,;:]\s*', ' ', normalize_input(text).punctuated)
    # Correct a greeting typo only as a whole social utterance; never change
    # these spans in a factual request or somebody's name.
    social_text = re.sub(r'^(?:helo|helloo|hllo)(?=\b)', 'hello', social_text, flags=re.I)
    for kind, pattern in FAST_PATTERNS.items():
        if pattern.fullmatch(social_text):
            return DialogueRoute(kind)
    social = match_social(social_text)
    if social:
        return DialogueRoute(social.kind, method=social.method, score=social.score, reply_language=social.reply_language)
    query, acknowledgement = social_edges(text)
    if query != text:
        self_intent = local_self_intent(query)
        if self_intent:
            return DialogueRoute(self_intent, acknowledgement=acknowledgement)
        return DialogueRoute('knowledge', query, acknowledgement)
    # Explicit requests, domain entities, numerical conditions and references
    # cannot be answered by model memory, even if they contain a social phrase.
    if (KNOWLEDGE.search(text) or FOLLOWUP.search(text) or
            re.search(r'\d|https?://', text) or INSTRUCTION.search(text)):
        # A simple emotional statement can receive general reassurance without
        # interpreting it as a request for university facts.
        if (FIRST_PERSON.search(text) and EMOTION.search(text) and not FACTUAL.search(text) and
                not REQUEST.search(text) and not INSTRUCTION.search(text) and not re.search(r'\d|https?://', text)):
            return DialogueRoute('support')
        return DialogueRoute('knowledge', text)
    if re.match(r'^(?:who|where|when|which|sino|saan|nasaan|kailan)\b', text, re.I):
        return DialogueRoute('knowledge', text)
    if re.search(r'\b(?:it|its|their|them|that|those|ito|iyon|nila|doon)\b', text, re.I) and FACTUAL.search(text):
        return DialogueRoute('knowledge', text)
    if FIRST_PERSON.search(text) and EMOTION.search(text) and not FACTUAL.search(text) and not REQUEST.search(text):
        return DialogueRoute('support')
    # An unknown single word can be a person's name or a future KB subject.
    # Known aliases were handled above; don't turn lookalike nouns into small
    # talk through semantic proximity (e.g. thinks/tanks versus thanks).
    if len(re.findall(r'\w+', text)) == 1 and not EMOTION.fullmatch(text):
        return DialogueRoute('knowledge', text)
    if semantic:
        try:
            result = social_router.classify(text)
        except Exception:
            result = None
        if result:
            kind, score = result
            # General factual questions cannot become small talk merely through
            # embedding overlap. Personal/social requests have explicit affordances.
            if (not FACTUAL.search(text) and not REQUEST.search(text)) or SELF_SOCIAL.search(text):
                return DialogueRoute(kind, method='semantic', score=score)
    if FACTUAL.search(text):
        return DialogueRoute('knowledge', text)
    # Unknown phrases and future entities belong to the normal contextual RAG
    # path. Absence from an intent vocabulary is never proof of small talk.
    return DialogueRoute('knowledge', text)

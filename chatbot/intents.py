"""Deterministic clarification and navigation; no generated facts or global state."""
import re
from .performance import timed


ENROLL_QUESTION = 'Are you enrolling as an incoming college freshman, a transferee, or an old/continuing college student?'
ENROLL_QUESTION_FIL = 'Ikaw ba ay incoming college freshman, transferee, o old/continuing college student?'
ENROLL_CHOICES = ('Incoming college freshman', 'Transferee student', 'Old/continuing college student')
NAV_QUESTION = 'Which campus office or building would you like to find?'
NAV_QUESTION_FIL = 'Aling opisina o gusali sa campus ang gusto mong puntahan?'
CATEGORY_LABELS = {
    'freshmen': 'incoming college freshmen',
    'transferee': 'transferee college students',
    'continuing': 'old continuing college students',
}

# Deliberately exclude ambiguous aliases such as "it", "dean", "payment",
# "scholarship", and "community". IDs match frontend CAMPUS_NODES.
DESTINATIONS = {
    'registrar_office': ('Registrar Office', ('registrar', 'registrar office', 'registrars office', 'registration office')),
    'finance_office': ('Finance Office', ('finance office', 'finance', 'cashier', 'accounting office')),
    'guidance_office': ('Guidance Office', ('guidance', 'guidance office', 'counseling office')),
    'cafeteria': ('Cafeteria', ('cafeteria', 'canteen', 'dining hall')),
    'cathedral': ('Cathedral', ('cathedral', 'church', 'chapel', 'simbahan')),
    'clinic': ('Clinic', ('clinic', 'infirmary', 'health center')),
    'sao': ('Student Affairs Office', ('sao', 'student affairs', 'student affairs office')),
    'ict_office': ('ICT Office', ('ict', 'ict office')),
    'music_room': ('Music Room', ('music room',)),
    'presidents_office': ('Office of the President', ('president office', 'presidents office', 'office of the president')),
    'presidents_boardroom': ('President Boardroom', ('boardroom', 'president boardroom', 'presidents boardroom')),
    'hr_office': ('Human Resource Management Office', ('hr', 'hrmo', 'human resource office', 'human resources')),
    'science_building': ('Science Building', ('science building', 'science lab', 'laboratory')),
    'open_court': ('Open Court', ('open court', 'court', 'basketball court')),
    'student_lounge_upper': ('Student Lounge Upper', ('student lounge upper', 'upper lounge')),
    'student_lounge_lower': ('Student Lounge Lower', ('student lounge lower', 'lower lounge')),
    'cfo': ('CFO', ('cfo', 'campus front office')),
    'ccje': ('College of Criminal Justice Education', ('ccje', 'criminal justice', 'criminology')),
    'ceit': ('College of Engineering and Information Technology', ('ceit', 'engineering', 'information technology')),
    'community_dev': ('Community Development Services', ('community development', 'community development services')),
    'dean_graduate': ('Dean Graduate School', ('graduate school', 'dean graduate school')),
    'main_entrance': ('Main Entrance', ('main entrance', 'main gate', 'entrance', 'gate')),
    'visitors_lodge': ('Visitors Lodge', ('visitors lodge', 'visitor lodge')),
    'snb_building': ('SNB Building', ('snb', 'snb building')),
    'inspire': ('INS PIRE', ('inspire', 'ins pire', 'scholarship office')),
    'college_education': ('College of Education Arts and Science', ('college of education', 'ceas')),
    'san_nicolas_bldg': ('San Nicolas Building', ('san nicolas', 'san nicolas building')),
    'restroom_left': ('Restroom Left Wing', ('restroom left', 'left restroom')),
    'restroom_lower': ('Restroom Lower', ('restroom lower', 'lower restroom')),
    'sp_building': ('St Paul Building', ('sp building', 'st paul building', 'saint paul building')),
}

VOCABULARY = set('''where location directions navigate registrar enrollment enrolment
    enroll enrolling admission requirements documents procedure freshman freshmen
    transferee continuing faculty scholarship tuition finance guidance cafeteria
    cathedral clinic entrance building office university president director principal dean
    choose benefits program course calendar contact application academic schedule'''.split())
PROTECTED_WORDS = {'officer', 'officers', 'finances', 'financial', 'offices',
                   'there', 'their', 'them', 'those', 'this', 'these', 'that', 'here',
                   'chose', 'chosen', 'choice', 'benefit', 'police'}


def _distance(left, right):
    """Compatibility wrapper for the shared, bounded matching implementation."""
    from .spelling import edit_distance
    return edit_distance(left, right)


@timed('normalization')
def normalize_query(message):
    """Matching-only compatibility entry point; no phrase-specific typo list."""
    from .spelling import matching_plan
    return matching_plan(message).matching


def enrollment_category(message):
    patterns = {
        'freshmen': r'\b(freshm[ae]n|first[ -]year|new college students?)\b',
        'transferee': r'\b(transferee?s?|transferring|transfer student)\b',
        'continuing': r'\b(continuing|old students?|old college students?)\b',
    }
    # Do not infer returnee/re-admission status or resolve negated categories.
    if re.search(r'\b(not|hindi|returnee|readmission|re-admission)\b', message, re.I):
        return None
    found = [key for key, pattern in patterns.items() if re.search(pattern, message, re.I)]
    return found[0] if len(found) == 1 else None


def enrollment_subject(title):
    """Separate an FAQ subject from its parenthesized source document code."""
    return re.sub(r'\(\s*Document\s+[^()]+\)', '', title, flags=re.I).strip()


def enrollment_request(message):
    if re.search(r'\b(account|password|website account|login)\b', message, re.I):
        return False
    if not re.search(r'\b(enroll\w*|enrol\w*|admission)\b', message, re.I) and not (
            enrollment_category(message) and re.search(r'\b(requirements?|documents?)\b', message, re.I)):
        return False
    if re.search(r'\b(when|kailan|deadline|calendar|fee|tuition|pay|payment)\b', message, re.I):
        return False
    return bool(re.search(r'\b(how|paano|steps?|procedure|process|requirements?|documents?|papers|want|help)\b', message, re.I)
                or re.fullmatch(r'(enroll|enrol|enrollment|enrolment)[!.? ]*', message, re.I))


def enrollment_resolution(message, history=None):
    """Return (needs_category, resolved_query), using only a pending question."""
    request = message
    selector=message
    previous = pending_request(history, 'enrollment')
    if previous:
        from .clarifications import selection_view
        selector=selection_view(message)
    if not enrollment_request(request) or selector != message:
        # These exact labels are enrollment controls supplied by PAULA. Recover
        # their procedure intent if an older client lost its clarification pair.
        # Other statements ('I am an old student') still require pending context.
        choice = message.strip().rstrip('.!?').casefold() in {label.casefold() for label in ENROLL_CHOICES}
        if not previous and choice:
            previous = 'How do I enroll at SPUS?'
        # Only a short category reply can resolve a pending clarification.
        reply_words = set(re.findall(r'\w+', selector.lower()))
        allowed = set('i am im m a an incoming college freshman freshmen first year new transferee transferees transfer '
                      'student students old continuing po ako ay isang na'.split())
        if not previous or len(message.split()) > 10 or not enrollment_category(selector) or not reply_words.issubset(allowed):
            return False, message
        request = previous
    if re.search(r'\b(grade\s*\d+|kindergarten|nursery|senior high|junior high|basic education|graduate|masters|doctoral)\b', request, re.I):
        return False, message
    category = enrollment_category(selector)
    if category is None:
        return True, message
    # SPUS is the implicit institution for a generic campus-assistant question.
    # Retain specific modifiers/named institutions rather than rewriting them.
    generic = set('how do i can to enroll enrol enrollment enrolment process procedure steps please help me '
                  'paano mag sa at the college university student students freshman freshmen transferee '
                  'old continuing am a an new want would like know requirements documents need for what'.split())
    if set(re.findall(r'\w+', request.lower())).issubset(generic):
        request = request.rstrip(' ?!.') + ' at SPUS?'
    return False, f'{request} ({CATEGORY_LABELS[category]})'


def pending_request(history, kind):
    if not isinstance(history, list) or len(history) < 2:
        return None
    user, assistant = history[-2:]
    if user.get('role') != 'user' or assistant.get('role') != 'assistant':
        return None
    from .response_style import strip_intro
    prefixes = (ENROLL_QUESTION, ENROLL_QUESTION_FIL) if kind == 'enrollment' else (NAV_QUESTION, NAV_QUESTION_FIL)
    if not strip_intro(assistant.get('content', '')).startswith(prefixes):
        return None
    previous = user.get('content', '')
    return normalize_query(previous) if isinstance(previous, str) else None


def guest_clarification_history(value):
    """Bounded transient context is used only for clarification, never as facts."""
    if not isinstance(value, list) or len(value) != 2:
        return []
    for row, role in zip(value, ('user', 'assistant')):
        if not isinstance(row, dict) or row.get('role') != role:
            return []
        if not isinstance(row.get('content'), str) or len(row['content']) > 2000:
            return []
    return value if pending_request(value, 'enrollment') or pending_request(value, 'navigation') else []


def navigation_intent(message):
    if re.search(r'\b(online|website|webpage|portal|download|url|email)\b', message, re.I):
        return False
    if re.search(r'\b(directions?(?:\s+to)?|navigate(?:\s+to)?|take me to|how (?:do i |can i )?get to|map(?:\s+of)?)\b', message, re.I):
        return True
    if re.search(r'\b(submit|pay|apply|enroll|enrol|register|magbayad|magpasa|forms?|requirements?|documents?|information|hours|phone|contact|faculty|lineup)\b', message, re.I):
        return False
    if re.search(r'\b(nasaan|saan|where (?:is|are|can i find)|location of)\b', message, re.I):
        return True
    return bool(navigation_destinations(message) and re.search(r'\b(find|locate|location)\b', message, re.I))


def navigation_destinations(message):
    text = ' '.join(re.findall(r'\w+', message.lower()))
    # For a route from A to B, B is the destination. The map asks for origin.
    route = re.search(r'\bfrom\b.+?\bto\s+(.+)', text)
    if route:
        text = route.group(1)
    matches = []
    for node, (_, aliases) in DESTINATIONS.items():
        for alias in aliases:
            for match in re.finditer(r'\b' + re.escape(alias) + r'\b', text):
                matches.append((match.start(), match.end(), node))
    accepted = []
    for start, end, node in sorted(matches, key=lambda row: -(row[1] - row[0])):
        if not any(start < other_end and end > other_start for other_start, other_end, _ in accepted):
            accepted.append((start, end, node))
    return list(dict.fromkeys(node for _, _, node in sorted(accepted)))


def navigation_choice(message, history):
    if not pending_request(history, 'navigation'):
        return False
    from .clarifications import selection_view
    message=selection_view(message)
    text = ' '.join(re.findall(r'\w+', message.lower()))
    text = re.sub(r'^(?:the |please )| please$', '', text).strip()
    return any(text in aliases or text == label.lower()
               for label, aliases in DESTINATIONS.values())

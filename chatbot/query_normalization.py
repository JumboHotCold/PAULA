"""Shared lexical canonicalization; no institutional facts are encoded here.

Keep display text untouched. Aliases align questions and evidence; dates,
negation, qualification and historical language are deliberately preserved.
"""
import re
import unicodedata

FRESHNESS_WORDS = {'currently', 'now', 'today', 'ngayon', 'kasalukuyan'}
ROLE_WORDS = {'president', 'vp', 'dean', 'director', 'principal', 'registrar', 'moderator', 'head'}
ALIASES = {
    'presidente':'president', 'pangulo':'president', 'dekano':'dean', 'direktor':'director',
    'akademiko':'academic', 'academics':'academic',
}


def normalized_text(value):
    value=unicodedata.normalize('NFKC',value or '')
    return ' '.join(re.findall(r'\w+',value.casefold().replace('&',' and ')))


def canonical_text(value):
    text=normalized_text(value)
    text=re.sub(r'\b(?:vice president|bise presidente|bise pangulo)\b','vp',text)
    text=re.sub(r'\binformation and communications technology\b','ict',text)
    text=re.sub(r'\bsa kasalukuyan\b','currently',text)
    words = (ALIASES.get(word,word) for word in text.split())
    return ' '.join(word[:-1] if word.endswith('s') and word[:-1] in ROLE_WORDS else word for word in words)


def roles_in(value):
    return set(canonical_text(value).split()) & ROLE_WORDS


def role_supported(query,role):
    requested=roles_in(query)
    actual=roles_in(role)
    if 'president' in requested and 'president' not in actual:
        return False
    # Canonical VP is not a president identity. A mixed prose section cannot
    # satisfy a precise personnel role unless its actual role metadata agrees.
    return requested.issubset(actual)


def person_key(value):
    """Candidate identity key, not proof that spelling variants are one person."""
    value=(value or '').split(',',1)[0]
    value=re.sub(r'^(?:(?:dr|mr|mrs|ms|sr|fr|engr|prof|arch)\.?\s+)+','',value,flags=re.I)
    return normalized_text(value)


def freshness_requested(value):
    return bool(set(canonical_text(value).split()) & (FRESHNESS_WORDS|{'current','latest'}))

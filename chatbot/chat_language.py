"""Config-backed chat shorthand and social-only modifiers; never facts."""
import re
from .conversation_config import conversation_config
from .query_normalization import normalize_input


def expand_shorthand(text, *, person_lookup=False):
    aliases=conversation_config().get('matching',{}).get('shorthand',{})
    # Preserve name/initial spans after explicit person lookup frames. Query
    # prefixes are grammatical, but name identifiers must stay literal.
    boundary=re.search(r'\b(?:who\s+is|sino\s+si|contact(?:\s+of)?|email(?:\s+of)?)\s+',text,re.I) if person_lookup else None
    def expand(match):
        raw=match.group()
        if raw.isupper() or (boundary and match.start()>=boundary.end()):return raw
        return aliases.get(raw.casefold(),raw)
    return re.sub(r'\b[^\W\d_]+\b',expand,text)


def social_core(text):
    classes=conversation_config().get('matching',{}).get('modifiers',{})
    words=normalize_input(expand_shorthand(text)).spaced.split()
    removed={word for spec in classes.values() for word in spec['tokens']}
    language=next((spec.get('language') for spec in classes.values() if spec.get('language') and set(words)&set(spec['tokens'])),None)
    return ' '.join(word for word in words if word not in removed),language

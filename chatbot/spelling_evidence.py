"""Bounded ambiguity resolution using existing evidence gates, never an LLM."""
from dataclasses import dataclass
from itertools import product
import re
from .evidence_identity import evidence_key
from .grounding import eligible_evidence
from .intents import navigation_destinations, navigation_intent
from .performance import timed
from .query_normalization import normalized_text
from .spelling import nearest,vocabulary

MAX_CANDIDATES=6


def inflection_key(word):
    """Small morphological grouping; this key alone never authorizes an answer."""
    if len(word)>5 and word.endswith('ies'):return word[:-3]+'y'
    for suffix in ('ing','ed','s'):
        if len(word)>len(suffix)+3 and word.endswith(suffix):return word[:-len(suffix)]
    return word


def candidate_questions(plan):
    if not plan.ambiguous:return (plan.matching,)
    words=list(dict.fromkeys(plan.ambiguous))
    choices=[nearest(word,vocabulary())[1] for word in words]
    size=1
    for values in choices:size*=len(values)
    if not size or size>MAX_CANDIDATES:return ()
    queries=[]
    for replacements in product(*choices):
        query=plan.matching
        for word,target in zip(words,replacements):
            query=re.sub(r'\b'+re.escape(word)+r'\b',target,query,flags=re.I)
        queries.append(query)
    return tuple(dict.fromkeys(queries))


@dataclass(frozen=True)
class CandidateResolution:
    status: str
    query: str=''
    choices: tuple=()
    attempts: int=0
    families: int=0


@timed('spelling_evidence')
def resolve_candidates(plan,rag):
    queries=candidate_questions(plan)
    groups={}
    for query in queries:
        key=tuple(inflection_key(word) for word in normalized_text(query).split())
        groups.setdefault(key,[]).append(query)
    if plan.protected_name or not plan.ambiguous or not queries:
        return CandidateResolution('clarification',choices=queries,families=len(groups))
    supported=[]
    attempts=0
    for query in queries:
        attempts+=1
        # Curated navigation identifiers are structured evidence. A generic
        # registration paragraph cannot establish a physical office location.
        locations=navigation_destinations(query)
        if navigation_intent(query) and len(locations)==1:
            supported.append((query,('navigation',locations[0])))
            continue
        outcome=rag.retrieve(query,limit=3)
        if outcome.status=='unavailable':return CandidateResolution('unavailable',attempts=attempts,families=len(groups))
        if outcome.status in ('conflict','ambiguous'):
            return CandidateResolution('conflict',choices=queries,attempts=attempts,families=len(groups))
        evidence=[row for row in outcome.evidence if eligible_evidence(query,row)]
        if re.match(r'^(?:where\s+(?:is|are)|nasaan|saan)\b',query,re.I):
            evidence=[row for row in evidence if row.get('source_type')=='campus_map' or row.get('record_type')=='location']
        if evidence:supported.append((query,evidence_key(evidence[0])))
    if supported and len({key for _,key in supported})==1:
        return CandidateResolution('resolved',supported[0][0],attempts=len(queries),families=len(groups))
    # Collapse inflection-equivalent choices for presentation only. Divergent
    # evidence still demands clarification; a common stem is never grounding.
    representatives=tuple(values[0] for values in groups.values())
    return CandidateResolution('clarification',choices=representatives,attempts=len(queries),families=len(groups))

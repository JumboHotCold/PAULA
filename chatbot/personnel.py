"""Exact personnel lookup over structured, source-linked website records.

This is a database lookup, not a relaxed semantic similarity threshold. Only
short, explicit identity/roster requests enter this path. Extra constraints
(dates, historical holders, named institutions, qualifications) fail closed.
"""
import re
from urllib.parse import urlsplit

from .grounding import DEPARTMENTS, FACULTY_RE, NAME_RE, departments, eligible_evidence, terms
from .web_crawler import PERSON_CATEGORY, ROSTER_CATEGORY
from .retrieval_types import EvidenceList
from .query_normalization import canonical_text, person_key, roles_in, role_supported, freshness_requested
from .evidence_identity import consolidate_evidence
from .performance import timed


def name_request(query):
    match=re.match(r'^(?:who is|sino si|tell me about)\s+(.+?)[?.!]*$',query,re.I)
    if not match or roles_in(query):return ''
    text=match.group(1).strip(' ?!.')
    if re.search(r'\b(for|at|of|in|our|my|your|responsible|handling)\b',text,re.I):return ''
    return person_key(text) if len(person_key(text).split())>=2 else ''


def lookup_kind(query):
    if not re.search(r'\b(who|sino|faculty|lineup|list|name)\b', query, re.I):
        return None
    if re.search(r'\b(previous|former|past|history|historical|before|after|next|will|was|were|appointed|salary|qualification|qualifications)\b|\d', query, re.I):
        return None
    query_terms = terms(query) - {'uh', 'um', 'hey', 'hello', 'now', 'today', 'currently', 'members'}
    if FACULTY_RE.search(query) and len(departments(query)) == 1:
        return 'roster' if query_terms <= set(DEPARTMENTS) | {'faculty'} else None
    roles = {'president', 'director', 'dean', 'registrar', 'principal', 'head', 'vp'}
    allowed = roles | set(DEPARTMENTS) | {'ict', 'academic', 'services', 'finance', 'prism', 'basic', 'education',
                                         'administrative', 'treasury', 'library', 'human', 'resources', 'management'}
    if query_terms & roles and query_terms <= allowed:return 'role'
    return 'name' if name_request(query) else None


def structured_person(obj):
    match = re.fullmatch(r'Section: ([^\n]+)\nName: ([^\n]+)\nRole: ([^\n]+)', obj.content)
    return dict(zip(('section', 'name', 'role'), match.groups())) if match else None


def role_matches(query, person):
    role = person['role']
    # A university president query must not match a vice president or a
    # director merely because their section mentions top management.
    if 'president' in roles_in(query):
        if not re.fullmatch(r'(?:university\s+)?president', role, re.I):
            return False
    if not role_supported(query,role):return False
    # A section named "Academic Services" contains several different VPs.
    # Role qualifiers must describe the person's role, not a nearby heading.
    qualifiers=terms(query)-roles_in(query)-{'members','services','service','office'}
    actual=terms(role)
    return qualifiers.issubset(actual)


def website_result(obj, person=None):
    result = dict(question=obj.title, document_title=obj.title, answer=obj.content,
                  text=obj.content, source_type='website', source_url=obj.url,
                  source_office=person['section'] if person else None,
                  retrieved_at=obj.last_scraped.isoformat(), retrieval_method='exact_personnel',
                  record_type='webresource',record_id=getattr(obj,'pk',None))
    if obj.category == ROSTER_CATEGORY:
        result['personnel_section'] = obj.title.removeprefix('SPUS Faculty Directory | ')
    if person:
        result.update(answer=f"{person['name']} — {person['role']}", personnel_role=person['role'],
                      personnel_name=person['name'], personnel_section=person['section'])
        # Eligibility uses the section in source_office and role in the title;
        # the returned statement contains only website text, no invented office.
        result['text'] = result['answer']
    return result


def local_review_notes(query, results, staff):
    """Surface differences; official-page excerpts do not rewrite local facts."""
    for result in results:
        if not result.get('personnel_name'):continue
        signature=terms(result['personnel_role'])-{'services','service','office'}
        for obj in staff:
            same_person=person_key(obj.name)==person_key(result['personnel_name'])
            same_role=(terms(obj.position)-{'services','service','office'})==signature
            note=None
            if same_role and not same_person:
                note='A local staff record names a different holder for this role. The official website excerpt is shown; the discrepancy needs institutional review.'
            elif same_person and obj.name != result['personnel_name']:
                note='The local staff record uses different name formatting or credentials. Verify the exact form with the responsible office.'
            if note:
                result.setdefault('review_notes',[])
                if note not in result['review_notes']:result['review_notes'].append(note)
                result.setdefault('review_references',[]).append({'name':obj.name,'role':obj.position,'record_id':obj.pk})
    return results


def office_conflict(query,results,faqs):
    """An eligible office-submitted identity claim cannot be silently ignored."""
    for faq in faqs:
        if faq.source_type!='office' or not NAME_RE.search(faq.answer):continue
        row=dict(question=faq.question,answer=faq.answer,source_type='office',source_office=faq.source_office)
        if not eligible_evidence(query,row):continue
        body=canonical_text(faq.answer)
        for result in results:
            if not result.get('personnel_name'):continue
            if person_key(result['personnel_name']) not in body:
                return True
    return False


@timed('structured_personnel')
def exact_personnel_lookup(query, resources=None):
    kind = lookup_kind(query)
    if kind is None:
        return []
    database_lookup=resources is None
    if database_lookup:
        from .models import WebResource
        resources = WebResource.objects.filter(
            category=ROSTER_CATEGORY if kind == 'roster' else PERSON_CATEGORY,
            url='https://spus.edu.ph/administrator/').order_by('-last_scraped', 'pk')
    if kind in ('role','name'):
        # The same president also appears in the graduate faculty tab. Cite
        # the top-management card when both contain the identical statement.
        resources = sorted(resources, key=lambda obj: (
            not obj.content.startswith('Section: TOP MANAGEMENT\n'),
            not obj.content.startswith('Section: ACADEMIC SERVICES\n')))
    results = []
    possible_names=set()
    for obj in resources:
        if urlsplit(obj.url).hostname != 'spus.edu.ph' or urlsplit(obj.url).path.rstrip('/') != '/administrator':
            continue
        if kind == 'roster':
            if obj.category != ROSTER_CATEGORY or not obj.title.startswith('SPUS Faculty Directory | '):
                continue
            # Match the containing section, not a college in a person's other role.
            if departments(obj.title) != departments(query):
                continue
            result = website_result(obj)
        else:
            if obj.category != PERSON_CATEGORY or not obj.title.startswith('SPUS Personnel | '):
                continue
            person = structured_person(obj)
            if not person:
                continue
            if kind=='name' and person_key(person['name'])!=name_request(query):
                left,right=name_request(query).split(),person_key(person['name']).split()
                if len(left)>=2 and len(right)>=2 and (left[0],left[-1])==(right[0],right[-1]):
                    possible_names.add(person['name'])
                continue
            if kind=='role' and not role_matches(query, person):
                continue
            result = website_result(obj, person)
        if not eligible_evidence(query, result):
            continue
        results.append(result)
    results=consolidate_evidence(results)
    if kind=='name' and not results and possible_names:
        return EvidenceList(status='ambiguous')
    if kind=='name' and len({row.get('personnel_name') for row in results})>1:
        return EvidenceList(status='ambiguous')
    if kind == 'role' and len(results) > 1:
        # Multiple different holders/roles are ambiguous, not an invitation to
        # select one arbitrarily (e.g. 'who is the director?').
        same_role=len({canonical_text(row.get('personnel_role','')) for row in results})==1
        return EvidenceList(status='conflict' if same_role else 'ambiguous')
    if database_lookup and results:
        from .models import StaffMember,FAQ
        results=local_review_notes(query,results,list(StaffMember.objects.all()))
        if kind in ('role','name') and office_conflict(query,results,FAQ.objects.filter(source_type='office')):
            return EvidenceList(status='conflict')
    if freshness_requested(query):
        for row in results:row['freshness_requested']=True
    return results

"""Claim-level duplicate handling shared by all retrieval sources."""
from copy import deepcopy

from .query_normalization import canonical_text, normalized_text


def evidence_key(row):
    if row.get('personnel_name') and row.get('personnel_role'):
        return ('person', normalized_text(row['personnel_name']), canonical_text(row['personnel_role']))
    return ('excerpt', canonical_text(row.get('question') or row.get('document_title') or ''),
            normalized_text(row.get('answer') or row.get('text') or ''), normalized_text(row.get('source_office') or ''))


def source_identity(row):
    return (row.get('source_url'), row.get('document_title'), row.get('record_type'), row.get('record_id'))


def consolidate_evidence(rows):
    """Keep ranked representatives and provenance, never vote by copy count."""
    merged={}
    for original in rows:
        key=evidence_key(original)
        if key not in merged:
            merged[key]=deepcopy(original)
            merged[key].setdefault('supporting_sources',[])
        representative=merged[key]
        if source_identity(original)!=source_identity(representative):
            source={key:original.get(key) for key in ('source_url','document_title','source_type','record_type','record_id','retrieved_at')}
            if source not in representative['supporting_sources']:
                representative['supporting_sources'].append(source)
        if original.get('personnel_section'):
            sections=representative.setdefault('source_sections',[])
            if original['personnel_section'] not in sections:sections.append(original['personnel_section'])
    return list(merged.values())

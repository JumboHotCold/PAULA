"""Pure, non-importing audit of scraped personnel references.

Row IDs are content/source identities, not filesystem modification times or
assertions of authority. Cross-file section memberships are preserved.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

from .query_normalization import canonical_text, normalized_text, person_key

REQUIRED={'web_scraper_order','web_scraper_start_url','data','data2'}
ALLOWED_SOURCE='https://spus.edu.ph/administrator/'


def audit_files(paths, website_people=(), local_staff=(), faqs=()):
    web_index={}
    web_names={}
    for row in website_people:
        key=(normalized_text(row['name']),canonical_text(row['role']))
        web_index.setdefault(key,[]).append(row)
        web_names.setdefault(person_key(row['name']),[]).append(row)
    seen={}; all_rows=[]; files=[]; membership_counts={}
    for path in sorted(map(Path,paths),key=lambda p:p.name):
        blob=path.read_bytes();digest=hashlib.sha256(blob).hexdigest()
        try:text=blob.decode('utf-8-sig')
        except UnicodeDecodeError:
            files.append({'file':path.name,'sha256':digest,'error':'Not valid UTF-8; manual encoding review required'})
            continue
        reader=csv.DictReader(io.StringIO(text,newline=''))
        if not REQUIRED.issubset(reader.fieldnames or []):
            files.append({'file':path.name,'sha256':digest,'error':'Unsupported columns','headers':reader.fieldnames})
            continue
        file_rows=[]
        for number,raw in enumerate(reader,2):
            name=(raw.get('data') or '').strip();role=(raw.get('data2') or '').strip()
            url=(raw.get('web_scraper_start_url') or '').strip()
            claim_key=(normalized_text(name),canonical_text(role))
            issues=[]
            if None in raw:issues.append('malformed_extra_columns')
            if not name or not role:issues.append('missing_name_or_role')
            if url!=ALLOWED_SOURCE:issues.append('unapproved_source_url')
            if any(isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) for v in raw.values()):
                issues.append('spreadsheet_formula_prefix')
            matches=web_index.get(claim_key,[])
            sections=sorted({row['section'] for row in matches})
            for section in sections:membership_counts.setdefault(path.name,{}).setdefault(section,0);membership_counts[path.name][section]+=1
            references=[{'kind':'website','record_id':row.get('record_id'),'section':row['section'],
                         'observed_at':row.get('observed_at'),'source_url':row.get('source_url',ALLOWED_SOURCE)} for row in matches]
            reviews=[];review_candidates=[]
            for obj in local_staff:
                if person_key(obj['name'])==person_key(name):
                    references.append({'kind':'staff','record_id':obj.get('record_id')})
                    if normalized_text(obj['name'])!=normalized_text(name):reviews.append('local_name_or_credential_variant')
                    if canonical_text(obj['role'])!=canonical_text(role):reviews.append('local_role_differs_review_required')
                    if normalized_text(obj['name'])!=normalized_text(name) or canonical_text(obj['role'])!=canonical_text(role):
                        review_candidates.append({'kind':'staff','record_id':obj.get('record_id'),'name':obj['name'],'role':obj['role']})
                elif (set(canonical_text(obj['role']).split())-{'services','service','office'})==(set(canonical_text(role).split())-{'services','service','office'}):
                    reviews.append('different_local_holder_for_role')
                    review_candidates.append({'kind':'staff','record_id':obj.get('record_id'),'name':obj['name'],'role':obj['role']})
                else:
                    left,right=person_key(obj['name']).split(),person_key(name).split()
                    if len(left)>=2 and len(right)>=2 and (left[0],left[-1])==(right[0],right[-1]):
                        reviews.append('possible_identity_variant_not_automatically_merged')
                        review_candidates.append({'kind':'staff','record_id':obj.get('record_id'),'name':obj['name'],'role':obj['role']})
            for faq in faqs:
                # Existing identity tokens can flag spelling candidates, but
                # surname overlap alone never establishes one identity.
                tokens=person_key(name).split()
                body_tokens=set(normalized_text(faq.get('answer','')).split())
                if len(tokens)>=2 and {tokens[0],tokens[-1]}.issubset(body_tokens) and person_key(name) not in normalized_text(faq.get('answer','')):
                    reviews.append('possible_faq_name_variant_manual_review')
                    review_candidates.append({'kind':'faq','record_id':faq.get('id'),'question':faq.get('question')})
            if claim_key in seen:reviews.append('repeated_claim_preserve_section_memberships')
            seen.setdefault(claim_key,[]).append({'file':path.name,'row':number})
            status='quarantined' if issues else 'corroborated_snapshot' if matches else 'pending_verification'
            # The observation ID remains stable across repeated audits of the
            # same file. A different capture is supplementary, not another vote.
            observation_id=hashlib.sha256(json.dumps([digest,number,name,role,url],ensure_ascii=False).encode()).hexdigest()
            row={'observation_id':observation_id,'file':path.name,'row':number,'file_sha256':digest,
                 'source_url':url,'source_origin':'spus.edu.ph/administrator','source_kind':'scraped_csv_snapshot',
                 'scraper_order':raw.get('web_scraper_order'),'capture_time':None,'appointment_effective_date':None,
                 'name':name,'role':role,'image_url':raw.get('image') or None,'status':status,
                 'issues':issues,'review_flags':sorted(set(reviews)),'review_candidates':review_candidates,
                 'matching_records':references,'possible_sections':sections,
                 'proposed_action':'preserve_existing_link_reference' if matches and not issues else 'manual_review_only'}
            file_rows.append(row);all_rows.append(row)
        dominant=membership_counts.get(path.name,{})
        files.append({'file':path.name,'sha256':digest,'encoding':'utf-8-sig' if blob.startswith(b'\xef\xbb\xbf') else 'utf-8',
                      'headers':reader.fieldnames,'rows':len(file_rows),'suggested_section':max(dominant,key=dominant.get) if dominant else None,
                      'section_mapping_requires_review':True})
    imported_names={person_key(row['name']) for row in all_rows}
    coverage=[{'name':obj['name'],'role':obj['role'],'action':'preserve_not_in_this_snapshot'} for obj in local_staff if person_key(obj['name']) not in imported_names]
    return {'schema_version':1,'mode':'dry_run_only','database_mutations':0,'authority':'supplementary_same_origin_snapshot',
            'files':files,'observations':all_rows,'local_records_outside_csv_preserved':coverage,
            'summary':{'files':len(files),'rows':len(all_rows),'distinct_name_role_claims':len(seen),
                       'repeated_claim_occurrences':sum(len(v)-1 for v in seen.values()),
                       'corroborated_rows':sum(r['status']=='corroborated_snapshot' for r in all_rows),
                       'quarantined_rows':sum(r['status']=='quarantined' for r in all_rows),
                       'pending_rows':sum(r['status']=='pending_verification' for r in all_rows),
                       'rows_with_review_flags':sum(bool(r['review_flags']) for r in all_rows)}}

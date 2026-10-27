"""Shared normalization, evidence identity and supplementary CSV safety tests.

Personnel names in these fixtures are fictional. No live provider, database
creation, institutional edits or embedding generation is required.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from .csv_reference_audit import audit_files
from .evidence_identity import consolidate_evidence
from .grounding import eligible_evidence, rank_evidence, terms
from .personnel import exact_personnel_lookup, local_review_notes, office_conflict
from .query_normalization import person_key
from .conversation_context import resolve_conversation
from .intents import normalize_query


def person(section='TOP MANAGEMENT',name='Dr. Alice Example',role='University President',pk=1):
    return SimpleNamespace(pk=pk,title=f'SPUS Personnel | {section} | {role} | {name}',
                           content=f'Section: {section}\nName: {name}\nRole: {role}',category='Website personnel',
                           url='https://spus.edu.ph/administrator/',last_scraped=datetime.now(timezone.utc))


class ConsistencyTests(unittest.TestCase):
    def test_president_paraphrases_share_one_supported_identity(self):
        rows=[person()]
        for query in ('Who is the University President?','Who is currently the university president?',
                      'Who is the university president now?','Who is the university president today?',
                      'Sino ang pangulo ng SPUS?','Sino ang presidente ng SPUS?'):
            with self.subTest(query=query):
                result=exact_personnel_lookup(normalize_query(query),rows)
                self.assertEqual(len(result),1)
                self.assertIn('Alice Example',result[0]['answer'])

    def test_vp_aliases_work_in_both_evidence_directions(self):
        for stored in ('VP for Academics Services','Vice President for Academic Services'):
            rows=[person('ACADEMIC SERVICES',role=stored)]
            for query in ('Who is the VP for Academic Services?','Who is the Vice President for Academic Services?'):
                self.assertEqual(len(exact_personnel_lookup(query,rows)),1)

    def test_vice_president_is_not_a_university_president(self):
        self.assertEqual(exact_personnel_lookup('Who is the university president?',
                         [person(role='VP for Academic Services')]),[])

    def test_role_qualifier_cannot_be_borrowed_from_section(self):
        rows=[person('ACADEMIC SERVICES',role='VP for Administrative Services')]
        self.assertEqual(exact_personnel_lookup('Who is the VP for Academics?',rows),[])

    def test_identity_lookup_works_without_semantic_similarity(self):
        rows=[person()]
        result=exact_personnel_lookup('Who is Dr. Alice Example?',rows)
        self.assertEqual(len(result),1)
        self.assertNotIn('distance',result[0])

    def test_missing_middle_initial_is_reviewed_not_merged_with_legacy_identity(self):
        result=exact_personnel_lookup('Who is Dr. Alice Example?',[person(name='Dr. Alice T. Example')])
        self.assertEqual(result,[])
        self.assertEqual(result.status,'ambiguous')

    def test_same_claim_across_sections_is_one_result_with_provenance(self):
        result=exact_personnel_lookup('Who is the university president?',
                                     [person(),person('GRADUATE SCHOOL FACULTY',pk=2)])
        self.assertEqual(len(result),1)
        self.assertEqual(set(result[0]['source_sections']),{'TOP MANAGEMENT','GRADUATE SCHOOL FACULTY'})
        self.assertEqual(len(result[0]['supporting_sources']),1)

    def test_distinct_official_holders_are_a_conflict(self):
        result=exact_personnel_lookup('Who is the president?',
                                     [person(),person(name='Dr. Bob Example',pk=2)])
        self.assertEqual(result,[])
        self.assertEqual(result.status,'conflict')

    def test_local_difference_is_flagged_without_modifying_any_object(self):
        row=exact_personnel_lookup('Who is the president?',[person()])[0]
        local=SimpleNamespace(pk=7,name='Dr. Bob Example',position='University President')
        result=local_review_notes('Who is the president?',[row],[local])
        self.assertTrue(result[0]['review_notes'])
        self.assertIn('Alice Example',result[0]['answer'])
        self.assertEqual(local.name,'Dr. Bob Example')

    def test_eligible_office_identity_conflict_is_not_overruled_by_website(self):
        rows=exact_personnel_lookup('Who is the president?',[person()])
        faq=SimpleNamespace(question='Who is the university president?',source_type='office',source_office='Responsible office',
                            answer='Dr. Bob Example is the University President.')
        self.assertTrue(office_conflict('Who is the university president?',rows,[faq]))
        faq.answer='Dr. Alice Example is the University President.'
        self.assertFalse(office_conflict('Who is the university president?',rows,[faq]))

    def test_office_suffix_does_not_break_an_organization_role(self):
        rows=[person('Publication, Documentation and Marketing Office',role='Director, Publication, Brand, and Marketing')]
        self.assertEqual(len(exact_personnel_lookup('Who is the PBMO director?',rows)),1)

    def test_missing_exact_directory_match_reaches_gated_hybrid(self):
        from .rag import RAGSearcher
        rag=RAGSearcher()
        with patch('chatbot.personnel.exact_personnel_lookup',return_value=[]), \
                patch('chatbot.models.StaffMember.objects.all',return_value=[]), \
                patch.object(rag,'_hybrid_search',return_value=[]) as fallback:
            rag.search('Who is the principal?')
        fallback.assert_called_once_with('Who is the principal?',5)

    def test_conflict_stops_the_entire_retrieval_pipeline(self):
        from .rag import RAGSearcher
        from .retrieval_types import EvidenceList
        rag=RAGSearcher()
        with patch('chatbot.personnel.exact_personnel_lookup',return_value=EvidenceList(status='conflict')), \
                patch.object(rag,'_hybrid_search') as fallback:
            result=rag.retrieve('Who is the university president?',allow_fallback=True)
        self.assertEqual(result.status,'conflict')
        self.assertEqual(result.evidence,[])
        fallback.assert_not_called()

    def test_contextual_exact_miss_does_not_repeat_exhausted_hybrid(self):
        from .rag import RAGSearcher
        rag=RAGSearcher()
        with patch('chatbot.personnel.exact_personnel_lookup',return_value=[]), \
                patch('chatbot.models.StaffMember.objects.all',return_value=[]), \
                patch.object(rag,'_hybrid_search',return_value=[]) as fallback:
            result=rag.retrieve('Who is the principal?',allow_fallback=True)
        self.assertEqual(result.status,'no_match')
        fallback.assert_called_once_with('Who is the principal?',5)

    def test_contextual_fallback_cannot_reintroduce_a_location_as_person(self):
        from .rag import RAGSearcher
        rag=RAGSearcher()
        location=dict(question='President office',answer='Located upstairs.',source_type='campus_map')
        with patch('chatbot.personnel.exact_personnel_lookup',return_value=[]), \
                patch('chatbot.models.StaffMember.objects.all',return_value=[]), \
                patch.object(rag,'_hybrid_search',return_value=[location]) as fallback:
            result=rag.retrieve('Who is the university president?',allow_fallback=True)
        self.assertEqual(result.evidence,[])
        fallback.assert_called_once()

    def test_historical_and_foreign_constraints_do_not_disappear(self):
        for query in ('Who was president in 2001?','Who is president in 2099?','Who is president of Mars?'):
            self.assertEqual(exact_personnel_lookup(query,[person()]),[])

    def test_temporal_words_align_across_all_knowledge_domains(self):
        for subject in ('scholarships','academic programs','university policies','office hours','enrollment'):
            row=dict(question=f'What are the {subject}?',answer=f'SPUS {subject}: stored source details.',source_type='office')
            self.assertTrue(eligible_evidence(f'What are the {subject} currently?',row))
            self.assertFalse(eligible_evidence(f'What are the {subject} in 2099?',row))

    def test_all_domains_deduplicate_same_question_answer_only_with_same_scope(self):
        for topic in ('scholarship','program','policy','procedure'):
            row=dict(question=f'{topic} requirements',answer='Stored requirements.',source_office='Office A',source_url='https://spus.edu.ph/a/')
            other=dict(row,source_url='https://spus.edu.ph/b/')
            self.assertEqual(len(consolidate_evidence([row,other])),1)
            self.assertEqual(len(consolidate_evidence([row,dict(other,source_office='Office B')])),2)

    def test_source_priority_is_a_tiebreaker_after_relevance(self):
        rows=[dict(question='Policy requirements',answer=f'Policy requirement: {source}.',source_type=source,distance=.2)
              for source in ('staff_directory','website','office')]
        result=rank_evidence('What are policy requirements?',rows)
        self.assertEqual([r['source_type'] for r in result],['office','website','staff_directory'])
        self.assertEqual(rank_evidence('What are policy requirements?',[dict(rows[-1],distance=.9)]),[])

    def test_location_cannot_answer_person_identity_after_exact_miss(self):
        from .rag import RAGSearcher
        rag=RAGSearcher()
        with patch('chatbot.personnel.exact_personnel_lookup',return_value=[]), \
                patch('chatbot.models.StaffMember.objects.all',return_value=[]), \
                patch.object(rag,'_hybrid_search',return_value=[dict(question='President Office',answer='Located upstairs.',source_type='campus_map')]):
            self.assertEqual(rag.search('Who is the university president?'),[])

    def test_role_switch_and_repeated_predicate_retain_intent(self):
        history=[{'role':'user','content':'Who is the University President?'},{'role':'assistant','content':'Stored evidence.'}]
        repeat=resolve_conversation('Who is currently holding that role?',history)
        self.assertEqual(repeat.queries,('Who is the University President?',))
        switch=resolve_conversation('How about the VP for Academics?',history)
        self.assertIn('VP for Academics',switch.queries[0])
        self.assertNotIn('President',switch.queries[0])

    def test_valid_pronouns_are_not_spelling_errors(self):
        for word in ('there','their','those','these','that','here'):
            self.assertEqual(normalize_query(word),word)


class CsvAuditTests(unittest.TestCase):
    def write(self,root,name,rows,headers=None):
        path=Path(root)/name
        headers=headers or ['web_scraper_order','web_scraper_start_url','data','data2']
        with path.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=headers);writer.writeheader()
            for row in rows:
                writer.writerow(dict(zip(headers,row)))
        return path

    def row(self,name='Dr. Alice Example',role='University President'):
        return ['1793110438-1','https://spus.edu.ph/administrator/',name,role]

    def test_idempotent_audit_preserves_bytes_and_keeps_capture_time_unknown(self):
        with TemporaryDirectory() as directory:
            path=self.write(directory,'source.csv',[self.row()]);original=path.read_bytes()
            first=audit_files([path]);second=audit_files([path])
            self.assertEqual(first,second)
            self.assertEqual(original,path.read_bytes())
            self.assertEqual(first['database_mutations'],0)
            self.assertIsNone(first['observations'][0]['capture_time'])
            self.assertEqual(first['observations'][0]['file_sha256'],hashlib.sha256(original).hexdigest())

    def test_duplicate_captures_do_not_become_independent_authority(self):
        with TemporaryDirectory() as directory:
            paths=[self.write(directory,name,[self.row()]) for name in ('one.csv','two.csv')]
            report=audit_files(paths)
            self.assertEqual(report['summary']['distinct_name_role_claims'],1)
            self.assertEqual(report['summary']['repeated_claim_occurrences'],1)
            self.assertEqual(report['authority'],'supplementary_same_origin_snapshot')

    def test_blank_role_and_foreign_source_are_quarantined(self):
        with TemporaryDirectory() as directory:
            rows=[self.row(role=''),self.row()];rows[1][1]='https://untrusted.invalid/administrator/'
            report=audit_files([self.write(directory,'source.csv',rows)])
            self.assertEqual(report['summary']['quarantined_rows'],2)
            self.assertTrue(all(row['proposed_action']=='manual_review_only' for row in report['observations']))

    def test_section_is_derived_from_evidence_not_the_filename(self):
        people=[dict(name='Dr. Alice Example',role='University President',section='ACTUAL SECTION',record_id=1)]
        with TemporaryDirectory() as directory:
            path=self.write(directory,'misleading_CFP.csv',[self.row()])
            report=audit_files([path],people)
            self.assertEqual(report['files'][0]['suggested_section'],'ACTUAL SECTION')
            self.assertTrue(report['files'][0]['section_mapping_requires_review'])

    def test_manual_record_outside_snapshot_is_preserved(self):
        staff=[dict(name='Locally Corrected Person',role='Organization Moderator',record_id=5)]
        with TemporaryDirectory() as directory:
            report=audit_files([self.write(directory,'source.csv',[self.row()])],local_staff=staff)
            self.assertEqual(report['local_records_outside_csv_preserved'][0]['action'],'preserve_not_in_this_snapshot')

    def test_local_conflict_is_a_review_flag_not_an_update(self):
        staff=[dict(name='Dr. Bob Example',role='University President',record_id=1)]
        with TemporaryDirectory() as directory:
            report=audit_files([self.write(directory,'source.csv',[self.row()])],local_staff=staff)
            self.assertIn('different_local_holder_for_role',report['observations'][0]['review_flags'])
            self.assertEqual(staff[0]['name'],'Dr. Bob Example')

    def test_bad_encoding_and_wrong_schema_do_not_enter_knowledge(self):
        with TemporaryDirectory() as directory:
            bad=Path(directory)/'bad.csv';bad.write_bytes(b'\xff\xfe\xfa')
            wrong=self.write(directory,'wrong.csv',[['test','test']],['unknown','columns'])
            report=audit_files([bad,wrong])
            self.assertEqual(report['summary']['rows'],0)
            self.assertTrue(all('error' in item for item in report['files']))

    def test_spreadsheet_formula_cells_are_flagged(self):
        with TemporaryDirectory() as directory:
            report=audit_files([self.write(directory,'source.csv',[self.row(name='=UNTRUSTED()')])])
            self.assertIn('spreadsheet_formula_prefix',report['observations'][0]['issues'])


if __name__=='__main__':unittest.main()

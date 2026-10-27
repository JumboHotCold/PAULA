"""Offline source extraction, network boundaries and exact lookup regressions.

All fixture personnel are fictional. No network, database or model is used.
"""
from datetime import datetime, timezone
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock

from .grounding import eligible_evidence
from .intents import normalize_query
from .personnel import exact_personnel_lookup, lookup_kind
from .web_crawler import (
    Document, OfficialSiteClient, PERSON_CATEGORY, ROSTER_CATEGORY,
    administration_records, canonical_url, discover_links, extract_records,
)


def card(name, role):
    return f'<div class="tlp-content"><h3><span class="team-name">{name}</span></h3><div class="tlp-position">{role}</div></div>'


def section(label, body):
    return f'<details><summary><div class="e-n-accordion-item-title-text">{label}</div></summary>{body}</details>'


def resource(section_name, name, role):
    return SimpleNamespace(title=f'SPUS Personnel | {section_name} | {role} | {name}',
                           category=PERSON_CATEGORY, url='https://spus.edu.ph/administrator/',
                           content=f'Section: {section_name}\nName: {name}\nRole: {role}',
                           last_scraped=datetime.now(timezone.utc))


class ExtractionTests(unittest.TestCase):
    def test_sections_survive_collapsed_accordions_and_role_boundaries(self):
        html = section('College of Engineering and Information Technology',
                       card('Engr. Alice Example', 'College Full-time Faculty') + card('Mr. Ben Example', 'Office Secretary'))
        html += section('College of Health Sciences', card('Dr. Carol Example', 'College Full-time Faculty'))
        records, details = extract_records(html, 'Administration', 'Administration', True)
        roster = next(row for row in records if row['category'] == ROSTER_CATEGORY and 'Engineering' in row['title'])
        self.assertIn('Alice Example', roster['content'])
        self.assertNotIn('Ben Example', roster['content'])
        self.assertNotIn('Carol Example', roster['content'])
        self.assertEqual(details['people_cards'], 3)

    def test_tab_label_supplies_section_without_accordion(self):
        html = '<button role="tab" aria-controls="grad">GRADUATE SCHOOL FACULTY</button>'
        html += '<div id="grad">' + card('Dr. Alice Example', 'Graduate School Faculty') + '</div>'
        _, details = administration_records(Document(html))
        self.assertEqual(details['sections'], ['GRADUATE SCHOOL FACULTY'])

    def test_seo_scripts_portrait_names_and_navigation_are_not_personnel(self):
        html = '<head><meta content="Fake President"><script>' + card('Fake Name', 'President') + '</script></head>'
        html += '<nav>' + card('Fake Navigation', 'President') + '</nav>'
        html += section('TOP MANAGEMENT', '<img alt="Fake Portrait">' + card('Dr. Alice Example', 'University President'))
        records, _ = extract_records(html, 'Administration', 'Administration', True)
        self.assertEqual(len(records), 1)
        self.assertNotIn('Fake', records[0]['content'])

    def test_missing_role_is_reported_never_borrowed_from_next_person(self):
        html = section('CEIT', card('Mr. Missing Example', '') + card('Engr. Alice Example', 'Faculty'))
        records, details = extract_records(html, 'Administration', 'Administration', True)
        self.assertEqual(len(details['incomplete_cards']), 1)
        self.assertTrue(all('Missing Example' not in row['content'] for row in records))

    def test_layout_change_without_team_cards_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'preserving'):
            extract_records('<p>New layout</p>', 'Administration', 'Administration', True)

    def test_generic_chunks_repeat_actual_section_heading_not_next_department(self):
        html = '<h2>Engineering</h2><p>' + 'Engineering programs. ' * 100 + '</p><h2>Health Sciences</h2><p>' + 'Nursing. ' * 30 + '</p>'
        records, _ = extract_records(html, 'Programs', 'Academics')
        self.assertTrue(all('Nursing' not in row['content'] for row in records if '| Engineering ' in row['title']))


class NetworkBoundaryTests(unittest.TestCase):
    def test_canonicalization_removes_fragments_and_rejects_other_hosts_and_queries(self):
        self.assertEqual(canonical_url('https://spus.edu.ph/administrator/#ceit'), 'https://spus.edu.ph/administrator/')
        for value in ('http://spus.edu.ph/', 'https://evil.test/', 'https://spus.edu.ph.evil.test/',
                      'https://spus.edu.ph:8443/', 'https://spus.edu.ph/?s=student',
                      'https://user:password@spus.edu.ph/', 'https://spus.edu.ph/wp-admin/',
                      'https://spus.edu.ph/file.pdf'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_url(value)

    def test_discovery_is_deduplicated_same_host_and_skips_assets(self):
        html = '<a href="/administrator/#ceit">A</a><a href="/administrator/">B</a><a href="https://evil.test/">X</a><a href="/p.pdf">PDF</a>'
        self.assertEqual(discover_links(html, 'https://spus.edu.ph/', ['spus.edu.ph']), ['https://spus.edu.ph/administrator/'])

    def test_robots_disallow_is_respected_without_requesting_page(self):
        client = OfficialSiteClient(['spus.edu.ph'])
        client._request = Mock(return_value=(200, {}, b'User-agent: *\nDisallow: /administrator/'))
        with self.assertRaisesRegex(ValueError, 'disallows'):
            client.fetch('https://spus.edu.ph/administrator/')
        client._request.assert_called_once()

    def test_redirect_cannot_leave_allowlist(self):
        client = OfficialSiteClient(['spus.edu.ph'])
        client._robots = Mock()
        client._request = Mock(return_value=(302, {'Location': 'http://127.0.0.1:5432/'}, b''))
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            client.fetch('https://spus.edu.ph/administrator/')
        client._request.assert_called_once()

    def test_http_error_does_not_become_html_content(self):
        client = OfficialSiteClient(['spus.edu.ph'])
        client._robots = Mock()
        client._request = Mock(return_value=(406, {}, b'<h1>Blocked</h1>'))
        with self.assertRaisesRegex(ValueError, 'HTTP 406'):
            client.fetch('https://spus.edu.ph/administrator/')

    def test_utf8_personnel_characters_are_preserved(self):
        client = OfficialSiteClient(['spus.edu.ph'])
        client._robots = Mock()
        client._request = Mock(return_value=(200, {'Content-Type': 'text/html'}, '<p>Niñal — Faculty</p>'.encode()))
        self.assertIn('Niñal — Faculty', client.fetch('https://spus.edu.ph/administrator/')[1])


class PersonnelTests(unittest.TestCase):
    def test_president_exact_lookup_needs_no_cosine_score_and_excludes_vp(self):
        rows = [resource('TOP MANAGEMENT', 'Dr. Alice Example', 'University President'),
                resource('TOP MANAGEMENT', 'Dr. Ben Example', 'Vice President for Academics')]
        result = exact_personnel_lookup('who is the university president?', rows)
        self.assertEqual(len(result), 1)
        self.assertIn('Alice Example', result[0]['answer'])
        self.assertNotIn('distance', result[0])
        self.assertEqual(result[0]['source_url'], 'https://spus.edu.ph/administrator/')

    def test_director_ict_uses_actual_role_and_section_and_ignores_filler(self):
        rows = [resource('ICT Systems and Services', 'Engr. Alice Example', 'Director, Information & Communications Technology Systems and Services'),
                resource('ICT Systems and Services', 'Mr. Ben Example', 'ICT Helpdesk')]
        result = exact_personnel_lookup('uh who is the ICT Director?', rows)
        self.assertEqual(len(result), 1)
        self.assertIn('Alice Example', result[0]['answer'])

    def test_two_distinct_holders_are_not_chosen_arbitrarily(self):
        rows = [resource('TOP MANAGEMENT', name, 'University President') for name in ('Dr. Alice Example', 'Dr. Ben Example')]
        self.assertEqual(exact_personnel_lookup('who is university president?', rows), [])

    def test_historical_foreign_and_additional_constraints_do_not_enter_exact_lookup(self):
        for query in ('Who was the president in 2010?', 'Who is the president of Mars?',
                      'Who is the former university president?', 'What qualifications does the president have?',
                      'Who are CEIT faculty teaching mining?'):
            with self.subTest(query=query):
                self.assertIsNone(lookup_kind(query))

    def test_reported_president_typo_and_other_domain_typos(self):
        self.assertEqual(normalize_query('who is the university preseidnt?'), 'who is the university president?')
        self.assertIn('director', normalize_query('who is the ICT direcotr?'))
        self.assertIn('Magalona', normalize_query('who is Magalona?'))

    def test_roster_keeps_section_members_even_with_other_roles(self):
        row = SimpleNamespace(title='SPUS Faculty Directory | College of Engineering and Information Technology',
                              content='Faculty listed under College of Engineering and Information Technology:\n- Dr. Alice Example — Dean, Graduate School Faculty\n- Engr. Ben Example — Part-time Faculty',
                              category=ROSTER_CATEGORY, url='https://spus.edu.ph/administrator/', last_scraped=datetime.now(timezone.utc))
        result = exact_personnel_lookup('who are the CEIT faculty?', [row])
        self.assertEqual(len(result), 1)
        self.assertIn('Ben Example', result[0]['answer'])
        self.assertTrue(eligible_evidence('who are the CEIT faculty?', result[0]))

    def test_rag_exact_lookup_does_not_load_embedding_model(self):
        from .rag import RAGSearcher
        row = resource('TOP MANAGEMENT', 'Dr. Alice Example', 'University President')
        result = exact_personnel_lookup('Who is the university president?', [row])
        with patch('chatbot.personnel.exact_personnel_lookup', return_value=result):
            rag = RAGSearcher()
            rag.ensure_embeddings = Mock(side_effect=AssertionError('Unexpected embedding write'))
            self.assertEqual(rag.search('Who is the university president?'), result)
            self.assertIsNone(rag.model)


class CrawlCommandTests(unittest.TestCase):
    def test_changed_content_clears_vector_and_unchanged_content_preserves_it(self):
        from .crawling import replace_page_resources
        for changed in (True, False):
            with self.subTest(changed=changed):
                obj = SimpleNamespace(pk=1, title='Administration', category='Administration',
                                      content='Old role' if changed else 'New role', embedding=[0.1] * 384, save=Mock())
                with patch('chatbot.crawling.transaction.atomic', return_value=MagicMock()), \
                        patch('chatbot.crawling.connection') as connection, \
                        patch('chatbot.crawling.WebResource') as model:
                    model.objects.select_for_update.return_value.filter.return_value = [obj]
                    model.objects.filter.return_value.delete.return_value = (0, {})
                    replace_page_resources('https://spus.edu.ph/administrator/',
                                           [dict(title='Administration', category='Administration', content='New role')], 'Administration')
                    self.assertEqual(obj.embedding, None if changed else [0.1] * 384)
                    self.assertIn('embedding', obj.save.call_args.kwargs['update_fields'])
                    connection.cursor.assert_called_once()

    def run_options(self, output='snapshots'):
        return dict(url=['https://spus.edu.ph/administrator/'], discover=True,
                    max_pages=1, max_depth=1, delay=0.5, dry_run=True,
                    no_embeddings=True, output_dir=output)

    def test_dry_run_respects_page_budget_and_does_not_write_database(self):
        from django.test import override_settings
        from .crawling import run_crawl
        html = section('TOP MANAGEMENT', card('Dr. Alice Example', 'University President'))
        html += '<a href="/about/">About</a>'
        core = [{'url': 'https://spus.edu.ph/administrator/', 'title': 'Administration', 'category': 'Administration'}]
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)), \
                patch('chatbot.crawling.connection', SimpleNamespace(vendor='postgresql')), \
                patch('chatbot.crawling.OfficialSiteClient') as client, \
                patch('chatbot.crawling.replace_page_resources') as replace:
            client.return_value.fetch.return_value = ('https://spus.edu.ph/administrator/', html)
            run_crawl(SimpleNamespace(stdout=Mock(), stderr=Mock()), core, self.run_options())
            report = json.loads((Path(folder) / 'snapshots/latest_crawl_report.json').read_text())
            self.assertEqual(report['pages_visited'], 1)
            self.assertEqual(report['queued_remaining'], 1)
            self.assertEqual(report['pages'][0]['status'], 'extracted')
            client.return_value.fetch.assert_called_once()
            replace.assert_not_called()

    def test_fetch_failure_reports_failure_without_replacing_previous_records(self):
        from django.core.management.base import CommandError
        from django.test import override_settings
        from .crawling import run_crawl
        core = [{'url': 'https://spus.edu.ph/administrator/', 'title': 'Administration', 'category': 'Administration'}]
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)), \
                patch('chatbot.crawling.connection', SimpleNamespace(vendor='postgresql')), \
                patch('chatbot.crawling.OfficialSiteClient') as client, \
                patch('chatbot.crawling.replace_page_resources') as replace:
            client.return_value.fetch.side_effect = ValueError('Page returned HTTP 406')
            with self.assertRaises(CommandError):
                run_crawl(SimpleNamespace(stdout=Mock(), stderr=Mock()), core, self.run_options())
            report = json.loads((Path(folder) / 'snapshots/latest_crawl_report.json').read_text())
            self.assertEqual(report['pages'][0]['status'], 'failed')
            self.assertIn('HTTP 406', report['pages'][0]['error'])
            replace.assert_not_called()


if __name__ == '__main__':
    unittest.main()

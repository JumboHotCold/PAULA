"""Config migration contract and matching views that preserve factual input."""
import hashlib
import json
import re
from unittest.mock import patch
from django.test import SimpleTestCase
from .conversation_config import CONFIG_PATH, conversation_config, validate_conversation_config
from .query_normalization import normalize_input, normalized_text


class ConversationConfigTests(SimpleTestCase):
    def test_migration_preserves_all_existing_copy_patterns_and_exemplars(self):
        data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        from pathlib import Path
        original=json.loads((Path(__file__).with_name('testdata')/'conversation_v1.json').read_text(encoding='utf-8'))
        def project(current,old):
            if isinstance(old,dict):return {key:project(current[key],value) for key,value in old.items()}
            if isinstance(old,list):
                # Original reviewed examples/copy remain verbatim; additions
                # are allowed by the explicitly approved Stage 3 config scope.
                self.assertTrue(all(value in current for value in old))
                return old
            self.assertEqual(current,old)
            return old
        digest = hashlib.sha256(json.dumps(project(data,original), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(digest, '207c9f6ff6ff49e24da73276c8a7e4144eb11884080d4f7ca0965aeef2408cb6')

    def test_config_is_loaded_once_and_cannot_leak_mutations_between_requests(self):
        current = conversation_config()
        with patch('pathlib.Path.read_text', side_effect=AssertionError('Repeated disk read')):
            self.assertIs(conversation_config(), current)
        with self.assertRaises(TypeError):
            current['replies']['identity']['en'] = ('Mutated persona',)

    def test_invalid_config_fails_explicitly_instead_of_silent_persona_fallback(self):
        for change in ('version', 'missing_persona', 'unknown_alias', 'invalid_regex', 'missing_guard', 'missing_pattern'):
            data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            if change == 'version': data['schema_version'] = 99
            elif change == 'missing_persona': del data['replies']['identity']
            elif change == 'unknown_alias': data['social']['abbreviations']['ty'] = 'unknown'
            elif change == 'invalid_regex': data['social']['fast_patterns']['greeting'] = '['
            elif change == 'missing_guard': del data['semantic']['exemplars']['knowledge']
            else: del data['social']['fast_patterns']['identity']
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError, re.error)):
                validate_conversation_config(data)

    def test_matching_forms_share_unicode_and_punctuation_normalization(self):
        raw = '  ＴＨＡＮＫ   YOU!!!  '
        view = normalize_input(raw)
        self.assertEqual(view.original, raw)
        self.assertEqual(view.spaced, 'thank you')
        self.assertEqual(view.squashed, 'thankyou')
        self.assertEqual(normalized_text(raw), view.spaced)
        self.assertEqual(normalize_input("What's your name?").punctuated, "what's your name?")

    def test_factual_original_dates_names_and_negation_are_preserved(self):
        raw = 'Who is Engr. O’Neil at CEIT in ２０３７, without credentials?'
        view = normalize_input(raw)
        self.assertEqual(view.original, raw)
        self.assertIn('2037', view.spaced)
        self.assertIn('without credentials', view.spaced)
        self.assertIn('o neil', view.spaced)

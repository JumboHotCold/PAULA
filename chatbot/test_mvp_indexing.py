"""Index lifecycle contracts use controlled PostgreSQL fixtures only."""
from io import StringIO
import json
from unittest.mock import Mock, patch
from django.core.management import call_command
from django.test import TestCase
from .grounding import eligible_evidence, faculty_identity_request
from .models import FAQ, Location, StaffMember, WebResource
from .rag import RAGSearcher

VECTOR = [0.1] * 384


class IndexLifecycleTests(TestCase):
    def test_partial_text_save_invalidates_the_persisted_vector_for_each_source(self):
        sources = (
            (FAQ.objects.create(question='What is Nova?', answer='Old text', category='Fixture', embedding=VECTOR), 'answer'),
            (Location.objects.create(name='Nova office', description='Old text', embedding=VECTOR), 'description'),
            (StaffMember.objects.create(name='Fixture person', position='Fixture role', office='Old text', embedding=VECTOR), 'office'),
            (WebResource.objects.create(title='Nova page', url='https://spus.edu.ph/fixture/', content='Old text', category='Fixture', embedding=VECTOR), 'content'),
        )
        for row, field in sources:
            with self.subTest(model=type(row).__name__):
                setattr(row, field, 'Changed text')
                row.save(update_fields=[field])
                row.refresh_from_db()
                self.assertIsNone(row.embedding)

    def test_web_category_is_part_of_embedding_input_and_invalidates_it(self):
        row = WebResource.objects.create(title='Nova', content='Fixture', url='https://spus.edu.ph/fixture/', category='Old', embedding=VECTOR)
        row.category = 'New'
        row.save(update_fields=['category'])
        row.refresh_from_db()
        self.assertIsNone(row.embedding)

    def test_unpersisted_dirty_fields_do_not_invalidate_an_unchanged_stored_source(self):
        row = FAQ.objects.create(question='What is Nova?', answer='Original', category='Fixture', embedding=VECTOR)
        row.answer = 'Unpersisted edit'
        row.save(update_fields=['source_office'])
        row.refresh_from_db()
        self.assertIsNotNone(row.embedding)
        self.assertEqual(row.answer, 'Original')

    def test_maintenance_fills_missing_vectors_only(self):
        missing = FAQ.objects.create(question='What is Nova?', answer='Original', category='Fixture')
        indexed = FAQ.objects.create(question='What is Luna?', answer='Existing', category='Fixture', embedding=VECTOR)
        rag = RAGSearcher()
        rag._generate_embedding = Mock(return_value=VECTOR)
        result = rag.ensure_embeddings()
        self.assertEqual(result['indexed'], 1)
        rag._generate_embedding.assert_called_once()
        missing.refresh_from_db()
        indexed.refresh_from_db()
        self.assertIsNotNone(missing.embedding)
        self.assertEqual(indexed.answer, 'Existing')

    def test_concurrent_source_edit_never_receives_a_stale_vector(self):
        row = FAQ.objects.create(question='What is Nova?', answer='Original', category='Fixture')
        rag = RAGSearcher()
        def encode(text):
            FAQ.objects.filter(pk=row.pk).update(answer='Concurrent corrected fact')
            return VECTOR
        rag._generate_embedding = encode
        result = rag.ensure_embeddings()
        row.refresh_from_db()
        self.assertEqual(result['indexed'], 0)
        self.assertEqual(result['skipped_changed_or_indexed'], 1)
        self.assertIsNone(row.embedding)
        self.assertEqual(row.answer, 'Concurrent corrected fact')

    def test_interactive_hybrid_search_never_indexes_even_with_missing_vectors(self):
        row = FAQ.objects.create(question='Nova fixture subject', answer='Fixture text', category='Fixture')
        rag = RAGSearcher()
        rag.ensure_embeddings = Mock(side_effect=AssertionError('Request-time indexing prohibited'))
        rag._generate_embedding = Mock(return_value=VECTOR)
        rag._hybrid_search('What are the unknown Nova conditions?')
        rag.ensure_embeddings.assert_not_called()
        row.refresh_from_db()
        self.assertIsNone(row.embedding)

    def test_index_command_is_read_only_without_apply(self):
        row = FAQ.objects.create(question='Nova fixture', answer='Fixture', category='Fixture')
        output = StringIO()
        with patch.object(RAGSearcher, 'ensure_embeddings') as index:
            call_command('index_knowledge', stdout=output)
        self.assertTrue(json.loads(output.getvalue())['dry_run'])
        index.assert_not_called()
        row.refresh_from_db()
        self.assertIsNone(row.embedding)

    def test_unindexed_exact_faq_still_works_when_semantic_model_is_unavailable(self):
        FAQ.objects.create(question='What programs are offered at Nova?', answer='Fixture programs list.', category='Fixture')
        rag = RAGSearcher()
        rag._generate_embedding = Mock(side_effect=RuntimeError('Model unavailable'))
        result = rag.retrieve('What programs are offered at Nova?')
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.evidence[0]['answer'], 'Fixture programs list.')
        rag._generate_embedding.assert_not_called()

    def test_faculty_policy_is_not_a_named_roster_request(self):
        query = 'How do faculty members borrow library materials?'
        row = {'question': query, 'answer': 'Fixture: faculty may borrow approved materials.', 'record_type': 'faq'}
        self.assertFalse(faculty_identity_request(query))
        self.assertTrue(eligible_evidence(query, row))
        self.assertTrue(faculty_identity_request('Who are the CEIT faculty?'))
        self.assertFalse(eligible_evidence('Who are the CEIT faculty?', row))

    def test_admin_save_indexes_only_the_edited_source(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from .admin import FAQAdmin
        other = FAQ.objects.create(question='Unrelated source', answer='Unrelated fixture', category='Fixture')
        row = FAQ(question='What is Nova?', answer='New fixture', category='Fixture')
        with patch.object(RAGSearcher, '_generate_embedding', return_value=VECTOR):
            FAQAdmin(FAQ, admin.site).save_model(RequestFactory().post('/admin/'), row, None, False)
        row.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(row.embedding)
        self.assertIsNone(other.embedding)

    def test_failed_admin_indexing_preserves_the_source_and_warns(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from .admin import FAQAdmin
        row = FAQ(question='What is Nova?', answer='New fixture', category='Fixture')
        model_admin = FAQAdmin(FAQ, admin.site)
        model_admin.message_user = Mock()
        with patch.object(RAGSearcher, '_generate_embedding', side_effect=RuntimeError('Private infrastructure detail')):
            model_admin.save_model(RequestFactory().post('/admin/'), row, None, False)
        row.refresh_from_db()
        self.assertEqual(row.answer, 'New fixture')
        self.assertIsNone(row.embedding)
        model_admin.message_user.assert_called_once()
        self.assertNotIn('Private', model_admin.message_user.call_args.args[1])

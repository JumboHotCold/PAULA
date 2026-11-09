from django.test import SimpleTestCase
from unittest.mock import Mock
from .dialogue import SemanticSocialRouter
from .spelling import matching_plan,build_lexicon


class MeasurementContractTests(SimpleTestCase):
    def test_spacing_ablation_is_request_local_and_keeps_protected_tokens(self):
        from .spelling import spacing_policy
        lexicon=build_lexicon(['programs offered'])
        self.assertEqual(matching_plan('prog rams',lexicon).matching,'programs')
        with spacing_policy(False):self.assertEqual(matching_plan('prog rams',lexicon).matching,'prog rams')
        self.assertEqual(matching_plan('prog rams',lexicon).matching,'programs')

    def test_rank_is_observable_without_mutable_user_cache(self):
        router=SemanticSocialRouter()
        self.assertEqual(router.rank('unprepared'),())

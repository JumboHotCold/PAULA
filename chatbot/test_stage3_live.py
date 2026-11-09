"""Explicit live-provider smoke; excluded unless the operator opts in."""
import os,unittest
from django.test import SimpleTestCase


@unittest.skipUnless(os.environ.get('PAULA_RUN_LIVE_SMOKE')=='1','Live provider smoke is opt-in')
class LiveProviderSmoke(SimpleTestCase):
    def test_reviewed_fixture_selection_does_not_invent_evidence(self):
        from .logic import PauliBotLogic
        value=PauliBotLogic()
        self.assertIsNotNone(value.client,'A configured provider is required for the explicit live smoke')
        rows=[dict(question='Synthetic fixture',answer='Reviewed synthetic fixture text.')]
        chosen=value._select('Synthetic fixture',rows)
        self.assertTrue(all(row in rows for row in chosen))

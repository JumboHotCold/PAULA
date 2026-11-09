from django.test import SimpleTestCase
from .intents import enrollment_resolution,navigation_choice,ENROLL_QUESTION,NAV_QUESTION


class PendingSelectionGrammarTests(SimpleTestCase):
    def history(self,question,prompt):return [{'role':'user','content':question},{'role':'assistant','content':prompt}]

    def test_followup_selection_wrappers_are_shared_across_pending_tasks(self):
        history=self.history('what are the requirements for enrollment',ENROLL_QUESTION)
        for text in ('how about for transferees','what about transferees','paano naman sa transferees'):
            needs,query=enrollment_resolution(text,history)
            self.assertFalse(needs);self.assertNotEqual(query,text);self.assertIn('transferee',query)
        nav=self.history('Where is the office?',NAV_QUESTION)
        self.assertTrue(navigation_choice('how about for Finance office',nav))

    def test_extra_conditions_and_missing_pending_context_are_not_discarded(self):
        for text in ('how about for transferees without documents','how about for transferees in 2037'):
            self.assertEqual(enrollment_resolution(text,self.history('How do I enroll?',ENROLL_QUESTION)),(False,text))
        self.assertEqual(enrollment_resolution('how about for transferees',[]),(False,'how about for transferees'))

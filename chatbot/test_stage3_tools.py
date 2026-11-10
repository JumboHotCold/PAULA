from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase,TestCase
from scripts.run_questions import load_questions


class PrivateRunnerInputTests(SimpleTestCase):
    def test_questions_are_data_and_threads_are_explicit(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'questions.jsonl'
            path.write_text('{"question":"What programs are offered?","thread":"one"}\n"hello"\n',encoding='utf-8')
            self.assertEqual(load_questions(path),[{'query':'What programs are offered?','thread':'one'},{'query':'hello'}])


class CiGateIsolationTests(TestCase):
    def test_ci_fixture_refuses_current_database_before_any_write(self):
        from scripts.ci_knowledge_gate import run_gate
        from .models import FAQ
        count=FAQ.objects.count()
        with self.assertRaises(RuntimeError):run_gate()
        self.assertEqual(FAQ.objects.count(),count)

"""
Management command to ingest knowledge_base/knowledge base.txt into the FAQ table.

This parses the verified knowledge base text file into granular, well-labeled
FAQ entries so that the RAG semantic search can accurately match user queries.
"""
import os
import re
from django.core.management.base import BaseCommand
from chatbot.models import FAQ


# Map section headers to clear categories and questions
SECTION_MAPPINGS = [
    {
        "match": "ANNOUNCEMENT ENROLLMENT",
        "entries": [
            {
                "category": "Admissions",
                "question": "What are the enrollment requirements for Grade 7?",
                "extract": lambda text: _extract_between(text, "FOR INCOMING GRADE 7", "===")
            },
            {
                "category": "Admissions",
                "question": "What are the enrollment requirements for Nursery, Kindergarten, and Grade 1?",
                "extract": lambda text: _extract_between(text, "FOR INCOMING NURSERY", "===")
            },
            {
                "category": "Admissions",
                "question": "What are the enrollment requirements for Grade 11 SHS?",
                "extract": lambda text: _extract_between(text, "FOR INCOMING GRADE 11", "===")
            },
        ]
    },
]


def _extract_between(text, start_marker, end_marker):
    """Extract text between two markers."""
    start = text.find(start_marker)
    if start == -1:
        return None
    end = text.find(end_marker, start + len(start_marker))
    if end == -1:
        return text[start:].strip()
    return text[start:end].strip()


class Command(BaseCommand):
    help = 'Ingest knowledge base.txt into the FAQ table with granular, well-labeled entries'

    def handle(self, *args, **options):
        file_path = os.path.join(os.getcwd(), 'knowledge_base', 'knowledge base.txt')
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Clear old entries
        deleted, _ = FAQ.objects.filter(category="Verified Knowledge Base").delete()
        self.stdout.write(f"Deleted {deleted} old 'Verified Knowledge Base' entries.")

        created_count = 0

        # ── Structured entries parsed from the text ──
        entries = self._parse_structured_entries(content)
        for entry in entries:
            defaults = {
                'category': entry['category'],
                'answer': entry['answer'],
                'embedding': None,  # Force re-embed
            }
            if 'source_type' in entry:
                defaults['source_type'] = entry['source_type']
            if 'source_office' in entry:
                defaults['source_office'] = entry['source_office']

            obj, created = FAQ.objects.update_or_create(
                question=entry['question'],
                defaults=defaults
            )
            status = "CREATED" if created else "UPDATED"
            self.stdout.write(f"  [{status}] {entry['category']}: {entry['question'][:80]}")
            created_count += 1

        self.stdout.write(f"\nTotal entries ingested: {created_count}")

        # Generate embeddings
        try:
            from chatbot.rag import RAGSearcher
            rag = RAGSearcher()
            self.stdout.write("Generating vector embeddings for new entries...")
            rag.ensure_embeddings()
            self.stdout.write(self.style.SUCCESS("Embeddings generated successfully!"))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"Could not generate embeddings: {e}"))

    def _parse_structured_entries(self, content):
        """Parse the knowledge base text into granular FAQ entries."""
        entries = []

        # ── 1. Enrollment: Grade 7 ──
        grade7 = _extract_between(content, "FOR INCOMING GRADE 7", "===")
        if grade7:
            entries.append({
                "category": "Admissions",
                "question": "What are the enrollment requirements for incoming Grade 7 students?",
                "answer": f"Early Admission and Enrollment is ongoing! {grade7}\n\nGOOD NEWS! 350 ESC SLOTS AVAILABLE!\nTo enroll, visit www.spus.edu.ph and click on the 'Admission' tab."
            })

        # ── 2. Enrollment: Nursery/Kinder/Grade 1 ──
        nkg1 = _extract_between(content, "FOR INCOMING NURSERY", "===")
        if nkg1:
            entries.append({
                "category": "Admissions",
                "question": "What are the enrollment requirements for Nursery, Kindergarten, and Grade 1?",
                "answer": f"Early Admission and Enrollment is ongoing! {nkg1}"
            })

        # ── 3. Enrollment: Grade 11 / SHS ──
        g11 = _extract_between(content, "FOR INCOMING GRADE 11", "===")
        if g11:
            entries.append({
                "category": "Admissions",
                "question": "What are the enrollment requirements for incoming Grade 11 (SHS) students?",
                "answer": f"Early Admission and Enrollment is ongoing! {g11}\n\nTo enroll, visit www.spus.edu.ph and click on the 'Admission' tab."
            })

        # ── 4. Webometrics Ranking ──
        webo = _extract_between(content, "WEBOMETRICS 2026", "===")
        if webo:
            entries.append({
                "category": "About SPUS",
                "question": "What is the SPUS Webometrics 2026 ranking?",
                "answer": f"Saint Paul University Surigao {webo}"
            })

        # ── 5. About Us ──
        about = _extract_between(content, "About us", "VISION-MISSION")
        if about:
            entries.append({
                "category": "About SPUS",
                "question": "What is Saint Paul University Surigao (SPUS)?",
                "answer": about
            })

        # ── 6. Vision-Mission ──
        vm = _extract_between(content, "VISION-MISSION", "PAULINIAN CORE VALUES")
        if vm:
            entries.append({
                "category": "About SPUS",
                "question": "What is the SPUS Vision and Mission?",
                "answer": vm
            })

        # ── 7. Core Values ──
        cv = _extract_between(content, "PAULINIAN CORE VALUES", "===")
        if cv:
            entries.append({
                "category": "About SPUS",
                "question": "What are the Paulinian Core Values?",
                "answer": cv
            })

        # ── 8. Why Choose SPUS ──
        why = _extract_between(content, "Why Choose SPUS?", "===")
        if why:
            entries.append({
                "category": "About SPUS",
                "question": "Why choose SPUS? What makes SPUS special?",
                "answer": why
            })

        # ── 9. Graduate School ──
        gs = _extract_between(content, "GRADUATE SCHOOL", "===")
        if gs:
            entries.append({
                "category": "Academics - Graduate School",
                "question": "What Graduate School programs does SPUS offer? What are the GSPS programs?",
                "answer": gs
            })

        # ── 10. College Department Overview ──
        college = _extract_between(content, "COLLEGE DEPARTMENT", "College of Health Sciences")
        if college:
            entries.append({
                "category": "Academics - College",
                "question": "What is the SPUS College Department? How do I contact the registrar?",
                "answer": college
            })

        # ── 10b. ALL Undergraduate Programs (Unified comprehensive entry) ──
        # This ensures a broad "What programs are available?" query returns ALL colleges
        all_programs = _extract_between(content, "Undergraduate Programs", "SPUS TVET")
        if all_programs:
            entries.append({
                "category": "Academics",
                "question": "What programs are offered at SPUS? What are the available undergraduate programs? What courses are available?",
                "source_type": "office",
                "source_office": "Registrar",
                "answer": (
                    "Saint Paul University Surigao (SPUS) offers a comprehensive range of undergraduate programs "
                    "across five (5) colleges:\n\n"
                    "**College of Health Sciences (4-Year Curriculum)**\n"
                    "- Bachelor of Science in Nursing\n"
                    "- Bachelor of Science in Psychology\n\n"
                    "**College of Education, Arts and Sciences (3-Year Curriculum)**\n"
                    "- Bachelor of Arts (Major in: Political Science, Philosophy, English Language, Sociology, Mass Communication)\n"
                    "- Bachelor of Science in Mathematics\n"
                    "- Bachelor of Science in Public Administration\n"
                    "- Bachelor of Elementary Education\n"
                    "- Bachelor of Secondary Education (Major in: English, Filipino, Mathematics, Sciences, Social Studies, Values Education)\n"
                    "- Bachelor of Early Childhood Education\n"
                    "- Bachelor of Physical Education\n\n"
                    "**College of Business Management and Accountancy (4-Year Curriculum)**\n"
                    "- Bachelor of Science in Accountancy\n"
                    "- Bachelor of Science in Business Administration (Major in: Financial Management, Marketing Management, Human Resource Development Management)\n"
                    "- Bachelor of Science in Hospitality Management\n"
                    "- Bachelor of Science in Tourism Management\n"
                    "- Bachelor of Science in Accounting and Information System\n"
                    "- Bachelor of Science in Office Administration\n\n"
                    "**College of Engineering & Information Technology (4-Year Curriculum)**\n"
                    "- Bachelor of Science in Mining Engineering\n"
                    "- Bachelor of Science in Civil Engineering\n"
                    "- Bachelor of Science in Computer Engineering\n"
                    "- Bachelor of Science in Information Technology\n\n"
                    "**College of Criminal Justice Education (4-Year Curriculum)**\n"
                    "- Bachelor of Science in Criminology\n"
                    "- Bachelor of Forensic Science\n\n"
                    "SPUS also offers Graduate School programs (PhD, Masters) and TVET/TESDA programs. "
                    "For inquiries, contact the Registrar at registrar@spus.edu.ph or call 09635606094."
                )
            })

        # ── 11. College of Health Sciences ──
        chs = _extract_between(content, "College of Health Sciences Program", "College of Education")
        if chs:
            entries.append({
                "category": "Academics - College of Health Sciences",
                "question": "What programs does the SPUS College of Health Sciences offer? Does SPUS offer Nursing or Psychology?",
                "answer": chs
            })

        # ── 12. College of Education, Arts and Sciences ──
        ceas = _extract_between(content, "College of Education, Arts and Sciences", "College of Business")
        if ceas:
            entries.append({
                "category": "Academics - College of Education",
                "question": "What programs does the College of Education, Arts and Sciences offer?",
                "answer": ceas
            })

        # ── 13. College of Business Management and Accountancy ──
        cbma = _extract_between(content, "College of Business Management and Accountancy", "College of Engineering")
        if cbma:
            entries.append({
                "category": "Academics - College of Business",
                "question": "What programs does the College of Business Management and Accountancy offer? Does SPUS offer Accountancy or HRM?",
                "answer": cbma
            })

        # ── 14. College of Engineering & IT ──
        ceit = _extract_between(content, "College of Engineering & Information Technology", "College of Criminal")
        if ceit:
            entries.append({
                "category": "Academics - College of Engineering & IT",
                "question": "What programs does the College of Engineering and Information Technology offer? Does SPUS offer IT or Engineering?",
                "answer": ceit
            })

        # ── 15. College of Criminal Justice Education ──
        ccje = _extract_between(content, "College of Criminal Justice Education", "SPUS TVET")
        if ccje:
            entries.append({
                "category": "Academics - College of Criminal Justice",
                "question": "What programs does the College of Criminal Justice Education offer? Does SPUS offer Criminology or Forensic Science?",
                "answer": ccje
            })

        # ── 16. TVET / TESDA ──
        tvet = _extract_between(content, "SPUS TVET\n\nSPUS TVET", "===")
        if not tvet:
            tvet = _extract_between(content, "SPUS TVET\r\n\r\nSPUS TVET", "===")
        if not tvet:
            tvet = _extract_between(content, "Certify Your Skills", "===")
        if tvet:
            entries.append({
                "category": "TVET / TESDA",
                "question": "What TVET or TESDA programs does SPUS offer? What are the TESDA training and assessment center programs?",
                "answer": f"SPUS TVET: Certify Your Skills. Launch Your Career.\n\n{tvet}"
            })

        # ── 17. Quality Policy ──
        qp = _extract_between(content, "QUALITY POLICY", "===")
        if qp:
            entries.append({
                "category": "About SPUS",
                "question": "What is the SPUS Quality Policy?",
                "answer": f"SPUS {qp}"
            })

        # ── 18. Data Privacy Policy ──
        dp_start = content.find("Data Privacy Policy")
        if dp_start != -1:
            dp_text = content[dp_start:].strip()
            entries.append({
                "category": "About SPUS",
                "question": "What is the SPUS Data Privacy Policy?",
                "answer": dp_text
            })

        return entries

"""Refresh official website knowledge with auditable, bounded crawling."""
from django.core.management.base import BaseCommand

from chatbot.crawling import configure_arguments, run_crawl
from chatbot.web_crawler import HEADERS


CORE_SPUS_PAGES = [
    {
        'title': 'College Admission Requirements',
        'url': 'https://spus.edu.ph/college-admission/',
        'category': 'Admissions',
    },
    {
        'title': 'Basic Education Admission Requirements',
        'url': 'https://spus.edu.ph/basic-education-admission/',
        'category': 'Admissions',
    },
    {
        'title': 'SPUS Contact Information and Office Hours',
        'url': 'https://spus.edu.ph/contact-us-2/',
        'category': 'Contact',
    },
    {
        'title': 'About SPUS & Paulinian Core Values',
        'url': 'https://spus.edu.ph/about-us-2/',
        'category': 'About',
    },
    {
        'title': 'TESDA Programs & TVET Assessment Center',
        'url': 'https://spus.edu.ph/tesda-program/',
        'category': 'TVET',
    },
    {
        'title': 'University Administration & Faculty',
        'url': 'https://spus.edu.ph/administrator/',
        'category': 'Administration',
    },
    {
        'title': 'SPUS Quality Policy',
        'url': 'https://spus.edu.ph/quality-policy/',
        'category': 'Academics',
    },
    {
        'title': 'Pillars and Formative Compasses',
        'url': 'https://spus.edu.ph/the-pillars-and-formative-compasses/',
        'category': 'About',
    },
    {
        'title': 'SPUS University Seal & Insignia',
        'url': 'https://spus.edu.ph/school-seal/',
        'category': 'About',
    },
    {
        'title': 'College Department Overview & Academic Programs',
        'url': 'https://spus.edu.ph/college-department/',
        'category': 'Academics',
    },
    {
        'title': 'College of Health Sciences - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-health-sciences/',
        'category': 'Academics',
    },
    {
        'title': 'College of Business Management and Accountancy - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-business-management-and-accountancy/',
        'category': 'Academics',
    },
    {
        'title': 'College of Education, Arts and Sciences - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-education-arts-and-sciences/',
        'category': 'Academics',
    },
    {
        'title': 'College of Engineering and Information Technology - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-engineering-and-information-technology/',
        'category': 'Academics',
    },
    {
        'title': 'College of Criminal Justice Education - Academic Programs',
        'url': 'https://spus.edu.ph/college-of-criminal-justice-education/',
        'category': 'Academics',
    },
    {
        'title': 'Graduate School and Professional Studies (GSPS) Programs',
        'url': 'https://spus.edu.ph/graduate-school/',
        'category': 'Academics',
    },
    {
        'title': 'Basic Education Department (Grade School, JHS, SHS)',
        'url': 'https://spus.edu.ph/basic-education/',
        'category': 'Academics',
    },
    {
        'title': 'SPUS Online Services Portal',
        'url': 'https://spus.edu.ph/online-services/',
        'category': 'Services',
    },
    {
        'title': 'SPUS Research, Innovations & Publications',
        'url': 'https://spus.edu.ph/research/',
        'category': 'Research',
    },
    {
        'title': 'Office of the Vice President for Academic Services (OVPaCS)',
        'url': 'https://sites.google.com/spus.edu.ph/spusovpacs/home',
        'category': 'Academics',
    },
    {
        'title': 'SPUS Finance Services Portal & Payment Guidelines',
        'url': 'https://sites.google.com/spus.edu.ph/spusfinanceservices/home',
        'category': 'Finance',
    },
    {
        'title': 'St. Paul University Surigao Library Portal',
        'url': 'https://library.spus.edu.ph/',
        'category': 'Academics',
    },
    {
        'title': 'Data Privacy Policy',
        'url': 'https://spus.edu.ph/data-privacy-policy/',
        'category': 'Policy',
    },
    {
        'title': 'SPUS Official Homepage & Campus Overview',
        'url': 'https://spus.edu.ph/',
        'category': 'General',
    },
]


class Command(BaseCommand):
    help = 'Crawl official SPUS pages with section-aware extraction and PostgreSQL ingestion'

    def add_arguments(self, parser):
        configure_arguments(parser)

    def handle(self, *args, **options):
        return run_crawl(self, CORE_SPUS_PAGES, options)

"""Bounded official-site fetching and DOM-aware extraction, without an LLM.

Personnel relationships come from the site's team cards and containing accordion,
never from SEO descriptions, portrait filenames, or the proximity of loose text.
"""
from dataclasses import dataclass, field
from html.parser import HTMLParser
import hashlib
import re
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
PERSON_CATEGORY = 'Website personnel'
ROSTER_CATEGORY = 'Website faculty roster'
IGNORED = {'head', 'script', 'style', 'noscript', 'nav', 'header', 'footer', 'svg', 'form'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
ASSET = re.compile(r'\.(?:jpg|jpeg|png|gif|webp|svg|ico|css|js|pdf|zip|mp4|mp3|docx?|xlsx?)$', re.I)


def compact(text):
    return ' '.join(text.split())


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def has_class(self, name):
        return name in self.attrs.get('class', '').split()

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        if self.tag in IGNORED:
            return ''
        return compact(' '.join(child.text() if isinstance(child, Node) else child for child in self.children))


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node('document')
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def short_title(value):
    if len(value) <= 255:
        return value
    return value[:240] + ' ' + hashlib.sha256(value.encode()).hexdigest()[:12]


def administration_records(document):
    """Extract every complete team card, retaining its actual section label."""
    people, incomplete = [], []
    tab_sections = {node.attrs.get('aria-controls'): node.text() for node in document.root.walk()
                    if node.attrs.get('role') == 'tab' and node.attrs.get('aria-controls')}

    def visit(node, section=''):
        if node.tag in IGNORED:
            return
        if node.attrs.get('id') in tab_sections:
            section = tab_sections[node.attrs['id']]
        if node.tag == 'details':
            summary = next((child for child in node.children if isinstance(child, Node) and child.tag == 'summary'), None)
            if summary:
                label = next((item for item in summary.walk() if item.has_class('e-n-accordion-item-title-text')), summary)
                section = label.text()
        if node.has_class('tlp-content'):
            name_node = next((item for item in node.walk() if item.has_class('team-name')), None)
            role_node = next((item for item in node.walk() if item.has_class('tlp-position')), None)
            name, role = name_node.text() if name_node else '', role_node.text() if role_node else ''
            if name and role and section:
                people.append({'name': name, 'role': role, 'section': section})
            else:
                incomplete.append({'name': name, 'role': role, 'section': section})
            return
        for child in node.children:
            if isinstance(child, Node):
                visit(child, section)

    visit(document.root)
    people = list({(p['section'], p['name'], p['role']): p for p in people}.values())
    records = [dict(title=short_title(f"SPUS Personnel | {p['section']} | {p['role']} | {p['name']}"),
                    category=PERSON_CATEGORY,
                    content=f"Section: {p['section']}\nName: {p['name']}\nRole: {p['role']}") for p in people]
    sections = {}
    for person in people:
        # Merely appearing in a college section does not establish a faculty role.
        if re.search(r'\b(faculty|instructor|professor|lecturer|teacher)\b', person['role'], re.I):
            sections.setdefault(person['section'], []).append(person)
    for section, faculty in sections.items():
        records.append(dict(title=short_title(f'SPUS Faculty Directory | {section}'), category=ROSTER_CATEGORY,
                            content=f'Faculty listed under {section} on the official SPUS website:\n' +
                            '\n'.join(f"- {p['name']} — {p['role']}" for p in faculty)))
    return records, {'people_cards': len(people), 'sections': sorted({p['section'] for p in people}),
                     'faculty_counts': {key: len(value) for key, value in sections.items()},
                     'incomplete_cards': incomplete}


def visible_blocks(document):
    blocks = []

    def visit(node):
        if node.tag in IGNORED:
            return
        if node.tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'tr', 'summary'}:
            text = node.text()
            if text:
                blocks.append(('heading' if node.tag.startswith('h') and len(node.tag) == 2 else 'text', text))
            return
        for child in node.children:
            if isinstance(child, Node):
                visit(child)
            elif compact(child):
                blocks.append(('text', compact(child)))

    visit(document.root)
    return blocks


def extract_records(html, title, category, administration=False):
    document = Document(html)
    if administration:
        records, details = administration_records(document)
        # A site layout change or missing card role must be reviewed before replacement.
        if not records or len(details['incomplete_cards']) > max(2, details['people_cards'] * 0.05):
            raise ValueError('Administration extraction incomplete; preserving previous page records')
        return records, details
    records, section, current, length = [], title, [], 0

    def flush():
        nonlocal current, length
        if current:
            records.append(dict(title=short_title(f'{title} | {section} (Part {len(records) + 1})'),
                                category=category, content=section + '\n' + '\n'.join(current)))
            current, length = [], 0

    for kind, text in visible_blocks(document):
        if kind == 'heading':
            flush()
            section = text
        else:
            # Bound unusually long paragraphs without carrying a preceding section.
            for offset in range(0, len(text), 1600):
                part = text[offset:offset + 1600]
                if length + len(part) > 1600:
                    flush()
                current.append(part)
                length += len(part)
    flush()
    if sum(len(record['content']) for record in records) < 100:
        raise ValueError('Insufficient visible text; preserving previous page records')
    return records, {'chunks': len(records)}


def canonical_url(value, allowed_hosts=('spus.edu.ph',)):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
        raise ValueError('URL is outside the explicit HTTPS host allowlist')
    if parsed.port not in (None, 443) or parsed.query or ASSET.search(parsed.path):
        raise ValueError('Query strings, nonstandard ports and assets are outside the crawl scope')
    if re.search(r'/(?:wp-admin|wp-login\.php|wp-json|feed|cdn-cgi|search)(?:/|$)', parsed.path, re.I):
        raise ValueError('Administrative, search and API paths are outside the crawl scope')
    return urlunsplit(('https', parsed.hostname, parsed.path.rstrip('/') + '/', '', ''))


class OfficialSiteClient:
    """Respect robots, throttle requests, validate each redirect, bound downloads."""
    def __init__(self, allowed_hosts, delay=0.5, session=None):
        self.allowed_hosts = tuple(allowed_hosts)
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay
        self.last_request = 0
        self.robots = {}

    def _request(self, url, limit=8 * 1024 * 1024):
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        response = self.session.get(url, timeout=(10, 30), allow_redirects=False, stream=True)
        try:
            if response.is_redirect:
                return response.status_code, response.headers, b''
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > limit:
                    raise ValueError('Response exceeds download limit')
            return response.status_code, response.headers, bytes(data)
        finally:
            response.close()

    def _robots(self, url):
        origin = 'https://' + urlsplit(url).hostname
        if origin not in self.robots:
            status, _, body = self._request(origin + '/robots.txt', limit=512 * 1024)
            if status == 404:
                body = b'User-agent: *\nDisallow:'
            elif status != 200:
                raise ValueError(f'robots.txt unavailable (HTTP {status}); crawl stopped for this host')
            elif not re.search(rb'(?im)^\s*user-agent\s*:', body):
                raise ValueError('robots.txt did not contain valid crawler rules')
            parser = RobotFileParser()
            parser.parse(body.decode('utf-8', errors='replace').splitlines())
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch('PAULA', url):
            raise ValueError('robots.txt disallows this page')
        self.delay = max(self.delay, parser.crawl_delay('PAULA') or parser.crawl_delay('*') or 0)

    def fetch(self, url):
        url = canonical_url(url, self.allowed_hosts)
        for _ in range(5):
            self._robots(url)
            status, headers, body = self._request(url)
            if status in (301, 302, 303, 307, 308):
                url = canonical_url(urljoin(url, headers.get('Location', '')), self.allowed_hosts)
                continue
            if status != 200:
                raise ValueError(f'Page returned HTTP {status}; previous records preserved')
            if 'html' not in headers.get('Content-Type', '').lower():
                raise ValueError('Page is not HTML')
            # WordPress declares UTF-8; requests otherwise defaults HTML to Latin-1.
            html = body.decode('utf-8-sig', errors='replace')
            if re.search(r'<title>\s*(?:Just a moment|Not Acceptable|Access Denied)', html, re.I):
                raise ValueError('Access challenge received; previous records preserved')
            return url, html
        raise ValueError('Too many redirects')


def discover_links(html, source, allowed_hosts):
    urls = set()
    for node in Document(html).root.walk():
        if node.tag != 'a' or not node.attrs.get('href'):
            continue
        try:
            url = canonical_url(urljoin(source, node.attrs['href']), allowed_hosts)
            if urlsplit(url).hostname == urlsplit(source).hostname:
                urls.add(url)
        except ValueError:
            continue
    return sorted(urls)

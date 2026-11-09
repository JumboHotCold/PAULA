"""Worker-start snapshot of the build; never reinterpret later Git commits as loaded code."""
from functools import lru_cache
import hashlib
from pathlib import Path
import re
from django.conf import settings

COMMIT = re.compile(r'[0-9a-fA-F]{40}')


def _git_commit(root):
    directory = root / '.git'
    try:
        if directory.is_file():
            pointer = directory.read_text(encoding='utf-8').strip()
            if not pointer.startswith('gitdir: '):
                return None
            directory = (root / pointer[8:]).resolve()
        head = (directory / 'HEAD').read_text(encoding='utf-8').strip()
        if COMMIT.fullmatch(head):
            return head.lower()
        if not head.startswith('ref: refs/'):
            return None
        reference = head[5:]
        if '..' in Path(reference).parts:
            return None
        path = directory / reference
        if path.is_file():
            value = path.read_text(encoding='utf-8').strip()
            return value.lower() if COMMIT.fullmatch(value) else None
        for line in (directory / 'packed-refs').read_text(encoding='utf-8').splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == reference and COMMIT.fullmatch(parts[0]):
                return parts[0].lower()
    except OSError:
        return None
    return None


def _source_digest(root):
    digest, count = hashlib.sha256(), 0
    try:
        for folder in ('chatbot', 'paulibot'):
            for path in sorted((root / folder).rglob('*')):
                if (not path.is_file() or path.suffix not in ('.py', '.json', '.html') or
                        path.name.startswith(('test_', 'audit_'))):
                    continue
                digest.update(path.relative_to(root).as_posix().encode() + b'\0')
                digest.update(path.read_bytes().replace(b'\r\n', b'\n') + b'\0')
                count += 1
    except OSError:
        return None
    return digest.hexdigest() if count else None


@lru_cache(maxsize=1)
def _build_snapshot():
    root = Path(settings.BASE_DIR)
    configured = settings.PAULA_BUILD_COMMIT.strip()
    if configured and configured != 'unknown' and not COMMIT.fullmatch(configured):
        raise ValueError('PAULA_BUILD_COMMIT must be a full 40-character Git commit hash')
    commit = _git_commit(root)
    if commit:
        source = 'git'  # A development bind mount overrides the image's baked source.
    elif configured and configured != 'unknown':
        commit, source = configured.lower(), 'environment'
    else:
        source = 'unknown'
    return commit, source, _source_digest(root)


def build_info():
    commit, source, digest = _build_snapshot()
    return {'build_commit': commit, 'build_source': source, 'build_source_digest': digest}

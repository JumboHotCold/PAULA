"""Compare OCR readings of the same image region; retain originals and audit trail.

Only substitutes verbatim recognized lines, never generates missing wording.
Run after reocr_office_documents.py completes. Does not touch source PDFs/JSON.
"""
import argparse
import json
from pathlib import Path
import re
import statistics


def rect(row):
    return (min(p[0] for p in row['box']), min(p[1] for p in row['box']),
            max(p[0] for p in row['box']), max(p[1] for p in row['box']))


def same_region(left, right):
    a, b = rect(left), rect(right)
    aw, ah = a[2] - a[0], a[3] - a[1]
    bw, bh = b[2] - b[0], b[3] - b[1]
    if min(aw, ah, bw, bh) <= 0 or not 0.5 <= aw / bw <= 2:
        return False
    if abs((a[1] + a[3]) / 2 - (b[1] + b[3]) / 2) > max(ah, bh) * 0.35:
        return False
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return overlap / min(aw * ah, bw * bh) >= 0.7


def reconcile(page):
    primary = next(run for run in page['passes'] if run['name'] == page['selected_pass'])
    rows, changes = [], []
    for index, original in enumerate(primary['rows']):
        alternatives = [(run['name'], row) for run in page['passes'] for row in run['rows']
                        if same_region(original, row)]
        if not alternatives:
            rows.append(original)
            continue
        name, best = max(alternatives, key=lambda pair: pair[1]['confidence'])
        if best['confidence'] >= 0.90 and best['confidence'] >= original['confidence'] + 0.05 and best['text'] != original['text']:
            rows.append(best)
            changes.append({'line': index + 1, 'original_pass': primary['name'],
                            'original_text': original['text'], 'original_confidence': original['confidence'],
                            'replacement_pass': name, 'replacement_text': best['text'],
                            'replacement_confidence': best['confidence'], 'box': best['box'],
                            'status': 'heuristic_alternate_reading_not_verified'})
        else:
            rows.append(original)
    return rows, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.review / 'manifest.json').read_text(encoding='utf-8'))
    audit = []
    for document in manifest['documents']:
        key = Path(document['source']).stem.replace(' ', '_')
        # Manifest source names deliberately correspond to output keys.
        folder = args.review / key
        combined = []
        for page_path in sorted(folder.glob('page_*.json')):
            if not re.fullmatch(r'page_\d{2}\.json', page_path.name):
                continue
            page = json.loads(page_path.read_text(encoding='utf-8'))
            rows, changes = reconcile(page)
            text = '\n'.join(row['text'] for row in rows)
            (folder / f'page_{page["page"]:02d}_reconciled.txt').write_text(text + '\n', encoding='utf-8')
            combined.append(f'--- PAGE {page["page"]} ---\n{text}\n')
            low = [row for row in rows if row['confidence'] < 0.85]
            audit.append({'document': key, 'page': page['page'], 'substitutions': changes,
                          'remaining_low_confidence_lines': low,
                          'mean_confidence': round(statistics.mean(row['confidence'] for row in rows), 4) if rows else None})
        (folder / 'reconciled_text.txt').write_text('\n'.join(combined), encoding='utf-8')
    (args.review / 'reconciliation_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Compared {len(audit)} pages; {sum(len(page["substitutions"]) for page in audit)} alternate readings retained.')


if __name__ == '__main__':
    main()

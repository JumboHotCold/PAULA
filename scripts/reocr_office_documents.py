"""Re-OCR office PDFs into a NEW review folder; never ingest or rewrite sources.

Designed for a disposable worker with office_documents mounted read-only.
OCR scores measure model recognition confidence, not factual/source validity.
"""
import argparse
import difflib
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time


DOCUMENTS = (
    ('Registrar/REGISTRAR ENROLLMENT PROCEDURES.pdf', 'REGISTRAR_ENROLLMENT_PROCEDURES', 'Registrar'),
    ('PBMO/PBMO FAQs.pdf', 'PBMO_FAQs', 'PBMO'),
    ('PBMO/PBMO PROCEDURES.pdf', 'PBMO_PROCEDURES', 'PBMO'),
    ('PBMO/PBMO SPUS BRANDING.pdf', 'PBMO_SPUS_BRANDING', 'PBMO'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text):
    return ' '.join(re.findall(r'\w+', text.lower()))


def ordered_rows(rows):
    if not rows:
        return []
    heights = [max(point[1] for point in row['box']) - min(point[1] for point in row['box']) for row in rows]
    bucket = max(8, statistics.median(heights) * 0.65)
    return sorted(rows, key=lambda row: (round(min(p[1] for p in row['box']) / bucket), min(p[0] for p in row['box'])))


def run_pass(engine, image, name, offset_y=0):
    import numpy as np
    started = time.monotonic()
    raw, _ = engine(np.asarray(image))
    rows = []
    for box, text, score in raw or []:
        if text.strip():
            rows.append({'box': [[round(float(x), 2), round(float(y) + offset_y, 2)] for x, y in box],
                         'text': text.strip(), 'confidence': round(float(score), 6)})
    rows = ordered_rows(rows)
    return {'name': name, 'seconds': round(time.monotonic() - started, 2),
            'rows': rows, 'text': '\n'.join(row['text'] for row in rows)}


def statistics_for(rows):
    scores = [row['confidence'] for row in rows]
    chars = sum(len(row['text']) for row in rows)
    return {'lines': len(rows), 'characters': chars,
            'mean_confidence': round(statistics.mean(scores), 4) if scores else None,
            'low_confidence_lines_below_0_85': sum(score < 0.85 for score in scores)}


def quality(pass_result):
    # Advisory preference for fuller, confidently recognized text. All passes
    # remain available; this does not establish which transcription is correct.
    return sum(len(row['text']) * row['confidence'] ** 2 for row in pass_result['rows'])


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def compare_knowledge(input_root, output_root, pages, filename='knowledge_comparison.json'):
    reviews = []
    for office in ('Registrar', 'PBMO'):
        path = input_root / office / f'{office}_knowledge.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        office_pages = [page for page in pages if page['office'] == office]
        for number, item in enumerate(data.get('items', []), 1):
            answer = item.get('answer', '')
            tokens = set(re.findall(r'[a-z]{4,}', answer.lower()))
            matches = []
            for page in office_pages:
                page_text = normalized(page['text'])
                page_tokens = set(page_text.split())
                score = len(tokens & page_tokens) / max(1, len(tokens))
                matches.append((score, page))
            matches.sort(key=lambda pair: -pair[0])
            # Candidate pages help a human compare. Lexical coverage is not an
            # entailment test and cannot automatically verify a knowledge item.
            top = matches[:3]
            corpus = ' '.join(normalized(page['text']) for page in office_pages)
            literal_numbers = sorted(set(re.findall(r'#[0-9a-fA-F]{6}\b|\b\d{2,}(?:[:.]\d+)?\b', answer)))
            absent = [value for value in literal_numbers
                      if normalized(value).replace(' ', '') not in corpus.replace(' ', '')]
            reviews.append({'office': office, 'item': number, 'question': item.get('question'),
                            'status': 'manual_comparison_required',
                            'candidate_pages': [{'document': page['document'], 'page': page['page'],
                                                 'lexical_coverage': round(score, 3)} for score, page in top],
                            'literal_numbers_not_found_in_selected_ocr': absent})
    write_json(output_root / filename, reviews)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review-date', default='2026-10-27')
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--bootstrap-target', type=Path)
    args = parser.parse_args()
    if args.bootstrap_target:
        target = str(args.bootstrap_target)
        # Isolated temporary target, never the app environment or requirements.
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                        '--no-cache-dir', '--target', target, '--no-deps',
                        'rapidocr_onnxruntime==1.4.4'], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                        '--no-cache-dir', '--target', target,
                        '--no-deps', 'onnxruntime==1.31.1', 'pyclipper==1.4.0',
                        'shapely==2.2.0', 'flatbuffers==25.12.19'], check=True)
        sys.path.insert(0, target)

    import fitz
    from PIL import Image, ImageOps, ImageDraw
    from rapidocr_onnxruntime import RapidOCR

    input_root = args.input.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if (output_root / 'manifest.json').exists():
        raise RuntimeError('This review already has a manifest; choose a new output folder.')
    engine = RapidOCR(text_score=0.3, det_limit_side_len=1600,
                      intra_op_num_threads=2, inter_op_num_threads=1)
    versions = {name: importlib.metadata.version(name) for name in
                ('rapidocr-onnxruntime', 'onnxruntime', 'PyMuPDF', 'Pillow', 'numpy')}
    manifest = {'review_date': args.review_date, 'versions': versions,
                'method': 'color + grayscale/autocontrast + overlapping vertical tiles',
                'confidence_caution': 'OCR model confidence is not a measured accuracy or factual verification rate.',
                'documents': []}
    all_pages = []

    for relative, key, office in DOCUMENTS:
        pdf_path = input_root / relative
        before = digest(pdf_path)
        folder = output_root / key
        folder.mkdir(exist_ok=True)
        pdf = fitz.open(pdf_path)
        doc_info = {'source': relative, 'office': office, 'sha256_before': before,
                    'bytes': pdf_path.stat().st_size, 'page_count': len(pdf), 'pages': []}
        combined = []
        for index, page in enumerate(pdf, 1):
            print(f'OCR {key} page {index}/{len(pdf)}', flush=True)
            pix = page.get_pixmap(dpi=args.dpi, colorspace=fitz.csRGB, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            # Retain sufficient detail without upscaling massive scanned sheets.
            image.thumbnail((4200, 4200))
            grayscale = ImageOps.autocontrast(ImageOps.grayscale(image)).convert('RGB')
            passes = [run_pass(engine, image, 'color'), run_pass(engine, grayscale, 'autocontrast')]
            height = image.height
            overlap = max(100, height // 12)
            split = height // 2
            upper = run_pass(engine, grayscale.crop((0, 0, image.width, split + overlap)), 'upper_tile')
            lower_start = max(0, split - overlap)
            lower = run_pass(engine, grayscale.crop((0, lower_start, image.width, height)), 'lower_tile', lower_start)
            # Each row belongs to one half by its center, avoiding overlap duplicates.
            tile_rows = [row for row in upper['rows'] if statistics.mean(p[1] for p in row['box']) < split]
            tile_rows += [row for row in lower['rows'] if statistics.mean(p[1] for p in row['box']) >= split]
            tile_rows = ordered_rows(tile_rows)
            passes.append({'name': 'overlapping_tiles', 'seconds': upper['seconds'] + lower['seconds'],
                           'rows': tile_rows, 'text': '\n'.join(row['text'] for row in tile_rows)})
            chosen = max(passes, key=quality)
            stats = statistics_for(chosen['rows'])
            flags = []
            if stats['characters'] < 100:
                flags.append('sparse_text_or_graphic_page_check_visually')
            if stats['low_confidence_lines_below_0_85']:
                flags.append('low_confidence_lines_present')
            base_similarity = difflib.SequenceMatcher(None, normalized(passes[0]['text']),
                                                       normalized(passes[1]['text']), autojunk=False).ratio()
            if base_similarity < 0.9:
                flags.append('color_and_contrast_passes_disagree')
            result = {'document': key, 'office': office, 'page': index,
                      'pdf_text_layer_characters': len(page.get_text()), 'requested_render_dpi': args.dpi,
                      'ocr_image_size': list(image.size), 'selected_pass': chosen['name'],
                      'selection_is_heuristic': True, 'stats': stats, 'review_flags': flags,
                      'color_contrast_text_similarity': round(base_similarity, 4), 'passes': passes}
            write_json(folder / f'page_{index:02d}.json', result)
            (folder / f'page_{index:02d}.txt').write_text(chosen['text'] + '\n', encoding='utf-8')
            preview = image.copy()
            preview.thumbnail((1400, 1800))
            preview.save(folder / f'page_{index:02d}.jpg', quality=88)
            overlay = image.copy()
            draw = ImageDraw.Draw(overlay)
            for row in chosen['rows']:
                if row['confidence'] < 0.85:
                    draw.line([tuple(point) for point in row['box']] + [tuple(row['box'][0])], fill='red', width=4)
            overlay.thumbnail((1400, 1800))
            overlay.save(folder / f'page_{index:02d}_low_confidence.jpg', quality=88)
            combined.append(f'--- PAGE {index} ---\n{chosen["text"]}\n')
            page_summary = {field: result[field] for field in
                            ('page', 'pdf_text_layer_characters', 'selected_pass', 'stats', 'review_flags')}
            doc_info['pages'].append(page_summary)
            all_pages.append({'document': key, 'office': office, 'page': index, 'text': chosen['text']})
            print(f'  {stats["lines"]} lines; {stats["characters"]} chars; '
                  f'{stats["low_confidence_lines_below_0_85"]} lines flagged; selected {chosen["name"]}', flush=True)
        pdf.close()
        transcript = '\n'.join(combined)
        (folder / 'raw_text.txt').write_text(transcript, encoding='utf-8')
        previous = input_root / 'extracted' / f'{key}_raw.txt'
        if previous.exists():
            old = previous.read_text(encoding='utf-8', errors='replace')
            diff = difflib.unified_diff(old.splitlines(), transcript.splitlines(),
                                        fromfile='previous_extraction', tofile='new_ocr', lineterm='')
            (folder / 'comparison_to_previous.diff').write_text('\n'.join(diff) + '\n', encoding='utf-8')
            doc_info['previous_characters'] = len(old)
        doc_info['new_characters'] = len(transcript)
        doc_info['sha256_after'] = digest(pdf_path)
        if doc_info['sha256_after'] != before:
            raise RuntimeError(f'Source changed during extraction: {relative}')
        manifest['documents'].append(doc_info)
        # Checkpoint completed documents in case a later PDF is interrupted.
        write_json(output_root / 'manifest.partial.json', manifest)

    compare_knowledge(input_root, output_root, all_pages)
    write_json(output_root / 'manifest.json', manifest)
    report = [f'# Automated Office PDF OCR Review — {args.review_date}', '',
              'All four PDFs were processed locally in an isolated worker. Source PDFs were mounted read-only.',
              'Original source hashes were unchanged. Existing JSON and database knowledge were not updated.', '',
              'OCR was run on every page, including pages that also contain a text layer.', '',
              '| Document | Pages | New transcript characters | Flagged pages |',
              '|---|---:|---:|---:|']
    for doc in manifest['documents']:
        flagged = sum(bool(page['review_flags']) for page in doc['pages'])
        report.append(f'| {doc["source"]} | {doc["page_count"]} | {doc["new_characters"]} | {flagged} |')
    report += ['', '## Method and interpretation', '',
               '- RapidOCR 1.4.4 CPU inference; engine/package versions are recorded in manifest.json.',
               '- Each page has color, grayscale/autocontrast, and overlapping-tile OCR passes.',
               '- The primary transcript is selected heuristically for fuller, confidently recognized text. All passes are retained.',
               '- Page JSON contains recognized boxes and scores. Red outlines in preview overlays identify lines below 0.85 recognition confidence.',
               '- Recognition confidence is not measured character accuracy. High confidence does not prove a transcription is correct.',
               '- Diff files compare against earlier raw extraction; differences may reflect reading order, spacing, omissions, or recognition errors.',
               '- Flowcharts/tables are flattened into text. Consult page previews to establish relationships and reading order.',
               '- knowledge_comparison.json proposes pages to compare with each existing FAQ; lexical coverage does not verify an answer.',
               '- Authenticity, latest-revision status, signatures, names, dates, codes, and branding colors require human/institutional checks.',
               '', '## Engine documentation', '',
               '[RapidOCR 1.4.4 API](https://rapidai.github.io/RapidOCRDocs/v1.4.4/install_usage/api/RapidOCR/)', '']
    (output_root / 'REVIEW_REPORT.md').write_text('\n'.join(report), encoding='utf-8')
    print(f'Completed {len(all_pages)} pages across {len(manifest["documents"])} PDFs.', flush=True)


if __name__ == '__main__':
    main()

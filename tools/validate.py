"""Validate this document repository with Python's standard library only."""
from pathlib import Path
import hashlib
import json
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
errors = []

def check(condition, message):
    if not condition:
        errors.append(message)

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def schema_check(value, schema, location):
    """Check the validation keywords used by data/case.schema.json."""
    kind = schema.get('type')
    valid_type = {
        'object': isinstance(value, dict),
        'array': isinstance(value, list),
        'string': isinstance(value, str),
        'integer': isinstance(value, int) and not isinstance(value, bool),
    }.get(kind, True)
    check(valid_type, f'{location}: expected {kind}')
    if not valid_type:
        return
    if 'const' in schema:
        check(value == schema['const'], f'{location}: invalid constant')
    if 'enum' in schema:
        check(value in schema['enum'], f'{location}: invalid enum')
    if isinstance(value, dict):
        for key in schema.get('required', []):
            check(key in value, f'{location}: missing {key}')
        for key, sub in schema.get('properties', {}).items():
            if key in value:
                schema_check(value[key], sub, f'{location}.{key}')
    if isinstance(value, list):
        check(len(value) >= schema.get('minItems', 0), f'{location}: too few items')
        check(len(value) <= schema.get('maxItems', len(value)), f'{location}: too many items')
        for i, item in enumerate(value):
            schema_check(item, schema.get('items', {}), f'{location}[{i}]')
    if isinstance(value, str):
        check(len(value) >= schema.get('minLength', 0), f'{location}: too short')
    if isinstance(value, int) and not isinstance(value, bool):
        check(value >= schema.get('minimum', value), f'{location}: below minimum')
        check(value <= schema.get('maximum', value), f'{location}: above maximum')

schema = read_json(ROOT / 'data/case.schema.json')
index = read_json(ROOT / 'data/case-index.json')
integrity = read_json(ROOT / 'sources/integrity.json')
expected = {x['id']: x for x in integrity['cases']}
check(len(index['cases']) == 24, 'Index must contain 24 cases')
check([x['id'] for x in index['cases']] == list(range(1, 25)), 'Case IDs must be unique and ordered')
check(len(list((ROOT / 'cases').glob('*/case.md'))) == 24, 'Expected 24 Markdown cases')
check(len(list((ROOT / 'cases').glob('*/case.json'))) == 24, 'Expected 24 JSON cases')
catalog = (ROOT / 'cases/README.md').read_text(encoding='utf-8')
qa_count = 0
figures = 0
for item in index['cases']:
    cid = item['id']
    c = read_json(ROOT / item['json_file'])
    md = (ROOT / item['markdown_file']).read_text(encoding='utf-8')
    schema_check(c, schema, f'case {cid:02d}')
    check(c['identity']['id'] == cid, f'{cid}: ID mismatch')
    check(c['identity']['learning_file'] == item['markdown_file'], f'{cid}: Markdown path mismatch')
    check(c['identity']['data_file'] == item['json_file'], f'{cid}: JSON path mismatch')
    intro = c['one_sentence_intro']
    check(intro == item['one_sentence_intro'], f'{cid}: index intro differs')
    check(intro in md and intro in catalog, f'{cid}: intro missing from Markdown/index')
    check('\n' not in intro and len(intro) >= 60, f'{cid}: intro must be a substantive single paragraph')
    check('```mermaid\nflowchart LR' in md, f'{cid}: missing editorial flow diagram')
    check(sum(c['identity']['ten_minute_timing_seconds']) == 600, f'{cid}: timing is not 10 minutes')
    check(sum(c['facilitation']['discussion_timing_seconds']) == 240, f'{cid}: discussion timing differs')
    p = c['provenance']
    lo, hi = p['pdf_physical_pages']
    check([lo, hi] == item['source_pdf_page_range'], f'{cid}: source range mismatch')
    check([x['pdf_page'] for x in p['original_page_text']] == list(range(lo, hi+1)), f'{cid}: missing source pages')
    check([q['question_id'] for q in p['original_qa']] == ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6'], f'{cid}: incomplete Q&A sequence')
    for q in p['original_qa']:
        qid = q['question_id']
        check(digest(q['original_block']) == expected[cid]['qa'][qid], f'{cid}/{qid}: source text changed')
        check(q['original_block'] in md, f'{cid}/{qid}: full source block missing in Markdown')
        check(f'<a id="{qid.lower()}"></a>' in md, f'{cid}/{qid}: anchor missing')
        qa_count += 1
    check(digest(json.dumps(p['original_page_text'], ensure_ascii=False, sort_keys=True)) == expected[cid]['page_text_sha256'], f'{cid}: source page text changed')
    for path in [p['source_pdf'], p['cover_image']] + [f['asset'] for f in p['figures']]:
        check((ROOT / path).is_file(), f'{cid}: missing asset {path}')
    for fig in p['figures']:
        check(lo <= fig['pdf_page'] <= hi, f'{cid}: figure page outside case')
        figures += 1
    for key, section in c['expanded_learning'].items():
        check(section['source_pdf_page_range'] == [lo, hi], f'{cid}/{key}: wrong source range')
        check(all(q in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6'] for q in section['reference_qa']), f'{cid}/{key}: invalid source Q&A reference')
    for key in ['setting', 'industry_mechanism', 'problem', 'discovery', 'solution', 'delivery', 'implementation', 'evaluation', 'frictions']:
        section = c[key]
        pages = section.get('source_pdf_pages', section.get('based_on_pdf_pages', []))
        check(all(lo <= x <= hi for x in pages), f'{cid}/{key}: reference outside case')
    learn = md.split('## 8. 原图与受访者介绍')[0]
    check(len(re.findall(r'[\u3400-\u9fff]', learn)) >= 2400, f'{cid}: learning section too short')

check(qa_count == 144, 'Expected 144 full Q&A blocks')
check(figures == 50, 'Expected 50 source figures')
check(len(list((ROOT / 'assets').iterdir())) == 74, 'Expected 74 source image files')
pdf = ROOT / 'sources/original-interviews.pdf'
check(hashlib.sha256(pdf.read_bytes()).hexdigest() == integrity['source_pdf_sha256'], 'Original PDF differs')
link_count = 0
for path in ROOT.rglob('*.md'):
    if '.git' in path.parts:
        continue
    text = path.read_text(encoding='utf-8')
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
        if target.startswith(('https://', 'http://', 'mailto:')):
            continue
        file_part, _, anchor = target.partition('#')
        dest = (path.parent / unquote(file_part)).resolve() if file_part else path
        check(dest.exists(), f'{path.relative_to(ROOT)}: broken link {target}')
        if anchor in ['full-interview', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6'] and dest.is_file():
            check(f'<a id="{anchor}"></a>' in dest.read_text(encoding='utf-8'), f'{path.relative_to(ROOT)}: missing anchor {target}')
        link_count += 1

result = {'status': 'passed' if not errors else 'failed', 'case_files': {'markdown': 24, 'json': 24}, 'full_qa_verified': qa_count, 'source_figures': figures, 'original_image_files': 74, 'editorial_flow_diagrams': 24, 'relative_links_checked': link_count, 'schema_keywords_checked': True, 'pdf_sha256': integrity['source_pdf_sha256'], 'errors': errors}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if errors else 0)

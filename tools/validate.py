"""Validate this document repository with Python's standard library only."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
from urllib.parse import unquote
import school

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
check(index.get('schema_version') == '3.2', 'Case index must include reflection and PDF citation routes')
online = read_json(ROOT / 'data/online-school.json')
backend = read_json(ROOT / 'data/school-backend.json')
check(backend.get('schema_version') == 'school-backend-v1', 'School backend route schema is missing')
check(backend.get('active_backend') in ('github', 'feishu'), 'Unknown school backend')
if backend.get('active_backend') == 'feishu':
    manifest_url = backend.get('feishu', {}).get('manifest_url')
    check(backend.get('status') == 'ready' and isinstance(manifest_url, str) and manifest_url.startswith('https://'), 'Feishu cutover requires a ready route and actual HTTPS manifest URL')
check(online.get('mode') == 'online' and online.get('persist_local_materials') is False, 'School entry must use online sources')
check(online.get('skill_install_url') == 'https://github.com/littleduckycoin-ai/DP-FDE-school/tree/main/.codex/skills/school-guide', 'Installable school skill URL is missing or unexpected')
feedback = online.get('feedback', {})
check(feedback.get('channel') == 'case_reflection_files', 'Learner feedback must use case reflection files')
check(feedback.get('path_template') == 'cases/{case_id}/reflections/{learner_id}-{date}.md', 'Reflection path template is missing or unexpected')
check(not (ROOT / '.github/ISSUE_TEMPLATE/learning-note.yml').exists(), 'Learning feedback must not use an Issue form')
pdf_viewer = 'https://littleduckycoin-ai.github.io/DP-FDE-school/sources/original-interviews.pdf'
pdf_template = pdf_viewer + '#page={pdf_page}'
check(online.get('source_pdf', {}).get('pdf_page_url_template') == pdf_template, 'Online service index must expose direct PDF page links')
check(index.get('citation', {}).get('pdf_page_url_template') == pdf_template, 'Case index must expose direct PDF page links')
check((ROOT / '.nojekyll').is_file(), 'GitHub Pages must publish the source PDF without Jekyll processing')
check(len(list((ROOT / 'cases').glob('*/base/case.md'))) == 24, 'Expected 24 Markdown cases')
check(len(list((ROOT / 'cases').glob('*/base/case.json'))) == 24, 'Expected 24 JSON cases')
catalog = (ROOT / 'cases/README.md').read_text(encoding='utf-8')
qa_count = 0
figures = 0
for item in index['cases']:
    cid = item['id']
    online_urls = item.get('online_urls', {})
    check(online_urls.get('raw_json') == online['raw_main_prefix'] + item['json_file'], f'{cid}: online JSON route mismatch')
    check(online_urls.get('raw_markdown') == online['raw_main_prefix'] + item['markdown_file'], f'{cid}: online Markdown route mismatch')
    check('discussions' not in online_urls, f'{cid}: obsolete Issue discussion route remains')
    check(online_urls.get('new_reflection') == online['repository_url'] + '/new/main/' + item['reflections_dir'], f'{cid}: reflection creation route mismatch')
    check(online_urls.get('source_pdf_start') == pdf_viewer + '#page=' + str(item['source_pdf_page_range'][0]), f'{cid}: direct source PDF route mismatch')
    c = read_json(ROOT / item['json_file'])
    md = (ROOT / item['markdown_file']).read_text(encoding='utf-8')
    schema_check(c, schema, f'case {cid:02d}')
    check(c['identity']['id'] == cid, f'{cid}: ID mismatch')
    check(c['identity']['case_id'] == item['case_id'], f'{cid}: case slug mismatch')
    check(item['markdown_file'] == f'cases/{item["case_id"]}/base/case.md', f'{cid}: unexpected base path')
    check((ROOT / item['json_file']).parent.joinpath(c['$schema']).resolve() == ROOT/'data/case.schema.json', f'{cid}: schema path mismatch')
    for area in ['reflections_dir','canon_dir']:
        check((ROOT / item[area] / 'README.md').is_file(), f'{cid}: missing {area} guide')
    reflection_guide = (ROOT / item['reflections_dir'] / 'README.md').read_text(encoding='utf-8')
    check('/issues' not in reflection_guide and 'school-reflection' not in reflection_guide, f'{cid}: reflection guide still routes learning records to Issues')
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

frozen = read_json(ROOT / 'data/base-manifest.json')
frozen_paths = {p.relative_to(ROOT).as_posix() for p in (ROOT/'cases').glob('*/base/*') if p.is_file()}
check(set(frozen['files']) == frozen_paths, 'Frozen base file list differs')
for relative, expected_hash in frozen['files'].items():
    path = ROOT / relative
    check(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash, f'Frozen base changed: {relative}; explain authorized corrections in a reviewed PR')

reflection_count = 0
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-ref', help='Check that a PR preserves the referenced learner history')
args = parser.parse_args()
try:
    reflection_count = len(school.validate_reflections(ROOT))
    if args.base_ref:
        school.preserve_history(ROOT, args.base_ref)
except (ValueError, KeyError, TypeError, OSError) as exc:
    errors.append('Learner records: ' + str(exc))

def frontmatter_json(text):
    match = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not match:
        raise ValueError('Missing frontmatter')
    values = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(':')
        if not sep or key in values:
            raise ValueError('Invalid or duplicate metadata key')
        values[key] = json.loads(value.strip())
    return values

reviewed_docs = list((ROOT/'cases').glob('*/canon/*.md')) + list((ROOT/'patterns').glob('*.md'))
known_case_ids = {x['case_id'] for x in index['cases']}
for path in reviewed_docs:
    if path.name == 'README.md':
        continue
    try:
        meta = frontmatter_json(path.read_text(encoding='utf-8'))
        kind = 'canon' if path.parent.name == 'canon' else 'pattern'
        check(meta.get('document_type') == kind, f'{path}: wrong document type')
        check(meta.get('status') in ['proposed','accepted'], f'{path}: invalid review status')
        check(isinstance(meta.get('authors'),list) and bool(meta['authors']), f'{path}: missing authors')
        if kind == 'canon':
            check(meta.get('case_id') == path.parent.parent.name, f'{path}: wrong case')
        else:
            ids = meta.get('case_ids',[])
            check(isinstance(ids,list) and len(set(ids)) >= 2 and set(ids) <= known_case_ids, f'{path}: pattern needs at least two known cases')
        if meta.get('status') == 'accepted':
            check(isinstance(meta.get('review_pr'),str) and bool(re.fullmatch(r'https://github.com/littleduckycoin-ai/DP-FDE-school/pull/[1-9][0-9]*',meta['review_pr'])), f'{path}: accepted content requires a review PR')
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f'{path.relative_to(ROOT)}: {exc}')

canonical = ROOT/'.codex/skills/school-guide/SKILL.md'
skill_text = canonical.read_text(encoding='utf-8')
check(all(term in skill_text for term in ['pdf_page_url_template', 'source_page_links', '物理页', 'JSON', '默认']), 'School skill must describe original PDF page citations for both backends')
skill_metadata = skill_text.split('---\n',2)[1]
for native in ['.agents','.claude']:
    adapter = ROOT/native/'skills/school-guide/SKILL.md'
    content = adapter.read_text(encoding='utf-8')
    check(content.split('---\n',2)[1] == skill_metadata, f'{native}: skill metadata differs')
    check('../../../.codex/skills/school-guide/SKILL.md' in content, f'{native}: missing canonical rule link')

link_count = 0
for path in ROOT.rglob('*.md'):
    if '.git' in path.parts or '.school' in path.parts:
        continue
    text = school.MARKER.sub('', path.read_text(encoding='utf-8'))
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
        if target.startswith(('https://', 'http://', 'mailto:')):
            continue
        file_part, _, anchor = target.partition('#')
        dest = (path.parent / unquote(file_part)).resolve() if file_part else path
        check(dest.exists(), f'{path.relative_to(ROOT)}: broken link {target}')
        if anchor in ['full-interview', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6'] and dest.is_file():
            check(f'<a id="{anchor}"></a>' in dest.read_text(encoding='utf-8'), f'{path.relative_to(ROOT)}: missing anchor {target}')
        link_count += 1

result = {'status': 'passed' if not errors else 'failed', 'case_files': {'markdown': 24, 'json': 24}, 'full_qa_verified': qa_count, 'frozen_base_files': len(frozen['files']), 'learner_records': reflection_count, 'source_figures': figures, 'original_image_files': 74, 'editorial_flow_diagrams': 24, 'relative_links_checked': link_count, 'schema_keywords_checked': True, 'pdf_sha256': integrity['source_pdf_sha256'], 'errors': errors}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if errors else 0)

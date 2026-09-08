"""Reference online reader: HTTP responses stay in memory; no clone or cache.

For integrations and maintenance verification. Learners use the school's URL,
not this program. Actual agents can use equivalent GitHub or HTTP tools.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import PurePosixPath
import re
import sys
from urllib.parse import urlencode, quote
import urllib.error
import urllib.request

from school import parse_record, record_anchor

REPOSITORY = 'littleduckycoin-ai/DP-FDE-school'


class OnlineReadError(ValueError):
    pass


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise OnlineReadError('A cutoff must include its timezone')
    return parsed.astimezone(timezone.utc)


def safe_path(path):
    if (not isinstance(path, str) or not path or path.startswith('/') or
            '\\' in path or '..' in PurePosixPath(path).parts):
        raise OnlineReadError('Unsafe repository path')
    return path


class OnlineSchool:
    def __init__(self, token=None, transport=None):
        self.token = token
        self.transport = transport or self._http
        self.api = 'https://api.github.com/repos/' + REPOSITORY
        self.web = 'https://github.com/' + REPOSITORY

    def _http(self, path, params):
        url = self.api + path + ('?' + urlencode(params) if params else '')
        headers = {'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28',
                   'Cache-Control': 'no-cache',
                   'User-Agent': 'FDE-Online-School'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise OnlineReadError(
                f'Online request failed with HTTP {exc.code}; no local fallback was used') from None
        except urllib.error.URLError:
            raise OnlineReadError(
                'Online request failed; no local fallback was used') from None

    def get(self, path, **params):
        return self.transport(path, params)

    def head(self):
        commit = self.get('/commits/main').get('sha', '')
        if not re.fullmatch('[a-f0-9]{40}', commit):
            raise OnlineReadError('The online main revision could not be verified')
        return commit

    def file(self, path, commit):
        safe_path(path)
        response = self.get('/contents/' + quote(path, safe='/'), ref=commit)
        if (not isinstance(response, dict) or response.get('type') != 'file' or
                response.get('encoding') != 'base64'):
            raise OnlineReadError('The response is not complete file content')
        try:
            return base64.b64decode(
                ''.join(response['content'].split()), validate=True).decode('utf-8')
        except (ValueError, KeyError, UnicodeDecodeError):
            raise OnlineReadError('The response body could not be decoded') from None

    def directory(self, path, commit):
        safe_path(path)
        response = self.get('/contents/' + quote(path, safe='/'), ref=commit)
        if not isinstance(response, list):
            raise OnlineReadError('The response is not a complete directory listing')
        if len(response) >= 1000:
            raise OnlineReadError(
                'The directory listing may be truncated; use the Git Trees API')
        prefix = path.rstrip('/') + '/'
        for item in response:
            item_path = item.get('path', '') if isinstance(item, dict) else ''
            if (item.get('type') not in {'file', 'dir'} or
                    not item_path.startswith(prefix) or
                    '/' in item_path[len(prefix):]):
                raise OnlineReadError('The directory listing contains an invalid entry')
            safe_path(item_path)
        return response

    def index(self, commit):
        value = json.loads(self.file('data/case-index.json', commit))
        if not isinstance(value.get('cases'), list):
            raise OnlineReadError('The online case index is incomplete')
        return value

    def lesson(self, case):
        commit = self.head()
        index = self.index(commit)
        row = next((r for r in index['cases']
                    if str(case) in [str(r['id']), f'{r["id"]:02d}', r['case_id']]), None)
        if row is None:
            raise OnlineReadError('Case not found in the current online index')
        value = json.loads(self.file(row['json_file'], commit))
        if value['identity']['case_id'] != row['case_id']:
            raise OnlineReadError('Online case identity differs from its index')
        return {'source_commit': commit,
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'source_url': self.web + '/blob/' + commit + '/' + row['json_file'],
                'case_id': row['case_id'], 'case': value,
                'local_materials_written': False}

    def reflections(self, case_ids, cutoff=None):
        commit = self.head()
        index = self.index(commit)
        requested = {str(v) for v in case_ids}
        rows = [r for r in index['cases']
                if requested.intersection({str(r['id']), f'{r["id"]:02d}', r['case_id']})]
        if len(rows) != len(requested):
            found = {v for r in rows for v in
                     (str(r['id']), f'{r["id"]:02d}', r['case_id'])}
            missing = sorted(requested - found)
            raise OnlineReadError('Case not found in the current online index: ' + ', '.join(missing))
        stop = timestamp(cutoff) if cutoff else datetime.now(timezone.utc)
        files = []
        interactions = []
        records = []
        entry_ids = set()
        skipped_after_cutoff = 0
        for row in rows:
            folder = row['reflections_dir']
            listing = self.directory(folder, commit)
            markdown = sorted((
                item for item in listing
                if item['type'] == 'file' and item['path'].endswith('.md')
                and PurePosixPath(item['path']).name != 'README.md'),
                key=lambda item: item['path'])
            for item in markdown:
                path = item['path']
                record = parse_record(self.file(path, commit))
                expected = (folder + '/' + record['learner_id'] + '-' +
                            record['study_date'] + '.md')
                if (record['case_id'] != row['case_id'] or path != expected or
                        record['visibility'] != 'shared_draft'):
                    raise OnlineReadError('Reflection identity differs from its path: ' + path)
                file_url = self.web + '/blob/' + commit + '/' + path
                files.append({'path': path, 'source_url': file_url,
                              'case_id': record['case_id'],
                              'learner_id': record['learner_id'],
                              'display_name': record['display_name']})
                for turn in record['interactions']:
                    if timestamp(turn['created_at']) > stop:
                        skipped_after_cutoff += 1
                        continue
                    interactions.append({
                        'case_id': record['case_id'],
                        'learner_id': record['learner_id'],
                        'display_name': record['display_name'],
                        'source_path': path,
                        'source_url': file_url,
                        'interaction': turn})
                    for position, contribution in enumerate(turn['contributions']):
                        entry_id = contribution['entry_id']
                        if entry_id in entry_ids:
                            raise OnlineReadError('Duplicate reflection entry ID: ' + entry_id)
                        entry_ids.add(entry_id)
                        records.append({
                            **contribution,
                            'case_id': record['case_id'],
                            'learner_id': record['learner_id'],
                            'display_name': record['display_name'],
                            'interaction_id': turn['interaction_id'],
                            'created_at': turn['created_at'],
                            'source_path': path,
                            'source_url': file_url + '#' +
                                          record_anchor(turn['interaction_id'], position)})
        records.sort(key=lambda row: (timestamp(row['created_at']), row['entry_id']))
        interactions.sort(key=lambda row: (
            timestamp(row['interaction']['created_at']),
            row['case_id'], row['learner_id'], row['interaction']['interaction_id']))
        return {'source_commit': commit,
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'cutoff': stop.isoformat(),
                'files': files,
                'interactions': interactions,
                'records': records,
                'interactions_after_cutoff': skipped_after_cutoff,
                'all_files_read': True,
                'local_materials_written': False,
                'note': 'Reflections are attributed learner knowledge, not reviewed case facts or consensus.'}


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', default='04')
    parser.add_argument('--reflections', action='store_true')
    args = parser.parse_args()
    client = OnlineSchool(token=os.environ.get('SCHOOL_GITHUB_TOKEN'))
    try:
        data = client.lesson(args.case)
        result = {k: v for k, v in data.items() if k != 'case'}
        result.update(
            one_sentence_intro=data['case']['one_sentence_intro'],
            source_pdf_pages=data['case']['provenance']['pdf_physical_pages'],
            original_qa_count=len(data['case']['provenance']['original_qa']))
        if args.reflections:
            result['reflections'] = client.reflections([data['case_id']])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OnlineReadError, KeyError, ValueError) as exc:
        print('Online reading unavailable: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

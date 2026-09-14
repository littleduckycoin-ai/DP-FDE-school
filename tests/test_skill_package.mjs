import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { main, validatePayload } from '../skills/school-guide/scripts/feishu_school.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const skill = join(root, 'skills/school-guide');

function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? files(path) : [path];
  });
}

test('one discoverable, self-contained skill includes its script and references', () => {
  assert.deepEqual(readdirSync(join(root, 'skills')), ['school-guide']);
  const text = readFileSync(join(skill, 'SKILL.md'), 'utf8');
  assert.match(text, /^---\nname: school-guide\ndescription: .+\n---/);
  assert.ok(existsSync(join(skill, 'scripts/feishu_school.mjs')));
  assert.equal(files(skill).filter(path => path.endsWith('SKILL.md')).length, 1);
  for (const path of files(skill).filter(path => path.endsWith('.md'))) {
    for (const [, target] of readFileSync(path, 'utf8').matchAll(/\]\(([^)]+)\)/g)) {
      if (/^https?:\/\//.test(target)) continue;
      const resolved = resolve(dirname(path), target.split('#')[0]);
      assert.ok(resolved.startsWith(skill + '/'), `Reference escapes installed Skill: ${path}: ${target}`);
      assert.ok(existsSync(resolved), `Missing reference: ${path}: ${target}`);
    }
  }
});

test('help runs without Feishu tooling, credentials or network', async () => {
  const fetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('Unexpected network call'); };
  try {
    const result = await main(['--help']);
    assert.ok(result.commands.bootstrap);
    assert.ok(result.commands.append);
  } finally { globalThis.fetch = fetch; }
});

test('documented reflection example conforms to the real input contract', () => {
  const text = readFileSync(join(skill, 'references/reflection-example.md'), 'utf8');
  const payload = JSON.parse(text.match(/```json\n([\s\S]*?)\n```/)[1]);
  const row = { case_id: 'case-01-manufacturing-training', source_pdf_pages: [8, 9] };
  assert.doesNotThrow(() => validatePayload(payload, row, [row]));
});

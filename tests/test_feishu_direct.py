"""Create-only staging: no discovery, trusted receipts, private source preservation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("migrate_feishu_direct", ROOT / "tools/migrate_feishu_direct.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class NoListTransport:
    def __init__(self, root):
        self.root, self.objects, self.events = Path(root), {}, set()
        self.writes, self.next_id = 0, 0
        self.timeout_create = False
        self.timeout_append = False
        self.corrupt_upload = False
        self.public_tokens, self.reads = set(), []
        self.identity_calls = 0

    def children(self, *args):
        raise AssertionError("Directory list must never be called")

    def find(self, *args):
        raise AssertionError("Resource search must never be called")

    def verify_identity(self, owner):
        self.identity_calls += 1
        if owner != "ou_owner":
            raise d.MigrationError("wrong OAuth owner")
        return {"app_id": "app1", "open_id": owner}

    def ensure_private(self, resource, owner):
        self.reads.append(resource["token"])
        if resource["token"] in self.public_tokens:
            raise d.MigrationError("privacy failed")
        return {"status": "owner_only_verified", "owner_open_id": owner}

    def add(self, parent, title, kind, **fields):
        self.next_id += 1
        self.writes += 1
        token = "new" + str(self.next_id)
        resource = {"type": kind, "token": token, "url": "https://school.feishu.cn/docx/" + token}
        self.objects[token] = {**resource, "parent": parent["token"], "title": title, **fields}
        if self.timeout_create:
            self.timeout_create = False
            raise d.MigrationError("timeout after successful server creation")
        return resource

    def container(self, parent, title):
        return self.add(parent, title, "folder")

    def document(self, parent, title, text):
        return self.add(parent, title, "docx", blocks=[{"block_type": 2, "text": {"elements": [{"text_run": {"content": text}}]}}])

    def upload(self, parent, rel, name):
        return self.add(parent, name, "file", checksum="bad" if self.corrupt_upload else d.base.file_hash(self.root / rel))

    def verify_file(self, resource, expected, scratch):
        self.reads.append(resource["token"])
        if self.objects[resource["token"]]["checksum"] != expected:
            raise d.MigrationError("uploaded checksum mismatch")

    def resource_url(self, resource):
        self.reads.append(resource["token"])
        return resource["url"]

    def blocks(self, token):
        self.reads.append(token)
        return self.objects[token].get("blocks", [])

    def append_blocks(self, token, blocks, event_id):
        if event_id not in self.events:
            self.events.add(event_id)
            self.objects[token]["blocks"].extend(blocks)
            self.writes += 1
        if self.timeout_append:
            self.timeout_append = False
            raise d.MigrationError("timeout after append")


class DirectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / ".school/direct/state.json"
        self.plan = {"plan_id": "source-plan", "source_root": str(self.root), "files": {}, "pages": {}, "cases": []}
        self.target = {"parent": {"type": "folder", "token": "explicit-private-root"},
                       "use_parent_as_school": True, "private_owner_open_id": "ou_owner"}
        self.transport = NoListTransport(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def runner(self):
        return d.DirectRunner(self.plan, self.target, self.state, self.transport)

    def file(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.plan["files"][rel] = d.base.file_hash(path)
        return path

    def test_creates_and_resumes_only_from_signed_receipts_without_listing(self):
        r = self.runner()
        school = r.school_root(self.target["parent"])
        folder = r.folder("cases", school, "案例")
        doc = r.doc("case1", folder, "案例一", "完整原问答", ["完整原问答"])
        before = self.transport.writes
        restored = self.runner().doc("case1", folder, "案例一", "完整原问答", ["完整原问答"])
        self.assertEqual(doc, restored)
        self.assertEqual(self.transport.writes, before)
        envelope = d.read_json(self.state)
        self.assertIn("hmac_sha256", envelope)
        receipt = envelope["state"]["operations"]["case1"]["creation_receipt"]
        self.assertEqual(receipt["parent"], folder)
        self.assertEqual(receipt["resource"]["token"], doc["token"])
        self.assertEqual(envelope["state"]["directory_reconciliation"], "pending")

    def test_unknown_creation_without_id_is_not_retried_or_discovered(self):
        r = self.runner()
        self.transport.timeout_create = True
        with self.assertRaisesRegex(d.MigrationError, "timeout"):
            r.doc("case1", self.target["parent"], "案例一", "原文")
        before = self.transport.writes
        with self.assertRaisesRegex(d.MigrationError, "no ID was received"):
            self.runner().doc("case1", self.target["parent"], "案例一", "原文")
        self.assertEqual(self.transport.writes, before)
        op = d.read_json(self.state)["state"]["operations"]["case1"]
        self.assertNotIn("resource", op)

    def test_tampered_journal_is_refused_before_any_remote_read(self):
        self.runner().doc("case1", self.target["parent"], "案例一", "原文")
        envelope = d.read_json(self.state)
        envelope["state"]["operations"]["case1"]["resource"]["token"] = "enterprise-document"
        d.save_json(self.state, envelope)
        before = (len(self.transport.reads), self.transport.identity_calls)
        with self.assertRaisesRegex(d.MigrationError, "signature is invalid"):
            self.runner()
        self.assertEqual((len(self.transport.reads), self.transport.identity_calls), before)

    def test_missing_key_cannot_be_regenerated_for_an_existing_journal(self):
        r = self.runner()
        r.key_path.unlink()
        with self.assertRaisesRegex(d.MigrationError, "pair is incomplete"):
            self.runner()

    def test_unregistered_enterprise_ids_cannot_be_used_as_parent_or_read_target(self):
        r = self.runner()
        before = len(self.transport.reads)
        with self.assertRaisesRegex(d.MigrationError, "no trusted creation receipt"):
            r.doc("foreign", {"type": "folder", "token": "enterprise-folder"}, "无权资料", "text")
        with self.assertRaisesRegex(d.MigrationError, "no trusted creation receipt"):
            r.transport.blocks("enterprise-doc")
        self.assertEqual(len(self.transport.reads), before)
        self.assertEqual(self.transport.writes, 0)

    def test_root_must_be_explicitly_private_and_target_cannot_change_on_resume(self):
        r = self.runner()
        self.target["parent"]["token"] = "other-root"
        with self.assertRaisesRegex(d.MigrationError, "different plan or explicit target"):
            self.runner()
        bad = {"parent": {"type": "folder", "token": "root"}, "use_parent_as_school": True}
        with self.assertRaisesRegex(d.MigrationError, "private_owner_open_id"):
            d.DirectRunner(self.plan, bad, self.state, self.transport)

    def test_privacy_is_rechecked_on_resume_and_checksum_failure_never_marks_done(self):
        r = self.runner()
        doc = r.doc("case1", self.target["parent"], "案例一", "原文")
        self.transport.public_tokens.add(doc["token"])
        with self.assertRaisesRegex(d.MigrationError, "privacy failed"):
            self.runner().doc("case1", self.target["parent"], "案例一", "原文")
        self.file("source.json", "source bytes")
        self.transport.corrupt_upload = True
        with self.assertRaisesRegex(d.MigrationError, "checksum mismatch"):
            self.runner().upload(self.target["parent"], "source.json")
        op = d.read_json(self.state)["state"]["operations"]["file:source.json"]
        self.assertEqual(op["status"], "started")
        self.assertIn("creation_receipt", op)

    def test_known_append_timeout_reads_back_without_duplicating_content(self):
        r = self.runner()
        doc = r.doc("case1", self.target["parent"], "案例一", "原文")
        block = d.marker_block("school-interaction-v1", {"interaction_id": "stable-id", "text": "学员原话"})
        self.transport.timeout_append = True
        r.append_markers("turn", doc, [block], "stable-id")
        before = self.transport.writes
        self.runner().append_markers("turn", doc, [block], "stable-id")
        self.assertEqual(self.transport.writes, before)

    def test_full_pipeline_preserves_cases_sources_pages_and_shared_routes(self):
        source = self.file("sources/original-interviews.pdf", "original PDF fixture")
        self.plan.update(source_pdf="sources/original-interviews.pdf", source_pdf_sha256=d.base.file_hash(source))
        rules = self.file("rules.md", "# 线上规则\n原话与身份保持。")
        for number in (1, 2):
            cid = f"case-{number:02d}-example"
            md, js, page = f"cases/{cid}/base/case.md", f"cases/{cid}/base/case.json", f".school/page{number}.pdf"
            qa = f"Q1 完整原始问答 {number}"
            self.file(md, f"# 案例 {number}\n{qa}\n[原文](../../../sources/original-interviews.pdf#page={number})")
            self.file(js, json.dumps({"provenance": {"original_qa": [{"original_block": qa}]}}))
            self.file(page, "physical page fixture")
            self.plan["pages"][str(number)] = {"path": page, "sha256": self.plan["files"][page]}
            reflection = f"cases/{cid}/reflections/learner{number}-2026-09-11.md"
            record = {"case_id": cid, "learner_id": f"learner{number}", "study_date": "2026-09-11",
                      "interactions": [{"interaction_id": "same-turn-id", "contributions": [{"text": f"学员{number}的原话"}]}]}
            self.file(reflection, f"学员{number}的原话\n<!-- school-record-v1\n" + json.dumps(record, ensure_ascii=False) + "\n-->")
            self.plan["cases"].append({"id": number, "case_id": cid, "learning_title": f"案例 {number}",
                "one_sentence_intro": "行业痛点与具体解决方法", "source_pdf_page_range": [number, number],
                "markdown_file": md, "json_file": js, "images": [], "reflections": [reflection], "canon": [],
                "qa_hashes": {"Q1": d.sha(qa)}, "page_text_sha256": d.sha(qa)})
        first = d.apply_plan(self.plan, self.target, self.state, self.transport, {1}, rules)
        result = d.apply_plan(self.plan, self.target, self.state, self.transport, {1, 2}, rules)
        before = self.transport.writes
        self.assertEqual(d.apply_plan(self.plan, self.target, self.state, self.transport, {1, 2}, rules), result)
        self.assertEqual(self.transport.writes, before)
        self.assertEqual(result["cases"][0]["base_document_id"], first["cases"][0]["base_document_id"])
        self.assertEqual(result["migration_status"], d.DIRECT_STATUS)
        self.assertEqual(result["directory_reconciliation"], "pending")
        self.assertEqual(result["verification_mode"], "signed_creation_receipts")
        for case in result["cases"]:
            reflection_doc = case["migrated_reflections"][0]["document_id"]
            native = [d.base.decode_marker_block(b) for b in self.transport.blocks(reflection_doc)]
            self.assertEqual(sum(value is not None and value[0] == ("school-interaction-v1", "same-turn-id") for value in native), 1)
        for area in ("patterns", "meetings", "curriculum"):
            self.assertIn(result[area + "_parent"]["token"], self.transport.objects)
        self.assertIn(d.DIRECT_STATUS, d.base.block_text(self.transport.blocks(result["manifest_document_id"])))

    def test_cli_requires_explicit_execute_before_reading_inputs(self):
        self.assertEqual(d.main(["--plan", "unused", "--target", "unused", "--state", "unused", "--all"]), 1)


if __name__ == "__main__":
    unittest.main()

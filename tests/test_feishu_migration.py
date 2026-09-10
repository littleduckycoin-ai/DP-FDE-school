"""Migration safety/data-preservation tests with an in-memory Feishu transport."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("migrate_feishu", ROOT / "tools/migrate_feishu.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeTransport:
    def __init__(self, root):
        self.root = Path(root)
        self.objects = {}
        self.counter = 0
        self.fail_document_once = False
        self.fail_append_once = False
        self.events = set()
        self.write_count = 0

    def add(self, parent, name, kind, **fields):
        self.counter += 1
        self.write_count += 1
        token = "resource" + str(self.counter)
        resource = {"token": token, "type": kind, "url": "https://school.feishu.cn/docx/" + token, "name": name, **fields}
        self.objects[token] = {**resource, "parent": parent["token"]}
        return {k: resource[k] for k in ("token", "type", "url")}

    def find(self, parent, name):
        rows = [x for x in self.objects.values() if x["parent"] == parent["token"] and x["name"] == name]
        if len(rows) > 1: raise m.MigrationError("ambiguous")
        return {k: rows[0][k] for k in ("token", "type", "url", "name")} if rows else None

    def container(self, parent, name):
        return self.add(parent, name, "folder")

    def document(self, parent, name, text):
        # Model visible text and actual image blocks separately.
        blocks = [{"block_type": 2, "text": {"elements": [{"text_run": {"content": text}}]}}]
        blocks += [{"block_type": 27, "image": {"token": "image"}} for _ in re.findall(r"!\[.*?\]\(@\./", text)]
        result = self.add(parent, name, "docx", blocks=blocks)
        if self.fail_document_once:
            self.fail_document_once = False
            raise m.MigrationError("network timeout after server committed document")
        return result

    def blocks(self, token):
        return self.objects[token].get("blocks", [])

    def append_blocks(self, token, blocks, event_id):
        if event_id not in self.events:
            self.objects[token]["blocks"] += blocks
            self.events.add(event_id)
            self.write_count += 1
        if self.fail_append_once:
            self.fail_append_once = False
            raise m.MigrationError("timeout after block append")

    def upload(self, parent, rel, name):
        return self.add(parent, name, "file", checksum=m.file_hash(self.root / rel))

    def verify_file(self, resource, expected, scratch):
        if self.objects[resource["token"]]["checksum"] != expected:
            raise m.MigrationError("checksum mismatch")

    def resource_url(self, resource):
        return resource["url"]


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.out = self.root / ".school/migration"
        self.out.mkdir(parents=True)
        self.plan = {"plan_id": "immutable-plan", "source_root": str(self.root), "files": {}, "pages": {}, "cases": []}
        self.target = {"parent": {"type": "folder", "token": "approved-target"}}
        self.state = self.out / "state.json"
        self.transport = FakeTransport(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def file(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        self.plan["files"][rel] = m.file_hash(p)
        return p

    def runner(self):
        return m.Runner(self.plan, self.target, self.state, self.transport)

    def test_real_repository_inventory_has_all_cases_and_exact_qa_hashes(self):
        inv = m.inventory(ROOT)
        self.assertEqual(inv["statistics"]["cases"], 24)
        self.assertEqual(inv["statistics"]["qa_blocks"], 144)
        self.assertEqual(inv["statistics"]["pdf_physical_pages"], 247)
        self.assertIn("sources/original-interviews.pdf", inv["files"])
        self.assertEqual(len({c["case_id"] for c in inv["cases"]}), 24)

    def test_source_mutation_fails_before_any_remote_call(self):
        p = self.file("source.md", "original")
        p.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(m.MigrationError, "Source changed"):
            m.verify_plan(self.plan)
        self.assertEqual(self.transport.write_count, 0)

    def test_created_document_timeout_recovers_without_duplicate(self):
        self.transport.fail_document_once = True
        r = self.runner()
        with self.assertRaises(m.MigrationError):
            r.doc("base:1", self.target["parent"], "案例一", "真实问答", ["真实问答"])
        before = self.transport.write_count
        doc = self.runner().doc("base:1", self.target["parent"], "案例一", "真实问答", ["真实问答"])
        self.assertEqual(self.transport.write_count, before)
        self.assertIn("真实问答", m.block_text(self.transport.blocks(doc["token"])))
        self.assertEqual(m.read_json(self.state)["operations"]["base:1"]["status"], "done")

    def test_existing_unrelated_document_is_not_adopted(self):
        self.transport.document(self.target["parent"], "案例一", "unrelated")
        with self.assertRaisesRegex(m.MigrationError, "unrelated"):
            self.runner().doc("base:1", self.target["parent"], "案例一", "真实问答")

    def test_unknown_create_is_not_retried_when_listing_may_lag(self):
        r = self.runner()
        r.state["operations"]["base:1"] = {"status": "started", "title": "案例一", "kind": "docx"}
        r.save()
        with self.assertRaisesRegex(m.MigrationError, "outcome is unknown"):
            self.runner().doc("base:1", self.target["parent"], "案例一", "原文")
        self.assertEqual(self.transport.write_count, 0)

    def test_corrupt_uploaded_file_is_not_marked_complete(self):
        self.file("source.json", "{\"original\":true}")
        real_upload = self.transport.upload
        def corrupt(parent, rel, name):
            result = real_upload(parent, rel, name)
            self.transport.objects[result["token"]]["checksum"] = "corrupt"
            return result
        self.transport.upload = corrupt
        with self.assertRaisesRegex(m.MigrationError, "checksum mismatch"):
            self.runner().upload(self.target["parent"], "source.json")
        self.assertEqual(m.read_json(self.state)["operations"]["file:source.json"]["status"], "started")

    def test_append_timeout_recovers_without_duplicate_interaction(self):
        r = self.runner()
        doc = r.doc("r", self.target["parent"], "reflection", "学习者原话")
        interaction = {"interaction_id": "preserved-original-id", "contributions": [{"text": "原话", "entry_id": "entry-unchanged"}]}
        blocks = [m.marker_block("school-interaction-v1", interaction)]
        self.transport.fail_append_once = True
        with self.assertRaises(m.MigrationError):
            r.append_markers("i", doc, blocks, '"interaction_id": "preserved-original-id"')
        before = self.transport.write_count
        self.runner().append_markers("i", doc, blocks, '"interaction_id": "preserved-original-id"')
        self.assertEqual(self.transport.write_count, before)
        self.assertEqual(m.block_text(self.transport.blocks(doc["token"])).count('"interaction_id": "preserved-original-id"'), 1)

    def test_missing_images_fail_readable_document_verification(self):
        with self.assertRaisesRegex(m.MigrationError, "Missing visible image"):
            self.runner().doc("base:1", self.target["parent"], "案例一", "真实问答", ["真实问答"], 1)

    def test_uploaded_bytes_are_verified_and_same_named_sources_are_distinct(self):
        self.file("a/README.md", "same content")
        self.file("b/README.md", "same content")
        r = self.runner()
        first = r.upload(self.target["parent"], "a/README.md")
        second = r.upload(self.target["parent"], "b/README.md")
        self.assertNotEqual(first["token"], second["token"])
        before = self.transport.write_count
        self.runner().upload(self.target["parent"], "a/README.md")
        self.assertEqual(self.transport.write_count, before)

    def test_link_rewrite_keeps_qa_and_maps_physical_pdf_pages(self):
        self.file("assets/img.png", "image fixture")
        self.file("case/base.md", '<details>\n<summary>原文</summary>\nQ1 原文不改\n![原图](../assets/img.png)\n[原PDF](../sources/original-interviews.pdf#page=8)\n[Q1](#q1)\n</details>')
        output = m.convert_markdown(self.root, "case/base.md", {8: "https://feishu.cn/file/page8"}, {})
        self.assertIn("Q1 原文不改", output)
        self.assertIn("![原图](@./assets/img.png)", output)
        self.assertIn("https://feishu.cn/file/page8", output)
        self.assertNotIn("#q1", output)
        self.assertNotIn("<details>", output)

    def test_original_reflection_identity_and_entry_ids_preserved(self):
        path = ROOT / "cases/case-01-manufacturing-training/reflections/test-2026-09-08.md"
        meta, entries = m.reflection_data(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["identity_source"], "self_declared")
        self.assertEqual(meta["learner_id"], "test")
        self.assertEqual(entries[0]["contributions"][0]["entry_id"], "case-01-manufacturing-training:test:s-01a08049-test-t01:01")
        blocks = [m.marker_block("school-record-meta-v1", meta), m.marker_block("school-interaction-v1", entries[0])]
        restored = m.block_text(blocks)
        self.assertIn("我觉得很好", restored)
        self.assertIn("school-record-meta-end", restored)
        self.assertIn("school-interaction-end", restored)

    def test_wrong_target_cannot_reuse_journal(self):
        self.runner().save()
        with self.assertRaisesRegex(m.MigrationError, "different plan or target"):
            m.Runner(self.plan, {"parent": {"type": "folder", "token": "other"}}, self.state, self.transport)

    def test_apply_requires_explicit_execute(self):
        self.assertEqual(m.main(["apply", "--plan", "unused", "--target", "unused", "--state", "unused", "--all"]), 1)
        self.assertEqual(self.transport.write_count, 0)

    def test_cli_shortcut_and_raw_envelopes_unwrap_without_false_success(self):
        business = {"document_id": "doc"}
        self.assertEqual(m.unwrap_response({"ok": True, "data": business}), business)
        self.assertEqual(m.unwrap_response({"ok": True, "data": {"code": 0, "data": business}}), business)
        self.assertEqual(m.unwrap_response({"code": 0, "data": business}), business)
        for value in ({"ok": False}, {"ok": True}, {"ok": True, "data": {"code": 403, "data": {}}}, {}):
            with self.assertRaises(m.MigrationError): m.unwrap_response(value)

    def test_paginated_raw_api_does_not_silently_truncate_or_loop(self):
        transport = m.LarkTransport(self.root, cli="fake")
        responses = iter([{"items": [{"block_id": "b1"}], "has_more": True, "page_token": "next"}, {"items": [{"block_id": "b2"}], "has_more": False}])
        transport.api = lambda *a, **k: next(responses)
        self.assertEqual(len(transport.blocks("doc")), 2)
        for value in ({"items": []}, {"items": [], "has_more": True}, {"has_more": False}):
            transport.api = lambda *a, **k: value
            with self.assertRaises(m.MigrationError): transport.blocks("doc")
        transport.api = lambda *a, **k: {"items": [{"block_id": "same"}], "has_more": True, "page_token": "same"}
        with self.assertRaises(m.MigrationError): transport.blocks("doc")

    def test_long_marker_json_chunks_roundtrip_without_inserting_newlines(self):
        payload = {"schema_version": m.SCHEMA, "long_text": "中文🙂" * 2000}
        block = m.marker_block("school-manifest-v1", payload)
        elements = block["code"]["elements"]
        self.assertGreater(len(elements), 1)
        self.assertTrue(all(len(e["text_run"]["content"].encode("utf-16-le")) // 2 <= 1500 for e in elements))
        text = m.block_text([block])
        restored = json.loads(text.split("school-manifest-v1\n", 1)[1].rsplit("\nschool-manifest-end", 1)[0])
        self.assertEqual(restored, payload)

    def test_pilot_then_all_and_resume_preserve_links_ids_and_no_extra_writes(self):
        self.file("sources/original-interviews.pdf", "original PDF fixture bytes")
        self.plan["source_pdf"] = "sources/original-interviews.pdf"
        self.plan["source_pdf_sha256"] = self.plan["files"][self.plan["source_pdf"]]
        rules = self.file("rules.md", "# 学校规则\n保留原文与身份。")
        for number in (1, 2):
            cid = f"case-{number:02d}-example"
            rel = f"cases/{cid}/base/case.md"
            jrel = f"cases/{cid}/base/case.json"
            img = f"assets/image{number}.png"
            page = f".school/page{number}.pdf"
            qa = f"Q1 原始问答 {number}"
            self.file(img, "image bytes")
            self.file(page, "single page fixture")
            self.plan["pages"][str(number)] = {"path": page, "sha256": self.plan["files"][page]}
            self.file(rel, f"# 案例{number}\n{qa}\n[原文](../../../sources/original-interviews.pdf#page={number})")
            self.file(jrel, json.dumps({"provenance": {"original_qa": [{"original_block": qa}]}}))
            self.plan["cases"].append({"id": number, "case_id": cid, "learning_title": f"案例{number}",
                "one_sentence_intro": "具体项目简介", "source_pdf_page_range": [number, number],
                "markdown_file": rel, "json_file": jrel, "images": [img], "reflections": [], "canon": [],
                "qa_hashes": {"Q1": m.sha(qa)}, "page_text_sha256": m.sha(qa)})
        first = m.apply_plan(self.plan, self.target, self.state, self.transport, {1}, rules)
        self.assertEqual(len(first["cases"]), 1)
        second = m.apply_plan(self.plan, self.target, self.state, self.transport, {1, 2}, rules)
        self.assertEqual(len(second["cases"]), 2)
        self.assertEqual(second["cases"][0]["base_document_id"], first["cases"][0]["base_document_id"])
        self.assertEqual([c["source_page_links"][0]["pdf_page"] for c in second["cases"]], [1, 2])
        before = self.transport.write_count
        final = m.apply_plan(self.plan, self.target, self.state, self.transport, {1, 2}, rules)
        self.assertEqual(self.transport.write_count, before)
        self.assertEqual(final["migration_status"], "content_verified_permissions_pending")
        self.assertEqual(final, second)


if __name__ == "__main__":
    unittest.main()

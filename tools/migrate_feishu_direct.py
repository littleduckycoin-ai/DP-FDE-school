"""Explicit create-only staging below a verified private folder, without discovery.

This does not replace normal directory-verified migration. It preserves actual
creation receipts in an HMAC-protected local journal. Unknown creation outcomes
stop without lookup or retry; directory reconciliation remains pending.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

try:
    from tools import migrate_feishu as base
except ModuleNotFoundError:
    import migrate_feishu as base

MigrationError = base.MigrationError
SCHEMA = base.SCHEMA
ROOT = base.ROOT
DIRECT_STATUS = "creation_receipts_verified_directory_reconciliation_pending"
read_json, save_json, sha = base.read_json, base.save_json, base.sha
verify_plan, convert_markdown, reflection_data = base.verify_plan, base.convert_markdown, base.reflection_data
marker_block = base.marker_block
preserve_literal_qa_backslashes = base.preserve_literal_qa_backslashes


class ReceiptTransport:
    """Only explicit-root or service-created IDs can reach authenticated IO."""
    def __init__(self, driver, parent):
        self.driver = driver
        self.allowed = {parent["token"]: {"resource": dict(parent), "parent": None}}

    def require(self, resource, kind=None):
        entry = self.allowed.get(resource.get("token"))
        if not entry or entry["resource"]["type"] != resource.get("type") or (kind and resource["type"] != kind):
            raise MigrationError("Resource has no trusted creation receipt inside the explicit private root")
        return entry

    def register(self, parent, resource):
        self.require(parent, "folder")
        if resource.get("type") not in ("folder", "docx", "file") or not re.fullmatch(r"[A-Za-z0-9_-]+", str(resource.get("token", ""))):
            raise MigrationError("Creation response did not provide a supported resource type and actual ID")
        if resource["token"] in self.allowed:
            raise MigrationError("Creation response reused an already registered resource ID")
        self.allowed[resource["token"]] = {"resource": dict(resource), "parent": dict(parent)}

    def children(self, *args, **kwargs):
        raise MigrationError("Directory listing is intentionally unavailable in create-only mode")

    def find(self, *args, **kwargs):
        raise MigrationError("Resource discovery is intentionally unavailable in create-only mode")

    def container(self, parent, title):
        self.require(parent, "folder")
        return self.driver.container(parent, title)

    def document(self, parent, title, text):
        self.require(parent, "folder")
        return self.driver.document(parent, title, text)

    def upload(self, parent, path, title):
        self.require(parent, "folder")
        return self.driver.upload(parent, path, title)

    def blocks(self, token):
        self.require({"type": "docx", "token": token}, "docx")
        return self.driver.blocks(token)

    def append_blocks(self, token, blocks, event_id):
        self.require({"type": "docx", "token": token}, "docx")
        return self.driver.append_blocks(token, blocks, event_id)

    def verify_file(self, resource, expected, scratch):
        self.require(resource, "file")
        return self.driver.verify_file(resource, expected, scratch)

    def resource_url(self, resource):
        self.require(resource)
        return self.driver.resource_url(resource)

    def ensure_private(self, resource, owner):
        self.require(resource)
        return self.driver.ensure_private(resource, owner)


class DirectRunner(base.Runner):
    def __init__(self, plan, target, state_path, transport):
        parent = target.get("parent", {})
        if (parent.get("type") != "folder" or not re.fullmatch(r"[A-Za-z0-9_-]+", str(parent.get("token", "")))
                or target.get("use_parent_as_school") is not True
                or not isinstance(target.get("private_owner_open_id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]+", target["private_owner_open_id"])):
            raise MigrationError("Create-only staging requires an explicit private folder, use_parent_as_school=true and private_owner_open_id")
        self.plan, self.target = plan, target
        self.root, self.state_path = Path(plan["source_root"]).resolve(), Path(state_path).resolve()
        if not self.state_path.is_relative_to(self.root / ".school"):
            raise MigrationError("Signed create-only state must stay in the ignored workspace .school directory")
        self.key_path = self.state_path.with_suffix(self.state_path.suffix + ".key")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if self.state_path.exists() != self.key_path.exists():
            raise MigrationError("State/key pair is incomplete; do not regenerate or adopt a journal after losing its integrity key")
        if self.state_path.exists():
            self.key = self.key_path.read_bytes()
            envelope = read_json(self.state_path)
            self.state = envelope.get("state")
            signature = envelope.get("hmac_sha256")
            if not isinstance(self.state, dict) or not isinstance(signature, str) or not hmac.compare_digest(self.sign(self.state), signature):
                raise MigrationError("Creation journal signature is invalid; no remote resource will be accessed")
            if self.state.get("format") != "feishu-direct-state-v1" or self.state.get("plan_id") != plan["plan_id"] or self.state.get("target") != target:
                raise MigrationError("Creation journal belongs to a different plan or explicit target")
        else:
            self.key = secrets.token_bytes(32)
            descriptor = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(self.key)
            self.state = {"format": "feishu-direct-state-v1", "plan_id": plan["plan_id"], "target": target,
                          "operations": {}, "cases": [], "directory_reconciliation": "pending"}
            self.save()  # No remote IO occurs before durable state exists.
        self.transport = ReceiptTransport(transport, parent)
        self.private_owner = target["private_owner_open_id"]
        self.restore_receipts()
        actor = transport.verify_identity(self.private_owner)
        if self.state.get("private_actor") and self.state["private_actor"] != actor:
            raise MigrationError("OAuth application/user differs from the signed creation journal")
        self.state["private_actor"] = actor
        self.state["target_privacy"] = self.transport.ensure_private(parent, self.private_owner)
        self.save()

    def sign(self, state):
        if len(self.key) != 32:
            raise MigrationError("Creation journal integrity key is invalid")
        return hmac.new(self.key, base.canonical(state).encode("utf-8"), hashlib.sha256).hexdigest()

    def save(self):
        save_json(self.state_path, {"state": self.state, "hmac_sha256": self.sign(self.state)})

    def restore_receipts(self):
        pending = [op for op in self.state["operations"].values() if op.get("resource") and op.get("kind") != "explicit_private_root"]
        while pending:
            progressed = False
            for op in list(pending):
                receipt = op.get("creation_receipt")
                if not isinstance(receipt, dict) or receipt.get("resource") != op["resource"] or receipt.get("parent") != op.get("parent"):
                    raise MigrationError("Resource is not backed by an intact creation response receipt")
                if op["parent"].get("token") not in self.transport.allowed:
                    continue
                self.transport.register(op["parent"], op["resource"])
                pending.remove(op)
                progressed = True
            if not progressed:
                raise MigrationError("Signed receipt ancestry does not lead to the explicit private root")

    def check_parent(self, parent, seen=None):
        self.transport.require(parent, "folder")

    def check_resource(self, parent, resource, kind):
        self.check_parent(parent)
        entry = self.transport.require(resource)
        if entry["parent"] is None or self.location(entry["parent"]) != self.location(parent):
            raise MigrationError("Resource creation receipt does not match this fixed parent")
        return dict(entry["resource"])

    def school_root(self, parent):
        if self.location(parent) != self.location(self.target["parent"]):
            raise MigrationError("Only the explicitly authorized private root can host this direct migration")
        self.state["operations"]["school-root"] = {"status": "done", "kind": "explicit_private_root", "resource": dict(parent)}
        self.check_private("school-root", parent)
        return dict(parent)

    def ensure(self, key, parent, title, kind, create, verify=None):
        self.check_parent(parent)
        op = self.state["operations"].get(key)
        if op:
            if op.get("kind") != kind or op.get("title") != title or self.location(op.get("parent", {})) != self.location(parent):
                raise MigrationError("Operation does not match its signed creation intent")
            if not op.get("resource"):
                raise MigrationError("Creation outcome is unknown and no ID was received; do not retry or search. Wait for directory approval and reconcile this intent")
            resource = self.check_resource(parent, op["resource"], kind)
        else:
            op = {"status": "started", "title": title, "kind": kind, "parent": dict(parent)}
            self.state["operations"][key] = op
            self.save()
            resource = create()  # Exactly one attempt; exceptions preserve unknown intent.
            expected = "folder" if kind == "container" else kind
            if resource.get("type") != expected:
                raise MigrationError("Creation response resource type did not match the requested operation")
            self.transport.register(parent, resource)
            op["resource"] = dict(resource)
            op["creation_receipt"] = {"parent": dict(parent), "resource": dict(resource),
                                      "requested_kind": kind, "requested_title": title,
                                      "evidence": "successful_service_creation_response"}
            self.save()  # Receipt reaches disk before any further token-based request.
        self.check_private(key, resource)
        if verify:
            verify(resource)
        if kind != "container":
            # This uses only a trusted created token; no URL is followed as a target.
            resource["url"] = self.transport.resource_url(resource)
        op["status"] = "done"
        self.save()
        return resource


# The orchestration below uses the same source-preserving stages as normal migration;
# only its Runner is replaced locally. The original module and its defaults are intact.
Runner = DirectRunner


def progress(stage, **details):
    print(json.dumps({"progress": stage, **details}, ensure_ascii=False), file=sys.stderr, flush=True)


def apply_plan(plan, target, state_path, transport, selected, rules_file):
    verify_plan(plan)
    progress("source_verified", selected_cases=sorted(selected))
    parent = target.get("parent", {})
    if parent.get("type") not in ("folder", "wiki") or not parent.get("token") or (parent["type"] == "wiki" and not parent.get("space_id")):
        raise MigrationError("Target requires parent.type, parent.token and Wiki space_id")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", str(parent[k])) for k in ("token", "space_id") if k in parent):
        raise MigrationError("Target must contain parsed tokens/IDs, not URLs or path fragments")
    if not isinstance(target.get("use_parent_as_school", False), bool):
        raise MigrationError("use_parent_as_school must be an explicit JSON boolean")
    runner = Runner(plan, target, state_path, transport)
    school = runner.school_root(parent)
    sources = runner.folder("sources", school, "原始资料")
    archive = runner.folder("archive", sources, "迁移源文件")
    cases_parent = runner.folder("cases", school, "案例")
    # Single original PDF. Per-case single-page links are always physical page numbers.
    full_pdf = runner.upload(sources, plan["source_pdf"])
    file_urls = {plan["source_pdf"]: full_pdf["url"]}
    rules_text = Path(rules_file).read_text(encoding="utf-8")
    rules_digest = sha(rules_text)
    old_digest = runner.state.get("rules_sha256")
    if old_digest and old_digest != rules_digest:
        raise MigrationError("Rules changed during migration; finish or explicitly start a new migration")
    runner.state["rules_sha256"] = rules_digest
    rules = runner.doc("rules", school, "学校规则", rules_text, [re.sub(r"^#{1,6}\s+", "", rules_text.splitlines()[0])])
    progress("shared_sources_verified")
    for case in plan["cases"]:
        cid = case["case_id"]
        if case["id"] not in selected:
            continue
        progress("case_started", case_id=cid)
        case_parent = runner.folder("case:" + cid, cases_parent, f"{cid}｜{case['learning_title']}")
        base = runner.folder("base:" + cid, case_parent, "基础案例")
        reflections = runner.folder("reflections:" + cid, case_parent, "学习者思考")
        canon = runner.folder("canon:" + cid, case_parent, "官方拆解")
        page_parent = runner.folder("pages:" + cid, base, "原访谈逐页PDF")
        pages = {}
        for n in range(case["source_pdf_page_range"][0], case["source_pdf_page_range"][1] + 1):
            res = runner.upload(page_parent, plan["pages"][str(n)]["path"], "page:" + str(n))
            pages[n] = res["url"]
        # Archive every case file and all referenced images; original bytes remain downloadable.
        case_files = [p for p in plan["files"] if p.startswith("cases/" + cid + "/")]
        for rel in sorted(set(case_files + case["images"])):
            res = runner.upload(archive, rel)
            file_urls[rel] = res["url"]
        text = convert_markdown(runner.root, case["markdown_file"], pages, file_urls)
        # Covers are in JSON and therefore may not appear in the original Markdown.
        for img in case["images"]:
            if "@./" + img not in text:
                text += f"\n\n![案例原图](@./{img})\n"
        text += "\n\n## 原访谈逐页查阅\n" + "\n".join(f"- [PDF物理页 {n}]({url})" for n, url in pages.items())
        c = read_json(runner.root / case["json_file"])
        qa = [q["original_block"] for q in c["provenance"]["original_qa"]]
        text = preserve_literal_qa_backslashes(text, qa)
        doc = runner.doc("base-doc:" + cid, base, case["learning_title"], text, qa, len(case["images"]))
        migrated_reflections = []
        for rel in case["reflections"]:
            raw = (runner.root / rel).read_text(encoding="utf-8")
            meta, interactions = reflection_data(raw)
            human = re.sub(r"<!--\s*school-record-v1[\s\S]*?-->", "", convert_markdown(runner.root, rel, pages, file_urls))
            title = f"school-reflection | {cid} | {meta['learner_id']} | {meta['study_date']}"
            rd = runner.doc("reflection:" + rel, reflections, title, human, [x["text"] for i in interactions for x in i.get("contributions", [])])
            runner.append_markers("reflection-meta:" + rel, rd, [marker_block("school-record-meta-v1", meta)], "school-record-meta-v1")
            for interaction in interactions:
                runner.append_markers("interaction:" + rel + ":" + interaction["interaction_id"], rd, [marker_block("school-interaction-v1", interaction)], '"interaction_id": "' + interaction["interaction_id"] + '"')
            migrated_reflections.append({"source_path": rel, "source_sha256": plan["files"][rel], "document_id": rd["token"], "url": rd["url"], **meta})
        for rel in case["canon"]:
            runner.doc("canon-doc:" + rel, canon, Path(rel).stem, convert_markdown(runner.root, rel, pages, file_urls))
        entry = {"case_id": cid, "id": case["id"], "title": case["learning_title"], "one_sentence_intro": case["one_sentence_intro"],
                 "base_document_id": doc["token"], "base_url": doc["url"], "reflections_parent": reflections, "canon_parent": canon,
                 "source_json_url": file_urls[case["json_file"]], "source_pdf_url": full_pdf["url"],
                 "source_page_links": [{"pdf_page": n, "url": u} for n, u in pages.items()],
                 "source_qa_hashes": case["qa_hashes"], "source_page_text_sha256": case["page_text_sha256"],
                 "migrated_reflections": migrated_reflections}
        runner.state["cases"] = sorted([x for x in runner.state["cases"] if x["case_id"] != cid] + [entry], key=lambda x: x["id"])
        runner.save()
        progress("case_verified", case_id=cid)
    # Shared historical material remains readable and is also archived byte-for-byte.
    shared = runner.folder("shared", school, "跨案例沉淀")
    shared_parents = {}
    for area in ("patterns", "curriculum", "meetings", "shared-notes", "learning-notes"):
        dest = runner.folder("shared:" + area, shared, area)
        shared_parents[area] = dest
        for rel in (p for p in plan["files"] if p.startswith(area + "/")):
            runner.upload(archive, rel)
            if rel.endswith(".md"):
                runner.doc("shared-doc:" + rel, dest, Path(rel).stem, convert_markdown(runner.root, rel, {}, file_urls))
    # Remaining original data/assets/manifests are archive resources, not hidden case content.
    if len(runner.state["cases"]) == len(plan["cases"]):
        for rel in plan["files"]:
            if "file:" + rel not in runner.state["operations"]:
                runner.upload(archive, rel)
    ids = "-".join(str(c["id"]) for c in runner.state["cases"])
    catalog = "# 案例目录\n\n" + "\n\n".join(f"## [{c['title']}]({c['base_url']})\n\n{c['one_sentence_intro']}" for c in runner.state["cases"])
    index_doc = runner.doc("index:" + ids, school, "案例目录（" + str(len(runner.state["cases"])) + "例）", catalog)
    manifest_doc = runner.doc("manifest:" + ids, school, "学校连接信息（" + str(len(runner.state["cases"])) + "例）", "学校连接信息：供学习助手读取线上规则与案例。")
    manifest = {"schema_version": SCHEMA, "school_id": "fde-school", "rules_document_id": rules["token"], "rules_url": rules["url"],
                "case_index_document_id": index_doc["token"], "manifest_document_id": manifest_doc["token"], "manifest_url": manifest_doc["url"],
                "school_parent": school, "patterns_parent": shared_parents["patterns"],
                "meetings_parent": shared_parents["meetings"], "curriculum_parent": shared_parents["curriculum"],
                "source_pdf_url": full_pdf["url"], "source_pdf_sha256": plan["source_pdf_sha256"],
                "migration_plan_id": plan["plan_id"], "cases": runner.state["cases"], "migration_status": DIRECT_STATUS,
                "directory_reconciliation": "pending", "verification_mode": "signed_creation_receipts"}
    runner.append_markers("manifest-data:" + ids, manifest_doc, [marker_block("school-manifest-v1", manifest)], "school-manifest-v1")
    save_json(runner.state_path.parent / "feishu-school.json", manifest)
    runner.state["manifest"] = manifest
    runner.save()
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--rules-file", type=Path, default=ROOT / ".codex/skills/school-guide/references/feishu-workflow.md")
    parser.add_argument("--profile", default="fde-school")
    parser.add_argument("--cli")
    selected = parser.add_mutually_exclusive_group(required=True)
    selected.add_argument("--cases")
    selected.add_argument("--all", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.execute:
            raise MigrationError("No writes made; --execute is required for explicit create-only staging")
        plan = read_json(args.plan)
        ids = {case["id"] for case in plan["cases"]}
        selected = ids if args.all else {int(value) for value in args.cases.split(",")}
        if not selected or not selected.issubset(ids):
            raise MigrationError("Unknown case selection")
        state = args.state.resolve()
        if not state.is_relative_to(Path(plan["source_root"]).resolve() / ".school"):
            raise MigrationError("Direct state must stay inside workspace .school")
        state.parent.mkdir(parents=True, exist_ok=True)
        lock = state.with_suffix(".lock")
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise MigrationError("Direct migration lock exists; confirm the earlier process ended before removing only its stale lock") from error
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(str(os.getpid()))
            manifest = apply_plan(plan, read_json(args.target), state,
                                  base.LarkTransport(plan["source_root"], args.profile, args.cli), selected, args.rules_file)
            print(json.dumps({"ok": True, "manifest_url": manifest["manifest_url"], "cases": len(manifest["cases"]),
                              "status": DIRECT_STATUS}, ensure_ascii=False))
        finally:
            lock.unlink()
        return 0
    except (MigrationError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error),
                          "resume": "Keep both signed state and its .key. Unknown creation without an ID must await approved directory reconciliation; do not retry it."}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


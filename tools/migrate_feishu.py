"""Maintainer-only, resumable migration. `plan` never calls Feishu.

Source materials remain unchanged. Apply requires an explicit target and --execute.
Python standard library + PyMuPDF (only PDF page preparation); official lark-cli
does all authenticated remote IO. State and prepared files belong in .school/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "feishu-school-v1"


class MigrationError(RuntimeError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise MigrationError(f"Path outside source workspace: {relative}")
    return path


def file_hash(path):
    return sha(Path(path).read_bytes())


def inventory(root):
    """Verify frozen hashes and retain every source/learning file, not just Q&A."""
    root = Path(root)
    index = read_json(root / "data/case-index.json")
    frozen = read_json(root / "data/base-manifest.json")
    integrity = read_json(root / "sources/integrity.json")
    source = read_json(root / "sources/manifest.json")
    for rel, expected in frozen["files"].items():
        if file_hash(inside(root, rel)) != expected:
            raise MigrationError(f"Frozen base checksum mismatch: {rel}")
    pdf_hash = file_hash(root / source["source_file"])
    if pdf_hash != source["sha256"] or pdf_hash != integrity["source_pdf_sha256"]:
        raise MigrationError("Original PDF checksum mismatch")
    expected = {c["id"]: c for c in integrity["cases"]}
    cases, qa_count, figures = [], 0, set()
    files = set(frozen["files"])
    for folder in ("assets", "sources", "data", "curriculum", "meetings", "patterns", "shared-notes", "learning-notes"):
        files.update(p.relative_to(root).as_posix() for p in (root / folder).rglob("*") if p.is_file())
    files.update(p.relative_to(root).as_posix() for p in (root / "cases").rglob("*") if p.is_file())
    for item in index["cases"]:
        c = read_json(root / item["json_file"])
        p = c["provenance"]
        md = (root / item["markdown_file"]).read_text(encoding="utf-8")
        if c["identity"]["case_id"] != item["case_id"]:
            raise MigrationError("Case ID mismatch")
        for q in p["original_qa"]:
            if sha(q["original_block"]) != expected[item["id"]]["qa"][q["question_id"]] or q["original_block"] not in md:
                raise MigrationError(f"Q&A lost or altered: {item['case_id']}/{q['question_id']}")
            qa_count += 1
        if sha(json.dumps(p["original_page_text"], ensure_ascii=False, sort_keys=True)) != expected[item["id"]]["page_text_sha256"]:
            raise MigrationError(f"Page text mismatch: {item['case_id']}")
        images = [p["cover_image"]] + [f["asset"] for f in p["figures"]]
        figures.update(images)
        cases.append({**item, "images": images,
                      "qa_hashes": expected[item["id"]]["qa"],
                      "page_text_sha256": expected[item["id"]]["page_text_sha256"],
                      "reflections": sorted(x.relative_to(root).as_posix() for x in (root / item["reflections_dir"]).glob("*.md") if x.name != "README.md"),
                      "canon": sorted(x.relative_to(root).as_posix() for x in (root / item["canon_dir"]).glob("*.md") if x.name != "README.md")})
    if len(cases) != source["case_count"] or qa_count != sum(source["qa_counts"]):
        raise MigrationError("Case or Q&A count mismatch")
    return {"cases": cases, "files": {rel: file_hash(inside(root, rel)) for rel in sorted(files)},
            "source_pdf": source["source_file"], "source_pdf_sha256": pdf_hash,
            "statistics": {"cases": len(cases), "qa_blocks": qa_count,
                           "pdf_physical_pages": source["pdf_page_count"],
                           "case_images": len(figures),
                           "asset_files": len(list((root / "assets").glob("*"))),
                           "reflections": sum(len(c["reflections"]) for c in cases)}}


def build_plan(root=ROOT, output=None):
    root = Path(root).resolve()
    output = Path(output or root / ".school/feishu-migration").resolve()
    if not output.is_relative_to(root):
        raise MigrationError("Preparation output must be under the workspace (CLI file policy)")
    inv = inventory(root)
    plan = {"format": "feishu-migration-plan-v1", "source_root": str(root), **inv}
    plan["plan_id"] = sha(canonical({k: v for k, v in plan.items() if k != "source_root"}))
    # A PDF is never rewritten in place. Only referenced physical pages are split.
    import fitz
    page_dir = output / "pages"
    page_dir.mkdir(parents=True, exist_ok=True)
    pages = sorted({n for c in inv["cases"] for n in range(c["source_pdf_page_range"][0], c["source_pdf_page_range"][1] + 1)})
    generated = {}
    with fitz.open(root / inv["source_pdf"]) as pdf:
        if len(pdf) != inv["statistics"]["pdf_physical_pages"]:
            raise MigrationError("PDF physical page count mismatch")
        for number in pages:
            dest = page_dir / f"original-interview-page-{number:03d}.pdf"
            if not dest.exists():
                with fitz.open() as single:
                    single.insert_pdf(pdf, from_page=number - 1, to_page=number - 1)
                    single.save(dest, garbage=4, deflate=True)
            with fitz.open(dest) as single:
                # Rendering checks detect stale/wrong page splits including page images.
                if len(single) != 1 or single[0].get_pixmap(matrix=fitz.Matrix(.5, .5)).samples != pdf[number - 1].get_pixmap(matrix=fitz.Matrix(.5, .5)).samples:
                    raise MigrationError(f"Generated page does not match physical PDF page {number}")
            generated[str(number)] = {"path": dest.relative_to(root).as_posix(), "sha256": file_hash(dest)}
    plan["pages"] = generated
    plan["statistics"]["prepared_single_page_pdfs"] = len(generated)
    save_json(output / "plan.json", plan)
    save_json(output / "source-inventory.json", {"plan_id": plan["plan_id"], "statistics": plan["statistics"], "files": plan["files"], "qa": {c["case_id"]: c["qa_hashes"] for c in inv["cases"]}})
    return plan


def verify_plan(plan):
    root = Path(plan["source_root"])
    for rel, expected in plan["files"].items():
        if file_hash(inside(root, rel)) != expected:
            raise MigrationError(f"Source changed after planning: {rel}; create a new plan")
    for p in plan["pages"].values():
        if file_hash(inside(root, p["path"])) != p["sha256"]:
            raise MigrationError(f"Prepared page changed: {p['path']}")


def normalized(text):
    return re.sub(r"\s+", "", text)


def reflection_data(text):
    match = re.search(r"<!--\s*school-record-v1\s*([\s\S]*?)-->", text)
    if not match:
        raise MigrationError("Reflection is missing school-record-v1; cannot infer its author")
    data = json.loads(match.group(1))
    return {k: v for k, v in data.items() if k != "interactions"}, data["interactions"]


def code_block(text):
    # Element limits apply independently from the larger total block text limit.
    pieces, current, units = [], [], 0
    for character in text:
        size = 2 if ord(character) > 0xFFFF else 1
        if units + size > 1500:
            pieces.append("".join(current))
            current, units = [], 0
        current.append(character)
        units += size
    if current:
        pieces.append("".join(current))
    return {"block_type": 14, "code": {"elements": [{"text_run": {"content": piece}} for piece in pieces], "style": {"language": 1}}}


def unwrap_response(envelope):
    """CLI shortcuts and raw API can use different success-envelope depths."""
    if not isinstance(envelope, dict):
        raise MigrationError("CLI returned a non-object response")
    if "ok" in envelope:
        if envelope["ok"] is not True or "data" not in envelope:
            raise MigrationError("CLI did not confirm success")
        envelope = envelope["data"]
    elif "code" not in envelope:
        raise MigrationError("Unrecognized CLI success envelope")
    while isinstance(envelope, dict) and "code" in envelope:
        if envelope["code"] != 0 or "data" not in envelope:
            raise MigrationError(f"Feishu API failed or omitted data (code={envelope.get('code')})")
        envelope = envelope["data"]
    if not isinstance(envelope, dict):
        raise MigrationError("Expected an object in CLI data")
    return envelope


def list_page(data, field, seen):
    if not isinstance(data.get(field), list) or not isinstance(data.get("has_more"), bool):
        raise MigrationError(f"Incomplete pagination response: {field}/has_more missing")
    cursor = data.get("page_token") if data["has_more"] else None
    if data["has_more"] and (not isinstance(cursor, str) or not cursor or cursor in seen):
        raise MigrationError("Pagination cursor missing or repeated; refusing to claim complete results")
    if cursor:
        seen.add(cursor)
    return data[field], cursor


def marker_block(tag, value):
    end = {"school-manifest-v1": "school-manifest-end", "school-record-meta-v1": "school-record-meta-end", "school-interaction-v1": "school-interaction-end"}[tag]
    return code_block(tag + "\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n" + end)


def decode_marker_block(block):
    """Read complete native code-block records, never a marker in readable prose."""
    if block.get("block_type") != 14:
        return None
    text = block_text([block]).replace("\r\n", "\n").strip()
    lines = text.splitlines()
    endings = {"school-manifest-v1": "school-manifest-end", "school-record-meta-v1": "school-record-meta-end", "school-interaction-v1": "school-interaction-end"}
    if not lines or lines[0] not in endings:
        return None
    tag = lines[0]
    if len(lines) < 3 or lines[-1] != endings[tag]:
        raise MigrationError("Structured code block is incomplete: " + tag)
    try:
        payload = json.loads("\n".join(lines[1:-1]))
    except (TypeError, ValueError) as error:
        raise MigrationError("Structured code block contains invalid JSON: " + tag) from error
    if not isinstance(payload, dict):
        raise MigrationError("Structured code block must contain a JSON object: " + tag)
    identity = (tag, payload.get("interaction_id") if tag == "school-interaction-v1" else None)
    if tag == "school-interaction-v1" and not isinstance(identity[1], str):
        raise MigrationError("Structured interaction is missing its stable ID")
    return identity, canonical(payload)


class LarkTransport:
    """Real official CLI transport. Shell=False; secrets remain in CLI credential store."""
    def __init__(self, root, profile="fde-school", cli=None):
        self.root = Path(root)
        native = Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@larksuite/cli/bin/lark-cli.exe"
        self.cli = cli or (str(native) if native.exists() else shutil.which("lark-cli"))
        if not self.cli:
            raise MigrationError("Install official @larksuite/cli first")
        self.profile = profile

    def call(self, args, content=None):
        argv = [self.cli, "--profile", self.profile, *args]
        if args[:1] != ["auth"]:
            argv += ["--as", "user"]
        result = subprocess.run(argv, input=content, cwd=self.root, encoding="utf-8", capture_output=True, timeout=240, shell=False)
        if result.returncode:
            # Do not persist complete CLI output; OAuth links and credentials do not belong in journals.
            raise MigrationError(f"CLI command failed ({result.returncode}): {' '.join(args[:3])}; use CLI auth status or rerun the diagnostic command locally")
        try:
            envelope = json.loads(result.stdout)
        except ValueError as exc:
            raise MigrationError("CLI returned non-JSON; write outcome unknown, resume with the same state") from exc
        # auth status emits a native diagnostic object, unlike API/shortcut envelopes.
        # The caller still requires verified=true and the exact requested owner.
        if args[:2] == ["auth", "status"] and isinstance(envelope, dict) and "ok" not in envelope and "identities" in envelope:
            return envelope
        return unwrap_response(envelope)

    def verify_identity(self, owner_open_id):
        status = self.call(["auth", "status", "--json", "--verify"])
        user = status.get("identities", {}).get("user", {})
        if (not status.get("appId") or user.get("openId") != owner_open_id
                or user.get("available") is not True or user.get("verified") is not True
                or user.get("status") not in ("ready", "needs_refresh")):
            raise MigrationError("Private migration requires the remotely verified OAuth owner; no bot or different user is allowed")
        return {"app_id": status["appId"], "open_id": owner_open_id}

    def ensure_private(self, resource, owner_open_id):
        kind, token = resource.get("type"), resource.get("token")
        if kind not in ("folder", "docx", "file") or not token:
            raise MigrationError("Owner-only migration supports verified Drive folders, Docx and files only; this resource type is unsupported")

        def inspect():
            settings = self.call(["drive", "+permission-get-setting", "--token", token, "--type", kind, "--json"])
            members = self.call(["drive", "+member-list", "--token", token, "--type", kind, "--json"])
            # Fresh creations can precede collaborator-index visibility. Re-read
            # only this exact known resource; never treat an empty ACL as private.
            for attempt in range(3):
                if members.get("items") != [] or members.get("has_more"):
                    break
                time.sleep(0.4 * (2 ** attempt))
                members = self.call(["drive", "+member-list", "--token", token, "--type", kind, "--json"])
            public, items = settings.get("permission_public"), members.get("items")
            if not isinstance(public, dict) or not isinstance(items, list) or not items or members.get("has_more"):
                raise MigrationError("Private permission inspection is incomplete; refusing to assume owner-only access")
            if any(not isinstance(member, dict) or member.get("member_type") != "openid"
                   or member.get("member_id") != owner_open_id or member.get("perm") != "full_access"
                   for member in items):
                raise MigrationError("Resource has collaborators other than the verified owner, or owner permission is unverified; stopped without removing collaborators")
            return public, items

        public, items = inspect()
        if kind == "folder":
            # Official permission.public PATCH v2 does not list folder as a type.
            if public.get("link_share_entity") != "closed":
                raise MigrationError("Folder link sharing is not closed; automatic folder permission mutation is unsupported")
        elif public.get("link_share_entity") != "closed" or public.get("external_access_entity") != "closed":
            self.api("PATCH", f"/open-apis/drive/v2/permissions/{token}/public",
                     {"external_access_entity": "closed", "link_share_entity": "closed"}, {"type": kind})
            public, items = inspect()
            if public.get("link_share_entity") != "closed" or public.get("external_access_entity") != "closed":
                raise MigrationError("Private document/file permissions failed readback after closing sharing")
        return {"status": "owner_only_verified", "checked_at": datetime.now(timezone.utc).isoformat(),
                "owner_open_id": owner_open_id, "type": kind, "member_count": len(items),
                "link_share_entity": public["link_share_entity"],
                "external_access_entity": public.get("external_access_entity"),
                "folder_setting_mutated": False}

    def api(self, method, path, data=None, params=None):
        args = ["api", method, path]
        if params:
            args += ["--params", canonical(params)]
        if data is not None:
            args += ["--data", "-"]
        return self.call(args, canonical(data) if data is not None else None)

    def children(self, parent):
        results, cursor, seen, ids = [], None, set(), set()
        while True:
            if parent["type"] == "folder":
                params = {"folder_token": parent["token"], "page_size": 200}
                if cursor: params["page_token"] = cursor
                data = self.api("GET", "/open-apis/drive/v1/files", params=params)
                rows, next_cursor = list_page(data, "files", seen)
            else:
                params = {"parent_node_token": parent["token"], "page_size": 50}
                if cursor: params["page_token"] = cursor
                data = self.api("GET", f"/open-apis/wiki/v2/spaces/{parent['space_id']}/nodes", params=params)
                nodes, next_cursor = list_page(data, "items", seen)
                rows = [{"name": n["title"], "token": n["obj_token"], "node_token": n["node_token"], "type": n["obj_type"], "url": n.get("url", "")} for n in nodes]
            for row in rows:
                token = row.get("node_token", row.get("token")) if isinstance(row, dict) else None
                if not token or token in ids:
                    raise MigrationError("Missing or repeated resource ID in directory pagination")
                ids.add(token)
            results += rows
            cursor = next_cursor
            if not cursor: break
        return results

    def find(self, parent, name):
        matches = [x for x in self.children(parent) if x.get("name") == name]
        if len(matches) > 1:
            raise MigrationError(f"Ambiguous duplicate names in target: {name}")
        return matches[0] if matches else None

    def container(self, parent, name):
        if parent["type"] == "folder":
            d = self.call(["drive", "files", "create_folder", "--data", "-"], canonical({"name": name, "folder_token": parent["token"]}))
            return {"type": "folder", "token": d["token"], "url": d.get("url", "")}
        d = self.call(["wiki", "+node-create", "--space-id", parent["space_id"], "--parent-node-token", parent["token"], "--title", name])
        return {"type": "wiki", "token": d["node_token"], "space_id": d.get("resolved_space_id", parent["space_id"]), "document_id": d["obj_token"]}

    def document(self, parent, title, markdown):
        d = self.call(["docs", "+create", "--title", title, "--parent-token", parent["token"], "--doc-format", "markdown", "--content", "-"], markdown)
        doc = d["document"]
        if d.get("warnings") or d.get("result") in ("partial_success", "failed"):
            raise MigrationError("Document import reported warnings/partial success; inspect before resuming")
        return {"token": doc["document_id"], "url": doc.get("url", ""), "type": "docx"}

    def blocks(self, token):
        items, cursor, seen, ids = [], None, set(), set()
        while True:
            params = {"page_size": 500, "document_revision_id": -1}
            if cursor: params["page_token"] = cursor
            d = self.api("GET", f"/open-apis/docx/v1/documents/{token}/blocks", params=params)
            rows, cursor = list_page(d, "items", seen)
            for row in rows:
                block_id = row.get("block_id") if isinstance(row, dict) else None
                if not block_id or block_id in ids:
                    raise MigrationError("Missing or repeated block ID in document pagination")
                ids.add(block_id)
            items += rows
            if not cursor: return items

    def append_blocks(self, token, blocks, event_id):
        import uuid
        return self.api("POST", f"/open-apis/docx/v1/documents/{token}/blocks/{token}/children",
                        {"children": blocks, "index": -1}, {"client_token": str(uuid.uuid5(uuid.NAMESPACE_URL, event_id)), "document_revision_id": -1})

    def upload(self, parent, path, name):
        flag = "--folder-token" if parent["type"] == "folder" else "--wiki-token"
        d = self.call(["drive", "+upload", "--file", path, flag, parent["token"], "--name", name])
        return {"token": d.get("file_token", d.get("token")), "url": d.get("url", ""), "type": "file"}

    def verify_file(self, resource, expected, scratch):
        self.call(["drive", "+download", "--file-token", resource["token"], "--output", scratch, "--overwrite"])
        if file_hash(inside(self.root, scratch)) != expected:
            raise MigrationError("Uploaded file checksum does not match source")

    def resource_url(self, resource):
        if resource.get("url"):
            return resource["url"]
        # The metadata batch API returns canonical URLs; do not invent a tenant domain.
        d = self.api("POST", "/open-apis/drive/v1/metas/batch_query", {"request_docs": [{"doc_token": resource["token"], "doc_type": resource["type"]}], "with_url": True})
        metas = d.get("metas", [])
        if not metas or not metas[0].get("url"):
            raise MigrationError("No canonical resource URL returned")
        return metas[0]["url"]


def block_text(blocks):
    strings = []
    for b in blocks:
        for value in b.values():
            if isinstance(value, dict):
                runs = []
                for element in value.get("elements", []):
                    if "text_run" in element:
                        runs.append(element["text_run"].get("content", ""))
                if runs:
                    strings.append("".join(runs))
    return "\n".join(strings)


class Runner:
    def __init__(self, plan, target, state_path, transport):
        self.plan, self.target, self.state_path, self.transport = plan, target, Path(state_path), transport
        self.root = Path(plan["source_root"])
        self.state = read_json(state_path) if Path(state_path).exists() else {"format": "feishu-migration-state-v1", "plan_id": plan["plan_id"], "target": target, "operations": {}, "cases": []}
        if self.state["plan_id"] != plan["plan_id"] or self.state["target"] != target:
            raise MigrationError("State belongs to a different plan or target; do not reuse it")
        self.private_owner = target.get("private_owner_open_id")
        if self.private_owner is not None:
            if not isinstance(self.private_owner, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", self.private_owner):
                raise MigrationError("private_owner_open_id requires an explicit verified OAuth open_id")
            self.state["private_actor"] = self.transport.verify_identity(self.private_owner)
            self.state["target_privacy"] = self.transport.ensure_private(target["parent"], self.private_owner)

    def save(self):
        save_json(self.state_path, self.state)

    @staticmethod
    def location(resource):
        return (resource.get("type"), resource.get("token"), resource.get("space_id"))

    def check_parent(self, parent, seen=None):
        """Prove the ancestry using only listings below the explicit target root."""
        if self.location(parent) == self.location(self.target["parent"]):
            return
        seen = set() if seen is None else seen
        identity = self.location(parent)
        if identity in seen:
            raise MigrationError("Container journal contains an ancestry cycle")
        seen.add(identity)
        matches = [op for op in self.state["operations"].values()
                   if op.get("status") == "done" and op.get("kind") == "container"
                   and self.location(op.get("resource", {})) == identity]
        if len(matches) != 1 or not isinstance(matches[0].get("parent"), dict):
            raise MigrationError("Parent is outside the explicit migration root or lacks a bound container journal")
        ancestor = matches[0]["parent"]
        self.check_parent(ancestor, seen)
        self.check_resource(ancestor, parent, "container")

    def check_resource(self, parent, resource, kind):
        # `parent` must already have passed check_parent. Never follow a journal URL.
        children = self.transport.children(parent)
        if not isinstance(children, list):
            raise MigrationError("Incomplete fixed-parent listing; resource boundary is unverified")
        wiki_container = kind == "container" and parent["type"] == "wiki"
        key = "node_token" if wiki_container else "token"
        matches = [child for child in children if child.get(key) == resource.get("token")]
        if len(matches) != 1 or (not wiki_container and matches[0].get("type") != resource.get("type")):
            raise MigrationError("Resource is not uniquely visible by ID in its fixed migration parent; no content or permissions were accessed")
        checked = dict(resource)
        checked.pop("url", None)
        if matches[0].get("url"):
            checked["url"] = matches[0]["url"]
        return checked

    def check_private(self, key, resource):
        if self.private_owner is not None:
            privacy = self.transport.ensure_private(resource, self.private_owner)
            self.state["operations"][key]["privacy"] = privacy
            self.save()

    def ensure(self, key, parent, title, kind, create, verify=None):
        self.check_parent(parent)
        ops = self.state["operations"]
        op = ops.get(key)
        if op and self.location(op.get("parent", {})) != self.location(parent):
            raise MigrationError("Operation journal has no matching fixed parent; reconcile it explicitly before resuming")
        if op and op["status"] == "done":
            resource = self.check_resource(parent, op["resource"], kind)
            if kind != "container":
                resource["url"] = self.transport.resource_url(resource)
            self.check_private(key, resource)
            return resource
        found = op.get("resource") if op else None
        if not found:
            found = self.transport.find(parent, title)
        if found:
            if not op:
                raise MigrationError(f"Target already contains {title}; refusing to adopt unrelated material")
            if kind == "container":
                resource = {"type": parent["type"], "token": found.get("node_token", found["token"])}
                if parent["type"] == "wiki": resource["space_id"] = parent["space_id"]
            else:
                resource = found
        else:
            if op:
                # An empty list immediately after a timeout is not proof that create
                # failed: service indexing can lag. Never recreate an uncertain write.
                raise MigrationError(f"Creation outcome is unknown for {key}; no matching resource is visible yet. Retry reading later or reconcile this operation before clearing its journal entry")
            ops[key] = {"status": "started", "title": title, "kind": kind, "parent": dict(parent)}
            self.save()  # durable intent before a non-idempotent creation request
            resource = create()
            ops[key]["resource"] = resource
            self.save()
        resource = self.check_resource(parent, resource, kind)
        if kind != "container":
            resource["url"] = self.transport.resource_url(resource)
        self.check_private(key, resource)
        if verify:
            verify(resource)
        privacy = ops[key].get("privacy")
        ops[key] = {"status": "done", "resource": resource, "title": title, "kind": kind, "parent": dict(parent)}
        if privacy is not None:
            ops[key]["privacy"] = privacy
        self.save()
        return resource

    def folder(self, key, parent, title):
        return self.ensure(key, parent, title, "container", lambda: self.transport.container(parent, title))

    def school_root(self, parent):
        if not self.target.get("use_parent_as_school", False):
            return self.folder("school-root", parent, "FDE AI School")
        if parent["type"] != "folder":
            raise MigrationError("use_parent_as_school currently requires an explicitly selected new empty folder")
        op = self.state["operations"].get("school-root")
        if op:
            resource = op.get("resource", {})
            if (op.get("status") != "done" or op.get("kind") != "adopted_empty_folder"
                    or op.get("verified_empty") is not True or resource != parent):
                raise MigrationError("School-root journal does not verify adoption of this empty target")
            # It is now expected to contain migrated material. Reuse only this journal.
            self.check_private("school-root", resource)
            return resource
        if self.state["operations"] or self.state["cases"]:
            raise MigrationError("Cannot adopt a parent after other migration operations have started")
        children = self.transport.children(parent)
        if not isinstance(children, list) or children:
            raise MigrationError("Selected school folder must be verified empty before first adoption; no unrelated content will be adopted")
        resource = dict(parent)
        self.state["operations"]["school-root"] = {
            "status": "done", "kind": "adopted_empty_folder", "resource": resource,
            "verified_empty": True, "title": "FDE AI School",
        }
        self.check_private("school-root", resource)
        self.save()  # Durable adoption evidence before the first remote child is created.
        return resource

    def upload(self, parent, rel, key=None):
        expected = self.plan["files"].get(rel) or file_hash(inside(self.root, rel))
        # Identical README files from different paths are distinct archive objects.
        title = f"{Path(rel).stem}-{sha(rel)[:8]}-{expected[:12]}{Path(rel).suffix}"
        scratch = self.state_path.parent.joinpath("verify-download.bin").relative_to(self.root).as_posix()
        return self.ensure(key or "file:" + rel, parent, title, "file", lambda: self.transport.upload(parent, rel, title), lambda r: self.transport.verify_file(r, expected, scratch))

    def doc(self, key, parent, title, text, required=(), image_count=0):
        marker = "school-migration-source:" + self.plan["plan_id"] + ":" + key
        markdown = text + "\n\n```text\n" + marker + "\n```\n"
        def verify(resource):
            blocks = self.transport.blocks(resource["token"])
            actual = normalized(block_text(blocks))
            for fragment in (marker, *required):
                if normalized(fragment) not in actual:
                    raise MigrationError(f"Readable document content verification failed: {key}")
            if sum(b.get("block_type") == 27 for b in blocks) < image_count:
                raise MigrationError(f"Missing visible image blocks: {key}")
        return self.ensure(key, parent, title, "docx", lambda: self.transport.document(parent, title, markdown), verify)

    def append_markers(self, key, doc, blocks, expected):
        matches = [op for op in self.state["operations"].values()
                   if op.get("status") == "done" and op.get("kind") == "docx"
                   and op.get("resource", {}).get("token") == doc["token"]]
        if len(matches) != 1 or not isinstance(matches[0].get("parent"), dict):
            raise MigrationError("Structured append target lacks a unique fixed-parent document journal")
        parent = matches[0]["parent"]
        self.check_parent(parent)
        self.check_resource(parent, doc, "docx")
        desired = {}
        for block in blocks:
            decoded = decode_marker_block(block)
            if decoded is None or decoded[0] in desired:
                raise MigrationError("Append requires unique complete structured code blocks")
            desired[decoded[0]] = decoded[1]
        if not desired or expected not in block_text(blocks):
            raise MigrationError("Append verification marker does not match its full payload")
        payload_hash = sha(canonical(sorted((list(identity), payload) for identity, payload in desired.items())))
        op = self.state["operations"].get(key)
        if op and (op.get("kind") != "append" or op.get("document_id", doc["token"]) != doc["token"]
                   or op.get("payload_sha256", payload_hash) != payload_hash):
            raise MigrationError("Structured append journal does not match this document and payload")

        def verified():
            found = {}
            for actual in self.transport.blocks(doc["token"]):
                decoded = decode_marker_block(actual)
                if decoded is None or decoded[0] not in desired:
                    continue
                identity, payload = decoded
                if identity in found or payload != desired[identity]:
                    raise MigrationError("Structured code block conflicts with the full expected content: " + key)
                found[identity] = payload
            if found and len(found) != len(desired):
                raise MigrationError("Structured code-block batch is incomplete; existing content was not changed: " + key)
            return len(found) == len(desired)

        # Old journals have only kind/status. They can be upgraded only after
        # the complete payload is found in this already-bound target document.
        if not verified():
            if op:
                raise MigrationError("Structured append is missing from its recorded target; outcome needs reconciliation, not a blind retry: " + key)
            self.state["operations"][key] = {"status": "started", "kind": "append", "document_id": doc["token"], "payload_sha256": payload_hash}
            self.save()
            try:
                self.transport.append_blocks(doc["token"], blocks, self.plan["plan_id"] + ":" + doc["token"] + ":" + key)
            except (MigrationError, OSError, subprocess.TimeoutExpired) as error:
                if not verified():
                    raise MigrationError("Structured append outcome is unverified; retain the journal and re-read this target before any retry: " + key) from error
            else:
                if not verified():
                    raise MigrationError("Structured block failed full-content readback: " + key)
        self.state["operations"][key] = {"status": "done", "kind": "append", "document_id": doc["token"], "payload_sha256": payload_hash}
        self.save()


def convert_markdown(root, rel, page_urls, file_urls):
    """Expand hidden HTML; preserve original text; rewrite images to CLI local refs."""
    text = inside(root, rel).read_text(encoding="utf-8")
    text = re.sub(r"</?details[^>]*>", "", text)
    text = re.sub(r"<summary>(.*?)</summary>", r"### \1", text)
    text = re.sub(r'<a\s+id="[^"]+"\s*></a>', "", text)
    def link(match):
        bang, label, dest = match.groups()
        if dest.startswith("#"):
            return label  # GitHub heading anchors are not Feishu block IDs.
        url = urlsplit(dest)
        if url.scheme:
            return match.group(0)
        path = (Path(rel).parent / unquote(url.path)).as_posix()
        path = inside(root, path).relative_to(Path(root).resolve()).as_posix()
        if bang:
            return f"![{label}](@./{path})"
        if path.endswith("original-interviews.pdf"):
            number = re.search(r"page=(\d+)", url.fragment)
            target = page_urls.get(int(number.group(1))) if number else file_urls.get(path)
        else:
            target = file_urls.get(path)
        return f"[{label}]({target})" if target else label
    return re.sub(r"(!?)\[([^\]]*)\]\(([^)]+)\)", link, text)


def apply_plan(plan, target, state_path, transport, selected, rules_file):
    verify_plan(plan)
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
    for case in plan["cases"]:
        cid = case["case_id"]
        if case["id"] not in selected:
            continue
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
                "migration_plan_id": plan["plan_id"], "cases": runner.state["cases"], "migration_status": "content_verified_permissions_pending"}
    runner.append_markers("manifest-data:" + ids, manifest_doc, [marker_block("school-manifest-v1", manifest)], "school-manifest-v1")
    save_json(runner.state_path.parent / "feishu-school.json", manifest)
    runner.state["manifest"] = manifest
    runner.save()
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan_cmd = sub.add_parser("plan", help="Verify all source hashes and prepare page PDFs; no remote calls")
    plan_cmd.add_argument("--root", type=Path, default=ROOT)
    plan_cmd.add_argument("--output", type=Path)
    app = sub.add_parser("apply", help="Explicit, resumable online migration")
    app.add_argument("--plan", type=Path, required=True)
    app.add_argument("--target", type=Path, required=True)
    app.add_argument("--state", type=Path, required=True)
    app.add_argument("--rules-file", type=Path, default=ROOT / ".codex/skills/school-guide/references/feishu-workflow.md")
    app.add_argument("--profile", default="fde-school")
    app.add_argument("--cli")
    choices = app.add_mutually_exclusive_group(required=True)
    choices.add_argument("--cases", help="Comma-separated numeric case IDs, e.g. 01,02")
    choices.add_argument("--all", action="store_true")
    app.add_argument("--execute", action="store_true", help="Required to make any remote write")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            plan = build_plan(args.root, args.output)
            print(json.dumps({"ok": True, "mode": "dry-run", "plan_id": plan["plan_id"], "statistics": plan["statistics"]}, ensure_ascii=False))
            return 0
        if not args.execute:
            raise MigrationError("No writes made. Review plan and provide --execute to apply")
        plan = read_json(args.plan)
        selected = {c["id"] for c in plan["cases"]} if args.all else {int(x) for x in args.cases.split(",")}
        if not selected or not selected.issubset({c["id"] for c in plan["cases"]}):
            raise MigrationError("Unknown case selection")
        state = args.state.resolve()
        if not state.is_relative_to(Path(plan["source_root"]).resolve()):
            raise MigrationError("State must be in the source workspace")
        state.parent.mkdir(parents=True, exist_ok=True)
        lock = state.with_suffix(".lock")
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise MigrationError("Migration lock exists; ensure no migration is running before removing the stale lock")
        try:
            os.write(descriptor, str(os.getpid()).encode())
            os.close(descriptor)
            manifest = apply_plan(plan, read_json(args.target), state, LarkTransport(plan["source_root"], args.profile, args.cli), selected, args.rules_file)
            print(json.dumps({"ok": True, "manifest_url": manifest["manifest_url"], "cases": len(manifest["cases"]), "status": manifest["migration_status"]}, ensure_ascii=False))
        finally:
            lock.unlink()
        return 0
    except (MigrationError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "resume": "Keep the same plan, target and state; successful operations will be reused."}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

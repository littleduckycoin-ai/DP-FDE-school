# 飞书迁移工具（维护者使用）

学员仍直接在线阅读学校，不需要运行本工具，也不需要下载教材。这里的本地文件只用于校方迁移、校验与断点续跑。

`tools/migrate_feishu.py` 将 GitHub 案例库迁移到指定飞书文件夹或知识库节点。默认命令只生成计划；只有 `apply --execute` 会写飞书。原有基础案例、学员记录和原 PDF 不被修改。

## 已实现的迁移范围

- 原库 24 个案例的 Markdown 转为可阅读的飞书 Docx：标题、段落、表格、完整问答、原图；原 Markdown 的折叠区域展开显示，图片通过官方 CLI 本地图片语法上传到文档，随后检查真实 image block 数量。
- 原 JSON、Markdown、图片、来源清单及其他源文件作为附件保留原始字节，上传后下载并校验 SHA-256。
- 完整 PDF 上传一份。每个案例引用的原 PDF 物理页分别生成单页 PDF，每页的渲染像素与原页比对。案例中的 PDF 引用改为对应单页附件链接，不假定飞书预览器支持 `#page=N`。
- 已有 reflection 保留作者、`identity_source`、`interaction_id`、`entry_id` 和学员原话，同时写入人可读正文与学校结构化 code block。历史作者不会被替换成迁移管理员。
- canon、patterns、curriculum、meetings、shared-notes、learning-notes 的已有文件保留；Markdown 同时转为可阅读文档。
- 学校规则、案例目录和供 Agent 读取的连接信息文档。仅完成部分案例时明确输出当前案例数。

迁移不会自动授予公开权限，不会将 `canon` 设置成人人可编辑。实际 ACL 和 mentor 审核权限需要部署验收完成后才能向学员发布。输出状态为 `content_verified_permissions_pending`，不冒称学校已经上线。

Markdown 里的 Mermaid 源码会作为代码保留；本工具不宣称飞书会自动将 Mermaid 渲染成图。原访谈的 74 个图片文件独立保存，并在对应案例内插入可见图片。

## 1. 生成并审核计划

维护电脑需要 Python 和 PyMuPDF；实际上传使用官方 `@larksuite/cli`，已核对的版本为 `1.0.94`。不需要把令牌写入配置或代码。

在仓库根目录执行：

```powershell
py -X utf8 tools/migrate_feishu.py plan --output .school/feishu-migration
```

生成的文件都在 Git 忽略的 `.school/` 中：

- `plan.json`：不可变源文件清单、原有 QA 哈希、24 个案例及页面资源计划。
- `source-inventory.json`：审核用的文件 SHA-256 清单与统计。
- `pages/`：被案例引用的 240 个 PDF 物理页，一页一个 PDF。

当前原库预期：24 案例、144 个完整 QA、247 页原 PDF、74 张图片、1 个已有 reflection。拆页 PDF 因字体及其他资源重复，合计约 318 MB，首次上传需要相应时间和云盘空间。

计划生成时检查 `data/base-manifest.json`、`sources/manifest.json` 和 `sources/integrity.json`。任何源文件在计划生成后发生变化，apply 会在写飞书之前停止；应审核变化并重新生成计划，不能直接忽略哈希差异。

## 2. 指定目标与身份

维护者在独立的 `fde-school` CLI profile 中完成自己的飞书 OAuth；不用共享账户令牌。目标配置写入 `.school/feishu-migration/target.json`，两种格式任选一种。

云盘文件夹：

```json
{"parent":{"type":"folder","token":"实际folder_token"}}
```

知识库节点：

```json
{"parent":{"type":"wiki","token":"实际wiki_node_token","space_id":"实际space_id"}}
```

token 必须从真实目标 URL/元数据读取，不能把 Wiki URL 中的 node token 当成 Docx document_id。工具会在目标下创建 `FDE AI School` 子目录，避免和无关材料混在一起。如果已存在同名目标且迁移状态无法证明它来自本次任务，工具停止，不自动接管。

规则正文通过 `--rules-file` 指定。默认是 `.codex/skills/school-guide/references/feishu-workflow.md`；这是校方发布的正文，不应包含令牌或密码。规则文件在迁移中途变更会停止当前任务，防止 pilot 和全量迁移采用不同规则而未记录。

## 3. 先迁一个案例，再继续全量

```powershell
py -X utf8 tools/migrate_feishu.py apply `
  --plan .school/feishu-migration/plan.json `
  --target .school/feishu-migration/target.json `
  --state .school/feishu-migration/state.json `
  --rules-file .codex/skills/school-guide/references/feishu-workflow.md `
  --profile fde-school --cases 01 --execute
```

验收案例 01 的全文、PDF 页面、原图和既有 reflection 后，使用同一份 plan、target、state，将 `--cases 01` 换为 `--all`。已完成的操作会复用，已有学员内容不会被覆盖。

Windows 下工具优先调用 npm 包内的原生 `lark-cli.exe`，避免 PowerShell `.ps1` 执行策略问题；也可以传 `--cli` 指定可执行文件。所有参数通过 `subprocess` 数组和 stdin 传递，不用 shell 拼接正文。

## 4. 恢复与失败处理

每次非幂等创建/上传之前，将操作意图写入 `state.json`；返回资源 ID 后立即记录。之后重新读取目标校验正文、图片或文件哈希，才标记完成。

- 正常中断：原命令原样重跑，复用已完成资源。
- 请求超时但服务器已创建：按原父目录和精确名称查找，并验证迁移标记、正文或附件哈希后复用。
- 请求结果不明且还找不到资源：停止，不立即新建副本。等待索引可见后重跑；确证服务器未创建后，维护者才能清理该单个 `started` 记录再试。
- 局部成功、图片丢失或正文不完整：停止并保留资源，人工检查失败位置；不自动重建或覆盖全文。
- 同名多个结果：停止，维护者明确应使用哪份后再恢复。
- 进程异常退出留下 `.lock`：确认没有其他迁移进程在运行，再删除该锁文件；不要删除 `state.json`。

结构化 reflection/manifest 追加使用官方 Docx block API，稳定的 `client_token` 由计划 ID 与操作 ID 生成；写后重新读取核验。该 token 用于同一请求重试去重，不代表跨文档事务，也不代表无限期的全局唯一约束。

## 5. Agent 使用的输出约定

每次完成一组案例都会生成 `feishu-school.json`，并在输出中给出真实 `manifest_url`。pilot 目录与完整目录采用不同版本的目录/连接信息文档；给学员分享前，应使用最后一次全量结果的链接。

```json
{
  "schema_version": "feishu-school-v1",
  "school_id": "fde-school",
  "rules_document_id": "...",
  "case_index_document_id": "...",
  "manifest_document_id": "...",
  "manifest_url": "...",
  "cases": [{
    "case_id": "case-01-manufacturing-training",
    "title": "把师傅经验变成培训闭环",
    "one_sentence_intro": "...",
    "base_document_id": "...",
    "base_url": "...",
    "reflections_parent": {"type":"folder","token":"..."},
    "canon_parent": {"type":"folder","token":"..."},
    "source_json_url": "...",
    "source_pdf_url": "...",
    "source_page_links": [{"pdf_page":8,"url":"..."}]
  }],
  "migration_status": "content_verified_permissions_pending"
}
```

连接信息文档的原生 code block 文本使用 `school-manifest-v1` 与 `school-manifest-end` 包围完整 JSON。reflection 使用 `school-record-meta-v1` / `school-record-meta-end` 包围原身份元数据；每个 interaction 使用 `school-interaction-v1` / `school-interaction-end`。普通学习过程中不得将学员记录写入文档评论区或 Issue。

## 验证

```powershell
py -X utf8 -m unittest discover -s tests -p test_feishu_migration.py -v
```

测试涵盖真实原库哈希与 QA 数量、源文件变更阻止写入、创建/追加超时后的恢复与去重、图片丢失检测、同名归档文件不混淆、历史身份与条目 ID 保留、错误目标拒绝复用状态。fake transport 验证算法，不替代真实租户中的 OAuth、ACL、图片呈现和跨设备 PDF 点击验收。

官方接口依据：[创建文档](https://github.com/larksuite/cli/blob/main/skills/lark-doc/references/lark-doc-create.md)、[Markdown 本地图片](https://github.com/larksuite/cli/blob/main/skills/lark-doc/references/lark-doc-md.md)、[创建块与 client_token](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block/create)、[上传文件](https://github.com/larksuite/cli/blob/main/skills/lark-drive/references/lark-drive-upload.md)。

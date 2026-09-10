# GitHub 后端

仅当学校公共路由仍以 GitHub 为当前后端，或维护者明确要求核对迁移前资料时使用。本阶段继续服务既有学员；不要因为飞书代码已经存在就提前切换数据源。

## 线上读取

仓库：`https://github.com/littleduckycoin-ai/DP-FDE-school`。

1. 查询 `https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/commits/main` 取得当前 commit SHA。
2. 按同一 SHA 在线读取 `data/online-school.json`、`data/case-index.json` 和本轮需要的资料。Contents API 为 `https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/contents/<path>?ref=<SHA>`；Base64 正文只在内存解码。可用按 SHA 的 Raw URL。
3. 下一轮依赖资料时重新检查 main；目录读取须覆盖全部分页/条目，达到 API 截断限制时换 Git Trees 或明确范围不完整。搜索摘要、登录页、截断网页不能冒充全文。
4. 规则与参考文件也按该线上版本读取。Raw main 可能被工具缓存，不把旧缓存当作最新规则；入口失败时切换 API 或 GitHub 文件页，仍失败则披露。

基础教材为 `cases/<case-id>/base/`；完整事实回到 `case.json` 的 `provenance.original_qa` 和 `original_page_text`。署名学习知识在 `reflections/`，正式拆解在 `canon/`，跨案例模式在 `patterns/`，会议产物在 `meetings/`。不要让学员克隆、建本地项目、安装 Git/Python 或运行维护工具。

案例事实的展示链接使用在线索引的 `pdf_page_url_template`；JSON 是机器核对入口。内部资料审计链接可用 `https://github.com/littleduckycoin-ai/DP-FDE-school/blob/<SHA>/<path>`；学员观点指向其 reflection 与条目 anchor。

## 追加 reflection

先遵守[共同记录契约](record-contract.md)。具体目标仍为：

`cases/<case-id>/reflections/<learner_id>-YYYY-MM-DD.md`

1. 读取 main 与目标文件，同时查找同一路径已开放的 reflection PR。复用可写分支与 PR；否则从最新 main 创建 `reflection/<learner_id>/<case-id>/<YYYY-MM-DD>`。
2. 读取目标分支当前文件，校验 ID 和已有历史。相同 `interaction_id` 且内容相同不重复写；内容改变则追加新的修订 interaction。
3. 通过 Contents API 或等价文件工具创建/更新 Markdown。更新须带最新 blob SHA；冲突时重读并保留其他会话新增内容。
4. 新 PR 标题为 `reflection: <case-id> / <learner_id> / <YYYY-MM-DD>`；已有 PR 继续追加。普通 reflection 不要求 CODEOWNER 审核，但必须通过 `school-checks`。连接账户有合并权限时在检查通过后合并，否则保留待合并 PR。
5. GitHub 成功回执后返回文件、commit 或 PR 真实链接；只有合并进入 main 后才能说“已进入共享知识库”。

精确 Markdown/JSON 格式按同一线上版本的 `docs/reflection-format.md` 及 `tools/school.py`。本地工具仅用于维护，不能成为学员前置步骤。

学习反馈不创建 Issue。没有可用写入连接时，提供完整 Markdown、准确路径及 `https://github.com/littleduckycoin-ai/DP-FDE-school/new/main/cases/<case-id>/reflections` 网页入口，由用户提交文件/PR。不得要求把访问令牌贴到聊天或擅改仓库权限。

## 会前与会后

固定 main SHA，逐个列出指定案例 `reflections/` 并读完除 `README.md` 外所有 Markdown。需涵盖刚提交内容时，再检查标题以 `reflection:` 开头且只修改 reflection 文件的开放 PR，按 PR head SHA 读取并标“待合并”。不把普通 Issue 或无关 PR 纳入学习记录。

清单记录抓取时间、main SHA、纳入的 PR head SHA、文件路径、interaction ID；按 interaction 的含时区时间应用截止范围。校验正文与结构化内容一致、路径与作者/日期/案例一致；发现历史改写或不完整读取时明确标注/排除。

汇总先在对话呈现；用户要求保存且有权限时，写 `meetings/<meeting-id>/` 的 `brief.md`、`manifest.json`、`synthesis.md`、`decisions.md`。Agent 整理和实际确认的决定分开；刷新生成稿不能覆盖既有确认决定。详见线上 `docs/meeting-workflow.md`。

## 正式知识

基础教材、`canon/`、`patterns/`、来源、规则和工具由 CODEOWNERS 与主分支保护共同保护。正式拆解及模式从 `proposed` 开始，真实 PR 审核通过后引用实际 `review_pr` 才能变为 `accepted`。跨案例模式至少引用两例，并说明条件、差异和反例；个人记录无需成为共识即可被引用。

维护基础材料需要明确维护请求，保留完整访谈、图片和修订理由，运行仓库要求的校验；不要把维护操作记为学员反馈。

# 学习记录的结构与归档

每个案例的`reflections/`保存学员的署名记录，文件名是`<learner-id>-YYYY-MM-DD.md`。一天可以讨论多轮，都追加到同一个文件；不同案例分别归档。Markdown可直接阅读，末尾的JSON注释供工具可靠提取，两部分由同一工具生成。

## 一条记录包含什么

| 层级 | 字段 | 含义 |
|---|---|---|
| 文件 | `case_id`、`learner_id`、`display_name` | 案例、稳定学习者标识和公开昵称 |
| 文件 | `identity_source`、`study_date`、`visibility` | 身份为本人自述；学习日期；共享草稿或私密 |
| 每轮 | `interaction_id`、`created_at`、`summary` | 重试不变的轮次编号、含时区的记录时间、简短主题 |
| 学员内容 | `entry_id`、`kind`、`text` | 可引用的唯一编号、内容类型、实际表达 |
| 表达来源 | `capture`、`confirmation` | 原话或概括；自动记录或学员明确确认 |
| 证据与关联 | `source_refs`、`relates_to`、`target_id` | 案例页码、同伴记录、被修订的旧记录或问题 |
| Agent内容 | `agent_feedback`、`next_steps` | 单独存放的建议，不代表学员认同或承诺 |

`kind`支持`thought`思考、`evaluation`评价、`question`问题、`application`应用设想、`disagreement`分歧、`feedback`同伴反馈、`revision`修订、`question_status`问题状态。一个发言可以拆成多条不同类型的内容，不能为了充实记录而虚构表达。

## Agent写入示例

下面是格式示例，**不是任何人的真实学习记录**。先读取具体案例核对内容，再使用实际用户表达替换：

```json
{
  "interaction_id": "s-example-t01",
  "summary": "讨论最小交付应该验证什么",
  "contributions": [
    {
      "kind": "question",
      "text": "如果用户还要在两个工具之间来回切换，怎么判断这个交付真的省了时间？",
      "capture": "verbatim",
      "confirmation": "captured",
      "source_refs": []
    }
  ],
  "agent_feedback": ["可以把单步操作耗时与整项任务完成时间分别测量。"],
  "next_steps": ["选一个完整任务设计前后对照；这是建议，尚未成为承诺。"]
}
```

Agent将JSON写入被忽略的`.school/turn.json`，在仓库根目录执行：

```sh
python tools/school.py record --case 04 --input .school/turn.json
```

学习者身份来自此前明确设置的`.school/identity.json`，不接受输入JSON偷偷换人。`record`只写本地、不执行Git推送；返回结果含路径和记录编号。`--date`可指定学习日期，默认使用运行环境当天日期；云端跨时区时应显式传学员当地日期。`created_at`用UTC记录实际归档时间，会前截止过滤以它为准。

引用结构为`{"case_id":"04","pdf_pages":[实际页码],"note":"引用用途"}`；工具按索引校验页码范围，Agent仍需核对原文是否支持观点。没有对应原文依据可用空列表，不编造页码。

## 更正、反馈与问题状态

- 更正旧观点：新轮次使用`kind: revision`和原`entry_id`作为`target_id`，写明改变和理由。禁止覆盖前文。
- 回应同伴：在自己文件里新增`feedback`或`disagreement`，`relates_to`放对方的`entry_id`；不改对方文件。
- 更新自己的问题：新增`question_status`，`target_id`指向原问题，`state`可为`open`、`answered`、`deferred`、`discussed`。只根据本人明确表达更新；除`answered`外仍列入未解决问题。
- 同一轮重试复用相同`interaction_id`，内容完全相同时不重复保存；不同内容使用新的修订轮次。

不要只手工编辑Markdown可见正文，或只编辑末尾JSON。它们必须一致；追加请使用工具，历史修订通过新条目表达。CI会拒绝改写已合并的学员历史；同一天不同设备产生Git冲突时合并双方新增轮次，保留全部旧条目，再用工具渲染和校验。

## 可见性与身份边界

共享草稿保存在`cases/.../reflections/`，直到PR合并才进入默认共享教材；分支或PR一旦推送到公共仓库也可被公开访问。私密模式加`--private`，写到Git忽略的`.school/private/`，会前工具不会读取它。要求“不记录”时跳过写入。

身份是自述标识，并非实名认证；Git提交作者、PR发起人和学习者标识不是同一字段。团队可以约定昵称映射，但不应因此推断单位或个人真实身份。已公开内容不能靠后来改为私密自动撤回，需单独处理原分支和历史。

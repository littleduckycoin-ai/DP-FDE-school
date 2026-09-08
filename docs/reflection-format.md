# Reflection知识文件格式

学习中的评论、问题、评价、思考、分歧、应用设想和修订都直接保存为案例知识文件：

`cases/<case-id>/reflections/<learner-id>-YYYY-MM-DD.md`

同一学习者、同一案例、同一天复用一个文件，每轮对话追加一个interaction。不同案例分别写文件。文件合并进main后，后续学习者和会前Agent可直接在线读取。学习反馈不使用GitHub Issue。

## 文件身份

文件开头的YAML字段和末尾的`school-record-v1` JSON必须一致：

| 字段 | 含义 |
|---|---|
| `schema_version` | 当前为`1.0` |
| `case_id` | 案例索引中的稳定标识 |
| `learner_id`、`display_name` | 学员自述的稳定标识与公开昵称 |
| `identity_source` | 固定为`self_declared` |
| `study_date` | 文件日期，格式为`YYYY-MM-DD` |
| `visibility` | 公开知识文件固定为`shared_draft` |
| `interactions` | 按时间追加的学习轮次，不得删除或改写旧轮次 |

文件名中的案例、学习者和日期必须与结构化字段一致。公开仓库不保存private记录。

## 每轮interaction

| 字段 | 含义 |
|---|---|
| `interaction_id` | 稳定轮次ID；同一次重试不换ID |
| `summary` | 这一轮讨论的简短主题 |
| `contributions` | 学员真实表达，可有多条 |
| `agent_feedback` | Agent建议，与学员观点分开 |
| `next_steps` | 待验证建议，不代表学员承诺 |
| `created_at` | 含时区的ISO 8601时间 |

贡献类型为`thought`、`evaluation`、`question`、`application`、`disagreement`、`feedback`、`revision`和`question_status`。每条还包括：

- `text`：学员原话或忠实概括。
- `capture`：`verbatim`或`paraphrase`。
- `confirmation`：自动记录用`captured`；学员明确确认后才能用`confirmed`。
- `source_refs`：案例依据，含case、原PDF物理页和说明；没有依据时用空数组。
- `entry_id`：`case_id:learner_id:interaction_id:序号`，序号从01开始。
- `relates_to`：关联的同伴条目ID；没有时用空数组。

`revision`用`target_id`指向自己的原条目。`question_status`还要提供`state`，只能是`open`、`answered`、`deferred`或`discussed`。只有提问者明确确认answered，问题才算解决。

## 追加和提交规则

1. 写入前读取main上的目标文件，也检查同一文件是否已有开放PR。
2. 同一`interaction_id`且内容一致时不重复写；内容变化时创建新的修订interaction。
3. 新文件从最新main建立reflection分支；更新文件必须携带最新blob SHA。遇到冲突先重新读取，保留所有已有interaction。
4. 一个学员当天在一个案例中复用同一分支和PR。PR标题为`reflection: <case-id> / <learner-id> / <date>`。
5. GitHub返回commit或PR链接后才叫“已上传”；PR合并进main后才叫“已进入共享知识库”。

普通reflection文件不要求CODEOWNER审核，但必须通过`school-checks`。历史文件只能追加，CI会拒绝删除或改写已有轮次。

## 公开范围和身份

学习者身份由本人自述，不等于实名认证；实际GitHub提交账户由commit和PR另行保留。用户说私密、不记录，或内容含未获授权的敏感信息时不上传。Agent只能记录用户实际表达，不能把自己的解释写成学员观点。

没有GitHub写入能力时，Agent应提供准确目标路径、完整Markdown和该案例`reflections/`目录的GitHub“Add file”入口，让学员登录后提交文件或PR。不要回退到Issue，也不要在没有成功回执时声称已经保存。

## 可读正文与机器数据

正文要让人能直接阅读：列出每轮时间、记录编号、内容类型、学员原话或概括、案例出处，以及分开的Agent反馈和下一步。文件末尾只放一个`school-record-v1` JSON注释。正文必须由同一份JSON渲染，不能出现两套含义不同的内容。

维护环境中的`tools/school.py`定义了精确校验和渲染规则；在线Agent无需让学员运行该工具，但生成的文件必须符合相同结构。

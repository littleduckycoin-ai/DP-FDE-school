# 线上学习记录

每位学习者、每个案例复用一个学习记录Issue，每轮新增评论。标题建议为`[学习记录] case-04-urban-planning-tools / alice`。发布后其他学习者和会前Agent可直接在线读取。

## 一轮记录的内容

| 字段 | 含义 |
|---|---|
| `case_id` | 案例索引中的稳定案例标识 |
| `learner_id`、`display_name` | 用户自述的稳定标识和公开昵称 |
| `interaction_id` | 本次会话的稳定轮次ID；同轮重试不换ID |
| `contributions` | 用户真实的思考、评价、问题、应用设想、分歧、反馈或修订 |
| `capture`、`confirmation` | 原话/概括；自动记录captured或用户明确确认confirmed |
| `source_refs`、`target_id`、`relates_to` | 案例页码、被修订的记录、同伴记录关联 |
| `agent_feedback`、`next_steps` | 单独存放的Agent建议；不代表学员认同或承诺 |
| GitHub回执 | 实际发布账户、帖子/评论ID、创建和修改时间、线上URL |

内容类型沿用`thought`、`evaluation`、`question`、`application`、`disagreement`、`feedback`、`revision`和`question_status`。条目ID由`case_id:learner_id:interaction_id:序号`组成。修订和问题状态指向原条目；反馈同伴放在自己的主题，不替对方改观点。

## 给Agent的可复制正文结构

下面仅为格式示例，不是任何人的真实记录。替换实际作者、案例与用户表达后发布：

```text
案例：case-04-urban-planning-tools
学习者：alice｜小艾（本人自述）
轮次：s-example-t01
记录方式：自动概括，可追加更正

学员问题：［用户实际提出的问题］
学员思考/评价：［用户实际表达的判断；没有就不填］
原文依据：［案例、PDF物理页与线上链接；尚未核实就明确说明］
Agent建议：［与学员观点分开］
```

需要机器提取时，可在正文末尾附`school-turn-v1` JSON注释。字段为`schema_version: "1.1"`、`case_id`、`learner_id`、`display_name`、`identity_source: "self_declared"`及`interaction`；interaction沿用原记录工具的`interaction_id/summary/contributions/agent_feedback/next_steps`字段。可见正文必须与结构化内容表达一致。

使用网页[学习记录表单](https://github.com/littleduckycoin-ai/DP-FDE-school/issues/new?template=learning-note.yml)提交的普通文字同样有效，不强制人类写JSON。Agent应读取表单中的案例、学习者标识、昵称与思考问题，保留原文和发布者信息。

## 每轮追加，保留变化

同一轮重试先查已有interaction_id，已发布就返回原链接。不同内容追加新轮次；更正引用原记录并说明变化。`question_status`只有提出者明确表示后才可更新为`open/answered/deferred/discussed`，只有answered代表已解决。Agent回答或主题关闭不自动解决问题。

姓名和身份为学习者自述，不等于实名认证；实际GitHub发布账户另行保留。没有身份可以先学习；没有写权限时只整理待提交内容，不冒称保存。用户说不记录或私密时不发布，默认只留在当前对话。

## 文件归档

各案例`reflections/`继续保存归档后的学习记录，按学习者与日期命名，沿用旧1.0 Markdown+JSON注释格式及追加校验。归档必须保留线上原记录链接和interaction_id，汇总时去重。文件归档是学校维护工作，学员无需下载教材、建立档案文件或操作PR。原始反馈发布后即能参与线上学习。

# 学习记录契约

学习记录只写飞书案例 reflections 的知识文档正文。保留稳定案例标识、作者、记录日期、原表达和关联关系。

## 身份与范围

只读学习不要求登记身份。首次保存前取得学员自述的稳定 `learner_id`、展示名及本次会话持续记录授权；已明确提供时直接沿用。说明真实可见范围：按目标飞书文档实际权限说明，未验证时不能称为“仅本组可见”。

将表达者与实际写入者分别记录。飞书 OAuth 登录账户、机器人或运行机器的账户不必然是当前学习者；只有身份映射已明确建立时才关联。不要从系统用户名、仓库拥有者、雇主或工具凭据猜作者。跨会话沿用用户确认过的标识。

飞书新建记录时，可将本次用户自述与其本人已验证的 OAuth 操作者作首次绑定，不要求事先建立外部身份表。写入前核对学校中该 `learner_id` 已有记录的实际操作者 `app_id + open_id`，跨日期、跨案例仍须一致。迁移旧文档缺少该元数据时，不能仅凭相同昵称或换一天认领；由维护者完成有依据的显式绑定，或由用户选择未占用的新学习标识继续。重新配置应用导致 app_id 改变时也需核实身份延续，不能冒充另一位学员。

用户明确不记录、要求私密，或内容包含未获授权的敏感身份/项目细节时不发布。只保存用户实际表达，维护讨论、普通事实查找、寒暄、Agent 讲解和工具回执不作为学员贡献。

## 记录粒度

每位学员、每个案例、每个学习日期一个 reflection 知识文档；日期使用学习会话明确的时区。每轮在其中追加 interaction；跨多个案例的表达分别落到各案例并保留关联。

记录结构沿用 `school-record-v1` 的语义：

| 层级 | 字段 |
|---|---|
| 文档 | `schema_version`、`case_id`、`learner_id`、`display_name`、`identity_source`、`study_date`、`visibility`、`interactions` |
| 一轮 | `interaction_id`、`summary`、`contributions`、`agent_feedback`、`next_steps`、含时区的 `created_at` |
| 学员条目 | `kind`、`text`、`capture`、`confirmation`、`source_refs`、`entry_id`、`relates_to` |
| 来源 | `case_id`、`case_number`、`pdf_pages`、`note` |

`kind` 新记录使用 `thought`、`evaluation`、`question`、`application`、`disagreement`、`feedback`、`revision`。旧 `question_status` 仅兼容读取原文，不再新增或推导业务状态。平台写入者、文档 token、版本和 API 回执放在平台元数据中，不冒充学员条目。

- `capture=verbatim` 表示原话；忠实概括用 `paraphrase`。
- 自动捕获用 `confirmation=captured`；学员明确确认这份记录后才能用 `confirmed`。
- `entry_id` 沿用 `case_id:learner_id:interaction_id:两位条目序号`，从 `01` 开始。
- 没有事实依据或关联条目时，`source_refs`、`relates_to` 使用空数组，不能补造出处。
- `agent_feedback` 与 `next_steps` 单独展示；后者是待验证建议，不代表用户承诺。
- 脚本当前写入 `visibility=school_shared`，它仅表达预期用途，不证明飞书 ACL 已配置；真实可见范围仍须核验。

正文须能直接阅读：时间、作者、条目类型、原话或概括、来源，以及分开的 Agent 反馈。结构化数据与正文应由同一份记录生成。飞书原生代码块保存唯一的 `school-record-meta-v1` 文档元数据，每轮追加 `school-interaction-v1` 代码块；可读正文由同一输入生成，具体由脚本处理。飞书正文是共享学习知识的载体；结构化字段可以辅助校验与检索，但不能只留在私聊、群消息或文档评论中。

## 历史与关联

同一请求重试必须复用 `interaction_id`、原时间、原授权与已返回的 `document_id`。同案例、同学员的 ID 跨日期也不可重复。`create-record` 仅准备文档；`append` 必须带文档 ID，永不隐式新建。创建结果不明时保留回执，重查携带 `retry:true`，查不到不能重建。写前读取目标文档；同 ID 且内容一致时核验正文并返回既有链接。内容不同则创建新的修订 interaction，不能改写旧条目。并发冲突先重读，保留其他会话已追加内容；当前工具无法保证原子性时如实标明，不声称强事务或绝对不重复。

`revision` 用 `target_id` 指向本人的原条目。对同伴的评价写入自己的 reflection，以 `relates_to` 引用对方条目。不得编辑对方观点来代替反馈。

问题进展保存为提问者的普通原话或忠实概括，可用 `relates_to` 引用原问题。Agent 据原文整理，不自行宣布解决；脚本不接受新 `question_status` 或 `state` 字段，不运行问题状态机，旧记录原样保留。

## 回执与失败

每轮获得授权且有可沉淀内容时尝试追加，成功后给出真实知识文档或条目链接。普通 reflection 不设额外审批步骤；保存状态按[飞书工作流](feishu-workflow.md)中的实际回执报告，共享权限另行核验。文档存在、工具已安装或模型生成了正文均不等于已保存。

如果网络、登录、权限或接口限制阻止提交，保留本轮完整待提交正文、原 `interaction_id` 与准确目标链接，说明缺少哪一步。入口本身不可读时，提供已知学校入口与 `case_id`，标记“目标待解析”，不猜文档位置。用户协助授权后从该记录恢复；不要反复重试同一失败，也不要把学习内容临时写到其他平台、私聊或评论来充数。教学可以继续。

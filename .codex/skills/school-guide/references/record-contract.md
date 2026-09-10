# 学习记录契约

GitHub 与飞书使用同一套学习记录含义。存储位置可变，稳定案例标识、作者、记录日期、原表达和关联关系不能因迁移而改变。

## 身份与范围

只读学习不要求登记身份。首次保存前取得学员自述的稳定 `learner_id`、展示名及本次会话持续记录授权；已明确提供时直接沿用。说明真实可见范围：GitHub 公共仓库是公开发布；飞书按目标文档实际权限说明，未验证时不能称为“仅本组可见”。

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

`kind` 只能使用既有类型：`thought`、`evaluation`、`question`、`application`、`disagreement`、`feedback`、`revision`、`question_status`。平台写入者、文档 token、版本和 API 回执放在平台元数据中，不冒充学员条目。

- `capture=verbatim` 表示原话；忠实概括用 `paraphrase`。
- 自动捕获用 `confirmation=captured`；学员明确确认这份记录后才能用 `confirmed`。
- `entry_id` 沿用 `case_id:learner_id:interaction_id:两位条目序号`，从 `01` 开始。
- 没有事实依据或关联条目时，`source_refs`、`relates_to` 使用空数组，不能补造出处。
- `agent_feedback` 与 `next_steps` 单独展示；后者是待验证建议，不代表用户承诺。
- `visibility=shared_draft` 表示署名学习记录的内容状态，不证明飞书 ACL 已配置。

正文须能直接阅读：时间、作者、条目类型、原话或概括、来源，以及分开的 Agent 反馈。结构化数据与正文应由同一份记录生成。GitHub 格式仍为 YAML 头、可读正文、唯一 `school-record-v1` JSON 注释，精确格式见线上 `docs/reflection-format.md`。飞书正文是共享学习知识的载体；结构化字段可以辅助校验与检索，但不能只留在私聊、群消息或文档评论中。

## 历史与关联

同一请求重试必须复用 `interaction_id`。写前读取目标文档；同 ID 且内容一致时返回既有记录链接。内容不同则创建新的修订 interaction，不能改写旧条目。并发冲突先重读，保留其他会话已追加内容；当前工具无法保证原子性时如实标明，不声称强事务或绝对不重复。

`revision` 用 `target_id` 指向本人的原条目。对同伴的评价写入自己的 reflection，以 `relates_to` 引用对方条目。不得编辑对方观点来代替反馈。

`question_status` 用 `target_id` 指向自己的问题，并提供 `state=open|answered|deferred|discussed`。只有提问者明确表示已解决、重新打开、暂缓或已讨论时才追加对应状态。Agent 回答、主持人整理和多数人意见不能自动关闭问题。

## 回执与失败

每轮获得授权且有可沉淀内容时尝试追加，成功后给出真实知识文档或条目链接。区分“待提交”“已写入待审核”“已发布可共享”。只有平台成功回执及必要回读才能报告对应状态。文档存在、工具已安装或模型生成了正文均不等于已保存。

如果网络、登录、权限或接口限制阻止提交，保留本轮完整待提交正文、原 `interaction_id` 与准确目标链接，说明缺少哪一步。入口本身不可读时，提供已知学校入口与 `case_id`，标记“目标待解析”，不猜文档位置。用户协助授权后从该记录恢复；不要反复重试同一失败，也不要把学习内容临时写到另一后端、Issue、私聊或评论来充数。教学可以继续。

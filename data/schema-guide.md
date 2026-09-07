# 单个案例的数据结构｜2.1

每例一个`case.json`，配套一个`case.md`。Markdown用于阅读和讲解，JSON保留可检索字段、详细扩充与完整原文，二者表达同一案例。[示例](../cases/01/case.json)

## 本次新增

| 字段 | 内容与用途 |
|---|---|
| `one_sentence_intro` | 一小段口语化文字：哪类行业遇到什么具体痛点，FDE做了哪些事，产生什么已观察的效果或目前做到哪一步。目标与未验证效果不写成已实现。 |
| `intro_metadata` | 简介证据类型、来源物理页范围和写法说明。 |
| `expanded_learning.business_context` | 更细的业务现场、参与者与原工作条件。 |
| `expanded_learning.industry_explanation` | 行业约束如何影响方案，属于补充分析。 |
| `expanded_learning.project_journey` | 调研、判断、尝试、转折及阶段推进。 |
| `expanded_learning.delivery_in_use` | 交付物进入日常工作后，使用者怎样操作和确认。 |
| `expanded_learning.key_tradeoffs` | 技术、业务、组织之间的取舍及可学习的方法。 |
| `expanded_learning.implementation_detail` | 数据、环境、培训、推广、维护等原文细节。 |
| `expanded_learning.effect_interpretation` | 数字能说明什么，哪些分母、范围或后续结果仍缺失。 |
| `expanded_learning.transfer_exercise` | 面向通用研发与协作场景的假设试点、输入、责任和验收建议。 |

每个扩充部分含`paragraphs`、`evidence_type`、`source_pdf_page_range`和`reference_qa`。这些来源范围用于定位；逐句精确引用时需继续查看完整问答及原页文字。

## 原有15组字段继续保留

| 字段组 | 内容 |
|---|---|
| `identity` | 编号、原题、学习标题、行业、主题、学习时间与文件位置。 |
| `setting` | 项目现场事实与来源。 |
| `industry_mechanism` | 行业机制的编辑解释。 |
| `problem` | 旧流程、重定义问题和FDE必要性。 |
| `discovery` | 观察到的信号与形成的决定。 |
| `solution` | 流程步骤、角色职责。 |
| `delivery` | 交付物及日常采用方式。 |
| `implementation` | 范围、阶段、推进与组织采用。 |
| `evaluation` | 效果、前后参照、限定和未披露事项。 |
| `frictions` | 挑战及应对。 |
| `lessons` | 命题、决策模式、复用条件与原经验入口。 |
| `learning_transfer` | 研发迁移情境、切口、验收和限制。 |
| `facilitation` | 讨论题、应形成的产物与主持人参考。 |
| `provenance` | 原PDF、页码、完整问答、逐页文字、封面和原图。 |
| `preservation` | 原文保存方式及此前PPT页码参考说明。 |

## 证据类型

- `INTERVIEW`：原访谈陈述或据其概括；不等于独立核验的客观成效，也不表示逐字引文。
- `ANALYSIS`：编辑补充的行业解释、流程抽象或证据解读。
- `EXERCISE`：面向其他工作场景的假设练习，不代表已有项目。

用户与Codex讨论中产生的新推断应另外标注，不能静默写回原访谈。不得补造客户名称、内部技术栈、预算、项目日期或收益。

## 路径与全文规则

JSON中的素材和文件路径均相对仓库根目录；`$schema`相对该JSON文件。Markdown链接相对当前MD文件。PDF页码默认指物理页，书内页码另存，正文通常相差1页。

`provenance.original_qa`保留6组完整问答，含`question_id`、`question`、`answer`、`original_block`；`original_page_text`保留各原页文字。图片文字不靠抽取文本替代，封面、50张正文原图与原PDF共同保留完整信息。

跨案例检索先读取[data/case-index.json](case-index.json)，再按任务读取单例，避免每次加载全部访谈。[JSON Schema](case.schema.json)用于结构校验；[校验脚本](../tools/validate.py)还检查144组原文、简介同步、图片和Markdown链接。

# FDE AI School

24个FDE落地案例，面向研发、产品、业务与交付人员的案例共学。每例先用口语化简介讲清项目，再展开行业、方案形成、交付、实际效果与迁移练习，最后保留完整访谈。

**[进入24例目录](cases/README.md)** · **[让Codex带你学习](START_HERE.md)** · [四次共学路线](curriculum/routes.md)

## 资料怎样组织

| 内容 | 入口 |
|---|---|
| 24份逐例Markdown详解 | `cases/01/case.md` 至 `cases/24/case.md` |
| 24份逐例JSON数据 | `cases/01/case.json` 至 `cases/24/case.json` |
| 一句话简介与检索索引 | [案例目录](cases/README.md) / [轻量JSON索引](data/case-index.json) |
| 数据结构与字段约定 | [结构说明](data/schema-guide.md) / [JSON Schema](data/case.schema.json) |
| 144组完整问答、原页文字与原图 | 每例末尾完整访谈、JSON中的provenance、[原PDF](sources/original-interviews.pdf) |
| 共学课程与主持提示 | [课程路线](curriculum/routes.md) / [主持人手册](curriculum/facilitator.md) |
| AI导师的项目指令 | [AGENTS.md](AGENTS.md) |

本次发布专门扩充Markdown和JSON。此前PPT中的页码引用保留作参考，PPT文件仍在此前交付材料中。

## 直接用Codex读

在Codex云端连接本仓库并创建/选择对应环境，或下载/克隆整个仓库，在本地Codex中打开项目根目录。然后发送：

```text
阅读AGENTS.md和cases/README.md。你是我的FDE学习导师。
我是研发人员，先从案例04开始，按10分钟节奏带我学习。
先讲清楚这个项目做了什么，再问我一个关键判断。
引用原文时给出PDF物理页；迁移到实际工作时标明假设。
```

也可以直接问：“比较案例06、17、21，为什么AI输出还需要专业人员确认？”或提交自己的试点方案，让Codex根据案例提出修改建议。

GitHub提供教材，Codex需要先获得对应项目的文件访问。共用仓库不会自动合并成员的聊天记录；学习记录可按需保存。[详细接入步骤](START_HERE.md)

## 一例10分钟怎么学

前6分钟抓住现场、转折、工作流程、交付与效果，后4分钟做一个具体迁移练习。详细段落用于课前阅读和追问，完整访谈用于核对信息。每次留下一个决定、一条依据、一项适用条件和一个待验证动作。

24例分为四次共学：专业工具与可控交付、知识与团队能力、流程采用与组织变化、经营联动与价值验证。个人可按任务自由选择。

## 资料依据

原文来自用户提供的Datawhale《FDE案例100》，原文署期2026年9月6日；课程整理日期为2026年9月7日。保留24例、144组问答、24张案例封面和50张正文原图，原PDF共247个物理页面，逐字节保存。

原访谈陈述、编辑补充分析和迁移假设演练分别标明。试点数字、估算、尚未实现的目标、其他客户经验和脱敏数据保留限定。[来源说明](sources/README.md) · [内容校验报告](docs/content-check.json)

## 共建课程

个人学习记录默认不进入Git，可使用[记录模板](templates/learning-note.md)。小组讨论结论可用[共学模板](templates/group-insight.md)整理到`shared-notes/`，维护者选择纳入课程。

修改案例时同时更新该例MD与JSON，简介改动同步索引，并保留原文来源。运行`python tools/validate.py`完成基础内容与链接校验。

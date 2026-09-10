# FDE AI School

**给Agent一个学校链接，让它在线读案例，带你学习。**

学员使用 Codex 和一个 school-guide Skill，Agent 在每轮需要资料时访问线上来源，结合你的问题讲解、追问和比较，让同一份在线知识服务不同学习者。

学校正在接入飞书文档：案例、署名学习记录和会议资料将由飞书承载，GitHub 保留 Skill 与连接工具的分发入口。**当前仍使用 GitHub 资料库；飞书登录、迁移与权限验收完成后才切换。**实际状态以[后端入口](data/school-backend.json)为准。[飞书学习说明](docs/feishu-learning.md)

案例事实的引用会直接打开原访谈PDF的对应物理页；JSON保留给Agent检索和核对，不作为学员默认看到的证据链接。

学习不要求克隆仓库、建立本地项目、安装 Git 或 Python。公开 GitHub 资料可以直接读；飞书切换后，Agent 准备连接工具，学员首次完成本人的飞书授权，并拥有学校文档权限。

## 先安装school-guide

把[school-guide文件夹](https://github.com/littleduckycoin-ai/DP-FDE-school/tree/main/.codex/skills/school-guide)发给Codex：

> 请使用 $skill-installer 安装这个skill：https://github.com/littleduckycoin-ai/DP-FDE-school/tree/main/.codex/skills/school-guide

安装后直接说“使用`$school-guide`，根据我的问题推荐一个案例并开始学习”。[安装说明](INSTALL_SKILL.md)

## 不安装也能开始

> 请在线读取 https://github.com/littleduckycoin-ai/DP-FDE-school/blob/main/START_HERE.md ，按照其中的线上教学规则带我学习。每轮需要资料时读取线上当前版本，不建立本地教材副本。先用10分钟带我学习案例04，先讲清项目，再围绕我的判断展开讨论，并给出出处。

[安装skill](INSTALL_SKILL.md) · [直接开始学习](START_HERE.md) · [24个案例](cases/README.md) · [学习方法](HOW_TO_LEARN.md) · [如何留下思考](docs/contributing.md)

## 一所持续生长的学校

```mermaid
flowchart LR
  A[学员发链接和学习目标] --> B[Agent在线读取相关资料]
  B --> C[讲解、追问与讨论]
  C --> D[署名反馈写入案例reflections]
  D --> E[会前实时汇总问题与分歧]
  E --> F[审核后沉淀拆解与模式]
  F --> B
```

| 在线资料 | 学习时如何使用 |
|---|---|
| `cases/<case-id>/base/` | 24个基础案例：口语化简介、行业约束、解法形成、交付与成效、完整访谈和原图 |
| `cases/<case-id>/reflections/` | 每位学员的署名知识文件，保存思考、评价、问题、分歧和修订 |
| `cases/<case-id>/canon/` | 经PR审核的案例拆解；待审与已审版本分开 |
| `patterns/` | 跨至少两个案例的方法、适用边界与反例 |
| `meetings/` | 已发布的会前资料、Agent整理和实际确认的会议决定 |

## 校规

访谈事实、教材分析、学员观点和Agent建议分别标明。相近提问不等于共识，Agent给答案不等于学员的问题已解决；原文不足时明确说明。

学习者需要署名反馈时提供稳定标识和昵称，并授权本次会话记录。之后 Agent 将有价值的表达逐轮追加到当前资料库对应案例的 reflection 知识正文，保存后给出经核对的链接。没有写入连接时继续教学，并给出待提交正文及具体协助方式。反馈不会进入 Issue、飞书评论或聊天消息，也不会在两处重复保存。

案例教学以当轮线上读取为准。reflection 是署名学习知识，进入共享资料库后即可用于后续学习和会前整理；它仍是个人表达。canon 与 patterns 经过真实维护者审核才成为正式知识。当前 GitHub 记录公开可见；飞书记录按实际文档权限共享，Agent 在首次保存前说明分享范围。

## 给Agent与维护者

[AGENTS.md](AGENTS.md)是入口，[school-guide](.codex/skills/school-guide/SKILL.md)维护启动规则；Codex和Claude Code的发现入口共用它。[后端入口](data/school-backend.json)声明当前资料库，GitHub 后端仍通过[在线服务索引](data/online-school.json)查找各类 URL。维护者按[飞书迁移说明](docs/FEISHU_MIGRATION.md)执行试迁移、保真检查和正式切换。

仓库中的脚本和CI服务于维护、验证和归档。它们不是学员的初始化步骤。现有基础案例与144段完整问答保留；[数据结构](data/schema-guide.md)、[来源](sources/README.md)、[在线读取协议](docs/online-protocol.md)、[反馈流程](docs/contributing.md)和[审核规则](docs/governance.md)可按需查阅。

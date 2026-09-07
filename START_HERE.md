# 用Codex或Claude Code开始

把[本仓库](https://github.com/littleduckycoin-ai/DP-FDE-school)发给学员即可分享教材。要让Agent自动保存讨论，还需要在可写入文件的仓库工作区里学习。

## 最顺手的方式

1. 用Codex桌面端、CLI或Claude Code打开克隆后的仓库文件夹。Codex云端可连接GitHub并选择本仓库对应环境；每位学员使用自己的账户与有权限的工作区。
2. 对Agent说：“读取AGENTS.md，用school-guide带我学习。我是`alice`，昵称小艾，先学案例04。”替换成自己的稳定标识与昵称。
3. 正常讨论。Agent在每轮有内容的讨论后给出保存的记录路径；发现概括不准确，直接要求更正，旧记录会保留。
4. 需要同学看到时说：“提交我的课前记录，创建PR。”PR合并后成为共享资料。也可以明确授权本次学习会话持续更新同一个PR。

如果Agent未自动加载skill，直接让它读取[完整规则](.codex/skills/school-guide/SKILL.md)。仓库包含Codex的`.agents/skills/`入口和Claude Code的`.claude/skills/`入口，两者引用同一份规则；不要分别改两份教学逻辑。[Codex技能说明](https://learn.chatgpt.com/docs/build-skills)、[Claude Code技能说明](https://code.claude.com/docs/en/skills)。

## 可直接复制的话

> 我是 learner-01，昵称小林。选一个适合学习需求发现的案例，先让我自己判断，再看同学的观点。每轮记录我的想法。

> 我修改刚才的观点：问题的关键是交付后的采用，而不只是生成质量。请保留原记录并追加修订。

> 这个回答还没解决我的问题，请继续保留为开放问题。

> 我的问题已经解决了，请更新它的状态。

> 汇总主分支中案例04和06的学习记录，截止到2026-09-07T18:00:00+08:00。按主题列出问题与分歧，并给出讨论建议。

示例日期应替换为实际会议截止时间。更完整的[学习方法](HOW_TO_LEARN.md)、[共享流程](docs/contributing.md)和[会议流程](docs/meeting-workflow.md)分别说明各环节。

只在普通聊天里粘贴GitHub链接，可能能够阅读部分页面，但无法保证完整读库、自动写文件或共享记录。请使用已打开本仓库的Agent工作区；在云端临时环境结束前提交需要保留的记录。私密笔记应自行保留在可信的个人工作区。

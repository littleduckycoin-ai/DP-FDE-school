# 教材链接与Agent工作区

GitHub负责存放共享教材和记录；Codex或Claude Code负责对话、读取文件与执行归档规则。两者通过仓库文件协作，每个人的私人聊天不会自动成为共同记忆。

| 使用方式 | 适合做什么 | 记录如何保留 |
|---|---|---|
| 直接打开GitHub | 阅读案例、同学记录和已审拆解 | 网页阅读本身不创建学习记录 |
| 本地Codex或Claude Code | 持续学习、逐轮保存和整理 | 本地文件；授权后推送PR并合并共享 |
| Codex云端仓库环境 | 在线读取仓库、学习和提交改动 | 确认环境可写且有GitHub权限；结束前提交需要持久保留的内容 |

Codex当前项目skill入口使用`.agents/skills`，Claude Code使用`.claude/skills`，本仓库的两个入口都指向`.codex/skills/school-guide/SKILL.md`。[Codex官方技能说明](https://learn.chatgpt.com/docs/build-skills)、[Claude Code官方技能说明](https://code.claude.com/docs/en/skills)。

云端环境的创建与GitHub连接方式见[Codex云端官方文档](https://learn.chatgpt.com/docs/cloud)。客户端界面会更新，以当前入口为准。课程本身没有独立登录系统、托管聊天机器人或自动的全组聊天访问权限。

返回[开始学习](../START_HERE.md)。

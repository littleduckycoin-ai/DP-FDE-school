# 飞书 FDE 学校 · school-guide

一个 Skill，完成 FDE 案例学习、署名反馈和会前整理。教材、规则和学习记录只在飞书读写；本仓库只分发 Skill。

## 安装

```bash
npx skills add littleduckycoin-ai/DP-FDE-school --skill school-guide
```

按提示选择使用的 Agent。需要跨项目使用时加 `-g`；只安装到 Codex 可加 `-a codex`。安装器会保留整个 Skill 目录，包括 `scripts/` 和 `references/`，不需要另下 ZIP 或手动复制文件。

运行安装命令需要 Node.js/npm 和 Git；连接脚本需要 Node.js 22+。学员不用克隆本仓库或准备本地教材。

## 开始学习

安装后，在 Agent 新会话中说：

> 使用 school-guide，帮我完成首次飞书连接，再开始第一个案例。

Agent 会检查连接工具、复用可用配置，并协助本人授权。**安装 Skill 不等于已连接飞书，也不等于获得学校文档权限。** 没有应用配置时，Agent 会说明个人应用与管理员配置两种方式，确认后再继续；不会替学员绕过组织审批或索取聊天中的密钥。

[学校首页](https://dptechnology.feishu.cn/docx/J5Uad8uqAoBNtyxkWfKcCSbZnQb) · [首次连接说明](skills/school-guide/references/feishu-connection.md)

只读学习不强制登记。需要保存反馈时再提供展示名、稳定学习标识和本次会话记录授权；说“不记录”的内容不会上传。反馈写入对应案例的飞书 reflections 文档正文，成功后返回实际链接，失败则明确待提交。

## 仓库结构

```text
skills/school-guide/
  SKILL.md           # 唯一教学入口
  agents/            # Agent 展示信息
  scripts/           # 零第三方依赖的飞书连接与记录脚本
  references/        # 连接、工作流、记录契约与输入示例
tests/               # 核心行为与安装包完整性测试
```

不维护多套 Agent 专用副本、自制安装器、ZIP 分发或 GitHub 教材后端。发布只需维护这一份 Skill；安装器负责不同 Agent 的安装位置。

## 维护与验证

```bash
node --test tests/*.mjs
```

本地安装验证应在临时目录执行，避免把生成的 Agent 安装目录混进仓库：

```bash
npx skills add /absolute/path/to/DP-FDE-school --skill school-guide -a codex -y
```

测试不连接真实飞书或上传虚构学习记录。真实连接、读权限和保存能力须分别核验，不能用单元测试代替。

### 历史归档

清理前版本：`5a2296a8393778d1e1dba5ca9d8615fee05b574a`，本地归档标签：`archive/pre-skills-only`。原始访谈、图片、24 个案例、历史学习记录和迁移工具均保留在该版本，不再作为当前学习入口。清理前已通过旧版校验，并从独立 Git bundle 恢复、逐字节核对全部 260 个受版本管理文件。

维护者可导出历史，不必切换当前工作目录：

```bash
git archive --format=tar --output=../school-legacy.tar 5a2296a8393778d1e1dba5ca9d8615fee05b574a
```

独立 bundle 应由维护者妥善保管；发布时将归档标签与更新一起推送。不要重写历史、删除归档或把归档教材重新接入学员学习流程。

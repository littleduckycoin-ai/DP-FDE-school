# 用Codex阅读和讨论这套案例

课程仓库：https://github.com/littleduckycoin-ai/DP-FDE-school

## 方式一：Codex云端

1. 用自己的ChatGPT账号进入 [Codex](https://chatgpt.com/codex)。
2. 按界面引导连接GitHub，允许Codex访问`littleduckycoin-ai/DP-FDE-school`。若由组织管理，可能需要管理员完成仓库授权。
3. 为本仓库创建或选择一个环境，再在该环境中发起学习任务。课程是文档项目，无需额外安装运行依赖。
4. 发送下方开场提示。Codex可读取根目录`AGENTS.md`中的导师规则，再按需查单个案例。

成员需要自己的可用Codex账户及相应仓库/环境访问权限。支持环境共享的工作空间可由维护者创建环境后分享，具体以账号和管理员设置为准；仅收到GitHub链接不等于环境已配置完成。[官方云端步骤](https://learn.chatgpt.com/docs/cloud)

## 方式二：本地Codex

1. 在GitHub仓库选择Code → Download ZIP并解压，或运行：

```sh
git clone https://github.com/littleduckycoin-ai/DP-FDE-school.git
```

2. 在Codex应用中打开解压或克隆得到的`DP-FDE-school`项目文件夹。根目录应能看到`AGENTS.md`、`README.md`和`cases`。
3. 在该项目新建会话并发送下方提示。CLI用户也可在该目录运行已安装并登录的`codex`。

本地项目以打开的文件夹作为上下文；只在云端聊天里粘贴本机路径不会自动上传文件。[官方项目说明](https://learn.chatgpt.com/docs/projects)

## 第一次学习，复制这段话

```text
阅读AGENTS.md和cases/README.md。
我是一名学习者，你是我的FDE学习导师。
先用口语解释案例04做了什么，再按10分钟节奏带我学习。
每次只问一个关键问题，等我回答后再继续。
事实要给原PDF页码，补充分析和迁移假设要分开。
```

AGENTS.md是Codex的项目指令文件，进入对应项目后会按其查找规则读取，无需额外制作插件。[官方AGENTS.md说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

## 常用提问

| 想做什么 | 可以直接发送 |
|---|---|
| 看懂具体项目 | “用一句话和一张流程图讲清案例17，分别说明AI、系统和人做什么。” |
| 核对原文 | “案例22实际证明了什么效果，哪些经营数据缺失？请找原文。” |
| 横向比较 | “比较案例01和18：为什么知识库本身不能完成新人培训？” |
| 迁移到研发 | “用案例19的方法，为仿真结果预审设计一个最小试点，列出专业复核边界。” |
| 模拟访谈 | “你扮演研发客户，我扮演FDE。先给我一个模糊需求，等我追问。” |
| 评议方案 | “按问题、证据、流程、交付和验收评议我的方案，给一个下一步动作。” |
| 保存学习 | “将本次判断、争议和下一步按模板保存到learning-notes。” |

## 组织讨论组

把仓库链接和本页发给成员，第一次共同确认大家已进入正确的Codex项目/环境。每次选6例，讲解与讨论约75分钟；也可每次只讲1至2例。

每位成员的对话独立。课后选择愿意共享的结论，整理到`shared-notes/`；GitHub同步教材与选定笔记，不会自动同步所有人的聊天或个人进度。要续学，打开原会话或让Codex读取已保存的学习记录。

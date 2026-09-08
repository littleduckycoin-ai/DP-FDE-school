# 发一个链接，开始在线学习

希望Codex以后自动识别FDE学习需求时，先[安装school-guide](INSTALL_SKILL.md)：

> 请使用 $skill-installer 安装这个skill：https://github.com/littleduckycoin-ai/DP-FDE-school/tree/main/.codex/skills/school-guide

安装后直接说“使用`$school-guide`，根据我的问题推荐一个案例并开始学习”。不安装也可按下面方式在线学习。

打开你常用的、能直接读取网页或GitHub内容的Agent，新建对话，复制下面这段话。整个学习过程从线上获取资料，不要求下载教材或配置本地项目。

> 请在线读取 https://github.com/littleduckycoin-ai/DP-FDE-school/blob/main/START_HERE.md ，并继续读取其中的school-guide教学规则。每轮需要资料时读取线上当前版本，不克隆仓库、不建立本地教材副本。先用10分钟带我学习案例04：讲清行业痛点、FDE做了什么、交付了什么、效果与限制，再围绕我的判断展开讨论。回答请给出线上出处。

把“案例04”换成想学的案例；不知道选什么，就说“根据我的工作问题推荐一个案例”。只想提问也可以直接问，Agent会查对应材料再回答。

## 第一次需要做什么

1. 让Agent在线打开上面的链接，读取教学规则与案例索引。
2. 告诉它想学什么、可用时间或当前疑问。仅阅读无需学习者身份或GitHub写权限。
3. 想留下署名反馈时再说：“我的学习者标识是alice，昵称小艾；请把本次学习中我的思考和问题逐轮追加到对应案例的reflections知识文件。”将示例名称换成自己的。

具备GitHub写入连接的Agent收到授权后，会创建或更新`cases/<case-id>/reflections/<learner-id>-YYYY-MM-DD.md`，复用同一分支和PR。若当前Agent只能读，它会给出准确路径、完整Markdown和该案例目录的GitHub“Add file”入口，由你登录后提交文件或PR。上传成功应有可打开的commit或PR链接；合并进main后才算进入共享知识库。没有写入能力也可以继续学习。

## 日常直接这样说

> 继续在线读取案例04的相关材料，解释你刚才判断的依据，并给我原访谈出处。

> 看看同学对案例06有什么不同看法。我的观点是：……。请把我的反馈追加到案例06中我的reflection文件。

> 我修订刚才的观点：……。保留旧记录并追加修订。这个问题暂时仍未解决。

> 实时读取学校线上案例01、04、06的reflections知识文件，汇总开放问题、分歧与建议讨论顺序，保留作者和原文件链接。

[学校主页](https://github.com/littleduckycoin-ai/DP-FDE-school) · [案例目录](https://github.com/littleduckycoin-ai/DP-FDE-school/tree/main/cases) · [如何留下思考](https://github.com/littleduckycoin-ai/DP-FDE-school/blob/main/docs/contributing.md)

## Agent从这里继续

先在线读取[完整教学规则](https://raw.githubusercontent.com/littleduckycoin-ai/DP-FDE-school/main/.codex/skills/school-guide/SKILL.md)及[案例索引](https://raw.githubusercontent.com/littleduckycoin-ai/DP-FDE-school/main/data/case-index.json)，按相关性读取案例、讨论和已审拆解，不批量下载全库。若Raw入口无法访问，使用[GitHub文件页面](https://github.com/littleduckycoin-ai/DP-FDE-school/blob/main/.codex/skills/school-guide/SKILL.md)或[Contents API](https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/contents/.codex/skills/school-guide/SKILL.md?ref=main)。

每轮需要资料时检查线上当前版本；同一轮尽量使用同一commit的教材并给出来源。直接网页读取、GitHub连接和HTTP请求都可用于读取，响应进入会话上下文即可。若工具无法访问线上，说明具体失败并引导启用可用的读取能力，不把搜索摘要、旧记忆或本地副本说成刚刚读到的最新教材。完整路由见[在线协议](https://github.com/littleduckycoin-ai/DP-FDE-school/blob/main/docs/online-protocol.md)。

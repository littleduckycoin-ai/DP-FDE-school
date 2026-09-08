# 安装FDE AI School skill

把下面整句话发给Codex：

> 请使用 $skill-installer 安装这个skill：https://github.com/littleduckycoin-ai/DP-FDE-school/tree/main/.codex/skills/school-guide

Codex会把`school-guide`安装到个人skill目录。安装完成后，它通常会在下一轮对话可用；若技能列表暂未出现，重启Codex。

然后直接说：

> 使用 $school-guide，根据我的工作问题推荐一个FDE案例并开始学习。

也可以不点名skill，直接说“带我学习案例04”或“比较几个案例怎样发现真实问题”；Codex可根据skill描述自动选择它。

skill只安装入口和工作方法。案例、同学的reflection知识文件与正式拆解由Agent按需读取GitHub上的当前版本，不下载整套教材。

阅读公开资料不需要GitHub写权限。对话中出现适合沉淀的思考、评价、问题或修订时，Agent会在第一次公开写入前确认学习者标识、昵称和本次会话授权；之后自动追加到对应案例的`reflections/<learner-id>-YYYY-MM-DD.md`，复用同一分支和PR。若当前Codex不能写GitHub，它会说明缺少的权限或连接，并给出准确路径、完整Markdown和网页提交入口。

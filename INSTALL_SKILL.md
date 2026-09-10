# 安装FDE AI School skill

把下面整句话发给Codex：

> 请使用 $skill-installer 安装这个skill：https://github.com/littleduckycoin-ai/DP-FDE-school/tree/main/.codex/skills/school-guide

Codex会把`school-guide`安装到个人skill目录。安装完成后，它通常会在下一轮对话可用；若技能列表暂未出现，重启Codex。

然后直接说：

> 使用 $school-guide，根据我的工作问题推荐一个FDE案例并开始学习。

也可以不点名skill，直接说“带我学习案例04”或“比较几个案例怎样发现真实问题”；Codex可根据skill描述自动选择它。

Skill 只安装入口、工作方法和连接脚本。案例、同学的 reflection 知识文档与正式拆解由 Agent 按需读取当前线上资料库，不下载整套教材。学校正在接入飞书，实际切换状态以[后端入口](data/school-backend.json)为准，学员继续用同一个 Skill。

飞书启用后，首次使用时 Agent 会准备官方飞书连接工具，并给你本人授权的链接。完成授权且具备文档权限后即可学习；无需另外安装飞书 Skill。不要把密码或密钥发进对话。

对话中出现适合沉淀的思考、评价、问题或修订时，Agent 会先明确分享范围、学习者标识、昵称和本次会话授权；之后自动追加到对应案例的 reflections 知识正文。保存后应给出实际记录链接；如果缺少权限，会说明具体需要你协助什么，并保留待提交内容。

已有旧版的学员，可把同一链接发给 Codex 并说：“请更新我已安装的 school-guide，保留线上读取方式。”新会话直接说“使用 $school-guide”会触发最新规则读取；安装 Skill 不等于每个空白会话都会自行联网。[飞书使用说明](docs/feishu-learning.md)

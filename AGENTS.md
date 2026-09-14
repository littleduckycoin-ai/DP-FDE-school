# 飞书 FDE 学校维护入口

学习与会前整理使用 [.codex/skills/school-guide/SKILL.md](.codex/skills/school-guide/SKILL.md) 和随包脚本，直接从内置飞书 Agent 目录读取当前规则、案例与 reflections。仓库仅分发工具；旧案例与迁移文件是维护历史，不是当前教学来源。用户要求优先于旧路由与历史说明，不查询旧 school-backend.json 来选择教学后端。

学员不克隆教材。署名反馈只写飞书案例 reflections 知识正文，不写 Issue、评论或消息；首次会话授权后沿用。基础资料、他人历史记录与无关目录不得随普通学习改动。维护对话不生成虚构学员记录。只操作用户自己的学校区域，不扩大共享权限。

维护时运行 `python tools/validate.py`、`python -m unittest discover -s tests -v`、`node --test tests/test_feishu_school.mjs`。飞书登录成功不等于保存成功；对实际写入按回执与回读报告。不要将尚未验证的学员登录或权限称为已打通。

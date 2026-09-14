# 个人沉淀：位置、输入与可读正文

实际路径为“学校/学习者沉淀/case01/个人文档”，不是“案例资料/case01/reflections”。总目录为 https://dptechnology.feishu.cn/drive/folder/QJp1f43d1lZzcjdM7gPc4eL6nRc 。下述 case01 文件夹是原 reflections 文件夹整体迁移后的同一对象，ID 未改变。其父目录以最新 manifest 核对，不能把总目录 token 当成 `--parent-token` 写个人文档。

具体案例的 `reflections_parent` 从当前飞书 Agent 目录读取。例如案例 01 的稳定标识是 `case-01-manufacturing-training`，其 reflections 为 https://dptechnology.feishu.cn/drive/folder/BtImfzZOIlMxEmdYWvKcCKE3nKg 。该链接仅作位置示例；每次保存仍核对当前目录，不把其他案例都写到这里。

每人每例每天一份 Docx，示例标题：`school-reflection | case-01-manufacturing-training | alice | 2026-09-14`。已有文档追加，没有才创建；不要给每轮新建文件夹，也不要把所有人写进同一篇文档。

以下是输入格式示例，不代表任何人真的授权或说过这些话。实际值由当前会话生成，日期按学校时区，ID 在重试中不变。不得把示例直接上传。

```json
{
  "learner": {"learner_id": "alice", "display_name": "Alice"},
  "consent": {"granted": true, "scope": "session", "session_id": "study-20260914-alice", "granted_at": "2026-09-14T09:00:00+08:00"},
  "study_date": "2026-09-14",
  "interaction": {
    "interaction_id": "turn-20260914-alice-001",
    "created_at": "2026-09-14T09:10:00+08:00",
    "summary": "如何判断知识整理是否真正改善培训",
    "contributions": [{
      "entry_id": "case-01-manufacturing-training:alice:turn-20260914-alice-001:01",
      "kind": "question",
      "text": "除了知识库里有多少条经验，还应该看新人能不能独立处理异常吧？",
      "capture": "verbatim",
      "confirmation": "captured",
      "source_refs": [],
      "relates_to": []
    }],
    "agent_feedback": ["可以把资料覆盖率与独立处理任务的表现分开讨论。"],
    "next_steps": []
  }
}
```

以上是不含文档 ID 的真实记录输入格式。首次未知当天文档时，Agent 安全传入标准输入，执行 `node scripts/feishu_school.mjs create-record --case 01 --input -`，保留回执中的 `document_id`。然后将该字段加入原 JSON 顶层，执行 `node scripts/feishu_school.mjs append --case 01 --input -`。已有文档 ID 时直接追加。创建结果不明先停下核查；重查原创建请求加 `retry:true`，不重复创建。重试追加保留同一文档 ID、轮次 ID 和原始内容。不要把用户文本拼接成 shell 命令。学员不需要编辑 JSON 或手动运行命令。

正文由脚本生成：作者和日期、轮次时间与主题、标注类型的用户表达、来源、单列的 Agent 反馈与待验证建议。脚本同时写原生代码块：唯一 `school-record-meta-v1` 元数据和每轮 `school-interaction-v1`，供后续 Agent 精确读取、去重和汇总；不要自行删掉这些标记。

首次创建绑定本人的实际 OAuth 操作者，已有学习标识不能靠昵称认领。新建和新轮次写入会读取各案例的身份元数据核对绑定；他人表达格式错误不阻断已核实的本人身份，身份元数据不明仍停止。已知文档的相同轮次重试只回读核对，不依赖无关案例。

手动辅助时：给出目标 reflections 链接、标准标题、完整可读正文和所需结构化代码块，由学员创建或追加到知识文档。无法核实 actor 或完整格式时明确为待整理，不伪造绑定，不承诺脚本已可识别。手动粘贴之后需要回读确认，不能只凭生成正文报告成功。

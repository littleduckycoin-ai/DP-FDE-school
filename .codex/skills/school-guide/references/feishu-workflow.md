# 飞书后端

只在公共路由已正式选择飞书后用于常规学习。迁移检查可按维护者明确指定的飞书入口读取，但不能自行把 GitHub 的在用后端切走或双写反馈。

学校提供 `scripts/feishu_school.mjs` 处理重复的路由、读取和记录操作。脚本属于本 skill；学员无需再安装另一套飞书 skill。首次使用先读取[连接与首次授权](feishu-connection.md)，已有可用连接则直接继续。

## 在线入口和全文读取

通过脚本的 bootstrap 能力读取学校已配置的入口，获取规则、案例索引与本次连接状态。规则来自飞书已配置的学校规则文档，参考文件与脚本是执行方法，案例和学习记录仍在线读取。

学校脚本接口如下，由 Agent 执行；参数中 manifest 使用公共路由返回的真实 URL/token，不让学员查找内部标识。首次运行核对脚本 `--help`，以当前发布实现为准。

| 任务 | 脚本子命令 |
|---|---|
| 当前入口与规则 | `bootstrap`，可选 `--router-url`；显式维护验收可用 `--manifest <URL/token>` |
| 缺项诊断 | `doctor` |
| 案例索引 | `index --manifest <URL/token>` |
| 单例全文 | `case --case 01 --manifest <URL/token>` |
| 指定案例全部记录 | `reflections --case 01 --manifest <URL/token>`，可选 `--cutoff <含时区ISO时间>` |
| 会前数据 | `meeting --cases 01,02 --cutoff <含时区ISO时间> --manifest <URL/token>` |
| 追加本轮记录 | `append --case 01 --input - --manifest <URL/token>` |

上述飞书命令可使用 `--profile fde-school`；必须保留当前用户实际已授权的正确 profile。manifest 类型为 `feishu-school-v1`，其文档/节点映射是路由依据。脚本的 JSON 输出是数据回执，不意味着会前分析、正式发布或审批已经完成。

`append` 从标准输入接收 JSON，包含 `learner: {learner_id, display_name}`、`consent: {granted: true, scope: "session", session_id, granted_at}`、`study_date` 与完整 `interaction`。授权字段必须来自实际本次会话，不得为了让脚本通过而编造。输入使用结构化工具或安全的标准输入传递，不把用户正文拼接成可执行 shell。平台实际执行身份由 CLI 的 `auth status --verify` 核对，作为执行元数据记录，不能代替 `learner`。

学校入口至少需要区分：

| 学校资料 | 用途 |
|---|---|
| 当前规则与索引 | 当前规则、案例标识、对应飞书文档/节点、来源与分享入口 |
| 每例基础资料 | 口语化简介、完整案例、原访谈、原图与证据页码 |
| 每例 reflections | 按作者和日期保存的署名学习知识文档 |
| 每例 canon | `proposed` 或经真实审核的 `accepted` 拆解 |
| patterns | 跨案例模式与适用边界 |
| meetings | 会前资料、来源清单、Agent 整理及已确认决定 |

目录和案例入口使用稳定 `case_id` 路由，不能以标题模糊匹配后直接写入。读取正文需要覆盖全部文档块和分页；搜索结果只能用于定位。保留原文引用、图片位置和附件信息，不能将文档 raw text 未返回的图片误报为已阅读。

每个需要资料的回合检查当前线上规则和资料版本；记录获取时间、文档 ID、可获得的 revision/修改时间及内容摘要。飞书多个文档不天然共享 Git commit；只有工具已验证一致性时才声称同一快照，否则说明本次实际读取窗口。失败时说明读取范围，不以本地教材或 GitHub 旧副本冒充当前飞书材料。

## 自动追加学习知识

遵守[共同记录契约](record-contract.md)。学员已授权时，Agent 对有价值的表达执行以下操作：

1. 从索引核对案例及其 reflections 父节点；分别确认用户自述和本人 OAuth 实际写入身份。新建记录可作首次绑定；更新已有文档要核对已存 `actor` 的应用与用户标识，不把外部身份映射表作为新学员前置。旧迁移文档缺 actor 时，不以昵称认领，按记录契约处理。
2. 查找同一 `case_id + learner_id + study_date` 的知识文档，读取已有 interactions；若不存在，在该案例 reflections 下创建文档。标准标题为 `school-reflection | <case_id> | <learner_id> | <YYYY-MM-DD>`，展示名保存在正文元数据中；匹配同时核对结构化稳定标识。手动辅助提交也采用相同标题和记录标记，不能只创建一份无归档标识的普通文档。
3. 使用脚本提供的追加能力提交新 interaction。重试前查 `interaction_id`，保留旧条目；修订和状态变化作为新条目追加。
4. 以 API 回执和回读结果核实保存；返回实际文档/条目链接。若创建成功但追加失败，要报告已有空文档和本轮待提交内容，不能称整轮已保存。

评论、私聊和群聊可以承载讨论，但它们不是 reflection 正文知识文档的替代品。跨案例内容分别进入对应案例；不要把全部人的学习长期混写进一个公共大文档。学员引用同伴内容时写自己的 reflection，并回链对方条目。

自动追加发生在正在运行且已授权的 Agent 会话中。只有经过真实配置与验收的后台服务才能宣称会话外持续运行；安装本 skill 本身不等于部署飞书机器人或后台监听。

如果因 OAuth、文档权限、网络或接口限制不能写，Agent 先处理能够代办的连接步骤，剩余部分请用户完成相应授权。仍失败时给完整待提交正文、稳定 interaction ID 和目标文档/父节点链接，保持“待提交”；manifest 本身无权读取时提供已知入口与 `case_id`、标记“目标待解析”。不回退 GitHub、Issue 或飞书评论。不要让用户为每轮学习手工运行命令。

## 会前汇总与正式知识

按指定案例列出并读完全部 reflection 文档及分页。按 interaction 时间应用截止范围，保留作者、条目 ID、源文档链接和可用版本信息；读取部分内容时显示缺失范围。若另有待审核草稿，只在实际可读时纳入并标注其状态。

相近问题可按主题聚类，保留不同解释与少数观点；统计独立学习者，不能把多次追问视作多票。没有名单不推断谁缺交；没有记录不等于缺席。未解决清单使用 `unresolved_questions`，包含 open、deferred 和 discussed；“已讨论”不等于已解决。只有提问者的明确状态事件能将问题标为 answered。

先在对话中呈现整理，用户已要求保存或发布且有权限时继续写入会议节点，不重复询问同一发布授权。brief 与来源 manifest、Agent synthesis、实际 decisions 分开；不编造同意、负责人和期限，刷新生成材料须保留已确认决定。脚本若只返回汇总输入而未发布文档，应继续通过可用写入工具发布或标“未发布”，不能把读取回执当作发布回执。

普通 reflection 是可引用的个人学习知识。canon 和 patterns 草稿从 `proposed` 开始，只有真实维护者审核记录后才可标 `accepted`；模式至少有两个案例、适用条件和反例。飞书文档 ACL、审批人与发布动作须实际配置并核验，不能把标题、状态文字或 skill 约定当成平台已强制保护。若尚无维护者审批操作能力，保留提案并返回审阅链接。

## 原 PDF 页码

优先使用飞书 `case` 返回的 `source_page_links: [{pdf_page, url}]`，按对应物理页选择已验收的链接。其目标可以是从原 PDF 保真提取的单页 PDF；打开即可看到那一页，无需添加未经验证的页码参数。GitHub 的 `pdf_page_url_template` 只在该后端索引提供时使用，不要求飞书 manifest 也具备这个字段。

若飞书尚未提供可用单页链接，完整附件预览是否支持固定页码跳转须实测；尚未验收时沿用已正常工作的原 PDF 阅读链接，不能机械替换为附件 URL 后宣称可定位。

页码优先取章节 `source_pdf_pages` / `based_on_pdf_pages`、图片 `pdf_page`，必要时从 `provenance.original_page_text` 定位；使用物理页而非印刷页。学员观点链接 reflection 文档或条目，编辑解释可补基础案例文档链接。若页面深链接不可用，明确给 PDF 原文链接和物理页码，不伪造跳转参数。

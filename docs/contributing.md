# 把思考留在线上

学习过程中可直接说：“我是alice，昵称小艾；请把本次会话中我的思考、评价和问题逐轮追加到对应案例的reflections知识文件。”替换为自己的标识和昵称。

## 反馈如何发布

具备GitHub写入连接的Agent在一次明确授权后，使用`cases/<case-id>/reflections/<learner-id>-YYYY-MM-DD.md`。同一学员、同一案例、同一天复用一个文件，每轮追加一个interaction；旧观点保留，更正另起修订条目，同伴反馈写在自己的文件并引用对方。

Agent会从最新main创建或复用你的reflection分支，更新文件并打开PR。普通reflection文件不需要CODEOWNER审核，但要通过`school-checks`。有合并权限时，校验通过后可直接合并；否则PR会保留为“已上传、待合并”。

当前Agent只能读时，先正常学习。它应给出准确目标路径、符合[记录格式](reflection-format.md)的完整Markdown和该案例`reflections/`目录的GitHub“Add file”入口，由你在网页提交文件或PR；不得改用Issue。

GitHub返回commit或PR链接后才叫“已上传”，合并进main后才叫“已进入共享知识库”。没有成功回执时只能写“待提交”。不要把账号密码或令牌贴进对话。仓库公开，发布前使用适合公开的内容。

## 学校怎样沉淀教材

学员表达一开始就保存在对应`reflections/`，作为署名学习知识；它仍是个人表达，不自动成为事实或共识。

案例canon、跨案例patterns仍先标proposed，经CODEOWNER审核的PR合并后才成为正式拆解。GitHub连接或文件API可以直接在线创建文件和PR，学员无需学习Git命令。没有真实审核不得预填accepted、审核人或共识。

来源勘误需要说明证据，并同步维护Markdown、JSON、索引和受保护的基础摘要。详见[治理规则](governance.md)。

# 在线读取与写入协议｜供Agent和维护者

学员从[START_HERE](https://github.com/littleduckycoin-ai/DP-FDE-school/blob/main/START_HERE.md)开始。教学材料和学习记录都在线读取；响应只进入当前会话上下文，不建立持久教材副本。

## 固定一轮资料版本

1. GET `https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/commits/main`取得当前commit SHA。
2. 用同一SHA请求`GET https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/contents/<path>?ref=<SHA>`。文件响应的Base64正文只在内存中解码；目录响应必须读取完整条目列表。
3. 路径从[在线服务索引](https://raw.githubusercontent.com/littleduckycoin-ai/DP-FDE-school/main/data/online-school.json)和[案例索引](https://raw.githubusercontent.com/littleduckycoin-ai/DP-FDE-school/main/data/case-index.json)取得。按需读单个案例的Markdown、完整访谈JSON、图片、reflection和已审拆解，不递归下载全库。
4. JSON、Markdown和reflection文件的内部引用使用`https://github.com/littleduckycoin-ai/DP-FDE-school/blob/<SHA>/<path>`。案例事实给学员展示时使用在线索引中的`pdf_page_url_template`，替换为准确的PDF物理页。下一轮需要资料时重新查询main SHA。

GitHub文件页和Raw URL是备用入口。网页只返回登录框、错误或截断内容时不算读到全文；切换API或直接文件读取。遇到403、404、限流或超时时说明实际读取范围，不改读本机旧材料来冒充线上当前版。

## 生成可点击的原PDF页引用

原PDF由GitHub Pages以`application/pdf`提供，页面入口为：

`https://littleduckycoin-ai.github.io/DP-FDE-school/sources/original-interviews.pdf#page=<物理页>`

Agent先用结构化案例定位证据，再把链接呈现为“原访谈PDF第N页”。`#page=N`中的N必须是`provenance.pdf_physical_pages`口径。具体论断优先取相应章节的`source_pdf_pages`或`based_on_pdf_pages`；需要更精确时，在`provenance.original_page_text`逐页定位原句。一个链接只声称它实际支持的内容。

JSON链接是机器核对入口，不能替代给学员看的PDF证据。教材编辑分析可以补充Markdown链接；学员表达使用reflection链接。浏览器不支持页码跳转时，仍会打开完整原PDF，并以链接文字中的物理页码供手动定位。

## 读取reflection知识文件

对每个指定案例：

1. 从案例索引取得`reflections_dir`，按固定main SHA读取该目录。
2. 读取目录内所有`.md`，排除`README.md`；若API提示目录可能截断，改用Git Trees API或明确资料不完整。
3. 校验路径与文件中的`case_id`、`learner_id`和`study_date`一致，解析唯一的`school-record-v1`。
4. 按interaction的`created_at`应用截止时间，保留作者、条目ID、文件路径和带anchor的在线链接。

会前需要覆盖刚提交但未合并的内容时，再列出开放PR，筛选标题以`reflection:`开头且只修改`cases/*/reflections/*.md`的PR；按各PR head SHA读取文件并标“待合并”。不要把别的PR或普通Issue当作学习记录。

## 在线创建或追加reflection

取得本次会话的公开记录授权和学员自述身份后：

1. 目标路径为`cases/<case-id>/reflections/<learner-id>-YYYY-MM-DD.md`。
2. 查找同一路径已有的开放reflection PR。可写时复用其head分支；否则从最新main创建`reflection/<learner-id>/<case-id>/<date>`。
3. 读取分支上的当前文件；不存在则按[记录格式](reflection-format.md)创建。重试前检查`interaction_id`，每轮只追加，不删除或重写旧内容。
4. 使用Contents API `PUT /repos/littleduckycoin-ai/DP-FDE-school/contents/<path>`提交Base64正文、commit message、分支名；更新文件时带当前blob SHA。
5. 新分支创建PR，已有PR继续更新。CI通过且连接账户有合并权限时合并；否则返回待合并PR。

更新冲突时重新读取目标分支，保留他人或其他会话新增的interaction后再提交。GitHub返回commit或PR链接后才能说“已上传”，合并进main后才能说“已进入共享知识库”。

学习反馈不创建Issue。写入连接、登录或权限不足时，Agent说明缺少哪一步，并给出准确路径、完整Markdown和`https://github.com/littleduckycoin-ai/DP-FDE-school/new/main/cases/<case-id>/reflections`形式的网页入口。不得索要聊天中的访问令牌，也不得冒用维护者身份声称学员本人发布。

## 正式知识与维护

reflection是署名学习知识，内容不自动成为事实或共识。canon、patterns和会议产物通过GitHub文件与PR维护；更新前读最新blob SHA，遇到冲突重新读取。

`tools/online_school.py`提供仅在内存中读取线上教材和main reflection文件的参考实现；`tools/school.py`定义reflection渲染、校验和维护快照。两者都不是学员的安装步骤。

# 在线读取与写入协议｜供Agent和维护者

学员入口是[START_HERE](https://github.com/littleduckycoin-ai/DP-FDE-school/blob/main/START_HERE.md)。所有教学读取来自线上；资料响应只进入当前会话上下文，不建立持久教材副本。

## 读取一轮所需材料

1. 有GitHub读取工具时使用它直接读文件。能发HTTP时，GET `https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/commits/main`取得当前commit SHA。
2. 用同一SHA请求`GET https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/contents/<path>?ref=<SHA>`。响应的`content`为Base64时在内存中解码；支持请求头时可用`Accept: application/vnd.github.raw+json`直接取正文。
3. 路径从[data/online-school.json](https://raw.githubusercontent.com/littleduckycoin-ai/DP-FDE-school/main/data/online-school.json)和[data/case-index.json](https://raw.githubusercontent.com/littleduckycoin-ai/DP-FDE-school/main/data/case-index.json)取得。索引有每例的绝对在线URL；按需读取该例Markdown、完整访谈JSON、图片和已审拆解，不递归下载全库。
4. 回答引用`https://github.com/littleduckycoin-ai/DP-FDE-school/blob/<SHA>/<path>`，并标原PDF物理页。下一轮需要资料时重新查询当前SHA。能确认版本未变时可沿用同一会话已读段落，不重复下载无变化正文。

GitHub网页和Raw URL是另外两种在线入口。若网页只返回登录框或截断内容，切换API或直接文件读取。能设置缓存头时请求`Cache-Control: no-cache`；工具不支持版本校验时记录实际获取时间，不将缓存内容保证为即时最新版。403、404、限流、超时或工具拒绝访问都需要明确说明，不能改读本机旧材料来冒充实时读取。

以上API公开资源可以无身份验证读取；文件API支持目录、原文及指定版本。[GitHub Contents API](https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28)。

## 读取线上学习记录

实时通道为带`school-reflection`标签的Issues。使用`GET https://api.github.com/repos/littleduckycoin-ai/DP-FDE-school/issues?state=all&labels=school-reflection&per_page=100&page=1`，处理全部分页并排除含`pull_request`的条目。也识别标题以`[学习记录]`开头且案例和学习者信息完整的主题，避免漏掉未成功贴标签的贡献。

从主题结构化内容或表单字段识别案例与学习者。再读取相关`/issues/<number>/comments?per_page=100&page=1`的全部分页，保留GitHub作者、创建时间、修改时间和`html_url`。只能读到部分页面时明确汇总范围。

也可读取线上各例`reflections/`中的归档记录。原始帖子与归档的同一条表达按原记录URL或稳定interaction_id去重。Issue的open/closed是主题管理状态，不等于其中每个问题是否解决。

## 在线追加一轮反馈

得到用户对本次会话的公开记录授权，并具有对应GitHub写入连接后：在线查找本案例、本学习者、本发布者的主题；不存在则POST `/issues`创建。随后每轮POST `/issues/<number>/comments`追加正文。使用[记录格式](reflection-format.md)，重试前按interaction_id检查是否已存在。不要更新旧正文来抹掉观点变化。

API返回的ID、作者、时间及URL用于确认提交；没有成功回执就标“待提交”。不得在用户不知情时使用学校维护者身份冒充学员。没有写入连接时给出[表单入口](https://github.com/littleduckycoin-ai/DP-FDE-school/issues/new?template=learning-note.yml)及可粘贴文字；学员仍可继续学习。评论读写能力与权限见[GitHub Issue Comments API](https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28)。

## 教材维护和归档

学习记录发布后即可在线阅读。定期归档时保留原Issue/评论链接和稳定ID。正式canon、patterns及会议产物可通过GitHub文件API和PR在线维护；更新文件先读取最新blob SHA，遇冲突重新读取并保留他人新增内容，不强行覆盖。

原有`tools/school.py`是维护与历史归档工具，旧`brief`只覆盖文件归档，不能代表全部实时反馈。新增`tools/online_school.py`提供在内存中读取线上教材与完整Issue线程的参考实现，供集成或维护验证；学员不需要安装或运行它。在线反馈尚未归档时，直接从Issues读取，不要求先转成文件。

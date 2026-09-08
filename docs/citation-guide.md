# 原访谈PDF引用

案例JSON帮助Agent检索和核对，但给学习者展示的事实证据应直接打开原PDF对应物理页。

链接模板：

`https://littleduckycoin-ai.github.io/DP-FDE-school/sources/original-interviews.pdf#page={pdf_page}`

例如：[原访谈PDF第8页](https://littleduckycoin-ai.github.io/DP-FDE-school/sources/original-interviews.pdf#page=8)。

## Agent怎样选页

1. 从案例索引定位案例，再读取单例JSON。
2. 优先使用具体章节中的`source_pdf_pages`或`based_on_pdf_pages`。
3. 需要引用一句具体陈述时，在`provenance.original_page_text`逐页定位，再生成该物理页链接。
4. 图片证据使用图片记录的`pdf_page`。
5. 不使用`printed_pages`生成链接；书内印刷页与PDF物理页通常相差一页。

一项结论跨多个关键页时分别链接各页。教材新增的行业解释或迁移练习不是原访谈事实，应明确标为编辑分析或练习；可以补充案例Markdown链接。学员观点链接其reflection文件。

原PDF仍完整保存在[GitHub仓库](../sources/original-interviews.pdf)，GitHub Pages只提供便于浏览器按页打开的同一文件。CI会校验原PDF SHA-256，避免引用页面在未说明的情况下发生变化。

# 审核与保护

学校分为线上即时讨论与经过审核的教材沉淀。每位学员可以留下署名思考；共享教材的修改由维护者审核。

## 即时讨论

学习记录Issue及评论承载每轮思考、评价和问题，发布后即可在线阅读和会前汇总。实际发布账户、时间和URL来自GitHub，学习者标识与昵称由本人自述。修订通过追加表达，不覆盖旧观点。

线上讨论可以归档到案例`reflections/`，保留原链接与稳定ID，汇总时去重。公共仓库不提供逐条私密访问；用户要求私密的内容不发布。

## 教材审核

[CODEOWNERS](../.github/CODEOWNERS)指定`@littleduckycoin-ai`审核base、canon、patterns、原始资料、工具和规则。主分支要求PR、school-checks通过及受保护文件的CODEOWNER审核，禁止强制推送和删除主分支；管理员保留明确授权维护所需的GitHub例外权限。

CODEOWNERS与分支保护需要共同使用，单独放一个文件不会让教材只读。[GitHub代码所有者说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)。

canon与patterns从proposed开始；实际审核合并后，再引用真实review_pr标记accepted。基础事实须回到原访谈，学员观点须回到线上帖子或署名记录，未形成共识的地方保留分歧。

CI检查24个案例、144段原访谈、基础文件摘要、链接、记录格式与已有文件历史。它不能认证学员真实身份，也不代表所有线上发言都经过内容审核。基础来源勘误必须有明确维护理由，并在受审改动中解释摘要更新。

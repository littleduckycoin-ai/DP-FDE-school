# 审核与保护

学校分为署名学习知识与经过审核的正式知识。每位学员可以把思考留在案例reflections；正式教材的修改由维护者审核。

## 署名学习知识

每轮思考、评价和问题直接追加到`cases/<case-id>/reflections/<learner-id>-YYYY-MM-DD.md`。实际提交账户、commit与PR来自GitHub，学习者标识和昵称由本人自述。修订通过新interaction追加，不覆盖旧观点。

普通reflection文件不在CODEOWNERS保护范围内，可通过PR和CI进入main；历史记录只能追加。它们是可引用的学习知识，但不代表内容已获维护者认可。公共仓库不提供逐条私密访问；用户要求私密的内容不发布。

## 教材审核

[CODEOWNERS](../.github/CODEOWNERS)指定`@littleduckycoin-ai`审核base、canon、patterns、原始资料、工具和规则。主分支要求PR、school-checks通过及受保护文件的CODEOWNER审核，禁止强制推送和删除主分支；管理员保留明确授权维护所需的GitHub例外权限。

CODEOWNERS与分支保护需要共同使用，单独放一个文件不会让教材只读。[GitHub代码所有者说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)。

canon与patterns从proposed开始；实际审核合并后，再引用真实review_pr标记accepted。基础事实须回到原访谈，学员观点须回到署名reflection文件，未形成共识的地方保留分歧。

CI检查24个案例、144段原访谈、基础文件摘要、链接、reflection格式与已有文件历史。它不能认证学员真实身份，也不代表reflection内容经过内容审核。基础来源勘误必须有明确维护理由，并在受审改动中解释摘要更新。

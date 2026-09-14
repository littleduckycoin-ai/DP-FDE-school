# 首次连接飞书：由 Agent 操作，学员完成授权

只需这一个学校 Skill。工具可安装在本机，教材与个人沉淀保持在线。下面命令均由 Agent 执行，路径相对于 Skill。不要要求学员复制一套命令。

## 1. 检查工具与已有连接

检查 Node.js 22+ 和 `lark-cli --version`。缺 CLI 时安装已适配的官方版本 `npm install --global @larksuite/cli@1.0.94`（Windows 用 npm.cmd），然后核对版本与 `config init --help`、`auth login --help`。不要安装另一套 skills，不改无关全局 Agent 配置。

先尝试 `lark-cli --profile fde-school auth status --json --verify`。已有可用学校 profile 直接复用；学员明确已有另一个本人授权的可用 profile 时，可以使用那个 profile，并在所有脚本命令中保持一致。只读所需状态，不展示凭据或复制完整认证文件。

## 2. 首次应用配置

CLI 的应用配置与个人 OAuth 是两步。应用 ID 本身不足以完成当前 CLI 的现有应用配置；学校没有在安装包内分发通用应用密钥。不能声称每个新学员都已具备统一应用登录入口。

- 已有本人可用配置：复用，不新建应用。
- 管理员已安全配置学校应用到本机：直接进入个人 OAuth。不要在聊天中收集或发送 app secret，也不要复制其他人的 profile/token。
- 没有可用配置：解释“首次需要建立飞书应用连接；你完成网页配置与本人授权，工具步骤由我处理”。执行 `lark-cli config init --new --name fde-school --brand feishu`。这是创建学员自己的应用连接，不是加入一个已经部署好的统一应用；用户若要求只能使用组织现有应用，则等待管理员提供安全配置，不另建。

配置命令可能等待浏览器操作。后台运行并读取真实验证链接后发给学员，继续恢复同一进程，不重复启动。不要输出配置中的密钥。组织禁止创建应用或要求审核时，说明当前报错与所需管理员动作，不尝试绕过；仍可让学员通过学校首页阅读。

## 3. 本人 OAuth

应用配置完成后执行：

```text
lark-cli --profile fde-school auth login --domain docs --domain drive --no-wait --json
```

当前学校是云盘文件夹和 Docx，只请求文档与云盘领域，不请求通讯录、消息、日历或全部领域。将返回的真实验证 URL 给学员，让其用自己的账号授权。完成后恢复原流程：

```text
lark-cli --profile fde-school auth login --device-code <本次返回的device_code>
lark-cli --profile fde-school auth status --json --verify
```

device_code 只用于本次认证，不写学校文档或公开文件。链接过期后才重新发起。所有学校 API 使用 `--as user`，不得借用维护者身份或改用机器人身份绕过。

核对 `identities.user.available`、`identities.user.verified`，以及 appId/openId；仅本地 token 未到期不能证明远端验证通过。已有可用登录不每次重登。

## 4. 验证学校读取与目录能力

```text
node scripts/feishu_school.mjs bootstrap --profile fde-school
node scripts/feishu_school.mjs case --case 01 --profile fde-school
node scripts/feishu_school.mjs reflections --case 01 --profile fde-school
```

依次验证学校目录和规则、案例全文、reflections 列表。只访问固定学校入口及其映射资源，不枚举整个云盘。doctor 只检查连接身份，不证明学校读写已通过。

- 登录失败：处理本人 OAuth。
- `missing_scope`：应用接口权限或用户授权尚未覆盖该操作；不能仅凭此断言管理员没批准。按实际返回检查应用配置、发布、审批和重新授权。
- 缺目录能力且返回要求 `space:document:retrieve`：可单独发起 `auth login --scope space:document:retrieve --no-wait --json` 并恢复同一流程；若应用未获批该能力，个人重复登录不能代替审批。
- 文档访问拒绝：请所有者检查学员账号对学校具体资源的共享权限。不要自行修改分享范围。
- 可读但不能创建/追加：分别核对文档写入接口授权与目标 reflections 的创建/编辑权限。

目录权限不等于正文或编辑权限；应用获权也不自动分享文件。学校工具只操作学校范围，不能把 Skill 规则声称为平台资源隔离。

## 5. 首次真实沉淀

读取成功即可教学。等学员实际表达、有署名和会话授权后，按记录契约执行 append 并回读，成功才说“已保存”。不要为验证登录创建虚构学员记录或空测试文档。

无法保存时给完整待提交正文与准确目标飞书链接，请学员协助授权或按示例粘贴到目标知识文档。没有 shell、网络或可用飞书工具的客户端无法仅靠安装 Skill 完成自动写入，应如实说明。工具可代办的步骤不转交学员。

参考官方 CLI：https://github.com/larksuite/cli/tree/v1.0.94 。该链接仅为工具文档，不是学校资料来源。

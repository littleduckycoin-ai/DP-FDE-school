# 首次连接：只用用户本人

所有学校资源读写显式使用 **`--as user`**，不使用机器人身份，不自动切换账号。复用用户当前 CLI 连接；用户明确指定 profile 时，所有命令保持同一个 `--profile <名称>`。不新建学校专用 profile、不修改默认身份或 strict-mode 策略，不搭建额外登录服务。

## 1. 检查工具与本人登录

检查 Node.js 22+ 和 `lark-cli --version`。缺 CLI 时由 Agent 安装已适配版本（Windows 用 `npm.cmd`）：

```bash
npm install --global @larksuite/cli@1.0.94
lark-cli auth status --json --verify
```

已有 CLI 不擅自降级；首次操作先核对相应 `--help`。本人登录有效就直接读取，不要求重新注册。核对 `identities.user.available`、`identities.user.verified` 和 appId/openId，不展示凭据或从登录账户猜学员署名。

若 CLI 明确提示没有应用配置，说明它仍需应用才能进行 OAuth；`--as user` 不能替代该配置。先复用用户明确认可的现有配置，确实没有时才征得同意并按 `config init --help` 引导官方一次性注册。不要把新建应用当所有学员的前置步骤，不索取聊天中的密钥，不绕过组织审批。注册若等待网页确认，保留原进程，不反复发起。

## 2. 未登录时，一次申请所需权限

```bash
lark-cli auth login --domain docs --domain drive --scope space:document:retrieve --no-wait --json
```

仅申请文档、云盘和目录所需范围，不使用 `--domain all` 或 `--recommend`。原样展示本次返回的真实授权 URL，并生成、展示二维码：

```bash
lark-cli auth qrcode '<本次真实URL>' --output authorization.png
```

二维码放临时目录。发链接后结束本轮，请用户完成网页操作后回复；收到确认后由 Agent 恢复本次授权：

```bash
lark-cli auth login --device-code <本次device_code>
lark-cli auth status --json --verify
```

注册链接也按相同方式展示真实 URL 和二维码。链接过期才重新申请，device_code 不写仓库或学校文档。`auth login` 本身就是用户授权流程，不给它编造 `--as user` 或 `--user` 参数。

## 3. 实际读取验收

从已安装的 Skill 目录执行；脚本内部所有资源操作均带 `--as user`：

```bash
node scripts/feishu_school.mjs bootstrap
node scripts/feishu_school.mjs case --case 01
node scripts/feishu_school.mjs reflections --case 01
```

分别核实当前目录与规则、案例正文、reflections 列表。补充读取同样显式使用本人身份：

```bash
lark-cli docs +fetch --as user --doc https://dptechnology.feishu.cn/docx/JlKadJc4OoYa4cxz7mDcIf3WnO2
```

登录成功不等于学校可读，可读不等于可写。缺权限时依据真实报错处理：`auth scopes --json` 查看应用能力，`auth check --scope <缺项> --json` 核对用户授权；应用未开通需配置/审批，用户漏授权才增量 OAuth，文件拒绝访问需所有者共享。不要为修复权限而换成 bot、扩大共享范围或读取整个云盘。

读取通过即可教学。取得真实学员表达、署名和会话授权后，才按[记录契约](record-contract.md)保存并回读；不用虚构记录测试写权限。失败则交付待提交内容和目标入口，继续教学。安装、登录、读取和保存分别报告，没完成的步骤不能称已通过。

命令依据：[官方 CLI v1.0.94](https://github.com/larksuite/cli/tree/v1.0.94) 与当前 `--help`。

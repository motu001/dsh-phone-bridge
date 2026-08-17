# DSH 统一通道集成说明（Telegram + QQ → 一个持久 agent）

把 `motu001/dsh-phone-bridge`（Python: Telegram/媒体）+ 官方
`@tencent-connect/dsh-qqbot`（QQ）统一到 **同一个 DSH agent 运行时**：
两个通道共享模型、工具、持久会话与工作目录，不再是互相独立的隔离进程。

## 架构

```
你的 Telegram        你的 QQ
   │                    │
   ▼                    ▼
telegram_bridge.py  ──►  (官方 @tencent-connect/dsh-qqbot 插件)
   │ ① POST                 │ ③ ctx.agents
   ▼                        ▼
POST /api/agent/message ──►  同一个 DSH agent 运行时（同一进程）
                                   │
                                   └─ 模型 / 工具 / JSONL 持久化
```

- **Telegram**：`telegram_bridge.py` 用 `run_unified_task` 把消息 `POST`
  到 `/api/agent/message`，按 `peer = tg:<user_id>` 分配一个持久 agent。
  媒体收发、`/send` 文件回传、`notify.py` 推送能力保留。
- **QQ**：官方插件在同一个 DSH profile/进程中驱动同一个 `agents` 运行时。

## 一、改动清单

| 文件 | 作用 |
|---|---|
| `bridge_common.py` | 新增 `run_unified_task()`：HTTP 打统一 agent，关闭系统代理直连本地 |
| `telegram_bridge.py` | 消息处理改走 `run_unified_task`（保留媒体），peer=`tg:<id>` |
| `config.json` / `config.example.json` | 新增 `unified` 段（`enabled`、`endpoint`） |
| `agent_bridge_plugin.js` | 可复用的 DSH HTTP 端点插件（ESM Cordis，供 profile 加载） |
| `~/.dsh/profiles/web/cordis.patch.yml` | web profile patch：挂载 QQ 插件（默认 disabled + 说明） |

## 二、当前进程里已验证

- `POST /api/agent/message` 返回 `{ ok, peer, reply, reason }`。
- 按 peer 持久会话：同 peer 两条消息能记住上下文（跨轮次）。
- Python 侧经 `run_unified_task` 端到端跑到真实 agent 并拿到回复。

## 三、让 QQ 真正启用（需要你操作）

官方 QQ 插件首次需要腾讯 QQ 机器人凭据（AppID/AppSecret）。
你要做一个交互步骤：终端扫码绑定 OR 直接设环境变量。

1. 设置环境变量：
   ```
   set QQBOT_APPID=你的AppID
   set QQBOT_SECRET=你的AppSecret
   set DEEPSEEK_API_KEY=你的Key
   ```
2. 打开 `C:\Users\Administrator\.dsh\profiles\web\cordis.patch.yml`，
   把 `im-qqbot` 那一行的 `disabled: true` 去掉 / 改 `false`。
3. 重启该 profile（`dsh --profile web`）。首次它会打印二维码，手机 QQ 扫
   码绑定后把凭据写回 patch；之后每次自动连接。

> 如果不想重启 Web，也可以另起一个专门的 `bridge` profile：
> ```
> dsh plugin --profile bridge add @tencent-connect/dsh-qqbot
> dsh --profile bridge --patch <dsh-phone-bridge>/agent_bridge_plugin.js
> ```
> 只要它里面同时有 webServer（HTTP 端点）和 QQ 插件即可。

## 四、启动 Telegram 桥

```
cd dsh-phone-bridge
:: 先在 config.json 填好 bot_token / 白名单
python telegram_bridge.py --config config.json
```

- 每发送消息 → 打到 `unified.endpoint`（默认 `http://127.0.0.1:3080/api/agent/message`）。
- 想退回旧的"每次 spawn headless"：把 `config.json` 的 `unified.enabled` 改成 `false`。

## 五、故障排查

| 症状 | 原因 / 处理 |
|---|---|
| `统一 agent 调用失败` | 确认 DSH(web profile) 已跑、插件 abr-2 已激活；检查 `unified.endpoint` |
| 连接本地却走了代理改超时 | 已通过 `trust_env=False` + `proxies=None` 修复；别把 127.0.0.1 输进系统代理 |
| QQ 不起作用 | 没有 `QQBOT_APPID/SECRET`，或 patch 里 `im-qqbot` 仍 `disabled: true` |
| 想关掉统一通道回旧逻辑 | `unified.enabled: false` |
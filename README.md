# DSH 手机桥 — 把手机接入本地 DeepSeek Harness，并支持发文件/图片/视频

> 面向 **DeepSeek/DSH agent** 的接入说明。看完这一份，你就能立刻明白它是什么、有哪些能力、怎么用。

---

## 一句话

这是一个跑在你电脑上、监听 **Telegram 和 QQ 机器人**的桥接层：用户手机给机器人发消息，它把消息喂给本地 **DeepSeek Harness（`dsh --profile headless`）** 执行任务，并把结果 —— **文本 / 图片 / 视频 / 任意文件** —— 主动推回手机。**不需要公网端口（Telegram）**。

## 你（DSH/agent）最需要知道的三件事

1. **它是"外部工具"，不是 DSH 插件**。它通过 `subprocess` 直接调 `node dsh/bin.js --profile headless "<任务>"`（已改成 node 调用，**不会弹 CMD 窗口**）。你这边只需保证 headless 能跑通。
2. **"发文件"能力是核心**：手机 → 电脑（收），电脑 → 手机（发）。发文件两条通道都已验证可用。
3. **所有可执行 / 要发送的文件放 `media_out/`**；手机收到的存 `inbox/`。

---

## 目录与职责

| 文件 | 作用 |
|---|---|
| `telegram_bridge.py` | Telegram 桥（polling）。收文本/图/视频/文件，+ `/send 文件名` 发回 |
| `qq_bridge.py`        | QQ 开放平台桥（WSS）。接收附件 + `/send 文件名` 发回 |
| `notify.py`           | **统一对外推送入口**：把文件/文本推到 QQ 或 Telegram（最常用） |
| `push_to_qq.py`       | 主动向单个 QQ openid 推文件/文本（独立脚本） |
| `bridge_common.py`    | 共享：加载配置 + 用 node 无窗口调用 dsh headless |
| `media_server.py`     | 本地静态服务 + cloudflared 隧道，给 QQ 提供公网 URL |
| `config.example.json` | 配置模板（复制为 `config.json`，填入真实密钥） |
| `generate_image.py`   | 样例：生成图片的调用示例 |

---

## 快速上手（DSH 使用视角）

### 1. 配置
```bash
cd phone_bridge
copy config.example.json config.json
# 填入：Telegram bot_token、QQ appid/secret、白名单 openid/user_id
```

### 2. 启动三个桥（无窗口，后台）
```bash
start-harness.bat
```
它会用 pythonw（无窗口）起 Telegram 桥 + QQ 桥 + media_server（cloudflared 隧道），最后开 DSH web。

### 3. 电脑侧给手机发文件（最常用入口）
```bash
python notify.py --channel all --file  视频.mp4      # 推给 QQ + Telegram
python notify.py --channel qq  --file   图.png
python notify.py --channel tg  --file   视频.mp4
python notify.py --channel qq  --message "H3 已完成"  # 推纯文本
```
`--channel`：`qq` / `tg` / `all`。

### 4. 手机侧发文件给电脑
用户在 Telegram/QQ 直接发图片/视频/文件 → 桥自动存 `inbox/` 并把本地路径作为上下文注入 DSH 任务。

### 5. 手机命令发回文件（`/send 文件名`）
放在 `media_out/` 的文件，手机发 `/send 文件名` 即发回。（Telegram 走原生上传；QQ 走 cloudflared 公网 URL。）

---

## 渠道与文件发送对比（重要，直接避免你踩坑）

| 能力 | Telegram | QQ |
|---|---|---|
| 接收图片/视频/文件 | ✅ 原生 `downloadFile` | ✅ WSS 附件下载 |
| **主动推送文件到手机** | ✅ **原生上传，无需公网** | ✅ 需 `post_c2c_file` + **公网 URL（腾讯服务器去拉）** |
| 主动推送文本 | ✅ sendMessage | ✅ POST messages |
| 文件类型 | sendPhoto/Video/Document 全部支持 | `file_type`：1图/2视频/4文件（4 未完全开放） |

**核心坑**：QQ 的 `post_*_file` 接口**只收 URL，不收二进制**（腾讯服务器去拉），所以本地文件必须先经 `media_server.py` + `cloudflared` 暴露成公网 URL。Telegram 则原生支持直接上传真实字节，不经网络暴露。

---

## 文件描述（发布版）

本目录只含**安全、可公开**的代码与文档：

- ✅ 代码 / 脚本 / 配置模板 / README / LICENSE / 启动脚本
- ❌ 已剔除：真实 `config.json`（含密钥）、`media_out/`、`inbox/`、`botpy.log`、运行产物、媒体文件、ComfyUI 提交脚本

`.gitignore` 已把密钥、产物、媒体排除，确保 `git add .` 不会带入敏感内容。

---

## 安全（必读红线）

- `config.json` 含真实密钥，**被 `.gitignore` 排除，绝不提交**。
- 白名单鉴权：只响应 `allowed_user_ids` / `allowed_usernames` / `whitelist` 内账号。
- `config.json` / 密钥文件 / 生成产物绝不进 Git、不上传 GitHub。

---

## 问题排查

| 现象 | 处理 |
|---|---|
| QQ 发文件 401 / 主动消息收不到 | 机器人是沙盒/未开通主动消息配额；在 q.qq.com 加公网出口 IP |
| cloudflared URL 经常变 | 每次启动换域名；用 `start-harness.bat` 统一管理，已先杀旧进程 |
| 发消息弹 CMD 窗口 | 已改 node 直接调用（`dsh.node`+`dsh.binjs`），不再走 `.cmd` |

---

## 参考

架构参考：`BiBoyang/dsh-im-bridge`（插件态）、WeWork Hermes agent 的 QQ 适配器、腾讯 `bot-node-sdk`。
本项目为**独立 Python 桥**形态（同 WeWork Hermes），对接官方 **QQ 机器人 API v2** 和 **Telegram Bot API**。
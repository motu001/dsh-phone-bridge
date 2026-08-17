# 📱 Control Your Computer (DeepSeek Harness) from Your Phone · Beginner Tutorial

> Use a chat app (**QQ** or **Telegram**) to remote-control the AI (DeepSeek Harness)
> on your computer — and **send images, videos, and files**. No coding, no public
> server needed. Just follow along.

---

## 🧐 What does this do? (30-second overview)

Imagine there is an "AI assistant" (DeepSeek Harness) on your computer. You are out,
with only your phone, and want it to work for you — for example:

- Chat, ask questions, have it write things or organize files;
- Better: have it **generate an image / a video** on your computer, then **deliver it straight to your phone**.

This project is a "bridge": one end connects to your phone's QQ or Telegram, the
other end connects to the AI on your computer. **Wherever you chat, the AI answers you there.**

```
Your phone (QQ or Telegram)
        │  send: "generate an image"
        ▼
    This "bridge" (this project, on your computer)
        │  hands the text to the AI
        ▼
  The AI works on the computer and sends the result back (text/image/video)
        │
        ▼
  You get the reply on your phone 📲
```

---

## ✅ Before you start, check you have these

Everything below is easy to get (about 10–15 minutes the first time):

| You need | Where to get it | Difficulty |
|---|---|---|
| A **phone** with **QQ** or **Telegram** | Install from the app store | 😀 Easy |
| A **QQ bot** or **Telegram bot** | See step 2 below | 🙂 Medium |
| **DeepSeek Harness** (the AI) | Auto-installed when you launch ✔ | 😀 Automatic |
| **Python** and basic tools on your computer | See step 1 | 🙂 Medium |

> In short: **pick one channel** — all Telegram, all QQ, or both.

---

## 🚀 Three-step quick start

### Step 1: Download the code
1. Create a folder (e.g. `D:\dsh-phone-bridge`).
2. Put all the files from this repo inside.
3. Install the dependencies in a terminal:
   ```bash
   pip install requests qq-botpy
   ```

### Step 2: Fill in your bot's "keys" (the key step)
Copy `config.example.json` to `config.json`. Then fill in the keys for the channel you
use (leave the other channel empty).

**If using Telegram:**
1. In Telegram, message **@BotFather**, run `/newbot`, choose a name — you will receive
   a long token (like `123456:ABC...`).
2. Put it into `config.json` at `"bot_token"`.
3. Add your numeric **ID** into `"allowed_user_ids": [你的ID]` (find it via @userinfobot `/start`).

**If using QQ:**
1. Register an app at the Tencent QQ bot platform (q.qq.com) to get an
   `appid` (numbers) and `appsecret` (a password-like string).
2. Fill them into `"qq": { "appid": ..., "secret": ... }`.
3. Change `"enabled": false` to `true`.

> ⚠️ This file holds your password (token/secret)! **Never upload it** (GitHub, chats).

### Step 3: One-click launch
Double-click **`start-harness.bat`** (Windows). It:
1. automatically checks Python and Node.js,
2. **automatically installs DeepSeek Harness** if missing,
3. starts the Telegram bridge + QQ bridge + media channel in the background,
4. opens the AI web UI (`http://127.0.0.1:3080`).

When you see "就绪 / ready" it worked. **Keep that window open** — closing it stops the bridges.

---

## 📱 Now try it from your phone
Open QQ or Telegram, find your bot, and send it a message, e.g.:

```
Hello, who are you?
```

If it answers, **your phone ↔ computer are connected**!

---

## 🖼️ Key feature: sending files to your phone
Put a file (image, video, mp4, etc.) into the `media_out\` folder on the computer, then
send to the bot:

```
/send filename
```

Example: you placed `myvideo.mp4` in `media_out\`, then send `/send myvideo.mp4` — the
video lands on your phone.

> 💡 No need to memorize commands for automation — use `notify.py`:
> `python notify.py --channel qq --file 我生成的图.png` automatically sends the image.

### Reverse: phone → computer
Send an image or file from your phone → it is stored in `inbox\` and the AI is asked
to process it.

---

## ❓ Stuck? Look here

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot "started" but never replies | Token not filled in / wrong | Re-check step 2 in `config.json` |
| QQ file send fails | Bot in "sandbox" mode | Switch to "official/live" on the QQ platform; whitelist the public IP |
| The old black CMD windows pop up | Using the old method | Now fixed; no more pop-ups |
| `cloudflared` errors | Network issue | Use a proxy, or use Telegram |
| Text works but image doesn't respond | Media permission disabled for the channel | Check the bot's "receive files" setting |

---

## 🧩 Advanced: unify to "the same AI" channel

By default, every message starts a separate one-shot AI task — each one forgets the
previous context. This repo also provides a **unified channel** that connects both
Telegram and QQ to **one long-lived DeepSeek Harness agent**, so both channels
**share the same conversation memory, tools, and model**. Details & setup:

> 📄 **[`INTEGRATION.md`](./INTEGRATION.md)** — unified-agent architecture,
> the list of changes, enabling QQ, and troubleshooting.

- Enable/disable: `unified.enabled` under `config.json` (`true` = unified channel,
  `false` = default one-shot task).
- Endpoint: `unified.endpoint` (default `http://127.0.0.1:3080/api/agent/message`).
- Per-account: every Telegram user (`tg:<id>`) and, once enabled, every QQ user has
  its own persistent agent session.

---

## 🔒 Never do these

1. **`config.json` holds your token / secret — never share it**, never push it to
   GitHub / drive / groups.
2. Share only `config.example.json` (the template), never your real config.
3. Don't add the bot to large public groups; use it per-user only (so strangers can't
   control your computer).
4. Never commit/share files containing secrets — this project already ignores
   `config.json`, media files, etc.

---

## 📂 What each file does (cheat sheet)

| File | Purpose |
|---|---|
| `start-harness.bat` | One-click launch (double-click it) |
| `config.json` / `config.example.json` | The bot's real / template "keys" config |
| `telegram_bridge.py` | The Telegram bridge |
| `qq_bridge.py` | The QQ bridge |
| `notify.py` | Push a file/message from the computer to the phone |
| `media_server.py` | Media channel for sending files (online) |
| `bridge_common.py` | Shared bridge logic (hands the command to the AI) |
| `media_files\` / `inbox\` | Files sent / received (created at runtime) |

---

Good luck! If you are stuck, check the table above. 🎉
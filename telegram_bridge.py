#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_bridge.py — 手机 Telegram → DSH headless 桥（polling 模式）

把手机里发给本 bot 的消息，转成 `dsh --profile headless "<消息>"` 任务执行，
并把最终回复发回 Telegram。只响应白名单内用户；不在白名单内被忽略/提示。

v2 新增：
  · 文件收发：接收图片/视频/文档（存 phone_bridge/inbox/ 并注入上下文）；
    /send 文件名 把 phone_bridge/media_out/ 下的文件发回手机
     (Telegram 原生 sendDocument/sendPhoto/sendVideo，无需 cloudflared)。
  · 任务执行经 bridge_common 用 node 直接调 dsh，不再弹 CMD 窗口。

用法：
  python telegram_bridge.py --config {path}
依赖配置：phone_bridge/config.json（由 config.example.json 复制后填 token/白名单）
"""
import argparse
import json
import os
import re
import sys
import time

import requests

<<<<<<< HEAD
from bridge_common import load_config, run_dsh_task
=======
from bridge_common import load_config, run_dsh_task, run_unified_task
>>>>>>> 818b011 (Add unified-agent bridge: Telegram + QQ share one persistent DSH agent)

API = "https://api.telegram.org/bot{token}"

HERE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(HERE, "inbox")
MEDIA_OUT = os.path.join(HERE, "media_out")


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def tg_request(cfg, method, files=None, **params):
    url = API.format(token=cfg["telegram"]["bot_token"]) + "/" + method
    r = requests.post(url, json=params, timeout=120)
    r.raise_for_status()
    return r.json()


def tg_download(cfg, file_id, prefix="tg"):
    """通过 Telegram getFile + downloadUrl 下载 attachment，存 inbox/，返回 (path, meta)。"""
    try:
        j = tg_request(cfg, "getFile", file_id=file_id)
        if not j.get("ok"):
            return None, None
        fp = j["result"]["file_path"]
        fname = os.path.basename(fp) or ("media_%d.bin" % int(time.time()))
        safe = re.sub(r"[^\w.\-]+", "_", fname) or "file.bin"
        os.makedirs(INBOX, exist_ok=True)
        local = os.path.join(INBOX, "%s_%s" % (prefix_safe(safe), safe))
        url = "https://api.telegram.org/file/bot{token}/{fp}".format(
            token=cfg["telegram"]["bot_token"], fp=fp)
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(local, "wb") as fh:
            fh.write(r.content)
        meta = {"name": safe, "path": local, "size": len(r.content),
                "content_type": r.headers.get("Content-Type", "")}
        return local, meta
    except Exception as e:
        log("下载 Telegram 文件失败:", e)
        return None, None


def prefix_safe(safe):
    return "tg"


def is_allowed(cfg, chat, user):
    allowed = cfg["telegram"].get("allowed_user_ids", [])
    usernames = cfg["telegram"].get("allowed_usernames", [])
    uid = user.get("id")
    uname = user.get("username", "") or ""
    if uid is not None and uid in allowed:
        return True
    if uname and uname in usernames:
        return True
    return False


def bootstrap_allowed(cfg, config_path, chat, user):
    boot = cfg["telegram"].get("allow_bootstrap", False)
    if not boot:
        return False
    if chat.get("type") != "private":
        return False
    uid = user.get("id")
    if uid is None:
        return False
    allowed = cfg["telegram"].setdefault("allowed_user_ids", [])
    if uid in allowed:
        return False
    allowed.append(uid)
    cfg["telegram"]["allow_bootstrap"] = False
    try:
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        log(f"🎉 已把 {uid}（@{user.get('username','')}）加入白名单并关闭 bootstrap")
    except Exception as e:
        log("写回 config 失败:", e)
    return True


def handle_media(cfg, msg):
    """提取消息里的媒体（photo/video/document/audio），下载并返回注入文本。
    Telegram 的 photo 是一组不同尺寸的 file_id，取最后（最大）一个。"""
    notes = []
    # 图片：取最大尺寸
    if msg.get("photo"):
        largest = msg["photo"][-1]
        local, meta = tg_download(cfg, largest["file_id"], "tg_photo")
        if local:
            notes.append("\n[收到图片] {} ({} bytes)".format(meta["name"], meta["size"]))
    # 文档/视频/音频：直接 file_id
    for key, tag in (("document", "file"), ("video", "video"),
                     ("audio", "audio"), ("voice", "voice"),
                     ("animation", "animation")):
        att = msg.get(key)
        if att:
            local, meta = tg_download(cfg, att["file_id"], "tg_" + tag)
            if local:
                notes.append("\n[{tag2}] {name} ({size} bytes)".format(
                    tag2=tag.capitalize(), name=meta["name"], size=meta["size"]))
    return "".join(notes)


def handle_message(cfg, chat, user, text, media_note=""):
    if not is_allowed(cfg, chat, user):
        return "抱歉，你的账号不在白名单中，无法使用此机器人。"
    t = (text or "").strip()
    if t.lower() in ("/start", "/help"):
<<<<<<< HEAD
        return ("这是把手机消息转发给本地 DSH agent 的桥。\n"
                "· 直接发消息（可带图/视频/文件）→ DSH 执行并回复。\n"
                "· /send 文件名 → 把 phone_bridge/media_out/ 下的文件发回。")
    log("task from", user.get("username") or user.get("first_name"), ":", t[:80])
=======
        return ("这是把手机消息转发给 DSH agent 的桥。\n"
                "· 直接发消息（可带图/视频/文件）→ DSH 执行并回复。\n"
                "· /send 文件名 → 把 media_out/ 下的文件发回。")
    log("task from", user.get("username") or user.get("first_name"), ":", t[:80])
    # 统一通道：同一个用户始终打到同一个持久 agent 会话（peer = tg:<user_id>）
    peer = "tg:{}".format(user.get("id"))
    if (cfg.get("unified") or {}).get("enabled", True):
        return run_unified_task(cfg, peer, t + media_note)
>>>>>>> 818b011 (Add unified-agent bridge: Telegram + QQ share one persistent DSH agent)
    return run_dsh_task(cfg, t + media_note)


def send_media_back(cfg, chat_id, file_ref):
    """把 media_out 下文件发回 Telegram（原生 sendPhoto/sendVideo/sendDocument）。"""
    rel = (file_ref or "").strip("/")
    if not rel:
        return "请填写 media_out 下的文件名，例如 /send output.mp4"
    p = os.path.join(MEDIA_OUT, rel)
    if not os.path.isfile(p):
        return "❌ media_out 下没找到: " + rel
    ext = os.path.splitext(rel)[1].lower()
    url = API.format(token=cfg["telegram"]["bot_token"])
    params = {"chat_id": chat_id}
    files = None
    with open(p, "rb") as fh:
        data = fh.read()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        method = "sendPhoto"
        files = {"photo": (rel, data)}
    elif ext in (".mp4", ".mov", ".webm"):
        method = "sendVideo"
        files = {"video": (rel, data)}
    else:
        method = "sendDocument"
        files = {"document": (rel, data)}
    try:
        r = requests.post(url + "/" + method, data=params, files=files, timeout=120)
        r.raise_for_status()
        return "✅ 已发送: " + rel
    except Exception as e:
        return "❌ 发送失败: " + str(e)[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config.json"))
    ap.add_argument("--poll-interval", type=float, default=1.0)
    args = ap.parse_args()

    global cfg
    cfg = load_config(args.config)
    config_path = args.config
    token = cfg["telegram"]["bot_token"]
    if not token or token == "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        sys.exit("请先在 config.json 填入 Telegram bot token（config.example.json 复制而来）。")
    if (not cfg["telegram"].get("allowed_user_ids")
            and not cfg["telegram"].get("allowed_usernames")
            and not cfg["telegram"].get("allow_bootstrap", False)):
        sys.exit("白名单为空且未开启 bootstrap，拒绝启动（避免任何人指挥本机）。")

    me = tg_request(cfg, "getMe")
    if not me.get("ok"):
        sys.exit("token 无效：" + json.dumps(me, ensure_ascii=False)[:300])
    log("Bot 已就绪：@", me["result"]["username"])

    os.makedirs(MEDIA_OUT, exist_ok=True)
    os.makedirs(INBOX, exist_ok=True)

    offset = 0
    while True:
        try:
            r = tg_request(cfg, "getUpdates", offset=offset, timeout=25)
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                chat = msg["chat"]
                user = msg.get("from") or {}
                if chat.get("type") not in ("private", "group", "supergroup"):
                    continue
                if not is_allowed(cfg, chat, user):
                    if bootstrap_allowed(cfg, config_path, chat, user):
                        log("bootstrap 通过，已放行")
                    else:
                        tg_request(cfg, "sendMessage", chat_id=chat["id"],
                                   text="抱歉，你的账号不在白名单中。")
                        continue

                # —— 媒体接收 ——
                media_note = handle_media(cfg, msg)

                text = str(msg.get("text") or "").strip()

                # —— 发送指令：/send <media_out 下文件名> ——
                sm = re.match(r"^/send(?:\s+(\S+))?$", text)
                if sm:
                    reply = send_media_back(cfg, chat["id"], sm.group(1))
                    tg_request(cfg, "sendMessage", chat_id=chat["id"], text=reply)
                    continue
                if text.lower() in ("/start", "/help"):
                    tg_request(cfg, "sendMessage", chat_id=chat["id"], text=(
                        "这是把手机消息转成本地 DSH agent 任务的桥。\n"
                        "· 直接发消息（可带图/视频/文件）→ DSH 执行并回复。\n"
                        "· /send 文件名 → 把 media_out/ 下文件发回，如 /send exp.mp4"))
                    continue

                if not (text or media_note):
                    continue
                # 只有媒体、没有文字时，也构造一个"分析这个文件"任务
                task = text if text else "分析我发来的这个文件，并说明它是什么。"
                task += media_note
                log("task from", user.get("username") or user.get("first_name"), ":", task[:80])
<<<<<<< HEAD
                reply = run_dsh_task(cfg, task)
=======
                peer = "tg:{}".format(user.get("id"))
                if (cfg.get("unified") or {}).get("enabled", True):
                    reply = run_unified_task(cfg, peer, task)
                else:
                    reply = run_dsh_task(cfg, task)
>>>>>>> 818b011 (Add unified-agent bridge: Telegram + QQ share one persistent DSH agent)
                tg_request(cfg, "sendMessage", chat_id=chat["id"], text=reply[:4096])
        except requests.exceptions.ConnectionError as e:
            log("网络错误，重试:", e)
            time.sleep(5)
        except requests.exceptions.Timeout:
            log("超时，继续")
        except Exception as e:
            log("错误:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
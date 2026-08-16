#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qq_bridge.py — QQ 开放平台机器人 → DSH headless 桥（基于官方 qq-botpy SDK）

把用户在 QQ（单聊 C2C / 群 @机器人）发给本机器人的消息，转成
`dsh --profile headless "<消息>"` 任务执行，并把最终回复发回。
支持接收图片/视频/文件（存到 phone_bridge/inbox/）并作为上下文指给 DSH；
支持把本地产物（phone_bridge/media_out/ 下文件）发送回 QQ 单聊/群。

依赖：qq-botpy（请用 Python 3.13 运行）。鉴权用 config.json 的 qq.appid / qq.secret。
安全：只处理白名单内用户；首次私聊可 bootstrap 自动加入。

用法：
  C:/Users/Administrator/AppData/Local/Programs/Python/Python313/python.exe qq_bridge.py --config config.json
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import botpy
from botpy import Client
from botpy.message import C2CMessage, GroupMessage

from bridge_common import load_config, run_dsh_task

HERE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(HERE, "inbox")
MEDIA_OUT = os.path.join(HERE, "media_out")


def now():
    return time.strftime("[%H:%M:%S]")


def download_attachment(att, prefix="qq"):
    """把 QQ 附件下载到 inbox/，返回 (local_path, meta_dict)。"""
    url = getattr(att, "url", None)
    if not url:
        return None, None
    fname = att.filename or ("media_%d.bin" % int(time.time()))
    safe = re.sub(r"[^\w.\-]+", "_", fname) or "file.bin"
    os.makedirs(INBOX, exist_ok=True)
    local = os.path.join(INBOX, "%s_%s" % (prefix, safe))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
        with open(local, "wb") as fh:
            fh.write(data)
        meta = {
            "name": safe, "path": local, "size": len(data),
            "content_type": getattr(att, "content_type", None),
            "width": getattr(att, "width", None),
            "height": getattr(att, "height", None),
        }
        return local, meta
    except Exception as e:
        print(now(), "❌ 下载附件失败:", e, flush=True)
        return None, None


class DSHQQClient(Client):
    def __init__(self, intents, cfg, config_path, **kw):
        super().__init__(intents=intents, **kw)
        self.cfg = cfg
        self.config_path = config_path
        self.whitelist = cfg["qq"].get("whitelist", []) or []

    def is_allowed_openid(self, openid):
        if not openid:
            return False
        if openid in self.whitelist:
            return True
        # bootstrap：私聊首次自动加入
        if self.cfg["qq"].get("allow_bootstrap", False):
            if openid not in self.whitelist:
                self.whitelist.append(openid)
            self.cfg["qq"]["whitelist"] = self.whitelist
            self.cfg["qq"]["allow_bootstrap"] = False
            try:
                with open(self.config_path, "w", encoding="utf-8") as fh:
                    json.dump(self.cfg, fh, ensure_ascii=False, indent=2)
                print(now(), "🎉 QQ bootstrap：已把", openid, "加入白名单并关闭 bootstrap", flush=True)
            except Exception as e:
                print(now(), "写回 config 失败:", e, flush=True)
            return True
        return False

    async def on_ready(self):
        print(now(), "QQ Bot 已就绪", flush=True)

    async def on_c2c_message_create(self, message: C2CMessage):
        openid = message.author.user_openid
        print(now(), "C2C 来自", openid, ":", str(message.content)[:80], flush=True)
        await self._handle(message, openid, is_c2c=True)

    async def on_group_at_message_create(self, message: GroupMessage):
        openid = getattr(message.author, "member_openid", None)
        print(now(), "GROUP/AT 来自", openid, ":", str(message.content)[:80], flush=True)
        await self._handle(message, openid, is_c2c=False)

    async def _handle(self, message, openid, is_c2c):
        if not openid:
            return
        if not self.is_allowed_openid(str(openid)):
            try:
                await message.reply(content="抱歉，你的账号不在白名单中。")
            except Exception as e:
                print(now(), "reply(deny) err:", e, flush=True)
            return

        text = (str(message.content or "")).strip() or ""
        # —— 媒体接收：把 attachments 下载到 inbox ——
        atts = getattr(message, "attachments", None) or []
        media_note = ""
        for att in atts:
            local, meta = download_attachment(att)
            if local:
                media_note += "\n[收到媒体] {} ({} bytes)".format(meta["name"], meta["size"])

        # 发送指令：/send <media_out 下文件名|子路径>
        sm = re.match(r"^/send(?:\s+(\S+))?$", text)
        if sm:
            rel = sm.group(1) or ""
            await self._send_media_back(message, rel, is_c2c)
            return
        if text.lower() in ("/start", "/help"):
            await message.reply(content=(
                "这是把 QQ 消息转成本地 DSH agent 任务的桥。\n"
                "· 直接发消息 → DSH 执行并回复，支持带图/视频/文件（自动存 inbox）。\n"
                "· 发送产物：/send 文件名（放 phone_bridge/media_out/）"
            ))
            return

        # 有媒体则把本地路径加入上下文，方便 DSH 当参考
        task = text + media_note
        if not task.strip():
            return
        print(now(), "→ DSH 任务:", task[:120], flush=True)
        reply = run_dsh_task(self.cfg, task)
        try:
            await message.reply(content=reply[:1000])
        except Exception as e:
            print(now(), "reply err:", e, flush=True)
            try:
                await message.reply(content="⚠️ 处理失败: " + str(e)[:200])
            except Exception:
                pass

    async def _send_media_file(self, message, file_ref, is_c2c):
        """把 media_out 下文件发回 QQ：用 post_c2c_file / post_group_file + 公网URL。"""
        base = self.cfg["qq"].get("media_base_url", "")
        if not base:
            try:
                await message.reply(content="未配置媒体公网地址 (qq.media_base_url)，无法回发文件。")
            except Exception:
                pass
            return
        rel = (file_ref or "").strip("/")
        url = base.rstrip("/") + "/" + urllib.parse.quote(rel)
        ext = os.path.splitext(rel)[1].lower()
        file_type = 1 if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp") else \
                    2 if ext in (".mp4", ".mov", ".webm") else \
                    4 if ext else 4
        api = getattr(message, "_api", None)
        if api is None:
            try:
                await message.reply(content="无 API 句柄，无法发文件。")
            except Exception:
                pass
            return
        try:
            if is_c2c:
                await api.post_c2c_file(
                    openid=message.author.user_openid,
                    file_type=file_type, url=url, srv_send_msg=True)
            else:
                await api.post_group_file(
                    group_openid=message.group_openid,
                    file_type=file_type, url=url, srv_send_msg=True)
        except Exception as e:
            print(now(), "发送媒体失败:", e, flush=True)
            try:
                await message.reply(content="⚠️ 发媒体失败: " + str(e)[:200])
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    qq = cfg["qq"]
    if not qq.get("enabled"):
        sys.exit("qq.enabled=false，跳过 QQ 桥（想启用请设 true）")
    appid = qq.get("appid", "")
    secret = qq.get("secret", "")
    if not appid or not secret:
        sys.exit("config.json 缺少 qq.appid / qq.secret")

    intents = botpy.Intents(public_messages=True)  # C2C 单聊 + 群@
    client = DSHQQClient(intents=intents, cfg=cfg, config_path=args.config,
                         log_level="INFO" if args.debug else "WARNING")
    print(now(), "启动 QQ 桥 appid=", appid,
          "（qq.whitelist 项数=", len(qq.get("whitelist", [])), "）", flush=True)
    client.run(appid=appid, secret=secret)


if __name__ == "__main__":
    main()
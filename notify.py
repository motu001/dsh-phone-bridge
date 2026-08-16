#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""notify.py — 把电脑上的文件/消息主动推送到手机（QQ + Telegram 双通道）。

用法：
  python notify.py --channel qq --message "H3 视频已完成"
  python notify.py --channel tg --message "H3 视频已完成"
  python notify.py --channel qq --file E:/path/out.mp4
  python notify.py --channel tg --file E:/path/out.mp4
  python notify.py --channel all --file E:/path/out.mp4

说明：
  - QQ：需 media_server + cloudflared 运行中（config.qq.media_base_url）；文件拷贝到 media_out
    后以公网 URL 调 post_c2c_file 主动推送（消耗主动消息频次，仅对已私聊过的用户）。
  - Telegram：用 bot API 原生上传（sendPhoto/sendVideo/sendDocument），chat_id 取
    config.telegram.allowed_user_ids[0]，无需公网 URL。
"""
import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
QQ_API = "https://api.bot.qq.com"
TG_API = "https://api.telegram.org/bot{token}"


def _mime(ext):
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp",
        ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    }.get(ext, "application/octet-stream")


def _post_json(url, payload, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", **(headers or {})})
    return _exec(req)


def _exec(req):
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            d = e.read().decode("utf-8")
        except Exception:
            d = ""
        return e.code, {"err": d[:600]}
    except Exception as e:
        return 0, {"err": str(e)}


# ---------- QQ ----------
def qq_token(appid, secret):
    payload = {"appId": appid, "clientSecret": secret}
    req = urllib.request.Request("https://bots.qq.com/app/getAppAccessToken",
                                 data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    code, data = _exec(req)
    if code != 200 or not data.get("access_token"):
        raise RuntimeError("QQ 换取 access_token 失败: {} {}".format(code, json.dumps(data, ensure_ascii=False)[:200]))
    return data["access_token"]


def qq_send_text(token, openid, text):
    return _post_json(QQ_API + "/v2/users/{}/messages".format(openid), {"content": text, "msg_type": 0},
                 {"Authorization": "QQBot " + token})


def qq_send_file(token, openid, file_url, file_type):
    return _post_json(QQ_API + "/v2/users/{}/files".format(openid),
                 {"file_type": file_type, "url": file_url, "srv_send_msg": True},
                 {"Authorization": "QQBot " + token})


# ---------- Telegram ----------
def tg_send_text(token, chat_id, text):
    return _exec(urllib.request.Request(TG_API.format(token=token) + "/sendMessage",
                                        data=json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8"),
                                        method="POST", headers={"Content-Type": "application/json"}))


def tg_send_file(token, chat_id, local_path):
    ext = os.path.splitext(local_path)[1].lower()
    if ext in (".mp4", ".mov", ".webm"):
        method, field = "sendVideo", "video"
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        method, field = "sendPhoto", "photo"
    else:
        method, field = "sendDocument", "document"
    boundary = "wb" + os.urandom(8).hex()
    fname = os.path.basename(local_path)
    with open(local_path, "rb") as fh:
        blob = fh.read()
    parts = [
        ('--%s\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n%d\r\n' % (boundary, chat_id)).encode(),
        ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
         'Content-Type: %s\r\n\r\n' % (boundary, field, fname, _mime(ext))).encode(),
        blob,
        ('\r\n--%s--\r\n' % boundary).encode(),
    ]
    req = urllib.request.Request(TG_API.format(token=token) + "/" + method,
                                 data=b"".join(parts), method="POST",
                                 headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    return _exec(req)


# ---------- 主流程 ----------
def push_qq(cfg, message=None, file_path=None):
    qq = cfg.get("qq", {})
    openid = (qq.get("whitelist") or [None])[0]
    if not openid:
        return "QQ: 无可用 openid（qq.whitelist 为空）"
    token = qq_token(qq["appid"], qq.get("secret", ""))
    if message:
        code, resp = qq_send_text(token, openid, message)
        return "QQ 文本 HTTP %d %s" % (code, json.dumps(resp, ensure_ascii=False)[:180])
    if not file_path:
        return "QQ: 需 --message 或 --file"
    if not os.path.isfile(file_path):
        return "QQ: 文件不存在 " + str(file_path)
    base = qq.get("media_base_url", "")
    if not base:
        return "QQ: 未配置 qq.media_base_url（需 media_server + cloudflared 运行中）"
    fname = os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower()
    file_type = 1 if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp") else \
                2 if ext in (".mp4", ".mov", ".webm") else 4
    media_out = os.path.join(HERE, "media_out")
    os.makedirs(media_out, exist_ok=True)
    shutil.copy(file_path, os.path.join(media_out, fname))
    file_url = base.rstrip("/") + "/" + urllib.parse.quote(fname)
    code, resp = qq_send_file(token, openid, file_url, file_type)
    return "QQ[%s] HTTP %d %s" % (fname, code, json.dumps(resp, ensure_ascii=False)[:180])


def push_tg(cfg, message=None, file_path=None):
    tg = cfg.get("telegram", {})
    token = tg.get("bot_token", "")
    chat_id = (tg.get("allowed_user_ids") or [None])[0]
    if not token or not chat_id:
        return "TG: 缺少 bot_token 或 allowed_user_ids"
    if file_path:
        if not os.path.isfile(file_path):
            return "TG: 文件不存在 " + str(file_path)
        code, resp = tg_send_file(token, chat_id, file_path)
        return "TG 文件 HTTP %d %s" % (code, json.dumps(resp, ensure_ascii=False)[:180])
    code, resp = tg_send_text(token, chat_id, message or "")
    return "TG 文本 HTTP %d %s" % (code, json.dumps(resp, ensure_ascii=False)[:180])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--channel", choices=["qq", "tg", "all"], required=True)
    ap.add_argument("--file", default=None)
    ap.add_argument("--message", default=None)
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8"))
    results = []
    if args.channel in ("qq", "all"):
        results.append(push_qq(cfg, message=args.message, file_path=args.file))
    if args.channel in ("tg", "all"):
        results.append(push_tg(cfg, message=args.message, file_path=args.file))
    for r in results:
        print(r)
    # 任一路径含 "HTTP 2"（200/201/204）视为成功
    success = any(("HTTP 2" in r) for r in results)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
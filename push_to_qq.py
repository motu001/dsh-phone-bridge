#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push_active.py — 主动向 QQ 用户推送图片/文件。

用 config 里的 qq.appid/qq.secret 换取 access_token，
再调官方 API-v2 的 POST /v2/users/{openid}/files 把 media_out 下的文件发给指定用户。

用法:
  python push_active.py --media_out 目录 --file 文件名 [--openid XXXXX]

说明：腾讯主动消息有频次/权限限制（srv_send_msg），仅对已与机器人私聊过的用户有效。
"""
import argparse, json, os, sys, urllib.request, urllib.parse, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))

# 统一请求地址（官方文档）
API_BASE = "https://api.bot.qq.com"


def get_access_token(appid, secret):
    """用 appid+secret 换 access_token（官方 OAuth2 客户端凭证）。"""
    url = "https://bots.qq.com/app/getAppAccessToken"
    body = json.dumps({"appId": appid, "clientSecret": secret}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError("获取 access_token 失败: " + json.dumps(data, ensure_ascii=False))
    return token


def post_c2c_file(token, openid, url, file_type):
    """给单个用户发文件（官方 POST /v2/users/{openid}/files）。"""
    api = API_BASE + "/v2/users/" + openid + "/files"
    payload = {
        "file_type": file_type,
        "url": url,
        "srv_send_msg": True,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api, data=body, method="POST", headers={
        "Authorization": "QQBot " + token,
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = ""
        return e.code, {"err": detail[:500]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--file", required=True, help="media_out 下的文件名或子路径")
    ap.add_argument("--openid", default=None, help="目标用户 openid（默认取白名单第一个）")
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8"))
    qq = cfg["qq"]
    appid = qq.get("appid", "")
    secret = qq.get("secret", "")
    base = qq.get("media_base_url", "")
    if not appid or not secret:
        sys.exit("❌ 缺少 qq.appid / qq.secret")
    if not base:
        sys.exit("❌ 缺少 qq.media_base_url（先跑 media_server 拿稳定隧道）")

    openid = args.openid or (qq.get("whitelist") or [None])[0]
    if not openid:
        sys.exit("❌ 没有可用的 openid（config.qq.whitelist 为空且未传 --openid）")

    rel = (args.file or "").strip("/")
    local = os.path.join(os.path.join(HERE, "media_out"), rel)
    if not os.path.isfile(local):
        sys.exit("❌ media_out 下没有: " + rel)

    ext = os.path.splitext(rel)[1].lower()
    file_type = 1 if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp") else \
                2 if ext in (".mp4", ".mov", ".webm") else 4

    file_url = base.rstrip("/") + "/" + urllib.parse.quote(rel)
    print("appid:", appid)
    print("openid:", openid)
    print("file:", rel, "-> file_url:", file_url)
    print("file_type:", file_type)

    print("换取 access_token ...")
    token = get_access_token(appid, secret)
    print("已取到 access_token (len=%d)" % len(token))

    code, resp = post_c2c_file(token, openid, file_url, file_type)
    print("HTTP:", code)
    print("响应:", json.dumps(resp, ensure_ascii=False)[:800])
    if code == 201 and not resp.get("err_code"):
        print("[OK] 已主动推送到 QQ")
    else:
        print("[WARN] 腾讯可能拒绝了主动消息（受配额/权限/沙盒限制），HTTP 状态码非 201 请查看上方响应")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
media_server.py — 本地媒体静态服务 + cloudflared 公网隧道

把 phone_bridge/media_out/ 目录暴露成本地 HTTP 服务，再经 cloudflared 快速隧道
产生一个公网 URL(.trycloudflare.com)。QQ 开放平台 post_*_file 靠该 URL 拉取
媒体并发送给用户。

用法：
  python media_server.py --config config.json [--port 8787]

行为：
  - 启动 http.server 服务 media_out/ 目录
  - spawn cloudflared tunnel --url 获取公网 URL
  - 把公网 URL 写回 config.json 的 qq.media_base_url
  - 常驻运行（Ctrl+C 退出后清理 cloudflared）
"""
import argparse
import functools
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA_OUT = os.path.join(HERE, "media_out")
CF = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"


def start_local_server(port):
    """在 127.0.0.1:port 提供 media_out/ 目录，返回 httpd。
    注意：SimpleHTTPRequestHandler 在部分 Python 版本按 os.getcwd() 解析路径，
    因此直接 chdir 到 media_out，保证 /<file> 正常返回。"""
    os.makedirs(MEDIA_OUT, exist_ok=True)
    os.chdir(MEDIA_OUT)

    class Handler(http.server.SimpleHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):  # 静音
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _kill_stale_cloudflared():
    """杀干净遗留的 cloudflared（避免多进程争抢 8787，导致隧道 URL 错乱）。"""
    try:
        import subprocess as sp
        out = sp.run(
            ['powershell', '-NoProfile', '-Command',
             "Get-CimInstance Win32_Process -Filter \"Name='cloudflared.exe'\" | "
             "Where-Object {$_.CommandLine -like '*127.0.0.1:8787*'} | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
            capture_output=True, text=True, timeout=30)
    except Exception as e:
        print("[media] cloudflared 清理失败(忽略):", e, flush=True)


def start_tunnel(port):
    """启动 cloudflared 快速隧道，返回 (proc, public_url)。"""
    _kill_stale_cloudflared()
    cmd = [CF, "tunnel", "--url", "http://127.0.0.1:%d" % port]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    url = None
    deadline = time.time() + 90
    while time.time() < deadline:
        line = p.stdout.readline()
        if line:
            print("[cf]", line.rstrip(), flush=True)
        m = re.search(r"(https://[a-z0-9\-]+\.trycloudflare\.com)", line or "")
        if m:
            url = m.group(1)
            break
    return p, url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8"))

    httpd = start_local_server(args.port)
    print("[media] 本地服务 media_out/ -> http://127.0.0.1:%d" % args.port, flush=True)

    p, url = start_tunnel(args.port)
    if not url:
        print("[media] ❌ 未能获取隧道 URL（cloudflared 可能未联网/被拦）", flush=True)
        p.kill()
        httpd.shutdown()
        sys.exit(1)

    print("[media] 公网 URL:", url, flush=True)
    cfg.setdefault("qq", {})["media_base_url"] = url
    with open(args.config, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    print("[media] 已写回 qq.media_base_url =", url, flush=True)

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        p.terminate()
        httpd.shutdown()
        print("[media] 已停止", flush=True)


if __name__ == "__main__":
    main()
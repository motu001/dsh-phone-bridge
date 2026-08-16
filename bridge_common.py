#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bridge_common.py — Telegram/QQ 桥共享：配置加载 + dsh headless 任务执行。

v2：改用 node.exe 直接调用 dsh 的 bin.js，彻底告别 .cmd 批处理 ——
不再需要 cmd.exe 外壳，因此发消息时电脑上不会弹出任何 CMD 窗口。
另加 CREATE_NO_WINDOW 标志，双重保险，保证 node 自身也不申请控制台。
"""
import json
import os
import shutil
import subprocess

# Windows：创建子进程时禁止其分配新控制台窗口。
CREATE_NO_WINDOW = 0x08000000
IS_WINDOWS = os.name == "nt"


def _default_node():
    """返回一个可用的 node.exe 绝对路径。"""
    # 1) PATH 里找 node
    try:
        n = shutil.which("node")
        if n:
            return n
    except Exception:
        pass
    # 2) 常见安装位置
    candidates = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        os.path.expandvars(r"%ProgramFiles%\nodejs\node.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # 3) 兜底：where node
    try:
        out = subprocess.check_output(["where", "node"], shell=True).decode().strip().splitlines()
        if out and os.path.exists(out[0].strip()):
            return out[0].strip()
    except Exception:
        pass
    return "node"


def _guess_binjs(cmd_path):
    """从旧配置里的 dsh.cmd 路径推导出 bin.js —— 兼容不弹窗前的旧配置。

    形如：
      C:\\...\\node_modules\\.bin\\dsh.cmd
    →  C:\\...\\node_modules\\@deepseek-ai\\dsh\\lib\\bin.js
    """
    try:
        p = os.path.abspath(cmd_path)
        parts = p.replace("\\", "/").split("/")
        if ".bin" in parts:
            idx = parts.index(".bin")
            base = "/".join(parts[:idx])  # .../node_modules
            cand = os.path.join(base, "@deepseek-ai", "dsh", "lib", "bin.js")
            if os.path.exists(cand):
                return os.path.abspath(cand)
        # 兜底
        cand = os.path.join(os.path.dirname(p), "..", "@deepseek-ai", "dsh", "lib", "bin.js")
        if os.path.exists(cand):
            return os.path.abspath(cand)
    except Exception:
        pass

    # 从 npm 全局根自动发现全局安装的 dsh（npm install -g @deepseek-ai/dsh）
    try:
        out = subprocess.check_output(["npm", "root", "-g"], shell=True,
                                      text=True, errors="replace").strip()
        if out and os.path.isdir(out):
            cand = os.path.join(out, "@deepseek-ai", "dsh", "lib", "bin.js")
            if os.path.exists(cand):
                return os.path.abspath(cand)
    except Exception:
        pass
    return None


def resolve_dsh_invocation(cfg):
    """返回 [executable, ...前缀参数]，用于直接 spawn，不经过 .cmd。

    读取顺序：
      1. dsh.node（node.exe 绝对路径）+ dsh.binjs（bin.js 绝对路径）——推荐
      2. dsh.bin（旧 .cmd 路径）→ 自动推导 bin.js
      3. 全缺 → PATH 里的 node + 尝试推导
    """
    d = cfg.get("dsh", {})
    node = d.get("node") or _default_node()
    binjs = d.get("binjs") or _guess_binjs(d.get("bin", ""))
    profile = d.get("profile", "headless")

    if binjs:
        return node, [binjs, "--profile", profile]
    # 极老配置 / 非标：退回 .cmd（可能仍弹窗），但优先保证能用。
    old = d.get("bin") or "dsh"
    return old, ["--profile", profile]


def load_config(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run_dsh_task(cfg, task_text):
    """把任务文本交给本地 dsh headless 执行，返回最终助手回复（无窗口）。"""
    d = cfg.get("dsh", {})
    timeout = int(d.get("timeout_sec", 300))
    exe, pre = resolve_dsh_invocation(cfg)
    cmd = [exe] + pre + [task_text]
    print("DSH:", " ".join(cmd)[:200], flush=True)
    kwargs = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = CREATE_NO_WINDOW
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", **kwargs)
    except subprocess.TimeoutExpired:
        return "⏱ 任务超时（>{}s）".format(timeout)
    except FileNotFoundError:
        return "❌ 找不到 dsh 可执行：{}".format(exe)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if p.returncode != 0:
        return "❌ dsh 退出码 {}：{}".format(p.returncode, err[-500:] or out[-500:])
    return out or "(空回复)"


if __name__ == "__main__":
    print("node  =", _default_node())
    print("binjs =", _guess_binjs(r"C:\Users\Administrator\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\.bin\dsh.cmd"))
    cfg = {"dsh": {"profile": "headless", "timeout_sec": 60}}
    print("cmd0  =", resolve_dsh_invocation(cfg)[0])
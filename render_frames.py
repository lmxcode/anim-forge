# -*- coding: utf-8 -*-
"""render_frames.py — 无头浏览器逐帧渲染。

用法:
    python render_frames.py --config config.json [--html anim.template.html]

原理:
    anim.html 是 ?t= 的纯函数 —— 同一个 t 永远渲染出同一帧。
    本脚本按 fps×duration 逐帧截图到 frames/。

特性:
    - 跳过已存在帧（断点续渲；配合删帧可做局部重渲）
    - 浏览器自动探测: Edge / Chrome / Chromium (Windows / macOS / Linux)
    - 帧文件名 f0000.png 起，与 mix_final.py 的 %04d 序列对齐
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

BROWSER_CANDIDATES = [
    # Windows
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    # macOS
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    # Linux
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
]


def find_browser(pref: str = "auto") -> str:
    if pref and pref != "auto" and Path(pref).exists():
        return pref
    which = shutil.which(pref) if pref and pref != "auto" else None
    if which:
        return which
    for c in BROWSER_CANDIDATES:
        if Path(c).exists():
            return c
    which = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chrome")
    if which:
        return which
    sys.exit("未找到 Edge/Chrome/Chromium，请在 config.json 的 browser 字段填写浏览器可执行文件路径")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--html", default=None, help="默认取 config 同目录的 anim.template.html")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    here = Path(args.config).resolve().parent
    html = Path(args.html) if args.html else here / "anim.template.html"
    if not html.exists():
        sys.exit(f"找不到 {html}")

    W, H = cfg["width"], cfg["height"]
    FPS, DUR = cfg["fps"], cfg["duration"]
    N = FPS * DUR
    browser = find_browser(cfg.get("browser", "auto"))

    out = here / "frames"
    out.mkdir(exist_ok=True)

    t0 = time.time()
    done = 0
    for i in range(N):
        shot = (out / f"f{i:04d}.png").resolve()  # ⚠️ 必须绝对路径，见 docs/lessons.md #1
        if shot.exists():
            done += 1
            continue
        t = i / FPS
        uri = html.resolve().as_uri() + f"?t={t:.4f}"
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={W},{H}", "--screenshot=" + str(shot), uri],
            capture_output=True, timeout=90)
        if not shot.exists():
            print(f"MISS frame {i}", file=sys.stderr)
        done += 1
        if done % 100 == 0:
            el = time.time() - t0
            print(f"{done}/{N}  elapsed={el:.0f}s  eta={el/done*(N-done):.0f}s", flush=True)
    print(f"RENDER DONE {done}/{N} total={time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

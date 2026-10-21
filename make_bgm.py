# -*- coding: utf-8 -*-
"""make_bgm.py — numpy 代码合成 BGM（确定性、零版权风险）。

用法:
    python make_bgm.py --config config.json

所有音乐事件（和弦垫/底鼓/镲/琶音/impact/riser/渐出）都从 config.json 的
bgm 字段读取，与 anim.html 的 cuts 对齐。示例配置就是一套可直接出声的编排：
  - Am-F-C-G 和弦垫铺底
  - 底鼓按 0.6s 一拍推进，段落间力度变化
  - impact 对齐画面揭示事件，riser 对齐切场
"""
import argparse
import json
import wave
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))

    SR = 44100
    DUR = float(cfg["duration"])
    N = int(SR * DUR)
    bg = cfg.get("bgm", {})
    rng = np.random.default_rng(42)

    L = np.zeros(N)
    R = np.zeros(N)

    def add(sig, t0, pan=0.0):
        i0 = int(t0 * SR)
        i1 = min(N, i0 + len(sig))
        if i0 >= N or i1 <= i0:
            return
        s = sig[: i1 - i0]
        L[i0:i1] += s * (1 - max(pan, 0))
        R[i0:i1] += s * (1 + max(-pan, 0))

    def env_ad(n, a, d):
        e = np.ones(n)
        na = max(1, int(a * SR))
        e[:na] = np.linspace(0, 1, na)
        nd = max(1, int(d * SR))
        e[-nd:] *= np.linspace(1, 0, nd)
        return e

    def seg(t0, dur):
        i0, i1 = max(0, int(t0 * SR)), min(N, int((t0 + dur) * SR))
        return i0, i1

    def pad(freqs, t0, dur, amp):
        i0, i1 = seg(t0, dur)
        n = i1 - i0
        if n <= 0:
            return
        tt = np.arange(n) / SR
        e = env_ad(n, 0.5, 0.9)
        s = np.zeros(n)
        for f in freqs:
            s += np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.004 * tt)
        add(s * e * amp / (len(freqs) * 1.5), t0, pan=-0.15)

    def kick(t0, amp):
        dur = 0.38
        n = int(dur * SR)
        tt = np.arange(n) / SR
        f = 150 * np.exp(-tt * 9) + 44
        ph = 2 * np.pi * np.cumsum(f) / SR
        s = np.sin(ph) * np.exp(-tt * 11)
        add(s * amp, t0, pan=0.0)

    def hat(t0, amp):
        dur = 0.05
        n = int(dur * SR)
        s = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 90)
        s = np.diff(s, prepend=0)
        add(s * amp * 4, t0, pan=0.45)

    def click(t0, amp):
        dur = 0.045
        n = int(dur * SR)
        tt = np.arange(n) / SR
        s = np.sin(2 * np.pi * 1900 * tt) * np.exp(-tt * 120)
        add(s * amp, t0, pan=0.0)

    def pluck(f, t0, amp):
        dur = 0.28
        n = int(dur * SR)
        tt = np.arange(n) / SR
        s = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 14)
        add(s * amp, t0, pan=0.35)

    def impact(t0, amp):
        kick(t0, amp)
        dur = 0.30
        n = int(dur * SR)
        s = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 18)
        s = np.diff(s, prepend=0)
        add(s * amp * 1.6, t0, pan=0.0)

    def riser(t0, dur, amp):
        n = int(dur * SR)
        tt = np.arange(n) / SR
        s = rng.standard_normal(n) * (tt / dur) ** 2.2
        s = np.diff(s, prepend=0)
        add(s * amp * 2.2, t0, pan=0.0)

    # ---------- 和弦垫（全程铺底） ----------
    CH = bg.get("chords")
    step = bg.get("chord_step", 2.4)
    pad_amp0 = bg.get("pad_amp_default", 0.085)
    sections = bg.get("sections", [])
    cuts = cfg.get("cuts", [0, DUR])

    tt = 0.0
    ci = 0
    while tt < DUR - 0.1:
        amp = pad_amp0
        if CH:
            for sec in sections:
                if sec["from"] <= tt < sec["to"]:
                    amp = sec.get("pad_amp", pad_amp0)
                    break
            pad(CH[ci % len(CH)], tt, min(step + 0.5, DUR - tt), amp)
        tt += step
        ci += 1

    # ---------- 底鼓 / 镲（从第一处 sections 起拍） ----------
    beat = bg.get("beat", 0.6)
    tb = sections[0]["from"] if sections else cuts[1] if len(cuts) > 1 else 0
    while tb < (sections[-1]["to"] if sections else DUR):
        amp = 0.22
        use_hat = False
        heartbeat = False
        for sec in sections:
            if sec["from"] <= tb < sec["to"]:
                amp = sec.get("kick_amp", 0.22)
                use_hat = sec.get("hat", False)
                heartbeat = sec.get("kick_note") == "heartbeat"
                break
        if heartbeat:
            period = next((s.get("kick_period", 1.2) for s in sections
                           if s["from"] <= tb < s["to"]), 1.2)
            if (tb - sections[-1]["from"]) % period < 0.01:
                kick(tb, amp)
        elif amp > 0:
            kick(tb, amp)
            if use_hat:
                hat(tb + 0.3, 0.05)
        tb += beat

    # ---------- 琶音（sections 覆盖区内，hat 段加花） ----------
    arp_from = sections[1]["from"] if len(sections) > 1 else None
    arp_to = sections[-2]["to"] if len(sections) > 2 else None
    if CH and arp_from and arp_to:
        ta = arp_from + 2.0
        ci = 0
        while ta < arp_to:
            ch = CH[(ci // 4) % len(CH)]
            pluck(ch[ci % 3] * 2, ta, 0.075 if ta < arp_to - 11 else 0.09)
            ta += 0.3
            ci += 1

    # ---------- 与画面事件对齐 ----------
    for c in bg.get("clicks", []) if isinstance(bg.get("clicks"), list) else []:
        click(c["t"], c.get("amp", 0.1))
    clicks = bg.get("clicks")
    if isinstance(clicks, dict) and clicks.get("count"):
        for k in range(clicks["count"]):
            click(clicks["start"] + k * clicks["step"], clicks.get("amp", 0.1))
    for im in bg.get("impacts", []):
        impact(im["t"], im.get("amp", 0.15))
    for ri in bg.get("risers", []):
        riser(ri["t"], ri.get("dur", 1.0), ri.get("amp", 0.05))

    # ---------- 主控 ----------
    fade_in = int(0.25 * SR)
    L[:fade_in] *= np.linspace(0, 1, fade_in)
    R[:fade_in] *= np.linspace(0, 1, fade_in)
    fo0 = int(bg.get("fade_out_at", DUR - 2.5) * SR)
    fo = N - fo0
    L[fo0:] *= np.linspace(1, 0, fo)
    R[fo0:] *= np.linspace(1, 0, fo)
    peak = max(np.abs(L).max(), np.abs(R).max())
    L *= 0.80 / peak
    R *= 0.80 / peak
    st = np.stack([L, R], axis=1)
    pcm = (st * 32767).astype(np.int16)

    out = Path(args.config).resolve().parent / "bgm.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"OK {out} {out.stat().st_size/1e6:.1f}MB peak={peak:.2f}")


if __name__ == "__main__":
    main()

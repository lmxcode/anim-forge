# -*- coding: utf-8 -*-
"""mix_final.py — 帧序列 + BGM + 口播 → 成片。

用法:
    python mix_final.py --config config.json [--out output/final.mp4]

混音设计:
    - BGM 压底（volume 0.25）
    - 每段口播按锚点 adelay 对齐 + 提升 3.5dB
    - amix normalize=0 防互相拉低，alimiter 限幅防爆音

坑位提示（详见 docs/lessons.md）:
    ffmpeg 的 -filter_complex 里 inputs 顺序必须严格对应：
    [0]=帧序列 [1]=BGM [2..]=各段口播。amix 的 inputs 数=bgm+口播段数。
"""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    here = Path(args.config).resolve().parent
    cfg = json.loads((here / Path(args.config).name).read_text(encoding="utf-8"))
    mix = cfg.get("mix", {})
    fps, dur = cfg["fps"], cfg["duration"]

    meta_path = here / "voice_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else []

    out = Path(args.out) if args.out else here / "output" / "final.mp4"
    out.parent.mkdir(exist_ok=True)

    cmd = ["ffmpeg", "-y", "-framerate", str(fps),
           "-i", str(here / "frames" / "f%04d.png"),
           "-i", str(here / "bgm.wav")]
    for m in meta:
        cmd += ["-i", m["mp3"]]

    fc = f"[1:a]volume={mix.get('bgm_volume', 0.25)}[bg]"
    parts = ["[bg]"]
    gain = mix.get("voice_gain_db", 3.5)
    for i, m in enumerate(meta):
        ms = int(m["anchor"] * 1000)
        fc += f";[{i+2}:a]volume={gain}dB,adelay={ms}|{ms}[a{i}]"
        parts.append(f"[a{i}]")
    fc += (";" + "".join(parts) + f"amix=inputs={len(parts)}:duration=longest:normalize=0,"
           f"alimiter=limit={mix.get('limiter', 0.95)}[aout]")

    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
            "-t", str(dur), "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-c:a", "aac", "-b:a", "128k",
            str(out)]
    print(" ".join(cmd)[:400], "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(r.returncode)
    print("OK", out, out.stat().st_size / 1e6, "MB")


if __name__ == "__main__":
    main()

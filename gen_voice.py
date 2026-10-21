# -*- coding: utf-8 -*-
"""gen_voice.py — 按「锚点 + 时间窗」逐段合成口播（MiniMax TTS）。

用法:
    python gen_voice.py --segments segments.json --config config.json

环境变量（不落盘、不进仓库）:
    MINIMAX_API_KEY   必填，MiniMax 开放平台 API Key
    MINIMAX_GROUP_ID  如你的账号需要则填写

segments.json 格式（见 example/segments.json）:
    [
      {"name": "S1_hook", "anchor": 0.6, "text": "……", "window": [0, 5.2]},
      ……
    ]
    anchor = 口播起播秒数（与 anim.html 的动画对齐）
    window = 该段必须落进去的 [起, 止] 区间（止留 0.15s 余量判定）

输出:
    voice/S1_hook.mp3 …
    voice_meta.json  → 供 mix_final.py 使用
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


def synth_one(text: str, out_path: Path, cfg_tts: dict) -> dict:
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        raise SystemExit("未设置 MINIMAX_API_KEY 环境变量（密钥不要写进任何文件/仓库）")

    voice_setting = {
        "voice_id": cfg_tts.get("voice_id", "male-qn-qingse"),
        "speed": cfg_tts.get("speed", 1.25),
        "vol": cfg_tts.get("volume", 3.0),
    }
    payload = json.dumps({
        "model": cfg_tts.get("model", "speech-2.8-turbo"),
        "text": text,
        "stream": False,
        "voice_setting": voice_setting,
        "audio_setting": {
            "sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1,
        },
        "subtitle_enable": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.minimaxi.com/v1/t2a_v2",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    base = data.get("base_resp", {})
    if base.get("status_code") != 0:
        raise SystemExit(f"MiniMax API error {base.get('status_code')}: {base.get('status_msg')}")
    mp3 = bytes.fromhex(data["data"]["audio"])
    out_path.write_bytes(mp3)
    dur_ms = data.get("extra_info", {}).get("audio_length", 0)
    return {"duration_ms": dur_ms}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", default="segments.json")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    here = Path(args.config).resolve().parent
    cfg = json.loads((here / Path(args.config).name).read_text(encoding="utf-8"))
    segs = json.loads(Path(args.segments).read_text(encoding="utf-8"))

    vdir = here / "voice"
    vdir.mkdir(exist_ok=True)

    meta = []
    all_fit = True
    for seg in segs:
        name = seg["name"]
        anchor, text = float(seg["anchor"]), seg["text"]
        win = seg.get("window")
        mp3 = vdir / f"{name}.mp3"

        if mp3.exists() and seg.get("reuse", True):
            # 已存在则直接读旧文件时长（ffprobe）
            import subprocess
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(mp3)], capture_output=True, text=True)
            dur_ms = int(float(r.stdout.strip()) * 1000)
            print(f"{name} reuse {dur_ms}ms", flush=True)
        else:
            r = synth_one(text, mp3, cfg.get("tts", {}))
            dur_ms = r["duration_ms"]
            print(f"{name} synth {dur_ms}ms", flush=True)

        end = anchor + dur_ms / 1000
        fit = True
        if win:
            fit = end <= win[1] - 0.15
            if not fit:
                all_fit = False
                print(f"⚠️  {name} 超窗: end={end:.2f} > {win[1]}（文本 {len(text)} 字，精简文案或挪锚点）",
                      file=sys.stderr, flush=True)
        meta.append({"name": name, "anchor": anchor, "text": text,
                     "mp3": str(mp3.resolve()), "duration_ms": dur_ms})

    out = here / "voice_meta.json"
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"meta saved: {out}", "ALL_FIT" if all_fit else "HAS_OVER")
    # 超窗的处理顺序：先精简文案重新合成 → 实在差 0.2s 内可微挪锚点（锚点只是放置位置）
    if not all_fit:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

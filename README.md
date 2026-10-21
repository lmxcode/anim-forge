# anim-forge 🐔

**把一篇稿子变成一条 60 秒竖版短视频，只用代码。**

HTML 时间轴 → 无头浏览器逐帧渲染 → TTS 口播 → 代码合成 BGM → ffmpeg 一次合成。
零剪辑软件、零素材库、零版权风险，改一帧只重渲一帧。

```
anim.template.html      ← 你的全部"工程文件"：场景、动画、时间轴
        │  ?t=12.5 是纯函数，永远渲染出同一帧
        ▼
render_frames.py        ← 无头 Edge/Chrome 逐帧截图（15fps × 900 帧，可断点续渲）
        │
        ├─ gen_voice.py ← MiniMax TTS 六段口播，锚点+时间窗对齐
        ├─ make_bgm.py  ← numpy 代码合成 BGM（和弦垫/鼓/impact 对齐画面事件）
        ▼
mix_final.py            ← ffmpeg：帧序列 + BGM(0.25) + 口播(+3.5dB) → final.mp4
```

## 为什么是代码渲染，不是剪辑

| | 手工剪辑 | anim-forge |
|---|---|---|
| 一条 60s 成片 | ~120 分钟 | ~25 分钟（多为挂机） |
| 改一句文案 | 找时间轴、重剪、重导出 | 改 HTML 一行，重渲受影响的那几秒 |
| 确定性 | 每次导出都可能不一样 | 同一 `?t=` 永远同一帧 |
| 版权 | 找素材 | BGM 是代码合成的，无版权风险 |
| 局部重渲 | 不可能 | 删掉坏帧重渲即可 |

## 成片效果

<video src="docs/demo-60s.mp4" controls width="360"></video>

[▶ 直接观看：demo-60s.mp4](docs/demo-60s.mp4) —— 本仓库 README 的示例配置一条命令跑出来的成片（60s / 1080×1920 / 2.2MB），口播与 BGM 全部代码合成。

## 快速开始

```bash
# 0. 依赖：Python 3.10+，Edge 或 Chrome（ Windows/macOS/Linux 均可），ffmpeg，numpy
pip install numpy

# 1. 复制示例配置
cp config.example.json config.json     # Windows: copy

# 2.（可选）合成口播 —— 需要 MiniMax API Key
set MINIMAX_API_KEY=你的key              # 密钥只进环境变量，别写进任何文件
python gen_voice.py --segments example/segments.json --config config.json

# 3. 渲染 900 帧（约 20-30 分钟，挂机）
python render_frames.py --config config.json

# 4. 合成 BGM + 成片
python make_bgm.py --config config.json
python mix_final.py --config config.json
# → output/final.mp4
```

只想看看效果？用模板直接出探针帧（几秒）：

```bash
# 手动方式：用无头浏览器打开
# <你的浏览器> --headless=new --window-size=1080,1920 --screenshot=probe.png "file:///…/anim.template.html?t=12.5"
```

## 配置说明（config.json）

| 字段 | 说明 |
|---|---|
| `width/height/fps/duration` | 画布与时长，1080×1920 / 15fps / 60s 是竖版短视频默认值 |
| `cuts` | 场景切换点（秒），**anim.html 里的 `CUTS` 常量必须与此一致** |
| `browser` | `auto` 自动探测 Edge/Chrome，或填浏览器可执行文件路径 |
| `tts` | MiniMax TTS 参数；`voice_id` 默认官方公共音色，也可填你的克隆音 |
| `bgm` | 和弦、节拍、impact/riser 事件表（与画面揭示事件对齐） |
| `mix` | BGM 音量、口播增益、限幅值 |

## 动画怎么写（anim.template.html）

- 每个场景一个 `<div class="scene" id="sN">`，由 `CUTS` 控制显隐
- 场景内动画读 `lt`（场景内局部时间），用 `ease()` 三次缓动做淡入/位移/计数
- **所有元素的出现/变化都是 `?t=` 的纯函数** —— 这是确定性的根源，别用 setInterval
- 文案里的大字号 CJK 词手动 `<br>` 控断点，防劈字（见 docs/lessons.md #4）

## 已知取舍

- 渲染 900 帧约 20-30 分钟，是挂机时间不是人时；改一幕可只重渲那一段帧
- 适合「图文卡点+数字揭示」式短视频；不适合实拍、复杂转场、真人出镜
- BGM 是程序化编排，听感是"科技感底乐"而非编曲级音乐；够用，但别期待艺术

## 踩坑记录

[docs/lessons.md](docs/lessons.md) —— 9 条真实生产环境付过学费的坑（绝对路径、删帧中断、
filter_complex 顺序、口播超窗……），开工前先读。

## License

MIT

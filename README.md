# Bilingual Subtitle Generator Skill

一键极速生成双语字幕并烧录到视频(5分钟视频用时约11秒)，支持卡拉OK逐词高亮模式，无论是5分钟视频还是1小时视频，Token花费大概7分钱（以 Opus4.5计算，当然你可以用任意哪怕免费的模型），当然你也可以用于中英、韩中、日中、英韩等一切，支持 99 种语言。

## 功能特性

- **智能硬件加速** - 自动检测 Apple Silicon / NVIDIA GPU / CPU
- **多种输出模式** - 双语、仅中文、仅原文、卡拉OK
- **高质量翻译** - 使用 translate-shell 本地翻译
- **一键处理** - 从视频直接输出带字幕的成品

## 快速开始

### 安装依赖

```bash
# macOS Apple Silicon (推荐)
pip install mlx-whisper

# NVIDIA GPU / CPU
pip install faster-whisper

# FFmpeg
brew install ffmpeg        # macOS
# Windows: 下载 ffmpeg 并添加到 PATH
```

### 使用方法

在 Claude Code 或其他支持 skill 的工具中：

```bash
# 双语字幕（默认）
/bilingual-subtitle video.mp4

# 仅英文字幕
/bilingual-subtitle video.mp4 --source-only

# 卡拉OK模式（逐词高亮）
/bilingual-subtitle video.mp4 --karaoke --fontsize 24
```
当然也可以更简单，比如一句 “用 skill，对 1.mp4 加字幕”、“用 skill，对 1.mp4 仅输出字幕”，随便 ，都行，模型们都能理解。

或直接运行脚本：

```bash
python scripts/process.py video.mp4
```

## 输出模式

| 模式 | 参数 | 字幕文件 | 视频文件 |
|------|------|----------|----------|
| 双语 | (默认) | `*_bilingual.srt` | `*_bilingual.mp4` |
| 仅中文 | `--chinese-only` | `*_zh.srt` | `*_zh.mp4` |
| 仅原文 | `--source-only` | `*_source.srt` | `*_source.mp4` |
| 卡拉OK | `--karaoke` | `*_karaoke.ass` | `*_karaoke.mp4` |

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-o, --output` | 输出视频文件 | 自动生成 |
| `-l, --language` | 源语言 | `en` |
| `-t, --target` | 目标语言 | `zh-CN` |
| `-m, --model` | Whisper 模型 | `small` |
| `--fontsize` | 字体大小 | `14` |
| `--margin` | 底部边距 | `25` |
| `--srt-only` | 仅生成字幕 | - |
| `--karaoke` | 卡拉OK模式 | - |
| `--highlight-color` | 高亮颜色 | `&H00FFFF&` |

## 硬件加速

### Whisper 语音识别

| 平台 | 方案 | 速度 |
|------|------|------|
| macOS M系列 | mlx-whisper | ~15x 实时 |
| NVIDIA GPU | faster-whisper CUDA | ~8x 实时 |
| CPU | faster-whisper int8 | ~1x 实时 |

### FFmpeg 视频编码

| 平台 | 编码器 | 速度 |
|------|--------|------|
| macOS | VideoToolbox | ~5x 实时 |
| NVIDIA | NVENC | ~8x 实时 |
| AMD | AMF | ~5x 实时 |
| Intel | QuickSync | ~5x 实时 |
| CPU | libx264 | ~1x 实时 |

## 示例

```bash
# 基础用法 - 生成中英双语字幕
python scripts/process.py lecture.mp4

# 学英语 - 仅英文 + 卡拉OK高亮
python scripts/process.py movie.mp4 --source-only --karaoke --fontsize 24

# 看外剧 - 仅中文（视频已有英文硬字幕）
python scripts/process.py drama.mp4 --chinese-only

# 自定义高亮颜色（红色）
python scripts/process.py video.mp4 --karaoke --highlight-color "&H0000FF&"

# 仅生成字幕文件（不烧录）
python scripts/process.py video.mp4 --srt-only
```

## 目录结构

```
bilingual-subtitle/
├── README.md          # 本文件
├── skill.md           # Claude Code skill 定义
└── scripts/
    └── process.py     # 一键处理脚本
```

## License

MIT

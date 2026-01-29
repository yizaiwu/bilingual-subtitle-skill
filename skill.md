# 双语字幕生成

从视频提取字幕，翻译成中文，烧录双语字幕。支持卡拉OK逐词高亮模式。

## 用法
```
/bilingual-subtitle <视频文件> [选项]
```

## 常用示例

```bash
# 中英文双语字幕（默认）
/bilingual-subtitle video.mp4

# 仅英文字幕
/bilingual-subtitle video.mp4 --source-only

# 英文逐词高亮（卡拉OK模式）
/bilingual-subtitle video.mp4 --karaoke --fontsize 24
```

## 一键处理

```bash
python "C:\Users\voroj\.claude\skills\bilingual-subtitle\scripts\process.py" <视频>
```

### 参数
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-o, --output` | 输出视频文件 | `<视频名>_<模式>.mp4` |
| `-l, --language` | 源语言 | `en` |
| `-t, --target` | 目标语言 | `zh-CN` |
| `-m, --model` | Whisper 模型 | `small` |
| `--fontsize` | 字体大小 | `14` (卡拉OK建议 `24`) |
| `--margin` | 底部边距 | `25` |
| `--srt-only` | 仅生成字幕文件 | - |
| `--chinese-only` | 仅输出中文字幕 | - |
| `--source-only` | 仅输出原文字幕 | - |
| `--karaoke` | 卡拉OK模式（逐词高亮） | - |
| `--highlight-color` | 高亮颜色 (ASS格式) | `&H00FFFF&` (黄色) |
| `--no-speech-threshold` | 非语音过滤阈值 (0-1) | `0.6` |

### 完整示例
```bash
# 中英文双语字幕（默认）
python process.py video.mp4

# 仅英文字幕（不翻译）
python process.py video.mp4 --source-only

# 仅中文字幕（适用于已有英文硬字幕的视频）
python process.py video.mp4 --chinese-only

# 英文逐词高亮（卡拉OK模式）
python process.py video.mp4 --karaoke --fontsize 24

# 卡拉OK + 自定义高亮颜色（红色）
python process.py video.mp4 --karaoke --fontsize 24 --highlight-color "&H0000FF&"

# 仅生成字幕文件（不烧录视频）
python process.py video.mp4 --srt-only
```

## 输出
| 模式 | 字幕文件 | 视频文件 |
|------|----------|----------|
| 默认（双语） | `*_bilingual.srt` | `*_bilingual.mp4` |
| `--chinese-only` | `*_zh.srt` | `*_zh.mp4` |
| `--source-only` | `*_source.srt` | `*_source.mp4` |
| `--karaoke` | `*_karaoke.ass` | `*_karaoke.mp4` |

## 硬件加速

### 字幕提取 (Whisper)
| 平台 | 方案 | 速度 |
|------|------|------|
| macOS M系列 | mlx-whisper | ~15x 实时 |
| NVIDIA GPU | faster-whisper CUDA | ~8x 实时 |
| CPU | faster-whisper int8 | ~1x 实时 |

### 视频编码 (FFmpeg)
| 平台 | 编码器 | 速度 |
|------|--------|------|
| macOS | VideoToolbox | ~5x 实时 |
| NVIDIA GPU | NVENC | ~8x 实时 |
| AMD GPU | AMF | ~5x 实时 |
| Intel | QuickSync | ~5x 实时 |
| CPU | libx264 | ~1x 实时 |

## 依赖
```bash
# macOS Apple Silicon
pip install mlx-whisper

# NVIDIA GPU / CPU
pip install faster-whisper

# FFmpeg (必需)
# Windows: 下载并添加到 PATH
# macOS: brew install ffmpeg
```

---
name: bilingual-subtitle
description: 從影片/音訊中提取語音字幕、用 AI 翻譯，並燒錄雙語（原文+譯文）字幕到影片，支援卡拉OK逐詞高亮、僅譯文、僅原文等模式，支援 99 種語言。當使用者說「給影片加字幕/生成字幕/雙語字幕/中英字幕/卡拉OK字幕/字幕燒錄/burn subtitles/add subtitles/translate subtitles/給視頻加字幕/生成字幕」時使用。
license: MIT
compatibility: 需要 Python 3.10+、FFmpeg（含 libass）、faster-whisper（或 macOS 上的 mlx-whisper）。GPU 可選，有 NVIDIA GPU 時自動加速。
---

# 雙語字幕生成

一句話：給一個影片，輸出「原聲字幕 + 譯文」疊在畫面下方的成品影片（或只要字幕檔）。

- 處理腳本：`scripts/process.py`（本 skill 目錄下的相對路徑，指令裡請用絕對路徑呼叫）
- 語音辨識：faster-whisper（Windows/Linux，CUDA 或 CPU）或 mlx-whisper（Apple Silicon）
- 翻譯：**預設用 AI**（由你直接翻，或設定 OpenAI 相容接口讓腳本呼叫）；Google 翻譯改成要明確指定 `--translator google` 才會用的備用選項
- 燒錄：FFmpeg + libass，自動挑選硬體編碼器（NVENC / AMF / QSV / VideoToolbox / libx264）

## 怎麼呼叫

```bash
python "C:\Users\user\.agents\skills\bilingual-subtitle\scripts\process.py" <影片檔> [選項]
```

在 macOS / Linux 上把路徑換成 `~/.agents/skills/bilingual-subtitle/scripts/process.py` 即可。

## 常用指令

```bash
# 雙語字幕（預設；需先設定 AI 接口環境變數。沒設定就用下面的三步流程自己翻）
python .../process.py video.mp4

# 只要字幕檔，不燒錄（最快，適合先看效果）
python .../process.py video.mp4 --srt-only

# 僅原文（不翻譯）
python .../process.py video.mp4 --source-only

# 僅譯文（影片裡已經有原文硬字幕時用）
python .../process.py video.mp4 --chinese-only

# 卡拉OK逐詞高亮（自動只輸出原文）
python .../process.py video.mp4 --karaoke --fontsize 24

# 日語影片 -> 繁體中文，用 distil-large-v3（本機已快取，實測最快）
python .../process.py video.mp4 -l ja -m distil-large-v3

# 要最準就用 large-v3-turbo（稍慢一點）
python .../process.py video.mp4 -m large-v3-turbo

# 需要簡體中文時才加 -t
python .../process.py video.mp4 -t zh-CN
```

## 翻譯（預設 AI，Google 只是備用）

**預設流程：由你（AI）自己翻譯，不要呼叫 Google。** 除非使用者明確說「用 Google 翻譯」。

### 預設做法：AI 自己翻（不用金鑰，品質最好）

```bash
# 1. 先只抽出原文字幕（不動用翻譯）
python .../process.py video.mp4 -m distil-large-v3 --source-only --srt-only
#    -> 產生 video_source.srt

# 2. 你讀 video_source.srt，逐條翻譯成目標語言，寫成一行一條的純文字檔：
#    video_zh.txt（條數必須與來源完全相同，順序對應）

# 3. 帶入譯文，合併並燒錄（不會再跑一次 Whisper，1 小時的影片也只需幾秒）
python .../process.py video.mp4 --source-srt video_source.srt --translation-file video_zh.txt
```

### 選項：腳本直接呼叫 AI 接口（設定好就能一句指令跑完）

設定環境變數後，預設的 `--translator auto` 會自動使用 AI：

```bash
# Windows（cmd）
set AI_TRANSLATE_API_KEY=sk-...
set AI_TRANSLATE_BASE_URL=https://api.openai.com/v1   # 任何 OpenAI 相容接口
set AI_TRANSLATE_MODEL=gpt-4o-mini
python .../process.py video.mp4

# macOS / Linux
export AI_TRANSLATE_API_KEY=sk-...
export AI_TRANSLATE_MODEL=gpt-4o-mini
python .../process.py video.mp4
```

本機 Ollama（不用金鑰）：

```bash
set AI_TRANSLATE_BASE_URL=http://127.0.0.1:11434/v1
set AI_TRANSLATE_MODEL=qwen2.5:7b
python .../process.py video.mp4
```

沒有設定任何 AI 時，預設會停下來並印出三種做法，**不會偷偷用 Google**。

### 備用：Google 翻譯（明確指定才用）

```bash
# 整個流程都用 Google（舊行為）
python .../process.py video.mp4 --translator google

# AI 優先；AI 失敗的批次才退回 Google
python .../process.py video.mp4 --translator ai --fallback google

# 只用 MyMemory（免費、免金鑰，品質較差）
python .../process.py video.mp4 --translator mymemory
```

要點：

- 用自然、適合字幕的譯文（口語、簡短），不要逐字直譯。
- 譯文檔兩種格式都接受：**一行一條的純文字**（最簡單），或**與來源同段數的 SRT**。
- 條數對不上會直接報錯並提示，不會默默錯位。
- 第一次抽字幕用什麼模型都沒關係，`--source-srt` 會直接沿用該檔的段落切分。
- 需要簡體時就翻成簡體，此時不必加 `-t`。
- **使用者沒特別交代時，一律走「AI 自己翻」流程，不要主動加 `--translator google`。**
- 只有使用者說「用 Google 翻譯」「不用 AI」「快就好」時，才用 `--translator google`。

## 參數

| 參數 | 說明 | 預設 |
|------|------|------|
| `-o, --output` | 輸出影片路徑 | `<影片名>_<模式>.mp4` |
| `-l, --language` | 來源語言 | `en` |
| `-t, --target` | 目標語言 | `zh-TW`（繁體中文） |
| `-m, --model` | Whisper 模型：`tiny`/`base`/`small`/`medium`/`large-v3`/`large-v3-turbo`/`distil-large-v3` | `small` |
| `--fontsize` | 字號 | `14`（卡拉OK建議 `24`） |
| `--margin` | 底部邊距 | `25` |
| `--srt-only` | 只產生字幕檔 | - |
| `--source-only` / `--chinese-only` | 僅原文 / 僅譯文 | - |
| `--karaoke` | 逐詞高亮（輸出 .ass） | - |
| `--highlight-color` | 高亮色，ASS 格式 | `&H00FFFF&`（黃） |
| `--no-speech-threshold` | 非語音過濾閾值 0-1 | `0.6` |
| `--translation-file` | 外部譯文檔（AI 翻譯模式），不呼叫任何翻譯接口 | - |
| `--source-srt` | 沿用現成原文字幕，跳過 Whisper 辨識 | - |
| `--translator` | 翻譯引擎：`auto`（有 AI 設定就用 AI）、`ai`、`google`（備用）、`mymemory` | `auto` |
| `--fallback` | AI 失敗時的備援，可選 `google` | `none` |
| `--ai-model` | AI 模型名稱 | `AI_TRANSLATE_MODEL` 或 `gpt-4o-mini` |
| `--ai-base-url` | OpenAI 相容接口網址 | `AI_TRANSLATE_BASE_URL` 或 OpenAI 官方 |
| `--ai-api-key` | AI 接口金鑰（建議用環境變數） | `AI_TRANSLATE_API_KEY` |

目標語言填 `zh-TW` 得到繁體中文，填 `zh-CN` 得到簡體中文。

## 輸出檔案

| 模式 | 字幕 | 影片 |
|------|------|------|
| 預設雙語 | `*_bilingual.srt` | `*_bilingual.mp4` |
| 僅譯文 | `*_zh.srt` | `*_zh.mp4` |
| 僅原文 | `*_source.srt` | `*_source.mp4` |
| 卡拉OK | `*_karaoke.ass` | `*_karaoke.mp4` |

字幕與影片預設落在**輸入影片所在目錄**。

## 依賴與排錯

安裝（本機已裝好 faster-whisper 與 CUDA 依賴，指令僅作記錄）：

```bash
pip install faster-whisper "av<19" "huggingface_hub<2" nvidia-cublas-cu12 nvidia-cudnn-cu12
# Apple Silicon 上改用：pip install mlx-whisper
```

- 首次執行會自動下載 Whisper 模型（small 約 500MB），請留出時間；之後走本機快取。
- 模型選擇（本機 RTX 4060 實測 125 秒音訊）：`distil-large-v3` 最快（3.69s，34x 即時）；`small` 4.40s；`large-v3-turbo` 5.01s 但錯誤率最低（1.2%）。三個都已在快取，不用下載。
- 腳本已固定 `condition_on_previous_text=False`：這讓 large-v3-turbo 快一倍且錯誤率從 12.1% 降到 1.2%（否則它在音訊結尾會幻聽出原文沒有的內容）。不要改回 True。
- 出現 `Library cublas64_12.dll is not found` → 缺 NVIDIA 執行庫，裝 `nvidia-cublas-cu12 nvidia-cudnn-cu12`。腳本已自動註冊這些 DLL 目錄。
- 出現 `open() got an unexpected keyword argument 'metadata_errors'` → PyAV 版本過新，`pip install "av<19"`。
- 出現 `翻譯接口返回 429（請求太頻繁）` → 只在你明確使用 `--translator google` 時才會發生；Google 免費接口會限流，腳本會自動改走 MyMemory。預設 AI 模式不會有這個問題。
- AI 翻譯報錯（401/403）→ 檢查 `AI_TRANSLATE_API_KEY` 是否正確；若用本機 Ollama，確認服務已啟動且 `AI_TRANSLATE_BASE_URL` 結尾是 `/v1`。
- 若譯文與原文相同 → 表示翻譯接口沒連上。AI 模式可加 `--fallback google` 當備援；或先用 `--source-only` 只做辨識，再讓 AI 自己翻。
- 燒錄很慢 → FFmpeg 精簡版可能沒有硬體編碼器，腳本會依序回退到 libx264。

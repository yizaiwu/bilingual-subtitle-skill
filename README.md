# 雙語字幕生成器（Bilingual Subtitle Generator）

> 給一個影片，自動聽出對白、翻譯成繁體中文，把「原文 + 譯文」兩行字幕燒進畫面。
> 支援卡拉 OK 逐詞高亮、僅原文、僅譯文，以及 99 種語言。

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Translation](https://img.shields.io/badge/translation-AI%20first-blueviolet)

---

## 原始作者與授權（請先看這裡）

本專案是 **[vorojar/bilingual-subtitle-skill](https://github.com/vorojar/bilingual-subtitle-skill)** 的修改版（fork）。

- **原始專案作者：vorojar** — <https://github.com/vorojar/bilingual-subtitle-skill>
- 核心流程、卡拉 OK 字幕、硬體加速與燒錄架構，皆來自原作者。
- 本專案依原專案的 **MIT License** 釋出；原始碼版權歸原作者所有，修改部分版權歸乙仔所有。
- 完整授權條文請見 [LICENSE](LICENSE)。

> 如果你喜歡這個專案，請也給[原始專案](https://github.com/vorojar/bilingual-subtitle-skill)一顆星。

---

## 這個版本改了什麼？

一句話：**翻譯預設改用 AI，Google 翻譯退居可選備用**，並修掉一堆在原專案上跑不起來、或默默出錯的問題。

以下是乙仔用愛發電慢慢磨出來的修改：

### 1. 翻譯預設改為 AI，Google 改為可選備用

- 新增 `--translator {auto,ai,google,mymemory}`，預設 `auto`。
- 有 AI 設定就用 AI；沒設定會停下並提示做法，**不會偷偷連 Google**。
- 想用 Google 必須明確加 `--translator google`。
- 新增 `--fallback google`：AI 失敗的批次才自動退回 Google。
- 支援任何 **OpenAI 相容接口**：OpenAI、DeepSeek、Groq、OpenRouter、本機 Ollama / LM Studio 等。
- 也可以用 `--source-srt` + `--translation-file`，讓正在對話的 AI 自己翻，**完全不需要 API 金鑰**。

### 2. Whisper GPU 偵測不再依賴 PyTorch

- 改用 `ctranslate2` 偵測 CUDA，並自動把 pip 安裝的 cuBLAS / cuDNN DLL 目錄註冊進 Windows 搜尋路徑。
- GPU 真的不可用時才回退 CPU int8。

### 3. 依賴版本修正

- PyAV 19 移除 `metadata_errors` 參數會讓 faster-whisper 直接 TypeError → 固定 `av<19`。
- `hf_xet` 與 `huggingface_hub` 版本衝突會讓模型下載失敗 → 固定 `huggingface_hub<2`。

### 4. 翻譯失敗不再默默出錯

- 429 / 5xx 自動指數退避重試。
- Google 被限流時自動改走 MyMemory。
- 最後還是翻不成，會在結尾明確告訴你有幾條失敗，不會把原文當譯文混過去。

### 5. 預設繁體中文

- 原作者預設 `zh-CN`，本版改為 `zh-TW`（繁體中文、台灣用語）。
- 終端機提示訊息也一併繁體化。需要簡體時加 `-t zh-CN` 即可。

### 6. 修正 large-v3-turbo 的「幻聽」

- 固定 `condition_on_previous_text=False`。
- 實測 125 秒音訊：turbo 從 10.14 秒降到 5.01 秒，錯誤率從 12.1% 降到 1.2%。

### 7. 可重複利用既有字幕

- `--source-srt`：沿用已抽好的原文字幕，跳過 Whisper。
- `--translation-file`：帶入外部譯文檔，條數對不上會直接報錯，不會默默錯位。
- 想換字級、換邊距重燒時，幾秒鐘就能完成。

### 8. 文件補齊

- 完整中文使用教學、模型速度／準確率實測、常見錯誤排解。

---

## 功能特色

- **硬體自動加速**：Apple Silicon（mlx-whisper）、NVIDIA GPU（faster-whisper CUDA）、CPU int8。
- **多種輸出模式**：雙語、僅譯文、僅原文、卡拉 OK 逐詞高亮。
- **AI 優先翻譯**：懂上下文，人名、術語、語氣比免費翻譯接口準。
- **一鍵燒錄**：FFmpeg + libass，自動挑選 NVENC / AMF / QSV / VideoToolbox / libx264。
- **99 種語言**：中英、日中、韓中、英韓……用 `-l` / `-t` 指定即可。
- **可完全離線翻譯**：搭配本機 Ollama，或由 AI 直接翻譯，不連任何翻譯網站。

---

## 安裝

### 1. 取得專案

```bash
git clone https://github.com/<你的帳號>/bilingual-subtitle-skill.git
cd bilingual-subtitle-skill
```

> 若要在 u1s1 / Claude Code 等支援 skill 的環境中使用，把整個資料夾放進 skills 目錄即可，例如
> `C:\Users\<你>\.agents\skills\bilingual-subtitle`（Windows）或 `~/.agents/skills/bilingual-subtitle`（macOS / Linux）。

### 2. 安裝 Python 依賴

```bash
# NVIDIA GPU / CPU（Windows、Linux）
pip install faster-whisper "av<19" "huggingface_hub<2" nvidia-cublas-cu12 nvidia-cudnn-cu12

# Apple Silicon
pip install mlx-whisper
```

### 3. 安裝 FFmpeg

- Windows：下載 FFmpeg 並加入 `PATH`（需包含 libass）
- macOS：`brew install ffmpeg`
- Linux：`sudo apt install ffmpeg`

確認可用：

```bash
ffmpeg -version
ffprobe -version
```

---

## 快速開始

### 預設流程：AI 自己翻（不用 API 金鑰）

```bash
# 步驟 1：抽出原文字幕（不做翻譯）
python scripts/process.py video.mp4 --source-only --srt-only
#   -> video_source.srt

# 步驟 2：請 AI 讀 video_source.srt，逐條翻譯，
#         寫成一行一條的純文字檔 video_zh.txt（條數、順序要一致）

# 步驟 3：合併雙語字幕並燒錄（不再跑 Whisper）
python scripts/process.py video.mp4 \
  --source-srt video_source.srt \
  --translation-file video_zh.txt
```

在支援 skill 的 AI 助手中，直接說「用 skill 給 video.mp4 加中英字幕」就會自動走這個流程。

### 一句指令：腳本直接呼叫 AI 接口

設定環境變數後，預設的 `--translator auto` 會自動使用 AI。

**Windows（cmd）**

```bat
set AI_TRANSLATE_API_KEY=sk-...
set AI_TRANSLATE_BASE_URL=https://api.openai.com/v1
set AI_TRANSLATE_MODEL=gpt-4o-mini
python scripts\process.py video.mp4
```

**macOS / Linux**

```bash
export AI_TRANSLATE_API_KEY=sk-...
export AI_TRANSLATE_BASE_URL=https://api.openai.com/v1
export AI_TRANSLATE_MODEL=gpt-4o-mini
python scripts/process.py video.mp4
```

**本機 Ollama（不用金鑰、可離線）**

```bash
export AI_TRANSLATE_BASE_URL=http://127.0.0.1:11434/v1
export AI_TRANSLATE_MODEL=qwen2.5:7b
python scripts/process.py video.mp4
```

### 備用：Google 翻譯（明確指定才用）

```bash
# 整個流程都用 Google（原專案行為）
python scripts/process.py video.mp4 --translator google

# AI 優先，AI 失敗的批次才退回 Google
python scripts/process.py video.mp4 --translator ai --fallback google

# 只用 MyMemory（免費、免金鑰，品質較差）
python scripts/process.py video.mp4 --translator mymemory
```

### 其他常用範例

```bash
# 只要字幕檔，不燒錄（最快，適合先看效果）
python scripts/process.py video.mp4 --srt-only

# 僅原文（學語言、或只想留原文字幕）
python scripts/process.py video.mp4 --source-only

# 僅譯文（影片本身已有原文硬字幕）
python scripts/process.py video.mp4 --chinese-only

# 卡拉 OK 逐詞高亮（輸出 .ass，字大一點）
python scripts/process.py video.mp4 --karaoke --fontsize 24

# 日文影片翻繁體中文，用較準的模型
python scripts/process.py video.mp4 -l ja -m large-v3-turbo

# 簡體中文
python scripts/process.py video.mp4 -t zh-CN
```

---

## AI 翻譯設定

| 環境變數 | 說明 | 預設 |
|---|---|---|
| `AI_TRANSLATE_API_KEY` | API 金鑰（本機 Ollama 可省略） | 無 |
| `AI_TRANSLATE_BASE_URL` | OpenAI 相容接口網址 | 有金鑰時為 `https://api.openai.com/v1` |
| `AI_TRANSLATE_MODEL` | 模型名稱 | `gpt-4o-mini` |
| `AI_TRANSLATE_MAX_TOKENS` | 單次回覆上限 | `4096` |
| `AI_TRANSLATE_TIMEOUT` | 單次請求逾時（秒） | `180` |

也接受 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 作為備援。

### 翻譯引擎比較

| 引擎 | 參數 | 需要金鑰 | 品質 | 適合情境 |
|---|---|---|---|---|
| AI（自己翻） | `--translation-file` | 否 | ★★★★★ | 預設、正式成品 |
| AI（API） | `--translator ai` | 視服務而定 | ★★★★☆ | 想一句指令跑完 |
| Google | `--translator google` | 否 | ★★☆☆☆ | 備用、快速預覽 |
| MyMemory | `--translator mymemory` | 否 | ★☆☆☆☆ | Google 也被限流時 |

---

## 參數一覽

| 參數 | 說明 | 預設 |
|---|---|---|
| `-o, --output` | 輸出影片路徑 | `<影片名>_<模式>.mp4` |
| `-l, --language` | 來源語言 | `en` |
| `-t, --target` | 目標語言 | `zh-TW`（繁體中文） |
| `-m, --model` | Whisper 模型 | `small` |
| `--fontsize` | 字體大小 | `14`（卡拉 OK 建議 `24`） |
| `--margin` | 字幕底部邊距 | `25` |
| `--srt-only` | 只產生字幕檔，不燒錄 | - |
| `--source-only` | 只輸出原文字幕 | - |
| `--chinese-only` | 只輸出譯文字幕 | - |
| `--karaoke` | 卡拉 OK 逐詞高亮（輸出 `.ass`） | - |
| `--highlight-color` | 高亮顏色（ASS 格式） | `&H00FFFF&`（黃） |
| `--no-speech-threshold` | 非語音過濾閾值 0–1 | `0.6` |
| `--source-srt` | 沿用現成原文字幕，跳過 Whisper | - |
| `--translation-file` | 外部譯文檔（AI 翻譯模式） | - |
| `--translator` | `auto` / `ai` / `google` / `mymemory` | `auto` |
| `--fallback` | AI 失敗時的備援 | `none`（可設 `google`） |
| `--ai-model` | AI 模型名稱 | `AI_TRANSLATE_MODEL` 或 `gpt-4o-mini` |
| `--ai-base-url` | OpenAI 相容接口網址 | `AI_TRANSLATE_BASE_URL` |
| `--ai-api-key` | AI 接口金鑰（建議用環境變數） | `AI_TRANSLATE_API_KEY` |

---

## 輸出檔案

| 模式 | 字幕 | 影片 |
|---|---|---|
| 預設雙語 | `*_bilingual.srt` | `*_bilingual.mp4` |
| 僅譯文 | `*_zh.srt` | `*_zh.mp4` |
| 僅原文 | `*_source.srt` | `*_source.mp4` |
| 卡拉 OK | `*_karaoke.ass` | `*_karaoke.mp4` |

字幕與影片預設輸出到**輸入影片所在目錄**。

譯文檔（`--translation-file`）支援兩種格式：

1. 一行一條的純文字（最簡單，推薦）
2. 與來源同段數的 SRT

條數或順序對不上會直接報錯，不會默默錯位。

---

## 效能實測

### Whisper 模型（RTX 4060 Laptop 8GB，125 秒英文音訊）

| 模型 | 推論時間 | 即時倍速 | 辨識錯誤率 | 模型大小 |
|---|---|---|---|---|
| `distil-large-v3` | 3.69s | 34.0x | 1.6% | 1443 MB |
| `small`（預設） | 4.40s | 28.5x | 1.6% | 461 MB |
| `large-v3-turbo` | 5.01s | 25.0x | 1.2% | 1543 MB |

- 想要快 → `distil-large-v3`
- 想要最準 → `large-v3-turbo`
- 真實影片（口音、雜訊、專有名詞）差距會比合成語音更明顯

### 硬體加速

**語音辨識**

| 平台 | 方案 | 約略速度 |
|---|---|---|
| Apple Silicon | mlx-whisper | ~15x 即時 |
| NVIDIA GPU | faster-whisper CUDA | ~8x 即時 |
| CPU | faster-whisper int8 | ~1x 即時 |

**影片編碼**

| 平台 | 編碼器 | 約略速度 |
|---|---|---|
| macOS | VideoToolbox | ~5x 即時 |
| NVIDIA | NVENC | ~8x 即時 |
| AMD | AMF | ~5x 即時 |
| Intel | QuickSync | ~5x 即時 |
| CPU | libx264 | ~1x 即時 |

> 以上為原作者與本專案在特定機器上的參考值，實際速度依硬體、影片長度與音訊內容而異。

---

## 常見問題

**Q：第一次跑很久，卡在下載？**
A：第一次會下載 Whisper 模型（`small` 約 500 MB），之後走本機快取。

**Q：出現 `Library cublas64_12.dll is not found`**
A：缺 NVIDIA 執行庫，執行 `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`。腳本已會自動註冊 DLL 目錄。

**Q：出現 `open() got an unexpected keyword argument 'metadata_errors'`**
A：PyAV 版本太新，執行 `pip install "av<19"`。

**Q：出現 `翻譯接口返回 429（請求太頻繁）`**
A：只會在你明確使用 `--translator google` 時遇到。腳本會自動改走 MyMemory；預設 AI 模式不會有這個問題。

**Q：AI 翻譯出現 401 / 403**
A：檢查 `AI_TRANSLATE_API_KEY` 是否正確；若用本機 Ollama，確認服務已啟動，且 `AI_TRANSLATE_BASE_URL` 結尾是 `/v1`。

**Q：翻譯出來還是原文**
A：代表翻譯接口沒連上。先確認 AI 設定或額度；也可以加 `--fallback google` 當備援。

**Q：燒錄很慢**
A：FFmpeg 精簡版可能沒有硬體編碼器，腳本會依序回退到 libx264（純 CPU）。

**Q：字幕出來了但影片沒字幕**
A：確認 FFmpeg 有 libass，可用 `ffmpeg -filters | grep subtitles` 檢查。

**Q：想調整字級、位置，需要重跑語音辨識嗎？**
A：不用。用 `--source-srt` + `--translation-file` 重跑，幾秒鐘就能重新燒錄。

---

## 專案結構

```
bilingual-subtitle-skill/
├── README.md                # 本文件
├── LICENSE                  # MIT（保留原作者版權）
├── skill.md                 # Skill 定義（給 AI 助手讀）
├── 使用教學.txt              # 完整中文使用教學
└── scripts/
    ├── process.py           # 一鍵處理：辨識 → 翻譯 → 合併 → 燒錄
    ├── extract_srt.py       # 只做語音辨識
    ├── translate_srt.py     # 只做翻譯（AI 優先，Google 可選）
    ├── merge_srt.py         # 只做字幕合併
    └── burn_srt.py          # 只做燒錄
```

---

## 致謝

- **原始專案：[vorojar/bilingual-subtitle-skill](https://github.com/vorojar/bilingual-subtitle-skill)**
  沒有原作者打下的基礎，就沒有這個版本。請務必支持原始專案。
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — 高效能 Whisper 推論
- [mlx-whisper](https://github.com/ml-explore/mlx-examples) — Apple Silicon 加速
- [FFmpeg](https://ffmpeg.org/) / libass — 字幕燒錄

## 授權

本專案採用 **MIT License**。原始碼版權歸 **vorojar** 所有，乙仔的修改同樣以 MIT 釋出。
完整條文請見 [LICENSE](LICENSE)。

---

Built with ❤️ by 乙仔

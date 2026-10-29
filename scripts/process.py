#!/usr/bin/env python
"""
雙語字幕一鍵生成工具
- 使用 Whisper 提取字幕（自動檢測 GPU）
- 翻譯：預設 AI（OpenAI 相容接口），Google 翻譯為明確指定才使用的備用
- 合併雙語字幕
- GPU 加速燒錄字幕
"""
import sys
import os

# Windows 控制台 UTF-8 編碼支援
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import argparse
import re
import json
import time
import platform
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============== 工具函式 ==============

def format_duration(seconds):
    """格式化長度"""
    if seconds < 60:
        return f'{seconds:.1f}秒'
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f'{int(m)}分{s:.1f}秒'
    else:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f'{int(h)}時{int(m)}分{s:.1f}秒'

def format_size(bytes):
    """格式化檔案大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f'{bytes:.1f}{unit}'
        bytes /= 1024
    return f'{bytes:.1f}TB'

def format_video_duration(seconds):
    """格式化影片長度 (mm:ss)"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f'{h}:{m:02}:{s:02}'
    return f'{m}:{s:02}'

def get_media_info(video):
    """取得影片詳細資訊"""
    info = {
        'size': 0,
        'duration': 0,
        'width': 0,
        'height': 0,
        'codec': '',
        'bitrate': 0
    }

    # 檔案大小
    try:
        info['size'] = os.path.getsize(video)
    except:
        pass

    # 使用 ffprobe 取得詳細資訊
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', video],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)

        # 時長
        if 'format' in data and 'duration' in data['format']:
            info['duration'] = float(data['format']['duration'])

        # 影片串流資訊
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                info['width'] = stream.get('width', 0)
                info['height'] = stream.get('height', 0)
                info['codec'] = stream.get('codec_name', '')
                if 'bit_rate' in stream:
                    info['bitrate'] = int(stream['bit_rate'])
                break

        # 如果影片流沒有位元速率，用總位元速率
        if not info['bitrate'] and 'format' in data and 'bit_rate' in data['format']:
            info['bitrate'] = int(data['format']['bit_rate'])
    except:
        pass

    return info

def print_file_comparison(input_video, output_video, srt_file):
    """列印輸入輸出檔案對比"""
    input_info = get_media_info(input_video)
    output_info = get_media_info(output_video)

    print('\n檔案資訊對比:')
    print('-' * 50)
    print(f'{"":12} {"輸入":>16}    {"輸出":>16}')
    print('-' * 50)

    # 檔案大小
    print(f'{"大小":12} {format_size(input_info["size"]):>16}    {format_size(output_info["size"]):>16}')

    # 時長
    if input_info['duration']:
        print(f'{"長度":12} {format_video_duration(input_info["duration"]):>16}    {format_video_duration(output_info["duration"]):>16}')

    # 解析度
    if input_info['width']:
        in_res = f'{input_info["width"]}x{input_info["height"]}'
        out_res = f'{output_info["width"]}x{output_info["height"]}'
        print(f'{"解析度":12} {in_res:>16}    {out_res:>16}')

    # 編碼
    if input_info['codec']:
        print(f'{"編碼":12} {input_info["codec"]:>16}    {output_info["codec"]:>16}')

    # 位元速率
    if input_info['bitrate']:
        in_br = f'{input_info["bitrate"]//1000}kbps'
        out_br = f'{output_info["bitrate"]//1000}kbps'
        print(f'{"位元速率":12} {in_br:>16}    {out_br:>16}')

    # SRT 檔案大小
    try:
        srt_size = os.path.getsize(srt_file)
        print(f'{"字幕檔案":12} {format_size(srt_size):>16}')
    except:
        pass

    print('-' * 50)

def format_ts(sec):
    """轉換秒數為 SRT 時間戳記格式"""
    h, m, s = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    return f'{h:02}:{m:02}:{s:06.3f}'.replace('.', ',')

def format_ass_ts(sec):
    """轉換秒數為 ASS 時間戳記格式 (H:MM:SS.cc)"""
    h, m, s = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    return f'{h}:{m:02}:{s:05.2f}'

def parse_srt(content):
    """解析 SRT 內容"""
    blocks = []
    for block in re.split(r'\n\n+', content.strip()):
        lines = block.split('\n')
        if len(lines) >= 3:
            blocks.append({
                'index': lines[0],
                'timestamp': lines[1],
                'text': '\n'.join(lines[2:])
            })
    return blocks

def write_srt(blocks, output):
    """寫入 SRT 檔案"""
    with open(output, 'w', encoding='utf-8') as f:
        for b in blocks:
            f.write(f"{b['index']}\n{b['timestamp']}\n{b['text']}\n\n")

# ============== 步驟 1: 提取字幕 ==============

def setup_nvidia_dlls():
    """Windows: 將 pip 安裝的 cuBLAS/cuDNN DLL 目錄加入搜尋路徑（GPU 加速必需）"""
    if platform.system() != 'Windows':
        return
    try:
        import importlib.util
        for pkg in ('nvidia.cublas', 'nvidia.cudnn'):
            try:
                spec = importlib.util.find_spec(pkg)
            except (ImportError, ValueError):
                spec = None
            if not spec or not spec.submodule_search_locations:
                continue
            for loc in spec.submodule_search_locations:
                for sub in ('bin', 'lib'):
                    d = os.path.join(loc, sub)
                    if not os.path.isdir(d):
                        continue
                    try:
                        os.add_dll_directory(d)
                    except Exception:
                        pass
                    os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass


def run_faster_whisper(video, model, language, word_timestamps, no_speech_threshold, device, compute_type, label):
    """用 faster-whisper 提取字幕；失敗時返回 None 以便回退到其它後端"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    try:
        print(f'  引擎: faster-whisper ({label})')
        whisper_model = WhisperModel(model, device=device, compute_type=compute_type)
        segs, _ = whisper_model.transcribe(
            video,
            language=language,
            word_timestamps=word_timestamps,
            vad_filter=True,
            # 不拿上一段的結果當上下文。實測（RTX 4060, 125 秒音訊）關掉之後
            # large-v3-turbo 快一倍（10.1s -> 5.0s）、錯誤率從 12.1% 降到 1.2%，
            # 因為它會在結尾默默幻聽出原文沒有的句子。distil 系列則幾乎無感。
            condition_on_previous_text=False,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        segments = []
        filtered_count = 0
        for s in segs:
            # 過濾高 no_speech_prob 的片段
            if s.no_speech_prob > no_speech_threshold:
                filtered_count += 1
                continue
            seg = {'start': s.start, 'end': s.end, 'text': s.text}
            if word_timestamps and s.words:
                seg['words'] = [{'start': w.start, 'end': w.end, 'word': w.word} for w in s.words]
            segments.append(seg)
        return segments, filtered_count
    except Exception as e:
        print(f'  {label} 不可用 ({type(e).__name__}: {str(e)[:120]})')
        return None


def extract_subtitles(video, output, language='en', model='small', word_timestamps=False, no_speech_threshold=0.6):
    """使用 Whisper 提取字幕，自動檢測硬體"""
    step_start = time.time()
    print(f'\n[1/4] 提取字幕...')
    print(f'  影片: {video}')
    print(f'  語言: {language}, 模型: {model}')
    print(f'  VAD 過濾: 已啟用')
    if word_timestamps:
        print(f'  詞級時間戳記: 已啟用')

    filtered_count = 0

    # 優先順序 1: Apple Silicon (mlx-whisper)
    if platform.system() == 'Darwin' and platform.machine() == 'arm64':
        try:
            import mlx_whisper
            print('  引擎: mlx-whisper (Apple Silicon)')
            result = mlx_whisper.transcribe(
                video,
                path_or_hf_repo=f'mlx-community/whisper-{model}-mlx',
                word_timestamps=word_timestamps
            )
            # mlx-whisper 的 no_speech_prob 過濾
            segments = []
            for seg in result['segments']:
                if seg.get('no_speech_prob', 0) > no_speech_threshold:
                    filtered_count += 1
                    continue
                segments.append(seg)
            print(f'  提取 {len(segments)} 條字幕（過濾 {filtered_count} 條非語音），耗時 {format_duration(time.time() - step_start)}')
            return segments
        except ImportError:
            pass

    # 優先順序 2: NVIDIA CUDA GPU (透過 ctranslate2 檢測，無需安裝 torch)
    try:
        import ctranslate2
        has_cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        has_cuda = False

    if has_cuda:
        setup_nvidia_dlls()
        try:
            gpu_name = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True, text=True, timeout=10
            ).stdout.strip().splitlines()[0]
        except Exception:
            gpu_name = 'NVIDIA GPU'
        result = run_faster_whisper(video, model, language, word_timestamps,
                                    no_speech_threshold, 'cuda', 'float16', f'CUDA GPU: {gpu_name}')
        if result:
            segments, filtered_count = result
            print(f'  提取 {len(segments)} 條字幕（過濾 {filtered_count} 條非語音），耗時 {format_duration(time.time() - step_start)}')
            return segments

    # 優先順序 3: CPU 回退
    result = run_faster_whisper(video, model, language, word_timestamps,
                                no_speech_threshold, 'cpu', 'int8', 'CPU int8')
    if result:
        segments, filtered_count = result
        print(f'  提取 {len(segments)} 條字幕（過濾 {filtered_count} 條非語音），耗時 {format_duration(time.time() - step_start)}')
        return segments

    print('  錯誤: 未找到 Whisper 後端，請安裝 faster-whisper 或 mlx-whisper')
    sys.exit(1)

# ============== 步驟 2: 翻譯字幕 ==============
# 預設用 AI 翻譯。Google 翻譯改成「明確指定才會用」的備用功能：
#   --translator ai                      AI（預設；需要 OpenAI 相容接口設定）
#   --translator ai --fallback google    AI 失敗時才退回 Google
#   --translator google                  直接用 Google（舊行為）
# 完全不想設 API 金鑰也沒關係：讓 AI（正在對話的模型）翻好，
# 再用 --source-srt + --translation-file 帶進來，全程不連翻譯網站。

LANGUAGE_NAMES = {
    'en': 'English', 'zh': 'Chinese', 'zh-TW': 'Traditional Chinese',
    'zh-CN': 'Simplified Chinese', 'zh-Hant': 'Traditional Chinese',
    'zh-Hans': 'Simplified Chinese', 'ja': 'Japanese', 'ko': 'Korean',
    'fr': 'French', 'de': 'German', 'es': 'Spanish', 'ru': 'Russian',
    'pt': 'Portuguese', 'it': 'Italian', 'ar': 'Arabic', 'th': 'Thai',
    'vi': 'Vietnamese', 'id': 'Indonesian', 'tr': 'Turkish', 'hi': 'Hindi',
}


def ai_config(model=None, base_url=None, api_key=None):
    """讀取 AI 翻譯設定。優先順序：命令列 > AI_TRANSLATE_* > OPENAI_* > 預設值
       本機服務（Ollama / LM Studio）可以不用金鑰。
    """
    base = (base_url
            or os.environ.get('AI_TRANSLATE_BASE_URL')
            or os.environ.get('OPENAI_BASE_URL')
            or '')
    key = (api_key
           or os.environ.get('AI_TRANSLATE_API_KEY')
           or os.environ.get('OPENAI_API_KEY')
           or '')
    name = (model
            or os.environ.get('AI_TRANSLATE_MODEL')
            or os.environ.get('OPENAI_MODEL')
            or '')
    if not base and key:
        base = 'https://api.openai.com/v1'
    return {
        'base_url': base.rstrip('/'),
        'api_key': key,
        'model': name or 'gpt-4o-mini',
        'max_tokens': int(os.environ.get('AI_TRANSLATE_MAX_TOKENS', '4096')),
        'timeout': int(os.environ.get('AI_TRANSLATE_TIMEOUT', '180')),
    }


def ai_is_ready(cfg):
    """有沒有可用的 AI 翻譯設定（本機服務允許沒有金鑰）"""
    if not cfg.get('base_url'):
        return False
    if cfg.get('api_key'):
        return True
    base = cfg['base_url']
    return any(h in base for h in ('localhost', '127.0.0.1', '0.0.0.0', '::1',
                                   'host.docker.internal'))


def print_ai_hint():
    """沒設定 AI 時，告訴使用者三條路"""
    print('錯誤: 目前沒有可用的 AI 翻譯設定。')
    print('')
    print('  方法一（推薦，不用金鑰）：讓 AI 自己翻')
    print('    python process.py <影片> --source-only --srt-only')
    print('    請 AI 讀產生的 *_source.srt，寫成一行一條的譯文檔，再執行：')
    print('    python process.py <影片> --source-srt <原文字幕> --translation-file <譯文檔>')
    print('')
    print('  方法二：設定 OpenAI 相容的 AI 接口（環境變數）')
    print('    AI_TRANSLATE_API_KEY=...      金鑰')
    print('    AI_TRANSLATE_BASE_URL=...     接口網址（預設 https://api.openai.com/v1）')
    print('    AI_TRANSLATE_MODEL=...        模型名稱（預設 gpt-4o-mini）')
    print('    本機 Ollama 範例：')
    print('      AI_TRANSLATE_BASE_URL=http://127.0.0.1:11434/v1 AI_TRANSLATE_MODEL=qwen2.5:7b')
    print('')
    print('  方法三（備用）：真的要用 Google 翻譯，明確加上 --translator google')


def _ai_http_json(url, payload, headers, timeout=180, retries=3):
    """POST JSON，遇到 429/5xx 自動重試（指數退避）"""
    data = json.dumps(payload).encode('utf-8')
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8', 'replace')[:300]
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f'\n    AI 接口返回 {e.code}，{wait} 秒後重試...', flush=True)
                time.sleep(wait)
                continue
            print(f'\n    AI 接口錯誤 {e.code}: {body}', flush=True)
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            print(f'\n    AI 接口連線失敗: {e}', flush=True)
            return None
    return None


def _parse_ai_list(content, expected):
    """從模型回覆裡取出等長的字串陣列（JSON 優先，失敗才用一行一條）"""
    text = content.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[A-Za-z]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    start, end = text.find('['), text.rfind(']')
    if start != -1 and end > start:
        try:
            arr = json.loads(text[start:end + 1])
            if isinstance(arr, list) and len(arr) == expected:
                return [str(x).strip() for x in arr]
        except Exception:
            pass
    # 退路：一行一條（順便去掉行號）
    lines = [re.sub(r'^\s*\d+[.、)]\s*', '', l).strip()
             for l in text.split('\n') if l.strip()]
    if len(lines) == expected:
        return lines
    return None


def translate_ai_batch(texts, source='en', target='zh-TW', cfg=None):
    """用 AI 翻譯一批字幕，回傳與輸入等長的字串清單（失敗回 None）"""
    if not texts:
        return []
    cfg = cfg or ai_config()
    src = LANGUAGE_NAMES.get(source, source)
    dst = LANGUAGE_NAMES.get(target, target)
    system = (
        f'你是專業字幕翻譯。把每一條字幕從 {src} 翻成 {dst}。\n'
        '規則：\n'
        '1. 只輸出 JSON 字串陣列，元素數量與輸入完全相同、順序一致。\n'
        '2. 一條輸入對應一條輸出，不可合併、拆分、省略或加註解。\n'
        '3. 用自然、口語、簡短、適合字幕的語氣，不要逐字硬譯。\n'
        '4. 人名、品牌、專有名詞用常見且一致的譯法；台灣正體中文請用台灣慣用語。\n'
        '5. 不要加程式碼圍籬或任何說明文字。'
    )
    payload = {
        'model': cfg['model'],
        'temperature': 0.2,
        'max_tokens': cfg['max_tokens'],
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(texts, ensure_ascii=False)},
        ],
    }
    headers = {'Content-Type': 'application/json'}
    if cfg.get('api_key'):
        headers['Authorization'] = f"Bearer {cfg['api_key']}"
    result = _ai_http_json(cfg['base_url'] + '/chat/completions', payload, headers,
                           timeout=cfg.get('timeout', 180))
    if not result:
        return None
    try:
        content = result['choices'][0]['message']['content']
    except Exception:
        return None
    return _parse_ai_list(content, len(texts))


def translate_batch(texts, source='en', target='zh-TW'):
    """批次翻譯（使用 Google Translate）"""
    if not texts:
        return texts

    # Google 已被限流時不再重試，直接交給逐條翻譯走備用介面
    if not GOOGLE_AVAILABLE:
        return None

    separator = '\n###\n'
    combined = separator.join(texts)

    url = 'https://translate.googleapis.com/translate_a/single'
    params = {
        'client': 'gtx',
        'sl': source,
        'tl': target,
        'dt': 't',
        'q': combined
    }

    full_url = url + '?' + urllib.parse.urlencode(params)

    result = fetch_json(full_url, timeout=30)
    if not result:
        return None
    translated = ''.join([item[0] for item in result[0] if item[0]])
    return translated.split('###')

# 翻譯介面開關：Google 被限流後自動切換到備用介面
GOOGLE_AVAILABLE = True

def fetch_json(full_url, timeout=30, retries=3, quiet=False):
    """請求介面，遇到限流/網路錯誤時自動重試（指數退避）"""
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                if not quiet:
                    print(f'\n    翻譯介面返回 {e.code}（請求太頻繁），{wait} 秒後重試...', flush=True)
                time.sleep(wait)
                continue
            return None
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return None
    return None

def translate_mymemory(text, source='en', target='zh-TW'):
    """備用翻譯介面（MyMemory，免費無需金鑰），Google 被限流時使用"""
    if not text.strip():
        return text
    langpair = f"{source}|{target}"
    url = 'https://api.mymemory.translated.net/get?' + urllib.parse.urlencode({'q': text, 'langpair': langpair})
    result = fetch_json(url, timeout=20, retries=2, quiet=True)
    if not result:
        return text
    translated = result.get('responseData', {}).get('translatedText', '')
    # MyMemory 出錯時會把錯誤資訊放在 translatedText 裡
    if not translated or 'MYMEMORY WARNING' in translated.upper() or 'INVALID' in translated.upper():
        return text
    return translated

def translate_single(text, source='en', target='zh-TW'):
    """單條翻譯：先用 Google，失敗（限流）時自動改走備用介面"""
    global GOOGLE_AVAILABLE

    if not text.strip():
        return text

    if GOOGLE_AVAILABLE:
        url = 'https://translate.googleapis.com/translate_a/single'
        params = {'client': 'gtx', 'sl': source, 'tl': target, 'dt': 't', 'q': text}
        full_url = url + '?' + urllib.parse.urlencode(params)
        result = fetch_json(full_url, timeout=10, retries=2)
        if result:
            try:
                return ''.join([item[0] for item in result[0] if item[0]])
            except Exception:
                pass
        GOOGLE_AVAILABLE = False
        print('\n    Google 翻譯不可用，後續改用備用介面 MyMemory（品質略差）', flush=True)

    return translate_mymemory(text, source, target)


def _google_translate_list(batch, source, target):
    """Google 批次翻譯，失敗時逐條翻"""
    result = translate_batch(batch, source, target)
    if result and len(result) == len(batch):
        return [r.strip() for r in result]
    print('  批次失敗，逐條翻譯')
    return [translate_single(t, source, target) for t in batch]


def translate_texts(texts, source='en', target='zh-TW', translator='ai',
                    fallback='none', ai_cfg=None, batch_size=None):
    """翻譯一串文字。translator: ai / google / mymemory
       回傳等長清單；翻譯失敗的條目會保留原文。
    """
    texts = [t.strip() for t in texts]
    if not texts:
        return []

    if translator == 'ai':
        cfg = ai_cfg or ai_config()
        size = batch_size or 20
        translated = []
        total = (len(texts) + size - 1) // size
        for i in range(0, len(texts), size):
            batch = texts[i:i + size]
            num = i // size + 1
            print(f'  AI 翻譯批次 {num}/{total}...', end=' ', flush=True)
            result = translate_ai_batch(batch, source, target, cfg)
            if result and len(result) == len(batch):
                translated.extend(result)
                print('完成')
                continue
            if fallback == 'google':
                print('失敗，改用 Google 翻譯這一批')
                translated.extend(_google_translate_list(batch, source, target))
            else:
                print('失敗，這一批保留原文')
                translated.extend(batch)
        return translated

    if translator == 'mymemory':
        return [translate_mymemory(t, source, target) for t in texts]

    # google（明確指定時才走這裡；被限流會自動改用 MyMemory）
    size = batch_size or 10
    translated = []
    total = (len(texts) + size - 1) // size
    for i in range(0, len(texts), size):
        batch = texts[i:i + size]
        num = i // size + 1
        print(f'  翻譯批次 {num}/{total}...', end=' ', flush=True)
        result = translate_batch(batch, source, target)
        if result and len(result) == len(batch):
            translated.extend([r.strip() for r in result])
            print('完成')
        else:
            print('批次失敗，逐條翻譯')
            translated.extend([translate_single(t, source, target) for t in batch])
        time.sleep(0.2)
    return translated

def parse_srt_ts(ts):
    """SRT 時間戳 -> 秒數"""
    m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', ts.strip())
    if not m:
        return None
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def srt_to_segments(path):
    """把現成的原文字幕讀回來當作 segments（跳過 Whisper 重跑）"""
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            blocks = parse_srt(f.read())
    except OSError as e:
        print(f'  錯誤: 讀不到原文字幕 {path} ({e})')
        return None

    segments = []
    for b in blocks:
        parts = b['timestamp'].split('-->')
        if len(parts) != 2:
            continue
        start, end = parse_srt_ts(parts[0]), parse_srt_ts(parts[1])
        if start is None or end is None:
            continue
        segments.append({'start': start, 'end': end, 'text': b['text']})

    if not segments:
        print(f'  錯誤: {path} 裡找不到有效的字幕段落')
        return None
    return segments


def read_translation_file(path, expected):
    """讀取外部譯文檔。支援兩種格式：
       1) SRT（段落數需與來源字幕相同）
       2) 純文字，一行一條譯文
    回傳譯文清單；數量對不上時回傳 None。
    """
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except OSError as e:
        print(f'  錯誤: 讀不到譯文檔 {path} ({e})')
        return None

    if '-->' in content:
        blocks = parse_srt(content)
        texts = [b['text'].replace('\n', ' ').strip() for b in blocks]
        kind = 'SRT'
    else:
        texts = [l.strip() for l in content.split('\n') if l.strip()]
        kind = '純文字（一行一條）'

    if len(texts) != expected:
        print(f'  錯誤: 譯文檔格式為 {kind}，但裡面有 {len(texts)} 條，來源字幕有 {expected} 條')
        print(f'  提示: 條數必須完全一致，順序也要對應')
        print(f'  最保險的做法：第二次執行時用 --source-srt 帶入第一次抽出的原文字幕，')
        print(f'  就會拿到一模一樣的段落數（順便省下一次 Whisper 辨識）')
        return None

    empty = sum(1 for t in texts if not t)
    if empty:
        print(f'  提醒: 有 {empty} 條譯文是空的，會直接顯示空白')
    print(f'  讀入譯文 {len(texts)} 條（{kind}）')
    return texts


def translate_subtitles(segments, source='en', target='zh-TW', translator='ai',
                        fallback='none', ai_cfg=None):
    """翻譯字幕"""
    step_start = time.time()
    print(f'\n[2/4] 翻譯字幕...')
    print(f'  語言: {source} -> {target}')
    print(f'  總計: {len(segments)} 條')

    if translator == 'ai':
        cfg = ai_cfg or ai_config()
        print(f'  引擎: AI ({cfg["model"]} @ {cfg["base_url"]})')
        if fallback == 'google':
            print('  備援: AI 失敗時改用 Google 翻譯')
    elif translator == 'google':
        print('  引擎: Google 翻譯（備用選項；限流時自動改走 MyMemory）')
    else:
        print('  引擎: MyMemory')

    texts = [s['text'].strip() for s in segments]
    translated = translate_texts(texts, source, target, translator, fallback, ai_cfg)

    # 統計沒翻譯成功（譯文與原文完全一樣）的條數，避免靜默失敗
    failed = sum(1 for src, dst in zip(texts, translated) if src and src == dst)
    if failed:
        if translator == 'ai':
            print(f'  警告: 有 {failed}/{len(texts)} 條未翻譯成功（AI 接口出錯或額度不足），這些條目會顯示原文')
            print('  建議: 稍後重試、檢查 AI 設定，或加 --fallback google 當備援')
        else:
            print(f'  警告: 有 {failed}/{len(texts)} 條未翻譯成功（翻譯介面限流或網路不通），這些條目譯文會與原文相同')
            print('  建議: 稍後重試，或先用 --source-only 只生成原文字幕')

    print(f'  翻譯 {len(translated)} 條字幕，耗時 {format_duration(time.time() - step_start)}')
    return translated

# ============== 步驟 3: 合併字幕 ==============

def generate_karaoke_ass(segments, output, fontsize=14, margin=25, highlight_color='&H00FFFF&'):
    """生成卡拉OK風格 ASS 字幕（逐詞高亮）"""
    step_start = time.time()
    print(f'\n[3/4] 生成卡拉OK字幕...')

    # ASS 檔案頭
    ass_header = f'''[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{fontsize},&HFFFFFF&,{highlight_color},&H000000&,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,{margin},1
Style: Highlight,Arial,{fontsize},{highlight_color},{highlight_color},&H000000&,&H80000000,1,0,0,0,100,100,0,0,1,2,1,2,10,10,{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''

    events = []
    for seg in segments:
        start_ts = format_ass_ts(seg['start'])
        end_ts = format_ass_ts(seg['end'])

        if 'words' in seg and seg['words']:
            # 有詞級時間戳記，生成卡拉OK效果
            karaoke_text = ''
            for word in seg['words']:
                # \kf 是漸變填充效果，duration 單位是釐秒 (1/100秒)
                duration_cs = int((word['end'] - word['start']) * 100)
                karaoke_text += f"{{\\kf{duration_cs}}}{word['word']}"
            events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{karaoke_text}")
        else:
            # 沒有詞級時間戳記，使用普通字幕
            events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{seg['text'].strip()}")

    with open(output, 'w', encoding='utf-8') as f:
        f.write(ass_header)
        f.write('\n'.join(events))

    print(f'  儲存到: {output}，耗時 {format_duration(time.time() - step_start)}')
    return output

def merge_bilingual(segments, translated_texts, output, chinese_only=False, source_only=False):
    """合併雙語字幕"""
    step_start = time.time()
    if source_only:
        mode = '僅原文'
    elif chinese_only:
        mode = '僅中文'
    else:
        mode = '雙語'
    print(f'\n[3/4] 生成{mode}字幕...')

    blocks = []
    for i, seg in enumerate(segments, 1):
        if source_only:
            text = seg['text'].strip()
        elif chinese_only:
            text = translated_texts[i-1].strip()
        else:
            text = f"{seg['text'].strip()}\n{translated_texts[i-1].strip()}"
        blocks.append({
            'index': str(i),
            'timestamp': f"{format_ts(seg['start'])} --> {format_ts(seg['end'])}",
            'text': text
        })

    write_srt(blocks, output)
    print(f'  儲存到: {output}，耗時 {format_duration(time.time() - step_start)}')
    return blocks

# ============== 步驟 4: 燒錄字幕 ==============

def get_video_info(video):
    """取得影片位元速率和位元深度"""
    info = {'bitrate': None, 'bit_depth': 8}

    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
             '-show_entries', 'stream=bit_rate', '-of', 'csv=p=0', video],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            info['bitrate'] = int(result.stdout.strip())
    except:
        pass

    if not info['bitrate']:
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=bit_rate',
                 '-of', 'csv=p=0', video],
                capture_output=True, text=True, timeout=10
            )
            if result.stdout.strip():
                info['bitrate'] = int(result.stdout.strip())
        except:
            pass

    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
             '-show_entries', 'stream=pix_fmt', '-of', 'csv=p=0', video],
            capture_output=True, text=True, timeout=10
        )
        pix_fmt = result.stdout.strip().lower()
        if '10' in pix_fmt or 'p010' in pix_fmt:
            info['bit_depth'] = 10
    except:
        pass

    return info

def get_available_encoders():
    """取得可用編碼器列表"""
    encoders = set()
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            for enc in ['hevc_nvenc', 'h264_nvenc', 'hevc_amf', 'h264_amf',
                        'hevc_qsv', 'h264_qsv', 'h264_videotoolbox', 'hevc_videotoolbox',
                        'libx265', 'libx264', 'libopenh264']:
                if enc in line:
                    encoders.add(enc)
    except:
        pass
    return encoders

def select_encoder(available_encoders, bit_depth, bitrate_kbps):
    """根據位元深度和可用編碼器選擇最佳編碼器"""
    system = platform.system()
    bitrate_str = f'{bitrate_kbps}k'

    # 10-bit 影片優先使用 HEVC 編碼器
    if bit_depth == 10:
        if 'hevc_nvenc' in available_encoders:
            return 'hevc_nvenc', ['-preset', 'p4', '-b:v', bitrate_str, '-maxrate', f'{int(bitrate_kbps * 1.5)}k', '-bufsize', f'{bitrate_kbps * 2}k']
        if 'hevc_amf' in available_encoders:
            return 'hevc_amf', ['-b:v', bitrate_str]
        if 'hevc_qsv' in available_encoders:
            return 'hevc_qsv', ['-b:v', bitrate_str]
        if 'hevc_videotoolbox' in available_encoders:
            return 'hevc_videotoolbox', ['-b:v', bitrate_str]
        if 'libx265' in available_encoders:
            return 'libx265', ['-preset', 'medium', '-b:v', bitrate_str]

    # 8-bit 影片或回退
    if system == 'Darwin':
        if 'h264_videotoolbox' in available_encoders:
            return 'h264_videotoolbox', ['-b:v', bitrate_str]
        if 'hevc_videotoolbox' in available_encoders:
            return 'hevc_videotoolbox', ['-b:v', bitrate_str]

    # Windows/Linux GPU 編碼器
    if 'h264_nvenc' in available_encoders and bit_depth == 8:
        return 'h264_nvenc', ['-preset', 'p4', '-b:v', bitrate_str, '-maxrate', f'{int(bitrate_kbps * 1.5)}k', '-bufsize', f'{bitrate_kbps * 2}k']
    if 'hevc_nvenc' in available_encoders:
        return 'hevc_nvenc', ['-preset', 'p4', '-b:v', bitrate_str, '-maxrate', f'{int(bitrate_kbps * 1.5)}k', '-bufsize', f'{bitrate_kbps * 2}k']
    if 'h264_amf' in available_encoders and bit_depth == 8:
        return 'h264_amf', ['-b:v', bitrate_str]
    if 'hevc_amf' in available_encoders:
        return 'hevc_amf', ['-b:v', bitrate_str]
    if 'h264_qsv' in available_encoders and bit_depth == 8:
        return 'h264_qsv', ['-b:v', bitrate_str]
    if 'hevc_qsv' in available_encoders:
        return 'hevc_qsv', ['-b:v', bitrate_str]

    # 軟體編碼回退
    if 'libx265' in available_encoders:
        return 'libx265', ['-preset', 'medium', '-b:v', bitrate_str]
    if 'libx264' in available_encoders:
        return 'libx264', ['-preset', 'fast', '-b:v', bitrate_str]
    if 'libopenh264' in available_encoders:
        return 'libopenh264', ['-b:v', bitrate_str]

    return None, None

def burn_subtitles(video, subtitle_file, output, fontsize=14, margin=25, is_ass=False):
    """燒錄字幕到影片"""
    step_start = time.time()
    print(f'\n[4/4] 燒錄字幕...')

    # 取得源影片資訊（讀取一次）
    video_info = get_video_info(video)
    src_bitrate = video_info['bitrate']
    bit_depth = video_info['bit_depth']

    # 預設 2000kbps
    bitrate_kbps = (src_bitrate // 1000) if src_bitrate else 2000

    print(f'  來源碼率: {bitrate_kbps}kbps')
    print(f'  位元深度: {bit_depth}-bit')

    # 取得可用編碼器（檢測一次）
    available_encoders = get_available_encoders()
    print(f'  可用編碼器: {", ".join(sorted(available_encoders)) if available_encoders else "未檢測到"}')

    # 選擇最佳編碼器
    encoder, encoder_opts = select_encoder(available_encoders, bit_depth, bitrate_kbps)

    if not encoder:
        print('  錯誤: 未找到可用的影片編碼器')
        print('  請安裝支援 libx264 或 libx265 的 FFmpeg')
        return False

    print(f'  選擇編碼器: {encoder}')

    # 跳脫字幕路徑
    sub_escaped = subtitle_file.replace('\\', '/').replace(':', r'\:')

    # ASS 字幕使用 ass 濾鏡，SRT 使用 subtitles 濾鏡
    if is_ass:
        vf = f"ass='{sub_escaped}'"
    else:
        style = f"FontSize={fontsize},MarginV={margin},BorderStyle=4,BackColour=&H80000000"
        vf = f"subtitles='{sub_escaped}':force_style='{style}'"

    cmd = [
        'ffmpeg', '-y',
        '-i', video,
        '-vf', vf,
        '-c:v', encoder,
        *encoder_opts,
        '-c:a', 'copy',
        output
    ]

    print(f'  輸出: {output}')
    print('  編碼中...', flush=True)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f'  完成，耗時 {format_duration(time.time() - step_start)}')
        return True

    # 編碼器失敗，嘗試回退
    print(f'  編碼器 {encoder} 失敗，嘗試其他編碼器...')

    fallback_order = []
    if bit_depth == 10:
        fallback_order = ['hevc_nvenc', 'hevc_amf', 'hevc_qsv', 'libx265', 'libopenh264']
    else:
        fallback_order = ['h264_nvenc', 'hevc_nvenc', 'h264_amf', 'hevc_amf', 'libx264', 'libx265', 'libopenh264']

    for fallback_enc in fallback_order:
        if fallback_enc in available_encoders and fallback_enc != encoder:
            print(f'  嘗試: {fallback_enc}')
            _, fallback_opts = select_encoder({fallback_enc}, bit_depth, bitrate_kbps)

            cmd = [
                'ffmpeg', '-y',
                '-i', video,
                '-vf', vf,
                '-c:v', fallback_enc,
                *fallback_opts,
                '-c:a', 'copy',
                output
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f'  完成，耗時 {format_duration(time.time() - step_start)}')
                return True

    print(f'  錯誤: 所有編碼器均失敗')
    print(f'  最後錯誤: {result.stderr[-500:] if result.stderr else "未知錯誤"}')
    return False

# ============== 主程式 ==============

def main():
    start_time = time.time()

    parser = argparse.ArgumentParser(
        description='雙語字幕一鍵生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
範例:
  python process.py video.mp4                      # 預設用 AI 翻譯
  python process.py video.mp4 -l en -t zh-TW
  python process.py video.mp4 --translator google  # 改用 Google（備用）

AI 翻譯（不需要 API 金鑰，讓 AI 自己翻）:
  python process.py video.mp4 --source-only --srt-only      # 先抽出原文字幕
  ...讓 AI 把 video_source.srt 翻好，寫成 video_zh.txt（一行一條）...
  python process.py video.mp4 --source-srt video_source.srt --translation-file video_zh.txt

AI 翻譯（腳本直接呼叫 OpenAI 相容接口）:
  set AI_TRANSLATE_API_KEY=...
  set AI_TRANSLATE_MODEL=gpt-4o-mini
  python process.py video.mp4
        '''
    )
    parser.add_argument('video', help='輸入影片檔案')
    parser.add_argument('-o', '--output', help='輸出影片檔案')
    parser.add_argument('-l', '--language', default='en', help='來源語言 (預設: en)')
    parser.add_argument('-t', '--target', default='zh-TW', help='目標語言 (預設: zh-TW)')
    parser.add_argument('-m', '--model', default='small', help='Whisper 模型 (預設: small)')
    parser.add_argument('--fontsize', type=int, default=14, help='字幕字型大小 (預設: 14)')
    parser.add_argument('--margin', type=int, default=25, help='字幕底部邊距 (預設: 25)')
    parser.add_argument('--srt-only', action='store_true', help='僅產生 SRT，跳過影片編碼')
    parser.add_argument('--chinese-only', action='store_true', help='僅輸出譯文字幕（適用於已有英文硬字幕的影片）')
    parser.add_argument('--source-only', action='store_true', help='僅輸出原文字幕（不翻譯）')
    parser.add_argument('--karaoke', action='store_true', help='卡拉OK模式（逐詞高亮）')
    parser.add_argument('--highlight-color', default='&H00FFFF&', help='高亮顏色 ASS 格式 (預設: &H00FFFF& 黃色)')
    parser.add_argument('--no-speech-threshold', type=float, default=0.6, help='非語音過濾閾值 0-1 (預設: 0.6)')
    parser.add_argument('--translation-file', help='外部譯文檔（AI 翻譯模式），不呼叫任何翻譯接口')
    parser.add_argument('--source-srt', help='直接沿用現成的原文字幕，跳過 Whisper 辨識')
    parser.add_argument('--translator', choices=['auto', 'ai', 'google', 'mymemory'],
                        default='auto',
                        help='翻譯引擎: auto=有 AI 設定就用 AI（預設）, ai, google（備用）, mymemory')
    parser.add_argument('--fallback', choices=['none', 'google'], default='none',
                        help='AI 翻譯失敗時的備援（預設 none，可選 google）')
    parser.add_argument('--ai-model', help='AI 模型名稱（預設讀 AI_TRANSLATE_MODEL，否則 gpt-4o-mini）')
    parser.add_argument('--ai-base-url', help='OpenAI 相容接口網址（預設讀 AI_TRANSLATE_BASE_URL）')
    parser.add_argument('--ai-api-key', help='AI 接口金鑰（建議改用 AI_TRANSLATE_API_KEY 環境變數）')
    args = parser.parse_args()

    ai_cfg = ai_config(args.ai_model, args.ai_base_url, args.ai_api_key)

    # 互斥檢查
    if args.chinese_only and args.source_only:
        print('錯誤: --chinese-only 和 --source-only 不能同時使用')
        return 1

    if args.translation_file and (args.source_only or args.karaoke):
        print('錯誤: --translation-file 不能和 --source-only / --karaoke 一起用')
        return 1

    if args.source_srt and args.karaoke:
        print('錯誤: --source-srt 不能和 --karaoke 一起用（卡拉OK 需要詞級時間戳，要重跑 Whisper）')
        return 1

    if args.karaoke and (args.chinese_only or not args.source_only and not args.chinese_only):
        # 卡拉OK模式強制為僅原文
        if not args.source_only:
            print('提示: 卡拉OK模式自動啟用 --source-only（僅原文）')
            args.source_only = True

    # 驗證輸入
    if not os.path.exists(args.video):
        print(f'錯誤: 影片檔案不存在: {args.video}')
        return 1

    # 設定輸出路徑
    video_dir = os.path.dirname(os.path.abspath(args.video))
    video_base = os.path.splitext(os.path.basename(args.video))[0]

    if args.karaoke:
        suffix = '_karaoke'
        sub_ext = '.ass'
    elif args.source_only:
        suffix = '_source'
        sub_ext = '.srt'
    elif args.chinese_only:
        suffix = '_zh'
        sub_ext = '.srt'
    else:
        suffix = '_bilingual'
        sub_ext = '.srt'
    subtitle_output = os.path.join(video_dir, f'{video_base}{suffix}{sub_ext}')
    video_output = args.output or os.path.join(video_dir, f'{video_base}{suffix}.mp4')

    print('=' * 50)
    print('雙語字幕生成器')
    print('=' * 50)
    print(f'輸入: {args.video}')
    print(f'輸出: {video_output}')

    # 步驟 1: 提取
    if args.source_srt:
        print(f'\n[1/4] 讀取既有原文字幕（跳過 Whisper 辨識）...')
        print(f'  檔案: {args.source_srt}')
        segments = srt_to_segments(args.source_srt)
        if segments is None:
            return 1
        print(f'  讀入 {len(segments)} 條字幕')
    else:
        segments = extract_subtitles(args.video, None, args.language, args.model, word_timestamps=args.karaoke, no_speech_threshold=args.no_speech_threshold)

    # 步驟 2: 翻譯（source_only 或 karaoke 模式跳過）
    if args.source_only or args.karaoke:
        print(f'\n[2/4] 跳過翻譯（僅原文模式）')
        translated = []
        if args.srt_only:
            print(f'  提示: 要高品質翻譯，可讓 AI 讀 {subtitle_output} 翻好後，再執行：')
            print(f'        --source-srt "{subtitle_output}" --translation-file <譯文檔>')
    elif args.translation_file:
        print(f'\n[2/4] 讀取外部譯文（AI 翻譯模式）...')
        print(f'  檔案: {args.translation_file}')
        translated = read_translation_file(args.translation_file, len(segments))
        if translated is None:
            return 1
        print(f'  未呼叫線上翻譯接口')
    else:
        if args.translator == 'auto':
            args.translator = 'ai' if ai_is_ready(ai_cfg) else None
        if args.translator is None:
            print_ai_hint()
            return 1
        translated = translate_subtitles(segments, args.language, args.target,
                                         args.translator, args.fallback, ai_cfg)

    # 步驟 3: 生成字幕
    if args.karaoke:
        generate_karaoke_ass(segments, subtitle_output, args.fontsize, args.margin, args.highlight_color)
    else:
        merge_bilingual(segments, translated, subtitle_output, args.chinese_only, args.source_only)

    # 步驟 4: 燒錄（可選）
    if not args.srt_only:
        success = burn_subtitles(args.video, subtitle_output, video_output, args.fontsize, args.margin, is_ass=args.karaoke)
        if not success:
            return 1

    elapsed = time.time() - start_time

    # 顯示檔案對比資訊
    if not args.srt_only:
        print_file_comparison(args.video, video_output, subtitle_output)

    print('\n' + '=' * 50)
    print('處理完成!')
    print(f'  字幕: {subtitle_output}')
    if not args.srt_only:
        print(f'  影片: {video_output}')
    print(f'  總耗時: {format_duration(elapsed)}')
    print('=' * 50)

    return 0

if __name__ == '__main__':
    sys.exit(main())

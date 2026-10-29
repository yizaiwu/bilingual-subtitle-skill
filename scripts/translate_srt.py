#!/usr/bin/env python
"""翻譯 SRT 字幕檔。

預設用 AI（OpenAI 相容接口，環境變數 AI_TRANSLATE_*）。
Google 翻譯改成明確加 --translator google 才會使用。
"""
import argparse
import os
import sys

# 重用 process.py 的翻譯後端
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import process as core  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description='Translate SRT subtitles (AI by default, Google opt-in)'
    )
    parser.add_argument('input', help='Input SRT file')
    parser.add_argument('-o', '--output', default='zh.srt', help='Output SRT file')
    parser.add_argument('-s', '--source', default='en', help='Source language (default: en)')
    parser.add_argument('-t', '--target', default='zh-TW', help='Target language (default: zh-TW)')
    parser.add_argument('--translator', choices=['auto', 'ai', 'google', 'mymemory'],
                        default='auto',
                        help='auto=有 AI 設定就用 AI（預設）, ai, google（備用）, mymemory')
    parser.add_argument('--fallback', choices=['none', 'google'], default='none',
                        help='AI 失敗時的備援（預設 none）')
    parser.add_argument('--ai-model', help='AI 模型名稱')
    parser.add_argument('--ai-base-url', help='OpenAI 相容接口網址')
    parser.add_argument('--ai-api-key', help='AI 接口金鑰')
    args = parser.parse_args()

    print(f'Translating: {args.input} -> {args.output}')
    print(f'Language: {args.source} -> {args.target}')

    with open(args.input, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    blocks = core.parse_srt(content)
    if not blocks:
        print('錯誤: 這個檔案裡找不到有效的 SRT 段落')
        return 1

    texts = [b['text'].replace('\n', ' ').strip() for b in blocks]
    ai_cfg = core.ai_config(args.ai_model, args.ai_base_url, args.ai_api_key)

    translator = args.translator
    if translator == 'auto':
        translator = 'ai' if core.ai_is_ready(ai_cfg) else None
    if translator is None:
        core.print_ai_hint()
        return 1

    translated = core.translate_texts(texts, args.source, args.target,
                                      translator, args.fallback, ai_cfg)

    with open(args.output, 'w', encoding='utf-8') as f:
        for block, text in zip(blocks, translated):
            f.write(f"{block['index']}\n{block['timestamp']}\n{text}\n\n")

    print(f'Done! Saved to {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

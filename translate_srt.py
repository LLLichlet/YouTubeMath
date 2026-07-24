#!/usr/bin/env python3
"""SRT 字幕翻译脚本 —— 读英文 SRT，调 Ollama 批量翻译，输出双语 SRT。

用法:
    python translate_srt.py audio.srt                  # 默认输出 audio.zh.srt
    python translate_srt.py audio.srt -o output.srt     # 指定输出文件
    python translate_srt.py audio.srt -b 20             # 每批 20 条，默认 20
    python translate_srt.py audio.srt -m qwen2.5:14b    # 指定模型
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

API = "http://localhost:11434/api/generate"

# 加在每批待译文本前的指令
BATCH_HEADER = """
请逐条翻译以下字幕。保持编号不变，每条格式: "序号. 中文译文"

{lines}
""".strip()


def load_prompt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_srt(path):
    """解析 SRT，返回 [(index, timestamp, text), ...]"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    entries = []
    blocks = re.split(r"\n\n+", content)
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        idx = lines[0].strip()
        ts = lines[1].strip()
        text = "\n".join(lines[2:]).strip()
        entries.append((idx, ts, text))
    return entries


def build_numbered_lines(entries):
    """一批条目 → 编号纯文本行列表"""
    parts = []
    for num, (idx, ts, text) in enumerate(entries, 1):
        # 多行字幕合并为一行，避免模型混淆编号
        flat = " ".join(text.split())
        parts.append(f"{num}. {flat}")
    return "\n".join(parts)


def call_ollama(model, prompt, max_retries=3):
    """调用 Ollama API"""
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 4096}
    }).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(API, data=body, headers={
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
                return data.get("response", "").strip()
        except Exception as e:
            print(f"  [重试 {attempt+1}/{max_retries}] {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return ""


def parse_numbered_response(text, expected_count):
    """解析模型输出: '1. xxx\\n2. xxx\\n...' → 译文列表"""
    results = []
    # 匹配 "1. text" 或 "1) text" 或 "1、text" 等
    pattern = re.compile(r"^\s*(\d+)\s*[\.\)、\s:：]\s*(.+)$", re.MULTILINE)
    for m in pattern.finditer(text):
        num = int(m.group(1))
        zh = m.group(2).strip()
        # 削掉模型可能残留的字面 "N." 前缀
        zh = re.sub(r"^[Nn]\s*[\.\)、\s]\s*", "", zh)
        # 削掉编号前缀（模型有时自己加多层前缀）
        zh = re.sub(r"^\d+\s*[\.\)、\s]\s*", "", zh)
        results.append((num, zh))
    got = {n: t for n, t in results}
    out = []
    for i in range(1, expected_count + 1):
        if i in got:
            out.append(got[i])
        else:
            print(f"    [合并 #{i}]", file=sys.stderr)
            out.append("(已与上一条字幕合并)")
    return out


def main():
    parser = argparse.ArgumentParser(description="SRT 字幕翻译工具 (Ollama)")
    parser.add_argument("input", help="输入 SRT 文件路径")
    parser.add_argument("-o", "--output", default=None, help="输出路径 (默认 input.zh.srt)")
    parser.add_argument("-b", "--batch", type=int, default=20, help="每批条数 (默认 20)")
    parser.add_argument("-m", "--model", default="qwen2.5:7b", help="模型名 (默认 qwen2.5:7b)")
    parser.add_argument("-p", "--prompt", default=None, help="提示词文件路径")
    parser.add_argument("--start", type=int, default=0, help="起始批次 (断点续传)")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = args.prompt or os.path.join(script_dir, "translate_prompt.txt")
    if args.output:
        output_path = args.output
    else:
        base, _ = os.path.splitext(args.input)
        output_path = f"{base}.zh.srt"

    if not os.path.exists(prompt_path):
        print(f"错误: 找不到提示词文件 {prompt_path}", file=sys.stderr)
        sys.exit(1)

    sys_prompt = load_prompt(prompt_path)
    entries = parse_srt(args.input)
    total = len(entries)
    print(f"已加载 {total} 条字幕, 提示词 {len(sys_prompt)} 字符")
    print(f"模型: {args.model}, 每批 {args.batch} 条, 输出: {output_path}")

    # 断点续传: 加载已有结果
    zh_map = {}
    if os.path.exists(output_path) and args.start > 0:
        existing = parse_srt(output_path)
        for idx, ts, zh in existing:
            zh_map[idx] = zh
        print(f"已有 {len(zh_map)} 条翻译, 从批次 {args.start} 继续")
    print()

    total_batches = (total + args.batch - 1) // args.batch
    for batch_no in range(total_batches):
        if batch_no < args.start:
            continue
        i = batch_no * args.batch
        batch_entries = entries[i:i + args.batch]
        numbered = build_numbered_lines(batch_entries)
        full_prompt = f"{sys_prompt}\n\n{BATCH_HEADER.format(lines=numbered)}"

        start = time.time()
        n0, n1 = i + 1, min(i + args.batch, total)
        print(f"批次 {batch_no} [{n0}-{n1}] ... ", end="", flush=True)

        response = call_ollama(args.model, full_prompt)

        if not response:
            print("翻译失败")
            for idx, ts, _ in batch_entries:
                zh_map[idx] = "[翻译失败]"
        else:
            translations = parse_numbered_response(response, len(batch_entries))
            for (idx, ts, _), zh_text in zip(batch_entries, translations):
                zh_map[idx] = zh_text
            elapsed = time.time() - start
            missing = sum(1 for t in translations if t == "(已与上一条字幕合并)")
            print(f"{elapsed:.1f}s" + (f", 合并{missing}条" if missing else ""))

        # 每 5 批存一次中间结果，防止丢进度
        if (batch_no + 1) % 5 == 0:
            _write_partial(output_path, entries, zh_map)

    _write_partial(output_path, entries, zh_map)
    print(f"\n已保存: {output_path}")


def _write_partial(output_path, entries, zh_map):
    lines = []
    for idx, ts, en_text in entries:
        zh = zh_map.get(idx, "")
        lines.append(f"{idx}\n{ts}\n{en_text}\n{zh}\n")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()

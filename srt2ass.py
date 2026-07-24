#!/usr/bin/env python3
"""双语 SRT → ASS 字幕转换。中英文不同颜色/字号，适合烧录。"""

import argparse
import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ASS_HEADER = """[Script Info]
Title: Bilingual Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF&,&H000000FF&,&H00000000&,&H80000000&,0,0,0,0,100,100,0,0,1,2,2,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# 样式: 英文白灰色小字在上，中文亮黄色大字在下
# \N = 换行, {\c&H...&} = 颜色, {\fs...} = 字号, {\b...} = 粗体
# BBGGRR 格式: FFFFFF=白, FFCB2B=黄, C0C0C0=灰

EN_COLOR = "&H00C0C0C0&"   # 银灰
ZH_COLOR = "&H0037C8F0&"   # 橙黄暖色，醒目但不刺眼


def srt_to_ass_time(srt_ts):
    """00:00:00,000 → 0:00:00.00"""
    m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", srt_ts)
    if not m:
        return srt_ts
    h, mm, ss, ms = m.groups()
    cs = int(ms) // 10
    return f"{int(h)}:{mm}:{ss}.{cs:02d}"


def parse_srt(path):
    """解析双语 SRT，返回 [](英文, 中文) ...]"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    entries = []
    blocks = re.split(r"\n\n+", content)
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 4:
            continue
        # idx, timestamp, en (may be multi-line), zh (may be multi-line)
        ts = lines[1].strip()
        body = lines[2:]
        # 找到中英文分界: 英文在前，中文在后
        # 简单策略: 最后一行是中文，前面的都是英文
        # 但中文可能多行，英文也可能多行
        # 更可靠: 英文在上半部分，中文在下半部分
        n = len(body)
        mid = n // 2
        en_text = " ".join(body[:mid]).strip()
        zh_text = " ".join(body[mid:]).strip()
        entries.append((ts, en_text, zh_text))
    return entries


def make_ass_event(start_srt, end_srt, en_text, zh_text):
    """生成一条 ASS Dialogue"""
    start = srt_to_ass_time(start_srt)
    end = srt_to_ass_time(end_srt)
    # 英文小字在上，中文大字在下，中间间隔
    line = (
        f"{{\\fs27}}{{\\c{EN_COLOR}}}{en_text}"
        f"\\N"
        f"{{\\fs36}}{{\\c{ZH_COLOR}}}{{\\b1}}{zh_text}"
    )
    return f"Dialogue: 0,{start},{end},Default,,0,0,0,,{line}"


def main():
    parser = argparse.ArgumentParser(description="双语 SRT → ASS")
    parser.add_argument("input", help="双语 SRT 文件")
    parser.add_argument("-o", "--output", default=None, help="输出 ASS 路径")
    args = parser.parse_args()

    if args.output:
        outpath = args.output
    else:
        base, _ = os.path.splitext(args.input)
        outpath = f"{base}.ass"

    entries = parse_srt(args.input)
    print(f"已加载 {len(entries)} 条字幕")

    lines = [ASS_HEADER]
    for i, (ts_range, en, zh) in enumerate(entries):
        m = re.match(r"(.+?)\s*-->\s*(.+)", ts_range)
        if not m:
            continue
        start, end = m.group(1), m.group(2)
        lines.append(make_ass_event(start, end, en, zh))

    with open(outpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"已保存: {outpath}")


if __name__ == "__main__":
    main()

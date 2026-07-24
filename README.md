# YT2Bili

YouTube 数学讲座 → B 站双语字幕，全本地工具链。

语音识别用 OpenAI Whisper，翻译用 Ollama + Qwen2.5，无需付费 API。

## 安装

```bash
winget install yt-dlp ffmpeg
uv tool install openai-whisper
scoop bucket add extras && scoop install ollama-full
ollama pull qwen2.5:7b
```

## 使用

```bash
# 1. 下载
yt-dlp -f "137+140" --merge-output-format mp4 -o "%(title)s.%(ext)s" "<url>"

# 2. 提取音频 → Whisper 识别
ffmpeg -i video.mp4 -vn -c:a pcm_s16le -ar 16000 audio.wav
whisper audio.wav --model medium --language en --output_format srt

# 3. 修正 Whisper 术语错误，然后翻译
python translate_srt.py audio.srt -b 10

# 4. 烧录双语字幕
python srt2ass.py audio.zh.srt
ffmpeg -i video.mp4 -vf "subtitles=audio.zh.ass" \
    -c:v libx264 -crf 20 -preset fast -c:a copy output.mp4
```

详细工作流见 [WORKFLOW.md](WORKFLOW.md)。

## 脚本

| 脚本 | 用途 |
|------|------|
| `translate_srt.py` | 调用 Ollama 批量翻译 SRT，输出双语字幕 |
| `srt2ass.py` | 双语 SRT 转 ASS，中英文独立样式 |
| `translate_prompt.txt` | 翻译提示词，含 100+ 条数学术语表 |

`translate_srt.py` 支持断点续传：

```
python translate_srt.py audio.srt -b 20           # 每批 20 条
python translate_srt.py audio.srt -m qwen2.5:14b  # 切换模型
python translate_srt.py audio.srt --start 30       # 从第 30 批继续
```

## 项目结构

```
videos.yml                   # 视频索引
subtitles/<id>.en.srt        # Whisper 英文识别
subtitles/<id>.zh.srt        # 双语字幕
```

## 贡献

欢迎修正字幕术语或翻译错误。编辑 `subtitles/` 下的 SRT 文件，提交 PR。新增视频请同步更新 `videos.yml`。

## License

MIT

# 详细工作流

## 1. 下载视频

YouTube 可能要求登录验证。先在浏览器安装 **Get cookies.txt LOCALLY** 扩展：

- Chrome/Edge: https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc

打开 YouTube，点扩展图标导出 `cookies.txt` 放到项目根目录。

```bash
yt-dlp --cookies cookies.txt -f "137+140" --merge-output-format mp4 -o "%(title)s.%(ext)s" "<url>"
```

`137+140` = 1080p H.264 视频流 + 128k AAC 音频流。查看可用格式：`yt-dlp --cookies cookies.txt -F <url>`。

若遇 `n challenge solving failed` 错误，安装 JS 运行时：`scoop install deno`。

## 2. 提取音频

```bash
ffmpeg -i video.mp4 -vn -c:a pcm_s16le -ar 16000 audio.wav
```

16kHz 单声道足够 Whisper 使用，再高没收益还占空间。

## 3. 语音识别

```bash
whisper audio.wav --model medium --language en --output_format srt
```

模型选择：`tiny` < `small` < `medium` < `large-v3`。`medium` 在准确度和速度间最佳平衡。

## 4. 修正术语

Whisper 会将数学专有名词识别为发音相近的错词。常见修正：

| Whisper 输出 | 修正为 |
|---|---|
| bordism / bortism / boardism | **bordism** |
| turn-Siemens | **Chern-Simons** |
| Whitten | **Witten** |
| Atiya | **Atiyah** |
| Cobb | **Cob** |
| kayak category | **Fukaya category** |

全文替换即可，Q&A 段落可跳过。

## 5. 翻译

```bash
python translate_srt.py audio.srt -b 10
```

`translate_prompt.txt` 包含完整术语表和人名保留规则，按需追加。每 5 批自动存档，中断后用 `--start` 继续。模型合并的相邻条目自动标注"(已与上一条字幕合并)"。

## 6. SRT → ASS

```bash
python srt2ass.py audio.zh.srt
```

默认样式：英文银灰 27px + 中文橙黄 36px 加粗。修改 `srt2ass.py` 中的 `fs` 和 `COLOR` 变量可调。

## 7. 烧录字幕

```bash
ffmpeg -i video.mp4 -vf "subtitles=audio.zh.ass" \
    -c:v libx264 -crf 20 -preset fast -c:a copy output.mp4
```

N 卡驱动 ≥ 610 可用 NVENC 加速（`-c:v h264_nvenc -preset p4 -cq 20`），快 5-10 倍。

## 新增视频

1. 在 `videos.yml` 追加记录，用 YouTube 视频 ID 作为文件名前缀
2. 字幕放入 `subtitles/<id>.en.srt` 和 `subtitles/<id>.zh.srt`

## 字体显示

ASS 默认用 Arial。若中文显示异常，安装思源黑体或微软雅黑后修改 `srt2ass.py` 中的 `Fontname`。

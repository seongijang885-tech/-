# YouTube Shorts Production Agent

A lightweight MVP agent that turns a topic into a complete YouTube Shorts production package:

- Korean shorts script and hook
- Scene-by-scene storyboard
- Narration text
- SRT subtitles
- Placeholder narration audio
- Optional vertical MP4 render via `ffmpeg`
- Upload metadata: title, description, hashtags, pinned comment, thumbnail copy

The project intentionally uses Python standard-library code for the core pipeline so it can run in a clean environment. If `ffmpeg` is installed, the CLI can also render a simple 1080x1920 short with burned-in subtitles and generated placeholder audio.

## Quick start

```bash
python -m shorts_agent --topic "AI 뉴스" --target "20대 직장인" --duration 60 --output-dir output/demo
```

Render an MP4 when `ffmpeg` is available:

```bash
python -m shorts_agent --topic "AI 뉴스" --target "20대 직장인" --duration 60 --render-video --output-dir output/demo
```

## Outputs

Each run creates a timestamped project folder containing:

```text
brief.json          # normalized user brief
script.md           # hook, narration, CTA, and scene table
storyboard.json     # machine-readable scene plan
subtitles.srt       # timed subtitles
narration.txt       # TTS-ready narration text
audio.wav           # placeholder narration track
metadata.json       # title, description, tags, hashtags, thumbnail copy
render_plan.json    # ffmpeg/rendering notes and status
short.mp4           # only when --render-video succeeds
```

## Notes

- `audio.wav` is a timing placeholder, not realistic speech. Replace it with a TTS provider output when integrating production narration.
- The render step requires `ffmpeg` on `PATH`.
- Generated copy is a deterministic baseline intended for review before publishing.

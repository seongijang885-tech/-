"""Deterministic YouTube Shorts production pipeline.

The module is intentionally dependency-light. It creates all text assets, timed
subtitles, placeholder audio, and can ask ffmpeg to render a simple vertical MP4.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from textwrap import shorten

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
SAMPLE_RATE = 44_100


@dataclass(frozen=True)
class ShortsBrief:
    """User-provided creative brief for one short."""

    topic: str
    target: str = "일반 시청자"
    duration_seconds: int = 60
    tone: str = "쉽고 빠르게"
    language: str = "ko"

    def normalized_duration(self) -> int:
        return max(15, min(self.duration_seconds, 180))


@dataclass(frozen=True)
class Scene:
    index: int
    start: float
    end: float
    title: str
    narration: str
    visual_prompt: str
    on_screen_text: str

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


@dataclass(frozen=True)
class ShortsPackage:
    output_dir: Path
    files: dict[str, str]
    render_status: str

    def summary(self) -> dict[str, object]:
        return {
            "output_dir": str(self.output_dir),
            "render_status": self.render_status,
            "files": self.files,
        }


def create_shorts_package(
    brief: ShortsBrief,
    output_root: Path,
    render_video: bool = False,
    force: bool = False,
) -> ShortsPackage:
    """Create a complete shorts package and optionally render an MP4."""

    run_dir = _make_run_dir(output_root, brief.topic, force=force)
    scenes = build_storyboard(brief)
    metadata = build_metadata(brief, scenes)

    files: dict[str, str] = {}
    files["brief"] = _write_json(run_dir / "brief.json", asdict(brief))
    files["storyboard"] = _write_json(run_dir / "storyboard.json", [asdict(scene) for scene in scenes])
    files["script"] = _write_text(run_dir / "script.md", render_script_markdown(brief, scenes, metadata))
    files["subtitles"] = _write_text(run_dir / "subtitles.srt", render_srt(scenes))
    files["narration"] = _write_text(run_dir / "narration.txt", "\n".join(scene.narration for scene in scenes) + "\n")
    files["metadata"] = _write_json(run_dir / "metadata.json", metadata)
    files["audio"] = _write_placeholder_audio(run_dir / "audio.wav", brief.normalized_duration())

    render_status = "skipped"
    render_plan = {
        "requested": render_video,
        "status": render_status,
        "video_size": f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
        "requires": "ffmpeg",
    }

    if render_video:
        render_status = render_vertical_video(run_dir, scenes, brief)
        render_plan["status"] = render_status
        if render_status == "rendered":
            files["video"] = str(run_dir / "short.mp4")

    files["render_plan"] = _write_json(run_dir / "render_plan.json", render_plan)
    return ShortsPackage(output_dir=run_dir, files=files, render_status=render_status)


def build_storyboard(brief: ShortsBrief) -> list[Scene]:
    """Build a scene plan with evenly distributed timings."""

    duration = brief.normalized_duration()
    topic = brief.topic.strip()
    target = brief.target.strip()
    tone = brief.tone.strip()
    templates = _korean_scene_templates(topic, target, tone) if brief.language == "ko" else _english_scene_templates(topic, target, tone)
    scene_count = len(templates)
    scene_length = duration / scene_count

    scenes: list[Scene] = []
    for index, template in enumerate(templates, start=1):
        start = round((index - 1) * scene_length, 2)
        end = round(duration if index == scene_count else index * scene_length, 2)
        scenes.append(
            Scene(
                index=index,
                start=start,
                end=end,
                title=template["title"],
                narration=template["narration"],
                visual_prompt=template["visual_prompt"],
                on_screen_text=template["on_screen_text"],
            )
        )
    return scenes


def build_metadata(brief: ShortsBrief, scenes: list[Scene]) -> dict[str, object]:
    topic = brief.topic.strip()
    hook = scenes[0].on_screen_text
    if brief.language == "ko":
        return {
            "title_candidates": [
                f"{topic}, {brief.normalized_duration()}초 만에 핵심만",
                f"모르면 손해인 {topic} 포인트",
                f"바쁜 사람을 위한 {topic} 정리",
                f"{topic} 지금 꼭 봐야 하는 이유",
                f"오늘의 {topic}: 핵심 3가지",
            ],
            "description": f"{brief.target}를 위해 {topic}의 핵심을 짧게 정리했습니다. 저장해두고 필요할 때 다시 확인하세요.",
            "hashtags": ["#쇼츠", "#유튜브쇼츠", f"#{_hashtag(topic)}", "#정보", "#트렌드"],
            "tags": [topic, brief.target, "쇼츠", "정보", "트렌드", "요약"],
            "thumbnail_copy": [hook, f"{topic} 핵심", "60초 요약"],
            "pinned_comment": f"다음에 다뤘으면 하는 {topic} 관련 질문을 댓글로 남겨주세요.",
        }
    return {
        "title_candidates": [
            f"{topic} in {brief.normalized_duration()} Seconds",
            f"What You Need to Know About {topic}",
            f"The Fast Guide to {topic}",
        ],
        "description": f"A quick {topic} breakdown for {brief.target}.",
        "hashtags": ["#shorts", f"#{_hashtag(topic)}", "#trends"],
        "tags": [topic, brief.target, "shorts", "explainer"],
        "thumbnail_copy": [hook, f"{topic} basics", "60 sec"],
        "pinned_comment": f"What should we cover next about {topic}?",
    }


def render_script_markdown(brief: ShortsBrief, scenes: list[Scene], metadata: dict[str, object]) -> str:
    lines = [
        f"# {brief.topic} Shorts Script",
        "",
        "## Brief",
        f"- Target: {brief.target}",
        f"- Duration: {brief.normalized_duration()} seconds",
        f"- Tone: {brief.tone}",
        "",
        "## Hook",
        f"> {scenes[0].narration}",
        "",
        "## Narration",
    ]
    lines.extend(f"{scene.index}. {scene.narration}" for scene in scenes)
    lines.extend([
        "",
        "## Storyboard",
        "| # | Time | On-screen text | Visual prompt |",
        "|---|---:|---|---|",
    ])
    for scene in scenes:
        lines.append(
            f"| {scene.index} | {_format_timestamp(scene.start)}-{_format_timestamp(scene.end)} | "
            f"{scene.on_screen_text} | {scene.visual_prompt} |"
        )
    lines.extend([
        "",
        "## Upload Package",
        f"- Recommended title: {metadata['title_candidates'][0]}",
        f"- Description: {metadata['description']}",
        f"- Hashtags: {' '.join(metadata['hashtags'])}",
        f"- Pinned comment: {metadata['pinned_comment']}",
        "",
    ])
    return "\n".join(lines)


def render_srt(scenes: list[Scene]) -> str:
    blocks = []
    for scene in scenes:
        blocks.append(
            f"{scene.index}\n"
            f"{_format_srt_time(scene.start)} --> {_format_srt_time(scene.end)}\n"
            f"{scene.on_screen_text}\n{scene.narration}\n"
        )
    return "\n".join(blocks)


def render_vertical_video(run_dir: Path, scenes: list[Scene], brief: ShortsBrief) -> str:
    """Render a simple vertical video with ffmpeg, returning a status string."""

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return "missing_ffmpeg"

    subtitle_path = run_dir / "subtitles.srt"
    audio_path = run_dir / "audio.wav"
    video_path = run_dir / "short.mp4"
    escaped_subtitle = str(subtitle_path).replace("'", "'\\''")
    drawtext = (
        "drawtext=fontcolor=white:fontsize=58:box=1:boxcolor=black@0.45:boxborderw=28:"
        f"x=(w-text_w)/2:y=170:text='{_escape_drawtext(shorten(brief.topic, width=28, placeholder='…'))}',"
        f"subtitles='{escaped_subtitle}':force_style='Fontsize=18,Alignment=2,MarginV=170'"
    )
    command = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x111827:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d={brief.normalized_duration()}",
        "-i",
        str(audio_path),
        "-vf",
        drawtext,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(video_path),
    ]
    result = subprocess.run(command, cwd=run_dir, capture_output=True, text=True, check=False)
    (run_dir / "ffmpeg.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    return "rendered" if result.returncode == 0 else "ffmpeg_failed"


def _korean_scene_templates(topic: str, target: str, tone: str) -> list[dict[str, str]]:
    return [
        {
            "title": "Hook",
            "narration": f"{topic}, 지금 바쁜 {target}라면 이것만 기억하세요.",
            "visual_prompt": f"세로형 쇼츠, 강한 후킹 타이포그래피, 주제는 {topic}",
            "on_screen_text": f"{topic} 핵심만!",
        },
        {
            "title": "Problem",
            "narration": f"정보는 너무 많은데, 실제로 중요한 포인트는 몇 가지로 압축됩니다.",
            "visual_prompt": "빠르게 지나가는 뉴스 카드와 알림 그래픽",
            "on_screen_text": "정보 과부하 끝",
        },
        {
            "title": "Point 1",
            "narration": f"첫째, {topic}이 내 일상이나 업무에 어떤 변화를 만드는지 먼저 보세요.",
            "visual_prompt": "노트북, 체크리스트, 변화 전후 비교 화면",
            "on_screen_text": "1. 내게 미치는 영향",
        },
        {
            "title": "Point 2",
            "narration": "둘째, 당장 써먹을 수 있는 행동 하나를 정하면 정보가 실행으로 바뀝니다.",
            "visual_prompt": "손가락이 하나의 실행 버튼을 누르는 클로즈업",
            "on_screen_text": "2. 바로 할 행동",
        },
        {
            "title": "Point 3",
            "narration": "셋째, 과장된 전망보다 확인 가능한 근거와 실제 사례를 우선하세요.",
            "visual_prompt": "돋보기, 데이터 차트, 검증 완료 스탬프",
            "on_screen_text": "3. 근거 확인",
        },
        {
            "title": "CTA",
            "narration": f"이 계정에서는 {tone} 이해할 수 있게 계속 정리해드릴게요. 저장하고 다음 영상도 확인하세요.",
            "visual_prompt": "저장 버튼, 구독 버튼, 밝은 마무리 그래픽",
            "on_screen_text": "저장하고 다시 보기",
        },
    ]


def _english_scene_templates(topic: str, target: str, tone: str) -> list[dict[str, str]]:
    return [
        {
            "title": "Hook",
            "narration": f"If you care about {topic}, here is the fast version for {target}.",
            "visual_prompt": f"Vertical shorts typography about {topic}",
            "on_screen_text": f"{topic}: the short version",
        },
        {
            "title": "Problem",
            "narration": "There is too much noise, so focus on the few points that change what you do next.",
            "visual_prompt": "Rapid news cards and notification graphics",
            "on_screen_text": "Cut through the noise",
        },
        {
            "title": "Point 1",
            "narration": f"First, ask how {topic} affects your work, money, or daily routine.",
            "visual_prompt": "Laptop checklist and before-after split screen",
            "on_screen_text": "1. Personal impact",
        },
        {
            "title": "Point 2",
            "narration": "Second, pick one action you can try today so information becomes execution.",
            "visual_prompt": "Finger pressing a glowing action button",
            "on_screen_text": "2. One action",
        },
        {
            "title": "Point 3",
            "narration": "Third, prefer proof, examples, and limits over hype.",
            "visual_prompt": "Magnifying glass over charts and verified stamp",
            "on_screen_text": "3. Check proof",
        },
        {
            "title": "CTA",
            "narration": f"Follow for more {tone} breakdowns and save this for later.",
            "visual_prompt": "Save and follow buttons with clean ending card",
            "on_screen_text": "Save this",
        },
    ]


def _make_run_dir(output_root: Path, topic: str, force: bool) -> Path:
    slug = _slugify(topic)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = output_root / f"{timestamp}-{slug}"
    if run_dir.exists() and not force:
        raise FileExistsError(f"Output directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=force)
    return run_dir


def _write_json(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_placeholder_audio(path: Path, duration_seconds: int) -> str:
    """Write a low-volume pulse track that reserves narration timing."""

    frame_count = duration_seconds * SAMPLE_RATE
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for frame in range(frame_count):
            second = frame / SAMPLE_RATE
            pulse = 0.18 if int(second * 2) % 2 == 0 else 0.05
            value = int(32767 * pulse * math.sin(2 * math.pi * 220 * second))
            wav.writeframesraw(value.to_bytes(2, byteorder="little", signed=True))
    return str(path)


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def _format_srt_time(seconds: float) -> str:
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    return "-".join(part for part in cleaned.split("-") if part)[:48] or "shorts"


def _hashtag(value: str) -> str:
    return "".join(char for char in value if char.isalnum()) or "shorts"


def _escape_drawtext(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

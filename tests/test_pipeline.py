from __future__ import annotations

import json
import wave

from shorts_agent.pipeline import ShortsBrief, build_storyboard, create_shorts_package, render_srt


def test_storyboard_uses_normalized_duration() -> None:
    brief = ShortsBrief(topic="AI 뉴스", target="직장인", duration_seconds=10)

    scenes = build_storyboard(brief)

    assert len(scenes) == 6
    assert scenes[0].start == 0
    assert scenes[-1].end == 15
    assert scenes[0].on_screen_text == "AI 뉴스 핵심만!"


def test_srt_contains_timed_blocks() -> None:
    scenes = build_storyboard(ShortsBrief(topic="AI", duration_seconds=60))

    srt = render_srt(scenes)

    assert "00:00:00,000 --> 00:00:10,000" in srt
    assert "00:00:50,000 --> 00:01:00,000" in srt


def test_create_package_writes_expected_assets(tmp_path) -> None:
    package = create_shorts_package(
        ShortsBrief(topic="AI 뉴스", target="20대 직장인", duration_seconds=30),
        output_root=tmp_path,
    )

    assert package.render_status == "skipped"
    for key in ["brief", "storyboard", "script", "subtitles", "narration", "metadata", "audio", "render_plan"]:
        assert key in package.files

    metadata = json.loads((package.output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["title_candidates"][0] == "AI 뉴스, 30초 만에 핵심만"

    with wave.open(str(package.output_dir / "audio.wav"), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 44_100
        assert wav.getnframes() == 30 * 44_100

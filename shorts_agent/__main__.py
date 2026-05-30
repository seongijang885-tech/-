"""CLI entry point for the YouTube Shorts production agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import ShortsBrief, create_shorts_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m shorts_agent",
        description="Create a YouTube Shorts production package from a topic.",
    )
    parser.add_argument("--topic", required=True, help="Video topic, for example: 'AI 뉴스'.")
    parser.add_argument("--target", default="일반 시청자", help="Target audience.")
    parser.add_argument("--duration", type=int, default=60, help="Target duration in seconds.")
    parser.add_argument("--tone", default="쉽고 빠르게", help="Narration tone.")
    parser.add_argument("--language", default="ko", choices=["ko", "en"], help="Output language.")
    parser.add_argument("--output-dir", default="output", help="Directory for generated assets.")
    parser.add_argument(
        "--render-video",
        action="store_true",
        help="Render a simple vertical MP4 when ffmpeg is installed.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing timestamped run directory if it already exists.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    brief = ShortsBrief(
        topic=args.topic,
        target=args.target,
        duration_seconds=args.duration,
        tone=args.tone,
        language=args.language,
    )

    package = create_shorts_package(
        brief=brief,
        output_root=Path(args.output_dir),
        render_video=args.render_video,
        force=args.force,
    )

    print(json.dumps(package.summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

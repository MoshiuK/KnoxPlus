"""
KnoxPlus – White‑Label Social Content Automation Tool
====================================================

Overview
--------

This script is the KnoxPlus implementation of the white‑label
social media automation engine.  It builds on the concepts from
Content360 Plus and renames the platform to **KnoxPlus**, at the
user’s request.  The aim remains to provide a flexible and
customisable tool that can generate AI‑written posts, create
simple narrated videos from those posts and schedule publishing
across multiple social platforms.

Key Features
------------

* **AI‑assisted content creation** – Generates social posts using the
  OpenAI API.  If your environment lacks the OpenAI library or API
  key, a placeholder message is returned instead.

* **Video generation** – Converts the generated text into speech with
  gTTS and assembles a vertical video of slides using MoviePy,
  tinted with your brand colour.

* **Multi‑platform posting stubs** – Stub functions demonstrate how
  to post to Twitter/X, Instagram, Facebook and LinkedIn.  Replace
  these stubs with real API calls to publish content.

* **White‑label customisation** – A `Brand` class holds the name,
  colour and optional logo for each client, enabling agencies to
  reuse the platform under different names and branding.

* **Scheduling** – A simple scheduler lets you delay posts until a
  specified time.  Swap in a more robust scheduler if needed.

Refer to the accompanying report for an explanation of how this
tool improves on existing offerings and how to extend it further.

"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

try:
    import openai
except ImportError:
    openai = None  # OpenAI library optional

from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
# Importing moviepy at runtime can fail if the full module isn't installed.
try:
    from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
except Exception:
    AudioFileClip = None  # type: ignore
    ImageClip = None  # type: ignore
    concatenate_videoclips = None  # type: ignore


@dataclass
class Brand:
    """Represents brand‑specific customisation settings for white‑label clients."""

    name: str
    color: str  # Hex colour code for primary brand colour
    logo_path: Optional[str] = None  # Path to a PNG/SVG logo
    font_path: Optional[str] = None  # Path to a TTF/OTF font

    def apply_to_image(self, img: Image.Image) -> Image.Image:
        """Apply the brand colour to an image as a tint."""
        color = tuple(int(self.color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        tinted = Image.new("RGB", img.size, color)
        blended = Image.blend(img.convert("RGB"), tinted, alpha=0.2)
        return blended


class ContentCreator:
    """Generates posts and corresponding media for social platforms."""

    def __init__(self, brand: Brand, openai_api_key: Optional[str] = None):
        self.brand = brand
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if openai is not None and self.openai_api_key:
            openai.api_key = self.openai_api_key

    def generate_post(self, topic: str, max_tokens: int = 200) -> str:
        """Generate a social media post about a given topic using the OpenAI API."""
        if openai is None or not self.openai_api_key:
            return f"[Placeholder post about {topic}]"
        prompt = (
            f"Write an engaging and concise social media post about '{topic}'.\n"
            "The post should be friendly, informative and include a call to action."
        )
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.7,
            top_p=1.0,
        )
        message = response["choices"][0]["message"]["content"].strip()
        return message

    def text_to_speech(self, text: str, lang: str = "en") -> str:
        """Convert text to speech using gTTS; fall back to silence if it fails.

        Google TTS may be unavailable in restricted environments.  In that
        case this method returns a path to an empty MP3 file.  You can
        replace this fallback with another text‑to‑speech engine if
        available (e.g. pyttsx3 for offline synthesis).
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tf:
            try:
                tts = gTTS(text=text, lang=lang)
                tts.save(tf.name)
            except Exception as e:
                # Create an empty MP3 file as a fallback
                print(
                    f"Warning: gTTS synthesis failed ({e}). Creating a silent audio placeholder instead."
                )
                # Write a few bytes to create a valid empty MP3 file header
                tf.write(b"\x49\x44\x33\x03\x00\x00\x00\x00\x00\x21")
                tf.flush()
            return tf.name

    def create_video(self, text: str, duration_per_line: float = 4.0) -> str:
        """Create a simple video from the provided text.

        If MoviePy is available the method produces a narrated MP4.  When
        MoviePy cannot be imported (e.g. missing dependency), a fallback
        is used: the audio narration is still generated via gTTS and
        returned as the output file, and a warning is printed to the
        console.  This allows the remainder of the workflow to
        proceed even in limited environments.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            lines = [text]
        audio_path = self.text_to_speech(" ".join(lines))
        if AudioFileClip is None or ImageClip is None or concatenate_videoclips is None:
            # Return the audio file as a fallback
            print(
                "Warning: moviepy.editor is unavailable. Generated audio only; install moviepy to enable video creation."
            )
            return audio_path
        audio_clip = AudioFileClip(audio_path)
        clips: List[ImageClip] = []
        width, height = 1080, 1920
        background = Image.new("RGB", (width, height), (255, 255, 255))
        background = self.brand.apply_to_image(background)
        draw = ImageDraw.Draw(background)
        font_path = self.brand.font_path or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_size = 48
        font = ImageFont.truetype(font_path, font_size)
        for line in lines:
            img = background.copy()
            text_width, text_height = draw.textsize(line, font=font)
            x = (width - text_width) / 2
            y = (height - text_height) / 2
            draw_img = ImageDraw.Draw(img)
            draw_img.text((x, y), line, fill="black", font=font)
            clip = ImageClip(img).set_duration(duration_per_line)
            clips.append(clip)
        video = concatenate_videoclips(clips, method="compose")
        video = video.set_audio(audio_clip)
        out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        video.write_videofile(out_file, fps=24, codec="libx264", audio_codec="aac")
        try:
            os.remove(audio_path)
        except OSError:
            pass
        return out_file


class SocialPoster:
    """Handles posting content to multiple social platforms."""
    def __init__(self, brand: Brand):
        self.brand = brand
    def post_to_twitter(self, text: str, media_path: Optional[str] = None):
        print(f"[TWITTER] Posting as {self.brand.name}:\n{text}\nMedia: {media_path}")
    def post_to_instagram(self, text: str, media_path: Optional[str] = None):
        print(f"[INSTAGRAM] Posting as {self.brand.name}:\n{text}\nMedia: {media_path}")
    def post_to_facebook(self, text: str, media_path: Optional[str] = None):
        print(f"[FACEBOOK] Posting as {self.brand.name}:\n{text}\nMedia: {media_path}")
    def post_to_linkedin(self, text: str, media_path: Optional[str] = None):
        print(f"[LINKEDIN] Posting as {self.brand.name}:\n{text}\nMedia: {media_path}")
    def post(self, platform: str, text: str, media_path: Optional[str] = None):
        platform = platform.lower()
        if platform in {"twitter", "x"}:
            self.post_to_twitter(text, media_path)
        elif platform == "instagram":
            self.post_to_instagram(text, media_path)
        elif platform == "facebook":
            self.post_to_facebook(text, media_path)
        elif platform == "linkedin":
            self.post_to_linkedin(text, media_path)
        else:
            raise ValueError(f"Unsupported platform: {platform}")


class Scheduler:
    """Simple scheduler to run functions at specific datetimes."""
    def __init__(self):
        self.jobs: List[threading.Timer] = []
    def schedule(self, when: dt.datetime, func: Callable, *args, **kwargs):
        now = dt.datetime.now(tz=when.tzinfo)
        delay = (when - now).total_seconds()
        if delay < 0:
            delay = 0
        timer = threading.Timer(delay, func, args=args, kwargs=kwargs)
        timer.start()
        self.jobs.append(timer)
    def cancel_all(self):
        for job in self.jobs:
            job.cancel()
        self.jobs.clear()


def parse_datetime(dt_str: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(dt_str)
    except ValueError:
        return dt.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser(
        description="Generate and schedule social media posts with videos using KnoxPlus."
    )
    parser.add_argument("--topic", required=True, help="Topic for the AI‑generated post")
    parser.add_argument(
        "--brand_name", default="KnoxPlus Brand", help="Name of your brand for white‑labelling"
    )
    parser.add_argument(
        "--brand_color", default="#000000", help="Hex code of your brand’s primary colour"
    )
    parser.add_argument(
        "--brand_logo", help="Path to an optional logo to include in videos"
    )
    parser.add_argument(
        "--schedule", help="Datetime to schedule posting (YYYY-MM-DD HH:MM:SS or ISO format)"
    )
    parser.add_argument(
        "--platforms",
        nargs="*",
        default=["twitter"],
        help="Platforms to post to (e.g. twitter instagram facebook)"
    )
    args = parser.parse_args()
    brand = Brand(name=args.brand_name, color=args.brand_color, logo_path=args.brand_logo)
    creator = ContentCreator(brand)
    poster = SocialPoster(brand)
    scheduler = Scheduler()
    post_text = creator.generate_post(args.topic)
    print(f"Generated post:\n{post_text}\n")
    video_path = creator.create_video(post_text)
    print(f"Video created at: {video_path}\n")
    def post_job():
        for platform in args.platforms:
            poster.post(platform, post_text, video_path)
    if args.schedule:
        when = parse_datetime(args.schedule)
        print(f"Scheduling post for {when}…")
        scheduler.schedule(when, post_job)
    else:
        post_job()
    if scheduler.jobs:
        try:
            for job in scheduler.jobs:
                job.join()
        except KeyboardInterrupt:
            print("Cancelling scheduled posts…")
            scheduler.cancel_all()


if __name__ == "__main__":
    main()
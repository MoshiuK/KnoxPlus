"""
Flask web interface for KnoxPlus
===============================

This simple Flask application exposes endpoints to generate social media posts
and corresponding media using the KnoxPlus engine.  It demonstrates how
the underlying classes (`Brand`, `ContentCreator`, `SocialPoster` and
`Scheduler`) can be integrated into a web service.  You can deploy this
application to platforms such as Heroku, Render or any other WSGI
compatible host.  The application is intentionally minimal; you can
extend it with authentication, templates or a front‑end framework.

Endpoints
---------

* **POST /generate** – Accepts JSON with `topic`, `brand_name` and
  `brand_color`.  Returns the generated post text and the path to the
  generated media file (MP4 or MP3 depending on your environment).
* **POST /schedule** – Allows scheduling a post to be published at a
  future time.  This endpoint accepts `topic`, `brand_name`,
  `brand_color`, `platforms` (comma separated) and `when` (ISO format).  It
  returns a confirmation message when scheduling is successful.

"""

from __future__ import annotations

import datetime as dt
import os

from flask import Flask, jsonify, request

from knoxplus import Brand, ContentCreator, SocialPoster, Scheduler, parse_datetime


app = Flask(__name__)

# In-memory scheduler; note that jobs are not persisted across restarts.
scheduler = Scheduler()


def _create_engine(data: dict) -> tuple[Brand, ContentCreator, SocialPoster]:
    """Instantiate brand, content creator and poster based on request data."""
    brand_name = data.get("brand_name", "KnoxPlus")
    brand_color = data.get("brand_color", "#000000")
    brand = Brand(name=brand_name, color=brand_color)
    creator = ContentCreator(brand)
    poster = SocialPoster(brand)
    return brand, creator, poster


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    topic = data.get("topic")
    if not topic:
        return jsonify({"error": "Missing required field 'topic'"}), 400
    _, creator, _ = _create_engine(data)
    post_text = creator.generate_post(topic)
    video_path = creator.create_video(post_text)
    return jsonify({"post_text": post_text, "media_path": video_path})


@app.route("/schedule", methods=["POST"])
def schedule():
    data = request.get_json(silent=True) or {}
    topic = data.get("topic")
    when_str = data.get("when")
    platforms = data.get("platforms", "twitter").split(",")
    if not (topic and when_str):
        return jsonify({"error": "Fields 'topic' and 'when' are required"}), 400
    brand, creator, poster = _create_engine(data)
    when = parse_datetime(when_str)
    post_text = creator.generate_post(topic)
    media_path = creator.create_video(post_text)
    def job():
        for platform in platforms:
            poster.post(platform.strip(), post_text, media_path)
    scheduler.schedule(when, job)
    return jsonify({"status": "scheduled", "execute_at": when.isoformat()})


@app.route("/")
def index():
    return (
        "<h1>KnoxPlus API</h1><p>Use POST /generate or /schedule to generate or schedule posts.</p>"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
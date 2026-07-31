#!/usr/bin/env python3
"""Sends a rendered post to the Make.com webhook, which publishes the
carousel to Instagram (Make's approved Meta app does the Graph API work).
Usage: MAKE_WEBHOOK_URL=... python3 post.py posts/<dir> <base_url>
base_url = public URL prefix where the slide PNGs are reachable, e.g.
https://raw.githubusercontent.com/<org>/masculinephilosopher-ig-media/main/<name>
Payload: {"caption": str, "images": [url, ...]}  (slide order preserved)"""
import json, os, re, sys, urllib.request


def main(post_dir, base_url):
    reel = os.path.join(post_dir, "reel.json")
    if os.path.exists(reel):  # reel post: Make routes on type=reel
        payload = {
            "type": "reel",
            "caption": json.load(open(reel))["caption"],
            "video_url": f"{base_url.rstrip('/')}/reel.mp4",
            "thumb_offset": 0,
        }
        return send(payload)
    slides = sorted((f for f in os.listdir(post_dir)
                     if re.fullmatch(r"slide-\d+\.jpg", f)),
                    key=lambda f: int(re.search(r"\d+", f).group()))
    # IG Graph API hard limit — 11 slides once failed SILENTLY in Make (2026-07-28)
    assert len(slides) <= 10, f"{len(slides)} slides — Instagram carousels max 10"
    payload = {
        "caption": open(os.path.join(post_dir, "caption.txt")).read(),
        "files": [{"media_type": "IMAGE",
                   "image_url": f"{base_url.rstrip('/')}/{f}"} for f in slides],
    }
    send(payload)


def send(payload):
    headers = {"Content-Type": "application/json"}
    if os.environ.get("MAKE_API_KEY"):
        headers["x-make-apikey"] = os.environ["MAKE_API_KEY"]
    req = urllib.request.Request(
        os.environ["MAKE_WEBHOOK_URL"], data=json.dumps(payload).encode(),
        headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        print("webhook response:", r.read().decode()[:200])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

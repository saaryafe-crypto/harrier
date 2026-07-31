#!/usr/bin/env python3
"""Turns a rendered tweet card into a 3-second reel video.
Usage: python3 reel.py posts/<dir>

Input:  <dir>/card.png (from render.py) + first audio file in ig/audio/
Output: <dir>/reel.mp4 (1080x1920, 3s, audio baked in)
        <dir>/reel.json (routes post.py to Make's reel branch)

Note: the Graph API cannot attach IG trending audio — the sound must be
baked into the video file. Drop the track (e.g. the Mask Off remix) at
ig/audio/track.mp3. If IG mutes it for copyright, swap the file."""
import glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SECONDS = 3


def audio_file():
    for ext in ("mp3", "m4a", "wav", "aac"):
        hits = sorted(glob.glob(os.path.join(HERE, "audio", f"*.{ext}")))
        if hits:
            return hits[0]
    return None


def build(post_dir):
    card = os.path.join(post_dir, "card.png")
    out = os.path.join(post_dir, "reel.mp4")
    assert os.path.exists(card), f"no card.png in {post_dir} — run render.py first"

    audio = audio_file()
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-t", str(SECONDS), "-i", card]
    if audio:
        cmd += ["-i", audio,
                "-af", f"atrim=0:{SECONDS},afade=t=out:st={SECONDS - 0.4}:d=0.4"]
        print("audio:", os.path.basename(audio))
    else:
        cmd += ["-f", "lavfi", "-t", str(SECONDS), "-i", "anullsrc=r=44100:cl=stereo"]
        print("WARNING: no file in ig/audio/ — reel will be silent")
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)

    caption = open(os.path.join(post_dir, "caption.txt")).read()
    json.dump({"caption": caption}, open(os.path.join(post_dir, "reel.json"), "w"),
              indent=1, ensure_ascii=False)
    print("reel ready:", out)


if __name__ == "__main__":
    build(sys.argv[1])

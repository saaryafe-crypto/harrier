#!/usr/bin/env python3
"""Publishes a reel via bundle.social with NATIVE Instagram trending audio
(the one thing the Graph API / Make cannot attach). Used by the 14:00 UTC
slot; Make keeps the other three slots.

Usage: python3 bundle_post.py posts/<dir>
Env:   BUNDLE_API_KEY (falls back to bundle_api_key in repo-root .env)

Flow: quota check (20 free posts/mo -> skip cleanly when spent)
      -> upload reel.mp4 -> search IG music library (rotating hard/
      aggressive queries, never soft) -> create REEL post with the track
      (original 3s-card audio muted) -> schedule first comment (share CTA).
"""
import datetime, json, os, sys, urllib.parse, urllib.request, uuid

API = "https://api.bundle.social/api/v1"
TEAM = os.environ.get("BUNDLE_TEAM_ID", "")
HERE = os.path.dirname(os.path.abspath(__file__))

# One query per weekday — variety without ever drifting into soft tracks.
AUDIO_QUERIES = ["dark phonk", "gym phonk", "hard trap instrumental",
                 "aggressive beat", "drift phonk", "phonk", "brazilian phonk"]

FIRST_COMMENT = ("Send this to a man who needs it today. "
                 "And tell me below: what's the ONE thing you refuse to quit on?")


def key():
    k = os.environ.get("BUNDLE_API_KEY")
    if not k:
        env = os.path.join(HERE, "..", ".env")
        if os.path.exists(env):
            for line in open(env):
                if line.startswith("bundle_api_key="):
                    k = line.split("=", 1)[1].strip()
    assert k, "no BUNDLE_API_KEY in env or .env"
    return k


def call(method, path, body=None, headers=None):
    h = {"x-api-key": key(), "User-Agent": "harrier-bot/1.0",
         **(headers or {})}
    data = None
    if body is not None and not isinstance(body, bytes):
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    elif isinstance(body, bytes):
        data = body
    req = urllib.request.Request(API + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"bundle.social {method} {path} -> {e.code}: {e.read().decode()[:500]}")


def upload(path):
    boundary = uuid.uuid4().hex
    name = os.path.basename(path)
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"teamId\"\r\n\r\n"
            f"{TEAM}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{name}\"\r\nContent-Type: video/mp4\r\n\r\n").encode()
    body += open(path, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
    return call("POST", "/upload/", body,
                {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def opening_energy(url):
    """Mean dBFS of a track's first 4s — the part IG actually plays.
    The API can't seek into a song, so the peak must BE the opening."""
    import subprocess, tempfile
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(4_000_000)  # first ~4MB is plenty for 4s
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(data)
        out = subprocess.run(
            ["ffmpeg", "-t", "4", "-i", f.name, "-af", "volumedetect",
             "-f", "null", "-"], capture_output=True, text=True).stderr
        os.unlink(f.name)
        for line in out.splitlines():
            if "mean_volume" in line:
                return float(line.split("mean_volume:")[1].split("dB")[0])
    except Exception as e:
        print("  energy probe failed:", e)
    return None


def pick_audio():
    q = AUDIO_QUERIES[datetime.date.today().toordinal() % len(AUDIO_QUERIES)]
    r = call("GET", "/misc/instagram/audio?" + urllib.parse.urlencode(
        {"teamId": TEAM, "audioType": "music", "searchQuery": q}))
    tracks = [t for t in (r.get("audio") or [])
              if (t.get("duration_in_ms") or 0) >= 30000] or (r.get("audio") or [])
    if not tracks:
        return None, q
    # score the top candidates by how hard their OPENING hits
    best, best_db = tracks[0], None
    for t in tracks[:5]:
        if not t.get("download_url"):
            continue
        db = opening_energy(t["download_url"])
        print(f'  candidate: {str(t.get("title"))[:35]:35s} opening {db} dB')
        if db is not None and (best_db is None or db > best_db):
            best, best_db = t, db
    return best, q


def gh_output(key, val):
    """Expose a step output so the workflow can fall back to Make on skip."""
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        open(p, "a").write(f"{key}={val}\n")


def publish(post_dir):
    usage = call("GET", "/organization/usage/posts")
    if usage.get("remaining", 0) < 1:
        print(f"bundle.social quota spent ({usage.get('used')}/{usage.get('limit')}) "
              "— falling back to Make for this slot")
        gh_output("posted", "false")
        return

    reel = os.path.join(post_dir, "reel.mp4")
    assert os.path.exists(reel), f"no reel.mp4 in {post_dir} — run reel.py first"
    caption = open(os.path.join(post_dir, "caption.txt")).read().strip()

    up = upload(reel)
    print("uploaded:", up["id"])

    track, q = pick_audio()
    ig = {"type": "REEL", "text": caption, "uploadIds": [up["id"]],
          "shareToFeed": True}
    if track:
        ig["musicSoundInfo"] = {"musicSoundId": track["audio_id"],
                                "musicSoundVolume": 90,
                                "videoOriginalSoundVolume": 0}
        print(f'audio ("{q}"): {track.get("title")} — {track.get("display_artist")}')
    else:
        print(f'WARNING: no IG music found for "{q}" — posting with baked audio')

    now = datetime.datetime.now(datetime.timezone.utc)
    post = call("POST", "/post/", {
        "teamId": TEAM,
        "title": os.path.basename(post_dir.rstrip("/")),
        "postDate": (now + datetime.timedelta(minutes=2)).isoformat(),
        "status": "SCHEDULED",
        "socialAccountTypes": ["INSTAGRAM"],
        "data": {"INSTAGRAM": ig},
    })
    print("post scheduled:", post["id"])

    call("POST", "/comment/", {
        "teamId": TEAM,
        "title": "first comment",
        "internalPostId": post["id"],
        "postDate": (now + datetime.timedelta(minutes=12)).isoformat(),
        "status": "SCHEDULED",
        "socialAccountTypes": ["INSTAGRAM"],
        "data": {"INSTAGRAM": {"text": FIRST_COMMENT}},
    })
    print("first comment scheduled")
    print(f"quota after this post: {usage['remaining'] - 1} of {usage['limit']} left")
    gh_output("posted", "true")


if __name__ == "__main__":
    publish(sys.argv[1])

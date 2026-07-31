# Remaining manual setup (one-time)

> The idea bank (`ig/ideas/`) lives in the private repo `harrier-state` —
> CI clones it at runtime with `MEDIA_REPO_TOKEN`. For local runs:
> `git clone git@github.com:<your-org>/harrier-state.git /tmp/state && cp -r /tmp/state/ideas ig/ideas`

## 1. Claude token (powers the cloud writer)
In a terminal:
```
claude setup-token        # copy the token it prints
gh secret set CLAUDE_CODE_OAUTH_TOKEN -R <your-org>/harrier
# paste the token when prompted, press Enter then Ctrl-D
```

## 2. Make.com scenario
Create a new scenario:

1. **Webhooks → Custom webhook** — name `masculine-philosopher-post`. Turn on
   "Get request headers" and set an API key requirement (x-make-apikey).
2. **Router** with two routes, filtered on the webhook JSON field `type`:
   - **Route A (type = reel)**: Instagram for Business →
     "Create a Reel" — Video URL = `video_url`, Caption = `caption` →
     then "Publish a Reel/Media".
   - **Route B (fallback, no type field — carousel)**:
     Iterator over `files[]` → Instagram for Business →
     "Create a Photo Item" for each `image_url` →
     "Create a Carousel" with the item IDs + `caption` → "Publish".
3. Connect the **@masculine_philosopher** Instagram professional account
   (must be linked to a Facebook page) when Make asks for the connection.
4. Copy the webhook URL + the API key into `.env` in this repo:
   ```
   MAKE_WEBHOOK_URL=...
   MAKE_API_KEY=...
   ```
   Then tell Claude — it sets the GitHub secrets from `.env` without
   displaying them.

## 3. Reel audio
Drop the track (Elliot Norlander, A3R0 — Mask Off, or any mp3) at:
```
ig/audio/track.mp3
```
It gets baked into every 3-second reel (first 3s, fade-out). If Instagram
ever mutes a reel for copyright, swap the file for a royalty-free dark beat.

## Payload contract (post.py → webhook)
- carousel: `{"caption": str, "files": [{"media_type": "IMAGE", "image_url": url}, ...]}`
- reel: `{"type": "reel", "caption": str, "video_url": url, "thumb_offset": 0}`

## Posting schedule (UTC cron `0 6,11,17 * * *`)
- 06:00 UTC → reel (09:00 IL)
- 11:00 UTC → carousel (14:00 IL)
- 17:00 UTC → reel (20:00 IL)

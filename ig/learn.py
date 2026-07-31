#!/usr/bin/env python3
"""Pure-data learning loop. Run weekly: .venv/bin/python learn.py [handle]
1. Re-scrapes OUR OWN page's recent posts (likes/comments) via spy.py — no login.
2. Joins them with the generated posts in posts/*/post.json (caption match).
3. Rewrites the measured-performance block in inspiration/learned.md.
   Numbers only — no assumptions. The writer prompt reads this file, so the
   system automatically writes more of what measurably worked.
4. Commits + pushes learned.md so the cloud writer sees the fresh data."""
import json, os, re, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OWN = "masculine_philosopher"
LEARNED = os.path.join(HERE, "inspiration", "learned.md")
MARK = ("<!-- data:begin -->", "<!-- data:end -->")


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def scrape_own(handle):
    from playwright.sync_api import sync_playwright
    import spy
    idx_path = os.path.join(spy.REF, "index.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else []
    # drop this handle's old entries so like-counts get refreshed, not skipped
    index = [e for e in index if e["handle"] != handle]
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            spy.PROFILE, headless=True, viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        pg.goto(f"https://www.instagram.com/{handle}/", wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        # "123 Followers, 45 Following, 6 Posts - ..." from the profile meta tag
        profile = spy.meta(pg, "og:description") or ""
        pg.close()
        spy.scrape_handle(ctx, handle, index)
        ctx.close()
    os.makedirs(spy.REF, exist_ok=True)
    json.dump(index, open(idx_path, "w"), indent=1)
    return [e for e in index if e["handle"] == handle], profile.split("-")[0].strip()


def local_posts():
    out, root = [], os.path.join(HERE, "posts")
    for d in sorted(os.listdir(root)):
        pj = os.path.join(root, d, "post.json")
        if not os.path.exists(pj):
            continue
        p = json.load(open(pj))
        hook = (p["text"].split("\n")[0] if "text" in p
                else p["slides"][0] if p.get("slides") else "")
        out.append({"dir": d, "kind": p.get("kind", "?"), "hook": hook,
                    "key": norm(p.get("caption", ""))[:40]})
    return out


def weekly_report(handle, profile, rows, posts):
    """Post the week's numbers via a GitHub issue (issue -> notification)."""
    from datetime import date, timedelta
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    published = [p for p in posts if p["dir"][:10] >= week_ago]
    lines = [f"**{profile or 'follower count unavailable'}**", "",
             f"- Posts published this week: {len(published)} "
             f"({sum(p['kind'] == 'reel' for p in published)} reels, "
             f"{sum(p['kind'] == 'carousel' for p in published)} carousels)",
             f"- Posts with measurable engagement: {len(rows)}"]
    if rows:
        med = statistics.median(r["likes"] for r in rows)
        lines += [f"- Median likes: {med:.0f} | total likes: {sum(r['likes'] for r in rows)}"
                  f" | total comments: {sum(r['comments'] for r in rows)}", "", "Top posts:"]
        for r in sorted(rows, key=lambda r: -r["likes"])[:3]:
            lines.append(f"- {r['likes']} likes, {r['comments']} comments ({r['kind']}): {r['hook']}")
    else:
        lines.append("- No likes registered yet — page is still warming up.")
    repo = os.environ.get("GITHUB_REPOSITORY", "harrier")
    subprocess.run(["gh", "issue", "create", "-R", repo,
                    "--title", f"Weekly IG report — @{handle} {date.today()}",
                    "--body", "\n".join(lines)], cwd=HERE)


def main(handle=OWN):
    scraped_all, profile = scrape_own(handle)
    scraped = [e for e in scraped_all if e.get("likes", 0) > 0]
    posts = local_posts()
    rows = []
    for e in scraped:
        key = norm(e["caption"])[:40]
        m = next((p for p in posts if key and p["key"] == key), None)
        rows.append({"likes": e["likes"], "comments": e["comments"],
                     "kind": m["kind"] if m else "?",
                     "hook": (m["hook"] if m else e["caption"][:80])})

    weekly_report(handle, profile, rows, posts)
    if not rows:
        raise SystemExit("report sent; no engagement data yet, learned.md unchanged")

    med = statistics.median(r["likes"] for r in rows)
    lines = [f"## Measured performance @{handle} — auto-updated {time.strftime('%Y-%m-%d')}, {len(rows)} posts, median {med:.0f} likes",
             "Real engagement numbers, not opinion. Write MORE like the over-performers, LESS like the under-performers.", ""]
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r["likes"])
    for k, ls in sorted(by_kind.items(), key=lambda kv: -statistics.median(kv[1])):
        lines.append(f"- format `{k}`: median {statistics.median(ls):.0f} likes across {len(ls)} posts")
    lines.append("")
    lines.append("OVER-performing hooks:")
    for r in sorted(rows, key=lambda r: -r["likes"])[:5]:
        lines.append(f"- {r['likes']} likes ({r['likes']/med:.1f}x median): {r['hook']}")
    lines.append("")
    lines.append("UNDER-performing hooks:")
    for r in sorted(rows, key=lambda r: r["likes"])[:3]:
        lines.append(f"- {r['likes']} likes ({r['likes']/med:.1f}x median): {r['hook']}")

    block = MARK[0] + "\n" + "\n".join(lines) + "\n" + MARK[1]
    text = open(LEARNED).read()
    if MARK[0] in text:
        text = re.sub(re.escape(MARK[0]) + r".*?" + re.escape(MARK[1]), block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    open(LEARNED, "w").write(text)
    print("\n" + block)

    subprocess.run(["git", "add", os.path.relpath(LEARNED, HERE)], cwd=HERE)
    r = subprocess.run(["git", "commit", "-m", f"learn: refresh @{handle} performance data"], cwd=HERE)
    if r.returncode == 0:
        subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=HERE, check=True)
        subprocess.run(["git", "push"], cwd=HERE, check=True)
        print("pushed — the cloud writer will use this data on the next post")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else OWN)

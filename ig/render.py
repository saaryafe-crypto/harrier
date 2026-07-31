#!/usr/bin/env python3
"""Renders Masculine Philosopher posts from a post JSON.
Usage: python3 render.py post.json out_dir/

Two formats (cloned from the owner's reference screenshots — do not restyle):

1. CAROUSEL (post.json has "slides"): 1080x1080 squares. Near-black card
   surrounded by a thin grey frame. ONE huge bold white centered line per
   slide. Bottom-center: "Masculine Philosopher" + Instagram glyph.
   Output: slide-N.jpg + caption.txt

2. REEL CARD (post.json has "text"): 1080x1920 black frame, tweet-style
   card — circular Tyler Durden avatar, "Masculine Philosopher" + blue
   verification check, grey @masculine_philosopher handle, white body text in
   short paragraphs. Output: card.png (reel.py turns it into a video).

The renderer stamps ALL text — never Canva."""
import html, json, os, subprocess, sys, tempfile

CHROME = os.environ.get("CHROME",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
HERE = os.path.dirname(os.path.abspath(__file__))

CHECK_SVG = ('<svg viewBox="0 0 24 24" fill="#1d9bf0"><path d="M22.25 12c0-1.43-.88-2.67'
 '-2.19-3.34.46-1.39.2-2.9-.81-3.91s-2.52-1.27-3.91-.81c-.66-1.31-1.91-2.19-3.34-2.19s'
 '-2.67.88-3.33 2.19c-1.4-.46-2.91-.2-3.92.81s-1.26 2.52-.8 3.91c-1.31.67-2.2 1.91-2.2 '
 '3.34s.89 2.67 2.2 3.34c-.46 1.39-.21 2.9.8 3.91s2.52 1.26 3.91.81c.67 1.31 1.91 2.19 '
 '3.34 2.19s2.68-.88 3.34-2.19c1.39.45 2.9.2 3.91-.81s1.27-2.52.81-3.91c1.31-.67 2.19'
 '-1.91 2.19-3.34zm-11.71 4.2L6.8 12.46l1.41-1.42 2.26 2.26 4.8-5.23 1.47 1.36-6.2 6.77z"/></svg>')

IG_GLYPH = ('<svg viewBox="0 0 24 24" fill="none" stroke="#FFF" stroke-width="1.8">'
 '<rect x="2.5" y="2.5" width="19" height="19" rx="5.2"/>'
 '<circle cx="12" cy="12" r="4.6"/><circle cx="17.6" cy="6.4" r="1.25" fill="#FFF" stroke="none"/></svg>')

CAROUSEL_CSS = """
@font-face{font-family:Poppins;src:url("FONTS/Poppins-SemiBold.ttf");font-weight:600}
@font-face{font-family:Poppins;src:url("FONTS/Poppins-ExtraBold.ttf");font-weight:800}
*{margin:0;box-sizing:border-box}
html,body{width:1080px;height:1080px;overflow:hidden}
body{background:#7a7a7a;font-family:Poppins,sans-serif;padding:22px}
.card{width:100%;height:100%;background:#070707;position:relative;
      display:flex;align-items:center;justify-content:center;padding:70px 64px 150px}
.line{font-weight:800;color:#FFF;text-align:center;font-size:SIZEpx;line-height:1.22}
.brand{position:absolute;bottom:44px;left:0;right:0;text-align:center}
.brand .name{font-weight:800;font-size:30px;color:#FFF;letter-spacing:.01em}
.brand svg{width:44px;height:44px;margin-top:12px}
.follow{display:flex;flex-direction:column;align-items:center;gap:34px}
.follow img{width:250px;height:250px;object-fit:cover;object-position:50% 18%;
            border:5px solid #FFF;display:block}
.follow .handle{font-weight:600;font-size:34px;color:#8B98A5}
"""

REEL_CSS = """
@font-face{font-family:Poppins;src:url("FONTS/Poppins-SemiBold.ttf");font-weight:600}
@font-face{font-family:Poppins;src:url("FONTS/Poppins-ExtraBold.ttf");font-weight:800}
*{margin:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden}
body{background:#000;font-family:Poppins,sans-serif;position:relative}
.card{position:absolute;left:110px;right:110px;top:50%;transform:translateY(-50%)}
.head{display:flex;align-items:center;gap:30px}
.head img{width:150px;height:150px;border-radius:50%;object-fit:cover;
          object-position:50% 18%;display:block}
.id .name{display:flex;align-items:center;gap:14px;
          font-weight:800;font-size:52px;color:#FFF;line-height:1.1}
.id .name svg{width:48px;height:48px;flex:none}
.id .handle{font-weight:600;font-size:40px;color:#8B98A5;margin-top:6px}
.text{margin-top:64px;font-weight:600;font-size:SIZEpx;line-height:1.42;color:#FFF}
.text p{margin-bottom:1.1em}
.text p:last-child{margin-bottom:0}
"""


def _shot(page_html, out_png, w, h):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page_html)
    subprocess.run([CHROME, "--headless", "--disable-gpu", f"--screenshot={out_png}",
                    f"--window-size={w},{h}", "--hide-scrollbars", f"file://{f.name}"],
                   check=True, capture_output=True)
    os.unlink(f.name)


def to_jpeg(png):
    jpg = png[:-4] + ".jpg"
    if sys.platform == "darwin":
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92",
                        png, "--out", jpg], check=True, capture_output=True)
    else:  # ubuntu runner: Pillow (installed in the workflow)
        from PIL import Image
        Image.open(png).convert("RGB").save(jpg, quality=92)
    os.remove(png)
    return jpg


def carousel_slide_html(text, hsize, n, total):
    css = CAROUSEL_CSS.replace("FONTS", HERE + "/fonts").replace("SIZE", str(hsize))
    # ONE huge line per slide, no sub-lines, no slide counter
    body = f'<div class="line">{html.escape(text)}</div>'
    if n == total:  # follow-CTA slide: square profile pic above the CTA line
        body = (f'<div class="follow"><img src="{HERE}/art/avatar.png">'
                f'<div class="line">{html.escape(text)}</div>'
                f'<div class="handle">@masculine_philosopher</div></div>')
    return f'''<!doctype html><meta charset="utf-8"><style>{css}</style>
<body><div class="card">
{body}
<div class="brand"><div class="name">Masculine Philosopher</div>{IG_GLYPH}</div>
</div></body>'''


def reel_card_html(text, hsize):
    css = REEL_CSS.replace("FONTS", HERE + "/fonts").replace("SIZE", str(hsize))
    # single \n inside a paragraph = real line break (numbered lists must
    # stack vertically, never run together)
    paras = "".join("<p>" + html.escape(p.strip()).replace("\n", "<br>") + "</p>"
                    for p in text.split("\n\n") if p.strip())
    return f'''<!doctype html><meta charset="utf-8"><style>{css}</style>
<body><div class="card">
<div class="head"><img src="{HERE}/art/avatar.png"><div class="id">
  <div class="name">Masculine Philosopher {CHECK_SVG}</div>
  <div class="handle">@masculine_philosopher</div>
</div></div>
<div class="text">{paras}</div>
</div></body>'''


def hsize_for(text, base=None):
    """Auto type size: shorter line -> bigger type (carousel slides)."""
    if base:
        return base
    n = len(text)
    if n <= 14: return 120
    if n <= 26: return 100
    if n <= 44: return 84
    if n <= 70: return 70
    return 58


def render(post_path, out_dir):
    post = json.load(open(post_path))
    os.makedirs(out_dir, exist_ok=True)

    if "slides" in post:  # carousel
        total = len(post["slides"])
        for n, s in enumerate(post["slides"], 1):
            text = s["text"] if isinstance(s, dict) else s
            size = hsize_for(text, s.get("hsize") if isinstance(s, dict) else None)
            if n == total:  # room for the profile-pic block
                size = min(size, 64)
            png = os.path.join(out_dir, f"slide-{n}.png")
            _shot(carousel_slide_html(text, size, n, total), png, 1080, 1080)
            print("rendered", to_jpeg(png))
    else:  # reel card
        n = len(post["text"])
        size = post.get("hsize") or (47 if n <= 260 else 42 if n <= 420 else 38)
        png = os.path.join(out_dir, "card.png")
        _shot(reel_card_html(post["text"], size), png, 1080, 1920)
        print("rendered", png)

    open(os.path.join(out_dir, "caption.txt"), "w").write(post["caption"])
    print("caption written")


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "out")

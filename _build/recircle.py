"""Transpose the LLMday London lineup to PEC London, every headshot on the PEC circle.

LLMday London 2026 Q4 and PEC London 2026 are one co-located event: llmday is the source of truth.
"Transpose the lineup from LLMday to PEC" (Marek 2026-11-11) means:
  1. copy llmday/<event>/_db/talks.csv byte for byte to this repo's <event>/_db/talks.csv
  2. every headshot the lineup uses must be in speakers/ ON THE PEC CIRCLE: a missing one, or one still
     on the LLMday circle (copied over as it was), is re-mixed from llmday/speakers/ onto the PEC circle.
     A headshot already on the PEC circle is never touched (they were hand-checked).

The swap: the person is greyscale, so each pixel L = m*grey + b*C_llmday (least squares per pixel) and
the output is L + b*(C_pec - C_llmday): person, framing and hair edges unchanged, only the circle moves.
The two circle colour maps live in _build/circles/ (estimated from 75 LLMday and 83 PEC headshots on
2026-11-11; `fitmaps` rebuilds them). Checked against hand-made PEC versions: mean diff ~0.5/255.

usage (repo root, sister llmday checkout next to this one):
  python _build/recircle.py transpose [event]     # default event: 2026-london-q4; --dry-run to only report
  python _build/recircle.py audit [event]         # which headshots are on which circle
  python _build/recircle.py convert <src.png> <dst.png>
  python _build/recircle.py check                 # compare against hand-made PEC versions
  python _build/recircle.py fitmaps               # rebuild _build/circles/*.png
"""
import csv, glob, os, shutil, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LLMDAY = os.path.join(os.path.dirname(ROOT), "llmday")
CIRCLES = os.path.join(ROOT, "_build", "circles")
N = 1000   # headshots are 1000x1000 RGBA
DS = 250   # map estimation grid


def load(p, size=N):
    im = Image.open(p).convert("RGBA")
    if im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    return np.asarray(im).astype(np.float64)


def maps():
    cl = np.asarray(Image.open(os.path.join(CIRCLES, "llmday.png")).convert("RGB")).astype(np.float64)
    cp = np.asarray(Image.open(os.path.join(CIRCLES, "pec.png")).convert("RGB")).astype(np.float64)
    return cl, cp


# ---------------------------------------------------------------- circle maps

def _estimate(files):
    stack, chs = [], []
    for f in files:
        a = load(f, DS)
        rgb, al = a[..., :3], a[..., 3]
        chroma = rgb.max(-1) - rgb.min(-1)
        chroma[al < 250] = -1
        stack.append(rgb); chs.append(chroma)
    stack, chs = np.stack(stack), np.stack(chs)
    top = chs.max(0)
    ok = (chs >= 0.75 * top[None]) & (chs > 8)   # near the most colourful pixel seen there = bare circle
    with np.errstate(all="ignore"):
        best = np.nan_to_num(np.nanmedian(np.where(ok[..., None], stack, np.nan), 0))
    return best, np.where(ok.sum(0) >= 3, top, 0.0)


def _fit(best, bestc, deg=5):
    from PIL import ImageFilter
    ys, xs = np.mgrid[0:DS, 0:DS]
    u, v = (xs + 0.5) / DS * 2 - 1, (ys + 0.5) / DS * 2 - 1
    thr = np.percentile(bestc[bestc > 0], 30)
    m = (bestc >= thr) & (u**2 + v**2 < 0.98)
    terms = [(i, j) for i in range(deg + 1) for j in range(deg + 1 - i)]
    coef = np.linalg.lstsq(np.stack([u[m]**i * v[m]**j for i, j in terms], 1), best[m], rcond=None)[0]
    ys, xs = np.mgrid[0:N, 0:N]
    u, v = (xs + 0.5) / N * 2 - 1, (ys + 0.5) / N * 2 - 1
    full = np.stack([u**i * v**j for i, j in terms], -1) @ coef           # smooth fill where never visible
    meas = Image.fromarray(np.clip(best, 0, 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    w = Image.fromarray(((bestc >= thr) * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    w = np.asarray(w.filter(ImageFilter.GaussianBlur(6))).astype(np.float64)[..., None] / 255
    meas = np.asarray(meas.filter(ImageFilter.GaussianBlur(3))).astype(np.float64)
    return np.clip(w * meas + (1 - w) * full, 0, 255)


def fitmaps():
    names = set()
    for c in glob.glob(os.path.join(LLMDAY, "2026-*", "_db", "talks.csv")):
        names |= {r["photo"] for r in csv.DictReader(open(c, encoding="utf-8")) if r.get("photo")}
    llm = [f for f in sorted(glob.glob(os.path.join(LLMDAY, "speakers", "*.png"))) if os.path.basename(f) in names]
    pec = sorted(glob.glob(os.path.join(ROOT, "speakers", "*.png")))
    os.makedirs(CIRCLES, exist_ok=True)
    for tag, files in (("llmday", llm), ("pec", pec)):
        Image.fromarray(_fit(*_estimate(files)).round().astype(np.uint8)).save(os.path.join(CIRCLES, tag + ".png"))
        print(tag, len(files), "headshots ->", os.path.join("_build", "circles", tag + ".png"))


# ---------------------------------------------------------------- swap + audit

def convert(src, dst, cm=None):
    cl, cp = cm or maps()
    a = load(src)
    L, al = a[..., :3], a[..., 3:]
    s12, s22 = cl.sum(-1), (cl * cl).sum(-1)
    r1, r2 = L.sum(-1), (L * cl).sum(-1)
    det = 3.0 * s22 - s12 * s12
    det = np.where(np.abs(det) < 1e-6, 1e-6, det)
    b = np.clip((3.0 * r2 - s12 * r1) / det, 0, 1)[..., None]
    out = np.clip(L + b * (cp - cl), 0, 255)
    Image.fromarray(np.concatenate([out, al], -1).round().astype(np.uint8), "RGBA").save(dst, optimize=True)


def which_circle(path, cm=None):
    """'pec', 'llmday' or '?' - counts bare-circle pixels matching each map where the two maps differ."""
    cl, cp = cm or maps()
    a = load(path)
    L, al = a[..., :3], a[..., 3]
    differ = (np.abs(cl - cp).max(-1) > 40) & (al > 250)
    dl, dp = np.abs(L - cl).max(-1), np.abs(L - cp).max(-1)
    nl, np_ = int(((dl < 14) & differ).sum()), int(((dp < 14) & differ).sum())
    if max(nl, np_) < 2000:
        return "?", nl, np_
    return ("pec" if np_ > nl else "llmday"), nl, np_


def lineup_photos(csv_path):
    seen = []
    for r in csv.DictReader(open(csv_path, encoding="utf-8")):
        p = (r.get("photo") or "").strip()
        if p and p not in seen:
            seen.append(p)
    return seen


def audit(event):
    cm = maps()
    rows = []
    for p in lineup_photos(os.path.join(ROOT, event, "_db", "talks.csv")):
        f = os.path.join(ROOT, "speakers", p)
        rows.append((p, which_circle(f, cm) if os.path.exists(f) else ("missing", 0, 0)))
    for p, (c, nl, np_) in rows:
        print("%-8s %-45s (llmday px %d, pec px %d)" % (c, p, nl, np_))
    return rows


def transpose(event, dry=False):
    src_csv = os.path.join(LLMDAY, event, "_db", "talks.csv")
    dst_csv = os.path.join(ROOT, event, "_db", "talks.csv")
    same = open(src_csv, "rb").read() == open(dst_csv, "rb").read()
    print("talks.csv:", "already identical" if same else "copied from llmday" + (" (dry run)" if dry else ""))
    if not same and not dry:
        shutil.copyfile(src_csv, dst_csv)
    cm = maps()
    done, kept, problems = [], 0, []
    for p in lineup_photos(src_csv):
        dst = os.path.join(ROOT, "speakers", p)
        src = os.path.join(LLMDAY, "speakers", p)
        state = which_circle(dst, cm)[0] if os.path.exists(dst) else "missing"
        if state == "pec":
            kept += 1
            continue
        if not os.path.exists(src):
            problems.append("%s: %s in PEC and not in llmday/speakers - needs a photo" % (p, state))
            continue
        src_state = which_circle(src, cm)[0]
        if src_state != "llmday":
            problems.append("%s: llmday copy is on the '%s' circle, not swapped - check it by eye" % (p, src_state))
            continue
        if not dry:
            convert(src, dst, cm)
            after = which_circle(dst, cm)[0]
            if after != "pec":
                problems.append("%s: still reads as '%s' after the swap - check it by eye" % (p, after))
        done.append("%s (%s)" % (p, state))
    print("headshots kept (already on the PEC circle): %d" % kept)
    print("headshots put on the PEC circle%s: %d" % (" (dry run)" if dry else "", len(done)))
    for d in done:
        print("  +", d)
    for pr in problems:
        print("  !", pr)
    return done, problems


def check():
    cm = maps()
    tmp = os.path.join(ROOT, ".cache", "recircle-check.png")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    for n in ("Harrison Kirby", "Paulius Rauba", "Veronika Ulanova"):
        convert(os.path.join(LLMDAY, "speakers", n + ".png"), tmp, cm)
        a, b = load(tmp), load(os.path.join(ROOT, "speakers", n + ".png"))
        d = np.abs(a[..., :3] - b[..., :3])[a[..., 3] > 0]
        print("%s: mean abs diff %.2f, p99 %.1f" % (n, d.mean(), np.percentile(d, 99)))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cmd = args[0] if args else "audit"
    event = args[1] if len(args) > 1 else "2026-london-q4"
    if cmd == "transpose": transpose(event, dry="--dry-run" in sys.argv)
    elif cmd == "audit": audit(event)
    elif cmd == "convert": convert(args[1], args[2])
    elif cmd == "check": check()
    elif cmd == "fitmaps": fitmaps()
    else: sys.exit(__doc__)

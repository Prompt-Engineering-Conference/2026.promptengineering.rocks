"""Twin events (Marek 2026-11-27): a PEC event that is the same event as an LLMday one - one lineup, schedule,
sponsors, Luma and CFP, built in llmday - is a copy of llmday's event folder with PEC's brand on top. This script
makes that copy; .github/workflows/twin.yml runs it every 15 minutes and on every push, so a twin can never drift
(an edit made here in PEC to a twin's facts is put back within minutes - change the event in llmday instead).

  twins.yml          which events are twins (repo root, PEC)
  _build/twin.yml    what stays PEC's: brand metadata keys + brand files. Everything else is llmday's.

usage (repo root, llmday checkout next to this repo, or --llmday <path>):
  python _build/twin_sync.py            copy every twin, print what changed
  python _build/twin_sync.py --check    only report the differences, exit 1 if there are any
  python _build/twin_sync.py --no-headshots
"""
import fnmatch, os, re, shutil, subprocess, sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = sys.argv[1:]
CHECK = "--check" in ARGS
HEADSHOTS = "--no-headshots" not in ARGS
LLMDAY = ARGS[ARGS.index("--llmday") + 1] if "--llmday" in ARGS else os.path.join(os.path.dirname(ROOT), "llmday")
KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:")

changes, notes = [], []


def rd(p):
    with open(p, "rb") as f:
        return f.read()


def wr(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def put(dst, data, what):
    """Write data to dst unless it is already identical; record the change."""
    if os.path.exists(dst) and rd(dst) == data:
        return
    changes.append(what)
    if not CHECK:
        wr(dst, data)


def tracked(repo, prefix):
    out = subprocess.run(["git", "-C", repo, "ls-files", "-z", "--", prefix], capture_output=True).stdout
    return [p.decode("utf-8") for p in out.split(b"\0") if p and os.path.isfile(os.path.join(repo, p.decode("utf-8")))]


def blocks(text):
    """Top-level YAML blocks of a metadata file: [(key or None, lines)]. A block is a top-level key line plus
    everything up to the next one (its indented lines, and comments/blank lines that follow it)."""
    out = [(None, [])]
    for line in text.splitlines(keepends=True):
        m = KEY_RE.match(line)
        if m:
            out.append((m.group(1), [line]))
        else:
            out[-1][1].append(line)
    return out


def is_brand(key, brand_keys):
    return any(fnmatch.fnmatchcase(key, pat) for pat in brand_keys)


def merge_metadata(src_text, own_text, brand_keys):
    """llmday's metadata.yml, text kept as is, with every brand key's block taken from PEC's file instead.
    PEC brand keys llmday does not have go right after the last brand block."""
    own = {k: "".join(v) for k, v in blocks(own_text) if k}
    out, used, last_brand = [], set(), None
    for k, lines in blocks(src_text):
        if k and is_brand(k, brand_keys):
            if k in own:
                out.append(own[k] if own[k].endswith("\n") else own[k] + "\n")
                used.add(k)
            last_brand = len(out)
        else:
            out.append("".join(lines))
    extra = [own[k] if own[k].endswith("\n") else own[k] + "\n" for k in own if is_brand(k, brand_keys) and k not in used]
    if extra:
        at = last_brand if last_brand is not None else len(out)
        out[at:at] = extra
    return "".join(out)


def where(repo, folder):
    for base in (folder, "past/" + folder):
        if os.path.isfile(os.path.join(repo, base, "metadata.yml")):
            return base
    return None


def sync_event(twin, cfg):
    src_folder, folder = twin["source"], twin.get("folder") or twin["source"]
    src_base = where(LLMDAY, src_folder)
    if not src_base:
        notes.append("%s: llmday has no event folder %s - nothing copied" % (folder, src_folder))
        return
    dst_base = where(ROOT, folder) or src_base.replace(src_folder, folder)
    want_base = ("past/" if src_base.startswith("past/") else "") + folder
    if dst_base != want_base:   # llmday moved the event to past/ (or back): PEC follows
        notes.append("%s: moved to %s like llmday (PEC home/metadata.yml events/events_past needs the same move)" % (folder, want_base))
        dst_base = want_base
    src_dir, dst_dir = os.path.join(LLMDAY, src_base), os.path.join(ROOT, dst_base)

    src_meta = yaml.safe_load(rd(os.path.join(src_dir, "metadata.yml"))) or {}
    if str(src_meta.get("twin") or "").lower() != "pec":
        notes.append("%s: llmday's metadata.yml has no 'twin: pec' - still copied (twins.yml decides); add it there" % folder)

    brand_files = cfg.get("brand_files") or []
    own_meta_p = os.path.join(dst_dir, "metadata.yml")
    if not os.path.exists(own_meta_p):   # a new twin: PEC's brand block starts from its event template
        own_meta_p = os.path.join(ROOT, "_event_template", "metadata.yml")
    seen = set()
    for p in tracked(LLMDAY, src_base + "/"):
        rel = p[len(src_base) + 1:]
        seen.add(rel)
        if any(fnmatch.fnmatchcase(rel, pat) for pat in brand_files):
            continue
        dst = os.path.join(dst_dir, rel)
        if rel == "metadata.yml":
            text = merge_metadata(rd(os.path.join(LLMDAY, p)).decode("utf-8"), rd(own_meta_p).decode("utf-8"), cfg["brand_keys"])
            check_meta(text, src_meta, folder, cfg["brand_keys"])
            put(dst, text.encode("utf-8"), "%s/metadata.yml (event facts from llmday)" % dst_base)
        else:
            put(dst, rd(os.path.join(LLMDAY, p)), "%s/%s" % (dst_base, rel))
    # PEC files llmday does not have (stale slides, an old template) go, except PEC's own brand files
    for p in tracked(ROOT, dst_base + "/"):
        rel = p[len(dst_base) + 1:]
        if rel not in seen and not any(fnmatch.fnmatchcase(rel, pat) for pat in brand_files):
            changes.append("%s/%s (removed: llmday has no such file)" % (dst_base, rel))
            if not CHECK:
                os.remove(os.path.join(ROOT, p))
    # the old folder, when llmday moved the event
    old = where(ROOT, folder)
    if old and old != dst_base:
        for p in tracked(ROOT, old + "/"):
            changes.append("%s (moved to %s)" % (p, dst_base))
            if not CHECK:
                os.remove(os.path.join(ROOT, p))

    sponsor_logos(src_meta, folder)
    home_card(src_meta, folder, LLMDAY_HOME.get(src_folder) or {})
    if HEADSHOTS:
        headshots(os.path.join(src_dir, "_db", "talks.csv"), folder)


def check_meta(text, src_meta, folder, brand_keys):
    """The merged file must parse, carry every llmday fact unchanged and only PEC's brand keys."""
    merged = yaml.safe_load(text) or {}
    for k, v in src_meta.items():
        if not is_brand(k, brand_keys) and merged.get(k) != v:
            sys.exit("%s: merged metadata.yml lost llmday's %r - not writing it" % (folder, k))


def sponsor_logos(src_meta, folder):
    """Sponsor logos live in each repo's root sponsors/: a logo the twin uses that PEC lacks comes from llmday."""
    for s in src_meta.get("sponsors") or []:
        logo = str((s or {}).get("logo") or "")
        if not logo:
            continue
        dst, src = os.path.join(ROOT, "sponsors", logo), os.path.join(LLMDAY, "sponsors", logo)
        if not os.path.exists(dst):
            if os.path.exists(src):
                put(dst, rd(src), "sponsors/%s (logo from llmday, for %s)" % (logo, folder))
            else:
                notes.append("%s: sponsor logo %s is in neither repo's sponsors/" % (folder, logo))


def home_card(src_meta, folder, src_entry):
    """PEC's home card keeps its own name and picture; date and location follow the event."""
    p = os.path.join(ROOT, "home", "metadata.yml")
    text = rd(p).decode("utf-8")
    want = {"date": src_meta.get("date_string"), "location": src_entry.get("location") or src_meta.get("location_string")}
    lines = text.splitlines(keepends=True)
    # find the entry (a "  - name:" item) whose url is ./<folder>/
    starts = [i for i, l in enumerate(lines) if re.match(r"^\s*-\s+name\s*:", l)]
    for n, s in enumerate(starts):
        e = starts[n + 1] if n + 1 < len(starts) else len(lines)
        seg = lines[s:e]
        if not any(re.match(r"^\s*url\s*:\s*\./%s/?\s*$" % re.escape(folder), l) for l in seg):
            continue
        indent = re.match(r"^(\s*)-", seg[0]).group(1) + "  "
        nl = "\r\n" if seg[0].endswith("\r\n") else "\n"
        for key, val in want.items():
            if not val:
                continue
            new = '%s%s: %s%s' % (indent, key, ('"%s"' % val) if key == "date" else val, nl)
            idx = next((j for j, l in enumerate(seg) if re.match(r"^\s*%s\s*:" % key, l)), None)
            if idx is None:
                seg.insert(1, new)
            elif seg[idx] != new:
                seg[idx] = new
        lines[s:e] = seg
        break
    else:
        notes.append("%s: PEC home/metadata.yml has no card for ./%s/ - add one (PEC name + picture)" % (folder, folder))
        return
    put(p, "".join(lines).encode("utf-8"), "home/metadata.yml (%s card: date/location)" % folder)


def headshots(src_csv, folder):
    """Every headshot the lineup uses, on the PEC circle (recircle.py): missing ones and any still on the LLMday
    circle are re-mixed from llmday/speakers/; ones already on the PEC circle are never touched."""
    sys.path.insert(0, os.path.join(ROOT, "_build"))
    import recircle as rc
    cm = rc.maps()
    for p in rc.lineup_photos(src_csv):
        dst, src = os.path.join(ROOT, "speakers", p), os.path.join(LLMDAY, "speakers", p)
        state = rc.which_circle(dst, cm)[0] if os.path.exists(dst) else "missing"
        if state == "pec":
            continue
        if not os.path.exists(src):
            notes.append("%s: headshot %s is %s here and not in llmday/speakers - needs a photo" % (folder, p, state))
            continue
        if rc.which_circle(src, cm)[0] != "llmday":
            notes.append("%s: llmday's %s is not on the LLMday circle - not swapped, check it by eye" % (folder, p))
            continue
        changes.append("speakers/%s (onto the PEC circle, was %s)" % (p, state))
        if not CHECK:
            rc.convert(src, dst, cm)
            if rc.which_circle(dst, cm)[0] != "pec":
                notes.append("%s: speakers/%s still reads as LLMday after the swap - check it by eye" % (folder, p))


if __name__ == "__main__":
    if not os.path.isdir(LLMDAY):
        sys.exit("no llmday checkout at %s (use --llmday <path>)" % LLMDAY)
    cfg = yaml.safe_load(rd(os.path.join(ROOT, "_build", "twin.yml")))
    twins = yaml.safe_load(rd(os.path.join(ROOT, "twins.yml"))) or []
    home = yaml.safe_load(rd(os.path.join(LLMDAY, "home", "metadata.yml"))) or {}
    LLMDAY_HOME = {str(e.get("url") or "").strip("./").rstrip("/"): e for e in (home.get("events") or []) + (home.get("events_past") or [])}
    for t in twins:
        sync_event(t, cfg)
    head = subprocess.run(["git", "-C", LLMDAY, "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True).stdout.strip()
    print("llmday %s, %d twin(s): %s" % (head or "?", len(twins), ", ".join(t.get("folder") or t["source"] for t in twins)))
    print(("differences: %d" if CHECK else "changed: %d") % len(changes))
    for c in changes:
        print("  ~", c)
    for n in notes:
        print("  !", n)
    sys.exit(1 if CHECK and changes else 0)

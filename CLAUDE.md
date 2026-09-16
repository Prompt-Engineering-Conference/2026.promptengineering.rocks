# Prompt Engineering Conference (PEC) — project overview for Claude Code

## What this is
A static site generator for the Prompt Engineering Conference (promptengineering.rocks). Each event is a separate folder (e.g. `2026-london-q4/`). `2023-online/` and `2024-online/` are frozen archives on an old generator - never touch them. `landing/`, `portal/` and `badges/` are standalone side projects, not part of the site build. Python + Jinja2 renders HTML into a `static/` subfolder per event.

## How to build

Build one event:
```bash
cd 2026-london-q4
make generate
```

Build all events:
```bash
for d in 2025-london-q4 2026-london-q4; do (cd "$d" && make generate); done
```

Output lands in `<event>/static/` — that's the deployable folder.

## Folder structure

```
_event_template/        ← master template — changes here propagate to all events
  _build/generate.py    ← the build script
  _templates/           ← Jinja2 HTML templates

_assets/template_v1/    ← shared CSS, JS, images (copied into static/ at build time)

sponsors/               ← sponsor logo images (copied into static/ at build time)
sponsorship.yaml        ← pricing tiers definition
home/metadata.yml       ← single source of truth for all events list

2026-london-q4/         ← one event folder (all event folders have identical structure)
  _build/generate.py    ← copy of _event_template/_build/generate.py
  _templates/           ← copy of _event_template/_templates/
  _db/talks.csv         ← speaker/talk data for this event
  _db/sponsors.csv      ← sponsor data for this event (if present)
  metadata.yml          ← event-specific config (city, date, capacity, etc.)
  assets/               ← event-specific images
  static/               ← BUILD OUTPUT (git-ignored)
```

## The golden rule
**Always edit `_event_template/` first, then copy to all event folders.**

After changing `_event_template/_build/generate.py` or any file in `_event_template/_templates/`, propagate with:
```bash
for event in 2025-london-q4 2026-london-q4; do   # never the frozen 2023-online / 2024-online folders
  cp _event_template/_build/generate.py $event/_build/generate.py
  cp _event_template/_templates/_base.html $event/_templates/_base.html
  cp _event_template/_templates/index.html $event/_templates/index.html
  cp _event_template/_templates/talk.html $event/_templates/talk.html
  cp _event_template/_templates/_lead_form.html $event/_templates/_lead_form.html
  cp _event_template/_templates/sponsorship.html $event/_templates/sponsorship.html
  cp _event_template/_templates/onboarding.html $event/_templates/onboarding.html
  cp _event_template/_templates/fasttrack.html $event/_templates/fasttrack.html
  cp _event_template/_templates/invitation.html $event/_templates/invitation.html
  cp _event_template/_templates/onboardsponsor.html $event/_templates/onboardsponsor.html
done
```
(everything except `venue.html`, which is per event.)

## Key templates
- `_templates/sponsorship.html` — sponsorship page; pricing tiers + expandable stats panel
- `_templates/index.html` — event homepage
- `_templates/_base.html` — shared layout; its og:image/twitter:image use the event's `photo_url` card image from `home/metadata.yml` (computed as `og_image_url` in generate.py, falling back to the first hero photo with a build warning)

## Stats panel (sp-stats-inner)
The "I need more stats" expandable section on the sponsorship page has two kinds of content:
- **Dynamic** (from generate.py): total_attendees, total_speakers, total_events, total_countries, global_top_companies (top 10 speaker orgs across all events), global_sponsors (deduplicated sponsors), timeline_events
- **Static** (hardcoded, derived from attendee CSV analysis): role breakdown, seniority, company size, top attendee companies

**Job-title filter:** `looks_like_job_title()` / `company_parts()` near the top of `_build/generate.py` keep speakers' job titles ("Principal Software Engineer", "Team Lead, SRE", "ex-Google SRE", stealth/independent/freelance) out of both the About panel's "Companies presenting" list and the sponsorship top-companies stats. A value is a title when its last word is a role noun, it carries seniority + a role word, starts with `ex-`, or consists only of role/tech vocabulary; company names with a proper noun survive ("Varnish Software", "Reliability Engineering Lab"). Dropped values are printed at build time. To extend, add words to `_JT_ROLE_NOUNS` / `_JT_VOCAB` / `_JT_EXPLICIT` in `_event_template/_build/generate.py` and propagate. Same code in llmday, sreday and platformday.

## Sister repos
Same structure: `llmday` (the reference copy), `sreday`, `platformday`. Ports go llmday -> PEC; PEC keeps a few local deltas in `_event_template/_build/generate.py` (`_og_domain` og:image fallback, `%I` instead of `%-I` for Windows builds, its own `_sp_exclude_logos` list). Marek: **PEC is no sister brand** on the sites - no cross-brand buttons, no PEC chip on the other brands' forms.

## Forms (lead form + hidden organizer pages)
The lead form and the hidden `/<event>/{onboarding,fasttrack,invitation,onboardsponsor}/` pages share the Apps Script deployments of llmday (`llmday/_build/*.gs`, brand key `pec` from `brand_key` in the event `metadata.yml`). PEC has no mail alias: emails go out from `mark@llmday.com`, the fast-track `anna@` route resolves to `anna@llmday.com`, the speaker discount code is `PEC20`. The PEC lead form has no "which conference" picker. See README for details.

## Dependencies
```bash
pip install jinja2 markdown pyyaml --break-system-packages
```
If `jinja-markdown` fails to install (network proxy), a local stub exists at `_build/jinja_markdown.py` — copy it alongside `generate.py` before running the build.

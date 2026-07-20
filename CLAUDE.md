# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Hugo static-site blog (theme: PaperMod, git submodule under `themes/PaperMod`) that explains Korean economic news to non-expert readers, deployed to GitHub Pages. There is no application code — the actual product is (a) the Hugo content/config and (b) two Claude Code custom slash commands that generate that content.

## Commands

```bash
hugo server              # local dev server with live reload
hugo --gc --minify       # production build (what CI runs), outputs to ./public
```

## GitHub CLI

`gh` is the preferred CLI for GitHub tasks in this repository. Check authentication with `gh auth status` before querying issues, pull requests, or Actions. Use `gh pr view`, `gh pr checks`, and `gh run view` for read-only inspection. Never merge, close, delete, or push through `gh` without explicit user approval. Keep post and dictionary drafts at `draft: true` until that approval is given.

No test suite, no linter — this is prompt files + Markdown content + Hugo config. "Correctness" for the slash commands means the prompt text is internally consistent and matches Hugo's actual content-file conventions (see below), not passing tests. Verify changes to `.claude/commands/*.md` or `.claude/daily-post/*.md` by running `hugo --gc --minify` and checking the `Pages` / `Non-page files` counts in the build summary, and by grepping for cross-file references (section numbers, file paths) actually resolving.

CI (`.github/workflows/hugo.yml`) builds with Hugo `0.164.0` on push to `main` and deploys via `actions/deploy-pages` — no `gh-pages` branch. Locally installed Hugo should match that version.

## The actual workflow: /daily-post

This blog is written by invoking `/daily-post`. No-arg = unattended (cloud-routine) contract; `/daily-post manual` = interactive. `.claude/commands/daily-post.md` is a thin 7-step sequencer, not where the writing logic lives — it Reads and follows stage files under `.claude/daily-post/`:

- `rank.md` — collects candidates (Hankyung 3 feeds, falling back through 연합뉴스/경향신문/동아일보/한겨레 if fewer than 10 fresh articles), scores them 0–15 across 5 criteria, and applies an 8-point quality floor. Unattended mode auto-picks #1 and aborts with zero output below threshold; manual mode presents 3 candidates and lets the user choose.
- (sequencer §2) fetches the source article (WebFetch) — aborts rather than fabricating facts if the fetch fails; unattended mode discards the candidate outright rather than falling through to #2.
- (sequencer §3) gathers external related articles via WebSearch — omits the field entirely on failure/empty results rather than inventing URLs.
- `analysis.md` — builds an "analysis note" (3-lens macro classification with lead/coincident tagging, a chapter lookup into `macro-reference.md`, a 🟢/🟡/🔴 threshold table for 1–2 web-searched indicators) that is *not* saved to disk, only carried forward in-context.
- `draft.md` — does the actual post writing, dictionary-entry creation, and wikilinking, consuming all 4 analysis-note fields (건드리는 렌즈 / 선행 vs 동행 / 확인된 수치 / 자산군별 함의) via one explicit §2 bullet each. `draft.md` delegates prose style/tone/prohibition rules to `.claude/daily-post/writing-styles.md` (no bold, 두괄식, numeric redlines extended to causal claims, personalized-advice ban extended to repeated directional sector calls, the 7-item AI-artifact self-review checklist) via inline path references.
- (sequencer §6) is the publish gate: unattended mode always writes `draft: true` and pushes only to an `auto/post-YYYY-MM-DD` branch + PR, never `main`. Manual mode requires an explicit answer to a specific approval question before flipping `draft: false` and running `git add`/`commit`/`push origin main`.

**Why the stages live at `.claude/daily-post/`, not under `.claude/commands/`:** Claude Code auto-registers any `.md` file found anywhere under `.claude/commands/` (including subdirectories) as its own top-level invokable slash command by filename, so nesting stage files there would silently create unwanted `/rank`, `/analysis`, `/draft`, `/writing-styles`, `/macro-reference` commands. There is no native "include another command" mechanism; the handoff is just prose instructing the agent to `Read` the file and follow it, so keep that instruction and the target path unambiguous when editing any side.

If you touch the stage split, keep the field names in sync: `analysis.md` emits four named fields (건드리는 렌즈 / 선행 vs 동행 / 확인된 수치 / 자산군별 함의) and `draft.md` §2 must have a bullet consuming each one — a field produced by analysis with no corresponding bullet in draft is silently dropped at runtime (this happened once; caught by review, not by any automated check, since none exists for prompt files). `.claude/audit/README.md` pins the score-adjustment contract `rank.md` reads from the not-yet-built weekly audit agent's `topic-report.md` — do not redesign that format without updating both files together.

## Content model

- `content/posts/` — one Markdown file per news explainer. Front matter: `title`, `date`, `tags`, `draft`, `source_url` (always the original article URL, verbatim), and optional `related_articles` (list of `{title, url, source}` — external articles on the same topic, gathered by `/daily-post`'s 연관 기사 수집 step (sequencer §3) via WebSearch, ordered oldest-first; the collection step excludes same-day articles and prefers older background pieces, so the block reads as run-up context rather than a second copy of the day's wire; omitted entirely when nothing survives selection, never an empty list). Post footer blocks render in this order via `layouts/partials/extend_post_content.html`: internal related posts → external `related_articles` → source link → disclaimer. Internal first is deliberate — dwell time is the only meaningful pre-AdSense signal. External links carry `rel="nofollow"` since they appear on every post.
- `content/dictionary/` — one Markdown file per economic term, `tags: ["용어사전"]`.
- `content/dictionary/_terms.yaml` — canonical term index, **not a Hugo page** (Hugo does not render `content/`-tree files whose name starts with `_`; verified via `hugo --gc --minify`, shows up under "Non-page files" not "Pages"). Maps each dictionary slug to `{title, aliases}`. This is the single source of truth for wikilink matching — both `/daily-post`'s draft stage (when creating a new term or linking to an existing one) and its rank stage (when scoring an article's dictionary relevance via `title` + `aliases` matching) read this file instead of scanning `content/dictionary/` directly, so that synonym mismatches (e.g. "정책금리" vs "기준금리") don't cause missed links or duplicate dictionary entries. When adding a dictionary entry, append to this file too — `aliases` should be real synonym forms likely to appear in other articles, not grammatical inflections.
- Wikilinking uses plain Hugo/Goldmark relative links (`[기준금리](/dictionary/base-rate/)`), never `[[...]]` — Hugo has no wikilink shortcode here and none should be added; this was a deliberate decision, not an oversight.
- `archetypes/posts.md` and `archetypes/dictionary.md` define the front-matter skeletons `hugo new` would use, mirroring the front matter the slash commands write directly.

## Local-only reference material (gitignored — will not exist in a fresh clone or CI)

`SEED.md`, `tudul.md`, and the McGee `Applied Financial Macroeconomics...pdf` at the repo root are gitignored and never published. As of the `/daily-post` unification, neither is a runtime dependency of any stage file anymore: `tudul.md`'s load-bearing pieces (lead/coincident indicator tags, the 🟢/🟡/🔴 threshold table, freshness rules) were inlined into `.claude/daily-post/analysis.md`, and the PDF was replaced by a self-written summary, `.claude/daily-post/macro-reference.md` (8 chapters, ~10 lines of original-wording causal logic each — original PDF sentences are never reproduced, a copyright constraint, not a style preference). Both local files remain on disk for reference only; deleting them no longer breaks anything.

If you need to re-derive or extend `macro-reference.md` from the PDF: the PDF's file-page number equals its printed page number **+ 19** (verified: file page 20 = printed page 1 = start of Ch. 1). The chapter-to-page-range table lives in `macro-reference.md`, not in `analysis.md` anymore.

## Design docs

`docs/superpowers/specs/` and `docs/superpowers/plans/` (gitignored) hold brainstorming specs and implementation plans for past work on this repo, written via the `superpowers` skill set. Check there before re-deriving architectural decisions already made and recorded.

## Repo conventions

- git commit author: `bjh7790` / `bjh7790@gmail.com`.
- Push authenticates via a repo-dedicated SSH key (`~/.ssh/id_ed25519_econblog`), already registered on GitHub — pushes should not need credential prompts.
- Never commit or push a post/dictionary draft without explicit user approval (see the `/daily-post` §6 publish gate above) — this applies even to trivial-looking fixes to already-drafted content.

## Roadmap (not yet built)

Deferred out of the original MVP scope; not implemented anywhere in this repo yet:

- **Agent3 (주간 감사)**: a periodic audit pass — link checking, SEO check, design check, performance/analytics report. No slash command exists for this yet. **Its output format is already specced, so do not redesign it**: the audit agent is expected to write `.claude/audit/topic-report.md` (sections 잘 되는 주제 / 안 되는 주제 / 좋은 포스트의 조건, plus a `생성일` line), which the planned `/daily-post` reads as an optional scoring input. The format contract will live at `.claude/audit/README.md`. Neither file exists yet — see `docs/superpowers/specs/2026-07-19-daily-cloud-routine-design.md`.
- **GA4 integration**: no analytics are wired up. `/daily-post`'s rank stage currently has no view-count signal and explicitly says so in its output; wiring up a GA4 service account + API would let it use real past-post performance.
- **네이버 SEO 최적화**: not addressed.
- **Google AdSense**: not applied for.
- **Kakao AdFit**: not applied for.
- **Scheduled/automatic runs**: BUILT (this unification, `docs/superpowers/plans/2026-07-20-unified-daily-post.md`). `/news-pick` and `/write-post` were replaced, not kept alongside — `/daily-post` (no arg) is the unattended cloud-routine path and `/daily-post manual` is the interactive path; there is only one command now. Key invariants: it pushes only to `auto/post-YYYY-MM-DD` branches (never `main`), always writes `draft: true` in unattended mode, calls no interactive tools in unattended mode, and aborts without producing anything when the top candidate scores below the 8/15 threshold. The publish gate is not removed, only moved to PR review in unattended mode. **Not yet done:** registering `/daily-post` as an actual cron/cloud-routine schedule — the command exists and is verified locally, but nothing calls it automatically yet.
- **Cross-verification via `/delegate agy deep-research`**: idea for `/daily-post`'s 원문 읽기 step (sequencer §2) — send the topic through the `/delegate` skill's `agy` (Antigravity CLI, Gemini 3.1 Pro High) provider's deep-research capability and use that report for fact cross-checking. Motivation: the rank stage sources primarily from Hankyung RSS (with a 4-feed fallback chain for volume, not for fact cross-checking), a single-source dependency with no cross-verification channel today. Note: agy was separately evaluated and **rejected** as a way to gather external related-article links — deep-research is a report generator, and `WebSearch` returns URLs more cheaply and directly. It remains open only for fact-checking, which is a different job.

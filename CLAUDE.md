# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## What this is

A Hugo static-site blog (theme: PaperMod, git submodule at `themes/PaperMod`) explaining Korean economic news to non-expert readers, deployed to GitHub Pages. There is no application code — the product is (a) the Hugo content/config and (b) the `/daily-post` slash command that generates that content.

## Commands

```bash
hugo server              # local dev server, live reload
hugo --gc --minify       # production build (what CI runs) → ./public
```

CI (`.github/workflows/hugo.yml`) builds with Hugo `0.164.0` on push to `main` and deploys via `actions/deploy-pages` — there is no `gh-pages` branch. Keep local Hugo on that version.

## Verification

No test suite, no linter — this is prompt files + Markdown + Hugo config. "Correctness" for the slash commands means the prompt text is internally consistent and matches Hugo's content-file conventions, not passing tests. After editing `.claude/commands/*.md` or `.claude/daily-post/*.md`:

1. Run `hugo --gc --minify`, check the `Pages` / `Non-page files` counts hold steady (currently 49 / 1).
2. Grep that cross-file references (section numbers, file paths, field names) actually resolve.

## GitHub CLI

`gh` is preferred for GitHub tasks. Check `gh auth status` first. Use `gh pr view`, `gh pr checks`, `gh run view` for read-only inspection. Never merge, close, delete, or push through `gh` without explicit user approval. Keep post and dictionary drafts at `draft: true` until that approval is given.

## The actual workflow: /daily-post

No-arg = unattended (cloud-routine); `/daily-post manual` = interactive. `.claude/commands/daily-post.md` is a thin 7-step sequencer (§0–§6), not where writing logic lives — it `Read`s stage files under `.claude/daily-post/`:

| Step | Lives in | Does |
|---|---|---|
| §1 랭킹 | `rank.md` | Hankyung 3 feeds → 연합/경향/동아/한겨레 fallback if <10 fresh; scores 0–15 across 5 criteria; 8-point floor. Unattended auto-picks #1 and aborts silently below floor; manual shows 3. |
| §2 원문 | sequencer (inline) | WebFetch the source. Aborts rather than fabricating; unattended discards the candidate instead of falling through to #2. |
| §3 연관 기사 | sequencer (inline) | WebSearch external related articles. Omits the field entirely on failure/empty — never invents URLs. |
| §4 분석 | `analysis.md` | Builds an in-context analysis note: 3-lens classification + lead/coincident tagging, one chapter lookup into `macro-reference.md`, 🟢/🟡/🔴 thresholds for 1–2 searched indicators. Never saved to disk. |
| §5 작성 | `draft.md` | Post + dictionary entries + wikilinks. Delegates prose/tone rules to `writing-styles.md`: no bold, 두괄식, numeric redlines extended to causal claims, personalized-advice ban extended to repeated directional sector calls, and a 7-item AI-artifact self-review checklist. |
| §6 게시 | sequencer (inline) | Publish gate — see below. |

**Publish gate.** Unattended always writes `draft: true` and pushes only to an `auto/post-YYYY-MM-DD` branch + PR, never `main`. Manual requires an unambiguous yes to a specific approval question before flipping `draft: false` and pushing `main`.

**Unattended invariants** (each enforced in its own stage file; this is the scannable checklist): pushes only to `auto/post-YYYY-MM-DD`, never `main`; always writes `draft: true`; calls no interactive tools; aborts producing nothing when the top candidate scores below 8/15.

### Two contracts that break silently — keep both sides in sync

- **The 4 analysis fields.** `analysis.md` emits 건드리는 렌즈 / 선행 vs 동행 / 확인된 수치 / 자산군별 함의, and `draft.md` §2 must have one bullet consuming each. A field with no matching bullet is dropped at runtime with no error. This has happened once; it was caught by human review, since no automated check exists for prompt files.
- **The audit score contract.** `.claude/audit/README.md` pins the format `rank.md` reads from the not-yet-built weekly audit agent's `topic-report.md`. Do not redesign either without updating both.

### Why stage files live outside `.claude/commands/`

Claude Code auto-registers every `.md` anywhere under `.claude/commands/` — including subdirectories — as its own invokable slash command, named by filename. Nesting the stages there would silently create `/rank`, `/analysis`, `/draft`, `/writing-styles`, `/macro-reference`. There is no native include mechanism; the handoff is prose telling the agent to `Read` a path, so keep that instruction and the path unambiguous on both sides.

## Content model

- `content/posts/` — one file per explainer. Front matter: `title`, `date`, `tags`, `draft`, `source_url` (original article URL, verbatim), optional `related_articles` (list of `{title, url, source}`).
  - `related_articles` are external articles gathered in §3, ordered oldest-first, excluding same-day pieces and preferring older background — so the block reads as run-up context, not a second copy of the day's wire. Omitted entirely when nothing survives; never an empty list.
  - Footer order via `layouts/partials/extend_post_content.html`: internal related posts → external `related_articles` → source link → disclaimer. Internal first is deliberate — dwell time is the only meaningful pre-AdSense signal. External links carry `rel="nofollow"` since they appear on every post.
- `content/dictionary/` — one file per term, `tags: ["용어사전"]`.
- `content/dictionary/_terms.yaml` — canonical term index, **not a Hugo page** (Hugo skips `content/` files starting with `_`; it shows under "Non-page files"). Maps slug → `{title, aliases}`, and is the single source of truth for wikilink matching. Both `draft.md` and `rank.md` read it instead of scanning `content/dictionary/`, so synonym mismatches ("정책금리" vs "기준금리") don't cause missed links or duplicate entries. When adding an entry, append here too — `aliases` are real synonyms other articles would use, not grammatical inflections.
- Wikilinks are plain Hugo/Goldmark relative links (`[기준금리](/dictionary/base-rate/)`), never `[[...]]`. Hugo has no wikilink shortcode here and none should be added — a deliberate decision, not an oversight.
- `archetypes/posts.md` / `archetypes/dictionary.md` mirror the front matter the slash commands write directly.

## `.claude/loop/` — writing-style feedback loop (in progress)

A measurement rig that compares published posts against a reference corpus of Korean economics blog posts to find AI-writing artifacts. Design spec: `docs/superpowers/specs/2026-07-20-loop-writing-style-design.md`.

- `extract_features.py` is the **only** thing that computes feature values — deterministic, stdlib + regex, no LLM. `test_extract_features.py` is its golden test.
- `reference-corpus/` is third-party copyrighted material: local-only, gitignored, never published or redistributed.
- `genre-diagnostic.md` records the current finding: of the features outside the corpus IQR, only `sentence_len_cv` qualifies as a patchable AI artifact. It proposes an **unrun** falsification test — remove the "40~60자" range from `writing-styles.md` and re-measure. Both occurrences of that string are therefore load-bearing; do not delete them incidentally.
- `writing-styles.md` is the loop's patch target (accepted patches get appended). Keep it a separate file — merging it into `draft.md` would break that.

## Repo conventions

- Commit author: `bjh7790` / `bjh7790@gmail.com`.
- Push authenticates via a repo-dedicated SSH key (`~/.ssh/id_ed25519_econblog`), already registered on GitHub — no credential prompts expected.
- Never commit or push a post/dictionary draft without explicit user approval. This applies even to trivial-looking fixes to already-drafted content.

## Roadmap

- **Agent3 (주간 감사)** — not built. A periodic audit pass: link checking, SEO, design, performance. **Its output format is already specced; do not redesign it.** The agent writes `.claude/audit/topic-report.md` (sections 잘 되는 주제 / 안 되는 주제 / 좋은 포스트의 조건 + a `생성일` line), which `rank.md` reads as an optional scoring input. Contract pinned at `.claude/audit/README.md`. `topic-report.md` not existing is normal — `rank.md` skips it silently.
- **GA4 & GSC** — Fully wired and API integrated:
  - GA4 measurement tag (`G-E2V0CFN172`) and GSC site verification tag (`Pq-uzUwYArRYxLu2YzvnVhdM43JSCa7wQuHup-UJdGk`) configured in `hugo.toml` & `layouts/partials/google_analytics.html`, and deployed live to GitHub Pages.
  - Google Analytics Data API (v1beta) integration completed with Service Account credentials (`ga4-credentials.json`, gitignored) and GA4 Property ID (`546174128`).
  - Python reporter script `scripts/fetch_ga4.py` created and verified working with `.venv` (`google-analytics-data` package), allowing AI Agent to query real-time active users, page views, top posts, and traffic sources on demand.

- **Scheduled runs** — the unattended path is built and locally verified, but nothing calls it automatically. Remaining: (1) register `/daily-post` as a cron/cloud routine; (2) verify git push auth from a cloud sandbox (local pushes use the dedicated SSH key a runner won't have); (3) verify Hankyung RSS reachability from datacenter IPs (the fallback chain mitigates but doesn't eliminate this); (4) calibrate the 8/15 threshold against the score distribution of the first ~2 weeks of real runs — 8 is an initial value, not empirically derived.
- **Fact cross-verification** — open idea for §2: route the topic through `/delegate`'s `agy` provider (Antigravity CLI, Gemini 3.1 Pro High) deep-research and cross-check facts. Motivation: the rank stage is single-sourced on Hankyung RSS; the fallback chain adds volume, not verification. Note that `agy` was separately evaluated and **rejected** for gathering related-article links — deep research is a report generator, and `WebSearch` returns URLs more cheaply.
- **네이버 SEO 최적화**, **Google AdSense**, **Kakao AdFit** — not addressed / not applied for.

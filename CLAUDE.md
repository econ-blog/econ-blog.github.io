# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Hugo static-site blog (theme: PaperMod, git submodule under `themes/PaperMod`) that explains Korean economic news to non-expert readers, deployed to GitHub Pages. There is no application code — the actual product is (a) the Hugo content/config and (b) two Claude Code custom slash commands that generate that content.

## Commands

```bash
hugo server              # local dev server with live reload
hugo --gc --minify       # production build (what CI runs), outputs to ./public
```

No test suite, no linter — this is prompt files + Markdown content + Hugo config. "Correctness" for the slash commands means the prompt text is internally consistent and matches Hugo's actual content-file conventions (see below), not passing tests. Verify changes to `.claude/commands/*.md` or `.claude/write-post/*.md` by running `hugo --gc --minify` and checking the `Pages` / `Non-page files` counts in the build summary, and by grepping for cross-file references (section numbers, file paths) actually resolving.

CI (`.github/workflows/hugo.yml`) builds with Hugo `0.164.0` on push to `main` and deploys via `actions/deploy-pages` — no `gh-pages` branch. Locally installed Hugo should match that version.

## The actual workflow: two slash commands

This blog is written by invoking, in order:

1. **`/news-pick`** (`.claude/commands/news-pick.md`) — pulls Hankyung RSS (economy/finance/realestate feeds), ranks candidates against past posts and dictionary terms, recommends 3 with one highlighted. Selection only — never writes a post.
2. **`/write-post`** (`.claude/commands/write-post.md`) — takes one chosen news item and drafts a post. This command is a thin 4-step sequencer, not where the actual writing logic lives:
   - §1 fetches the source article (WebFetch) — aborts rather than fabricating facts if the fetch fails.
   - §2 tells the agent to `Read` and follow `.claude/write-post/analysis.md` — builds an "analysis note" (3-lens macro classification, optional targeted lookups into the local reference PDF and `tudul.md`, 1–2 real web-searched indicators) that is *not* saved to disk, only carried forward in-context to the next step.
   - §3 tells the agent to `Read` and follow `.claude/write-post/draft.md` — does the actual post writing, dictionary-entry creation, and wikilinking, consuming the analysis note from §2.
   - §4 is the publish gate: drafts are written with `draft: true` and **never committed or pushed without explicit user approval**. Only after approval does the command flip `draft: false` and run `git add`/`commit`/`push`.

**Why analysis and drafting are split into separate files instead of inline in `write-post.md`:** keeps the entry point thin and lets the two stages be edited independently. They deliberately live at `.claude/write-post/`, *not* under `.claude/commands/` — Claude Code auto-registers any `.md` file found anywhere under `.claude/commands/` (including subdirectories) as its own top-level invokable slash command by filename, so nesting them there would silently create unwanted `/analysis` and `/draft` commands. There is no native "include another command" mechanism; the handoff is just prose instructing the agent to `Read` the file and follow it, so keep that instruction and the target path unambiguous when editing either side.

If you touch the analysis/draft split, keep the field names in sync: `analysis.md` emits four named fields (건드리는 렌즈 / 선행 vs 동행 / 확인된 수치 / 자산군별 함의) and `draft.md` §2 must have a bullet consuming each one — a field produced by analysis with no corresponding bullet in draft is silently dropped at runtime (this happened once; caught by review, not by any automated check, since none exists for prompt files).

## Content model

- `content/posts/` — one Markdown file per news explainer. Front matter: `title`, `date`, `tags`, `draft`, `source_url` (always the original article URL, verbatim).
- `content/dictionary/` — one Markdown file per economic term, `tags: ["용어사전"]`.
- `content/dictionary/_terms.yaml` — canonical term index, **not a Hugo page** (Hugo does not render `content/`-tree files whose name starts with `_`; verified via `hugo --gc --minify`, shows up under "Non-page files" not "Pages"). Maps each dictionary slug to `{title, aliases}`. This is the single source of truth for wikilink matching — both `/write-post` (when creating a new term or linking to an existing one) and `/news-pick` (when scoring an article's relevance to recently-covered terms) read this file instead of scanning `content/dictionary/` directly, so that synonym mismatches (e.g. "정책금리" vs "기준금리") don't cause missed links or duplicate dictionary entries. When adding a dictionary entry, append to this file too — `aliases` should be real synonym forms likely to appear in other articles, not grammatical inflections.
- Wikilinking uses plain Hugo/Goldmark relative links (`[기준금리](/dictionary/base-rate/)`), never `[[...]]` — Hugo has no wikilink shortcode here and none should be added; this was a deliberate decision, not an oversight.
- `archetypes/posts.md` and `archetypes/dictionary.md` define the front-matter skeletons `hugo new` would use, mirroring the front matter the slash commands write directly.

## Local-only reference material (gitignored — will not exist in a fresh clone or CI)

`SEED.md`, `tudul.md`, and the McGee `Applied Financial Macroeconomics...pdf` at the repo root are gitignored and never published. `tudul.md` (a macro "traffic-light" analysis framework) and the PDF are **active runtime dependencies** of `.claude/write-post/analysis.md` — deleting `tudul.md` will break that stage with no fallback (only the PDF has an explicit "skip this step if missing" fallback; `tudul.md` does not). Both are referenced only for their *framework*, never quoted directly ("이 책에 의하면" phrasing is explicitly forbidden in `analysis.md`).

If you need to map news topics to PDF chapters: the PDF's file-page number equals its printed page number **+ 19** (verified: file page 20 = printed page 1 = start of Ch. 1). The chapter-to-page-range lookup table already lives in `analysis.md` §2 — extend it there rather than re-deriving offsets elsewhere.

## Design docs

`docs/superpowers/specs/` and `docs/superpowers/plans/` (gitignored) hold brainstorming specs and implementation plans for past work on this repo, written via the `superpowers` skill set. Check there before re-deriving architectural decisions already made and recorded.

## Repo conventions

- git commit author: `bjh7790` / `bjh7790@gmail.com`.
- Push authenticates via a repo-dedicated SSH key (`~/.ssh/id_ed25519_econblog`), already registered on GitHub — pushes should not need credential prompts.
- Never commit or push a post/dictionary draft without explicit user approval (see `/write-post` §4 above) — this applies even to trivial-looking fixes to already-drafted content.

## Roadmap (not yet built)

Deferred out of the original MVP scope; not implemented anywhere in this repo yet:

- **Agent3 (주간 감사)**: a periodic audit pass — link checking, SEO check, design check, performance/analytics report. No slash command exists for this yet.
- **GA4 integration**: no analytics are wired up. `/news-pick`'s ranking currently has no view-count signal and explicitly says so in its output; wiring up a GA4 service account + API would let it use real past-post performance.
- **네이버 SEO 최적화**: not addressed.
- **Google AdSense**: not applied for.
- **Scheduled/automatic runs**: `/news-pick` and `/write-post` are manual-only by design (invoked by the user, not cron/Actions-triggered). Automating either was explicitly deferred, not merely unbuilt.
- **Cross-verification via `/delegate agy deep-research`**: idea for `/write-post` §1 — instead of relying solely on one WebFetch of the Hankyung article, send the topic through the `/delegate` skill's `agy` (Antigravity CLI, Gemini 3.1 Pro High) provider's deep-research capability and use that report for additional fact cross-checking. Motivation: `/news-pick` sources from Hankyung RSS only, a single-source dependency with no cross-verification channel today.

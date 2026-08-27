# pp-citation-audit

**Multi-model AI citation audit for Kapowsin Business Solutions.**

Thin Go client that talks to the Kapowsin Citation Audit Server (FastAPI on port 8421). Runs 4-model quick checks (free) or full 13-model audits (token gated).

Checks what Grok, Claude, Gemini, DeepSeek, Kimi, Mistral, Nemotron, and live web search actually say when someone asks "Who is the best real estate agent in Tacoma?"

## Why this matters

A business can have perfect Google reviews, GBP, Zillow, Instagram — and still be invisible to AI buyers.

**The One Model Problem:** Most people ask one AI assistant. If that model never recommends you, the lead is lost forever.

## Install

```bash
go install github.com/kapowsin/printing-press-library/library/other/citation-audit/cmd/citation-audit-pp-cli@latest
```

Or during local dev (from this dir):

```bash
go build -o pp-citation-audit .
./pp-citation-audit health
```

## Prerequisites

Server must be running:

```bash
cd /home/openclaw/.openclaw/workspace
uvicorn scripts.citation_audit_server:app --host 0.0.0.0 --port 8421 --log-level warning
```

Or via the skill wrapper once installed.

## Commands

### health

```bash
pp-citation-audit health
# → ✅ Server healthy — 13 models available (v1.0.0)
```

### check (quick, 4 models, ~30s, free)

```bash
pp-citation-audit check "Theory Real Estate" \
  --city Tacoma \
  --state WA \
  --industry "real estate" \
  --owner "Allen Miller"
```

Output:

```
  AI Visibility Score: F  (1/4 models cited you)
  Score: 12/100

  One-line verdict:
  When buyers ask AI for a real estate in Tacoma, Theory Real Estate appears in 1 of 4 AI systems.

  Top gap: Owner name generates zero citations across models.
  🔴 Competitor: Keller Williams cited in 3/4 models

  📅 Book Your Full Assessment →
  https://cal.com/thekapowsincompany/discovery
```

Flags:
- `--city` (required)
- `--state` (default WA)
- `--industry` (required)
- `--owner`
- `--email`
- `--json` (raw JSON)
- `--server` (override)

### audit (full, 13 models, ~2min, requires token)

```bash
pp-citation-audit audit "Theory Real Estate" \
  --city Tacoma \
  --state WA \
  --industry "real estate" \
  --owners "Allen Miller,Austin Miller" \
  --aliases "Theory Realty Group,Theory Companies" \
  --website "theoryre.com" \
  --email "allen@theoryre.com"
```

Returns full citation matrix, name consistency grade, competitor analysis, quick wins.

Use `--json` for the complete machine-readable matrix (recommended for assessments).

## Environment

```bash
export CITATION_AUDIT_URL=http://localhost:8421
export CITATION_AUDIT_TOKEN=kapowsin-assessment-2026
```

## Scoring

- ✅ Cited + recommended (2+ of 3 runs)
- ⚠️ Mentioned but not recommended
- ❌ Not mentioned or competitor wins

Grades: A (80-100) dominant → F (0-19) invisible to AI.

## Integration

Used inside Kapowsin AI Readiness Assessments (Section 13 — AI Marketing Searchability).

See `printing-press-contrib/citation-audit/SKILL.md` for full trigger phrases and context.

## Development

```bash
go build -o pp-citation-audit .
go run main.go check "Test Co" --city Seattle --industry mortgage --json
```

## License

Apache-2.0 (Kapowsin internal tooling)

---
name: pp-citation-audit
description: "Multi-model AI citation audit. Checks what 13 AI models say about a business when asked for recommendations — Grok, Claude, Gemini, DeepSeek, Kimi, Mistral, Nemotron, and more. Returns a citation matrix, AI Visibility Score, name consistency audit, and competitor gap analysis. Trigger phrases: `citation audit for <company>`, `AI visibility check <company>`, `check AI search for <company>`, `how does <company> appear in AI`, `run pp-citation-audit`."
author: "Kapowsin AI - Callie"
license: "Apache-2.0"
argument-hint: "<command> [args]"
allowed-tools: "Read Bash"
metadata:
  openclaw:
    requires:
      bins:
        - pp-citation-audit
    install:
      - kind: shell
        bins: [pp-citation-audit]
        command: "go install github.com/tsagastizadoailabs-creator/printing-press-library/library/other/citation-audit/cmd/citation-audit-pp-cli@latest"
        label: "Install via go install"
---

# Citation Audit — Printing Press CLI

## Prerequisites

This skill drives the `pp-citation-audit` binary backed by the Kapowsin Citation Audit Server.

Verify server is running first:
```bash
pp-citation-audit health
# or: curl http://localhost:8421/api/citation-audit/health
```

If server is not running:
```bash
cd /home/openclaw/.openclaw/workspace
uvicorn scripts.citation_audit_server:app --host 0.0.0.0 --port 8421 --log-level warning &
```

Install the CLI:
```bash
go install github.com/tsagastizadoailabs-creator/printing-press-library/library/other/citation-audit/cmd/citation-audit-pp-cli@latest
# Or run directly during development:
python3 /home/openclaw/.openclaw/workspace/scripts/citation_audit_client.py <command> [args]
```

## What Makes This CLI Unique

Traditional searchability audits check *platform presence* — Zillow profiles, Google Business Profiles, Instagram followers. Those measure what you've built (inputs).

This CLI checks the *output*: what AI models actually say when a buyer or seller asks who to call.

**The core insight surfaced Aug 27 2026 (Theory Real Estate case):**
A business can have 4.9 stars, 109 Google reviews, GBP + Instagram + YouTube + Zillow — and score Grade F on AI citations. Because:

1. **Different training data:** DeepSeek was trained on different web data than Claude. Kimi knows different Pacific Northwest businesses than GPT-4.
2. **Name fragmentation:** "Theory Real Estate" vs "Theory Realty Group" = split citation credit. AI models treat these as separate entities.
3. **Crawler blocking:** Sites that block Googlebot and AI crawlers can't be indexed — invisible to Perplexity and Claude web search.
4. **The one-model problem:** Most buyers use one AI assistant. If you don't appear in ChatGPT, those users never find you — even if you're #1 on Google.

**Two scores, always displayed together:**
```
Platform Presence Score:  35/68  — Grade C  (what you've built)
AI Citation Score:         1/13  — Grade F  (what AI actually says)
```

The gap between those two letters is where leads leak.

## Model Roster — 13 Models

### Commercial Models (3)
| Model | Data Source | What It Sees |
|-------|-------------|--------------|
| Grok (grok-fast) | X + real-time web | Social signals, recent web content, X posts |
| Claude (claude-sonnet) | Training corpus (no live web) | What Anthropic's training data includes |
| Gemini (gemini-flash) | Google Search grounding | GBP data, Google-indexed content |

### NVIDIA NIM Models (9) — Free tier, 40 req/min each
| Alias | Model | Corpus Differentiator |
|-------|-------|-----------------------|
| nvidia-deepseek-flash | deepseek-ai/deepseek-v4-flash | Chinese training corpus — different web data |
| nvidia-deepseek-pro | deepseek-ai/deepseek-v4-pro | Heavy reasoning; best for business analysis |
| nvidia-kimi | moonshotai/kimi-k2.6 | Moonshot AI corpus — distinct from OpenAI/Anthropic |
| nvidia-minimax | minimaxai/minimax-m3 | General; lightweight fallback |
| nvidia-mistral-small | mistralai/mistral-small-4-119b | EU-trained; strong on European + global business data |
| nvidia-mistral | mistralai/mistral-medium-3.5-128b | EU flagship; best Mistral analysis capability |
| nvidia-nemotron | nvidia/nemotron-3-ultra-550b | NVIDIA's own 550B parameter model; unique training |
| nvidia-nemotron-nano | nvidia/nemotron-3-nano-omni-30b | Fast NVIDIA reasoning model |
| nvidia-step-flash | stepfun-ai/step-3.7-flash | StepFun AI corpus — additional diversity |

### Live Web Search (1)
| Alias | Source | Notes |
|-------|--------|-------|
| web_search | DDG/live web | Real-time web search grounding; crawler-blocked sites score low |

## Commands

### `health` — Check server status
```bash
pp-citation-audit health
# → ✅ Server healthy — 13 models available (v1.0.0)
```

### `check` — Quick citation check (4 models, ~30 seconds, free)

Runs Grok + Claude + DeepSeek Flash + Web Search. Returns score, grade, top gap, competitor citations.

```bash
pp-citation-audit check "Theory Real Estate" \
  --city "Tacoma" \
  --state "WA" \
  --industry "real estate" \
  --owner "Allen Miller"

# → Grade F | Appeared in 1/4 models
# → Top gap: Owner name generates zero citations
# → Competitor: Keller Williams cited in 3/4 models
```

**Options:**
```
<company>           Primary brand name (required)
--city              City (required)
--state             State abbreviation (default: WA)
--industry          Industry type (required) — e.g., "real estate", "mortgage", "property management"
--owner             Owner/agent name (optional but recommended)
--email             Email for follow-up and caching (optional)
--json              Output raw JSON instead of formatted display
```

### `audit` — Full 13-model citation audit (~2 minutes)

Runs all 13 models × 3 query templates × 3 consensus runs = 117 API calls. Returns full citation matrix, name consistency audit, competitor gap analysis, and quick wins.

Requires server-side audit token (pre-configured).

```bash
pp-citation-audit audit "Theory Real Estate" \
  --city "Tacoma" \
  --state "WA" \
  --industry "real estate" \
  --owners "Allen Miller,Austin Miller,Isaac Miller" \
  --aliases "Theory Realty Group,Theory Companies,theory_re" \
  --website "theoryre.com"

# → Citation matrix across 13 models
# → Name Consistency Grade: D (3 variants found)
# → Competitor: Keller Williams cited in 9/13 models
# → Quick wins: [1] Standardize name [2] Add owner bios [3] Fix crawler blocking
```

**Options:**
```
<company>           Primary brand name (required)
--city              City (required)
--state             State (default: WA)
--industry          Industry (required)
--owners            Owner names, comma-separated
--aliases           Known alternate/wrong names, comma-separated
--website           Website domain (e.g., theoryre.com)
--email             Email for logging
--json              Raw JSON output
```

## Scoring

### Citation Scoring Per Query
| Result | Score | Symbol |
|--------|-------|--------|
| Cited + recommended (2+ of 3 runs) | 2 | ✅ |
| Mentioned but not recommended (1 of 3 runs) | 1 | ⚠️ |
| Not mentioned | 0 | ❌ |
| Cited under wrong name variant | 1 + flag | ⚠️🔴 |
| Competitor cited instead | 0 + flag | ❌🔴 |

### AI Visibility Score (0–100)
```
Score = (sum of all citation scores) / (models × queries × 2) × 100
```

### Grade Bands
| Score | Grade | Meaning |
|-------|-------|---------|
| 80–100 | A | Dominant — consistently cited across models |
| 60–79 | B | Solid — cited in most models for direct lookups |
| 40–59 | C | Mixed — visible in some models |
| 20–39 | D | Weak — only cited when searched directly |
| 0–19 | F | Invisible — AI agents never surface this business |

## Use in Kapowsin Assessments

The citation audit slots into Section 13 (AI Marketing Searchability Assessment) as a subsection after the platform-by-platform scores:

```
## Section 13 — AI Marketing Searchability Assessment
  [platform scores, review count, content activity — existing]

  ### AI Citation Reality Check
  [citation matrix table — from pp-citation-audit]

  ### Name Consistency Audit
  [variant table — from pp-citation-audit]

  [Quick Win Rules, Recommended Action Plan — existing]
```

**Two scores always displayed separately — never merged:**
```
Composite Searchability:  36/68 — Grade C  (platform inputs)
AI Citation Score:         2/13 — Grade F  (AI output)
```

## Pricing

| Tier | Price | What You Get |
|------|-------|--------------|
| Quick check (4 models) | FREE | Lead gen — self-serve on Kapowsin website |
| Full audit (13 models) | Included in $250–$1,500 assessment | Complete citation matrix |
| Quarterly re-audit | $250/quarter | Are the fixes working? |
| Competitive monitoring | +$50/mo | Track 3 competitors monthly |

## Server Configuration

Server runs on KapowsinBS-Ops at port 8421.

Environment variables required:
```
XAI_API_KEY              — Grok models
ANTHROPIC_API_KEY        — Claude models
GOOGLE_AI_API_KEY        — Gemini
NVIDIA_NIM_API_KEY       — All 9 NVIDIA NIM models
CITATION_AUDIT_TOKEN     — Full audit endpoint auth (default: kapowsin-assessment-2026)
```

## Related CLIs

- `pp-zillow` — Zillow Zestimate + deal intelligence
- `pp-redfin` — Redfin comps and market data (Stingray-backed)
- `pp-rate-compare` — Mortgage rate scenario comparison
- `pp-mortgage-intel` — Live FRED mortgage rate intelligence

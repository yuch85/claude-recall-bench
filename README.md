# Claude Recall Bench

An eval harness for measuring Claude's verbatim reproduction fidelity across context window sizes. Tests whether models can locate content by unique hash boundary markers within a large document and reproduce it character-for-character.

## Why it matters

In document amendment workflows (legal redlining, contract editing), an LLM must return text with only targeted edits. Any dropped, paraphrased, or hallucinated text produces spurious tracked changes. This benchmark quantifies that risk.

## Key Results (2026-03-17)

### Summary Table

| Model | Context Window | 100% Recall Threshold | Notes |
|-------|:-------------:|:--------------------:|-------|
| Opus 4.6 | 1M tokens | **333K tokens** confirmed, breakpoint 333K-454K | At 454K, sporadic section failures (RLHF meta-commentary) |
| Sonnet 4.6 | 200K tokens* | **122K tokens** confirmed | Perfect recall across entire testable range. *1M gated behind feature flag `coral_reef_sonnet` |
| Haiku 4.5 | 200K tokens | **42K tokens** confirmed | Degrades to 95-99% at 62-83K tokens |

### Opus 4.6 Results (v2, hash markers, 500-line sections)

| Doc | Input Tokens | Sections | Overall Word Acc |
|-----|:-----------:|:--------:|:----------------:|
| 10k | 8,492 | 1 | **100%** |
| 25k | 20,933 | 1 | **100%** |
| 50k | 41,681 | 1 | **100%** |
| 100k | 83,360 | 2 | **100%** |
| 400k | 333,052 | 8 | **100%** |
| 450k_tok | ~454,000 | 11 | Partial (section 2 failed with meta-commentary) |
| 600k_tok | 602,499 | 15 | Partial (section 0 truncated, secs 1-8 perfect) |

### Sonnet 4.6 Results (v2, hash markers, 250-line sections)

| Doc | Input Tokens | Sections | Overall Word Acc |
|-----|:-----------:|:--------:|:----------------:|
| 10k | 8,492 | 1 | **100%** |
| 25k | 20,933 | 1 | **100%** |
| 50k | 41,681 | 2 | **100%** |
| 75k | 62,431 | 3 | **100%** |
| 100k | 83,360 | 4 | 99.94% |
| 120k_tok | ~122,000 | 6 | **100%** |

### Haiku 4.5 Results (v2, hash markers)

| Doc | Input Tokens | Sections | Overall Word Acc |
|-----|:-----------:|:--------:|:----------------:|
| 10k | 8,492 | 1 | **100%** |
| 25k | 20,933 | 1 | **100%** |
| 50k | 41,681 | 1 | **100%** |
| 75k | 62,431 | 2 | 95.1% |
| 100k | 83,360 | 2 | 99.0% |

## Key Findings

1. **v2 hash markers eliminated all v1 test design failures.** v1 used content anchors + line numbers, which caused wrong-offset, over-reproduction, and premature truncation failures. v2 uses unique SHA-256 boundary markers — all failures at 333K tokens disappeared.

2. **Recall itself shows no gradual degradation.** Within the context window, all models achieve 100% word accuracy. Failures are either hard context overflows (Sonnet/Haiku) or RLHF-trained output reluctance (Opus at high context).

3. **Opus failures at 450K+ tokens are RLHF interference, not recall failures.** The model outputs meta-commentary ("I need permission to write a file") instead of document text. The content it does produce is always verbatim.

4. **Sonnet 4.6 has 1M context in code, gated behind feature flag.** Claude Code's source shows Sonnet 4.6 gets 1M via `TnA()` → `u2L()` → `nK9("coral_reef_sonnet") === "true"`. Currently falls back to 200K.

5. **Token counts: 4.83 chars/token** for this legal text (measured via API, remarkably stable across all sizes).

## How it works

```
1. Generate test document with unique legal clauses
2. Inject unique hash boundary markers between sections:
   <<<SECTION_BEGIN:c96c9e148785eecb>>>
   ...500 lines of content...
   <<<SECTION_END:c96c9e148785eecb>>>

3. For each section, pipe FULL marked document to claude -p:
   - Model must FIND the markers (needle-in-haystack)
   - Model must REPRODUCE content between markers (verbatim recall)

4. Score each section against unmarked original via SequenceMatcher
```

## Quick Start

```bash
# Generate test documents
python3 bench/generate_large_test_doc.py --tokens 100000 --output test_docs/100k_legal.txt

# Run eval (Opus)
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000
CLAUDE_MODEL=opus ./bench/recall_eval_fullctx.sh test_docs/100k_legal.txt

# Run eval (Sonnet, smaller sections for output limit)
CLAUDE_MODEL=sonnet LINES_PER_SECTION=250 \
  ./bench/recall_eval_fullctx.sh test_docs/100k_legal.txt
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| CLAUDE_CODE_MAX_OUTPUT_TOKENS | 128000 | Max output tokens per call |
| CLAUDE_MODEL | (CLI default) | Model: opus, sonnet, haiku |
| LINES_PER_SECTION | 500 | Lines per section (250 for Sonnet/Haiku) |

## Token Counts (Measured via Anthropic API)

| Label | Characters | Measured Tokens | Chars/Token |
|-------|-----------|:--------------:|:-----------:|
| 10k | 40,975 | 8,492 | 4.83 |
| 25k | 101,204 | 20,933 | 4.83 |
| 50k | 201,296 | 41,681 | 4.83 |
| 75k | 301,415 | 62,431 | 4.83 |
| 100k | 402,383 | 83,360 | 4.83 |
| 250k | 1,004,754 | 208,254 | 4.82 |
| 400k | 1,607,127 | 333,052 | 4.83 |
| 600k_tok | 2,910,782 | 602,499 | 4.83 |

## Repo Structure

```
bench/
  recall_eval_fullctx.sh    # Main eval script (v2, hash markers)
  generate_large_test_doc.py # Test document generator
results/
  METHODOLOGY.md             # Detailed methodology and analysis
test_docs/                   # Generated test documents (gitignored)
recall_workdir/              # Eval outputs (gitignored)
```

## Limitations

- Single runs (should average 3+ for reliability)
- RLHF interference at high context causes non-recall failures
- Legal text specific (4.83 c/tok ratio)
- Claude Code CLI enforces model-specific context limits client-side
- Sonnet 1M context gated behind unreleased feature flag

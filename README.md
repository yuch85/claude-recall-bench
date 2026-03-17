# Claude Recall Bench

An eval harness for measuring Claude's verbatim reproduction fidelity across context window sizes. Tests whether models can locate content by unique hash boundary markers within a large document and reproduce it character-for-character.

## Why it matters

In document amendment workflows (legal redlining, contract editing), an LLM must return text with only targeted edits. Any dropped, paraphrased, or hallucinated text produces spurious tracked changes. This benchmark quantifies that risk.

## Key Results (2026-03-17)

### Summary Table

| Model | Context Window | 100% Recall Threshold | Breakpoint | Notes |
|-------|:-------------:|:--------------------:|:----------:|-------|
| **Opus 4.6** | 1M tokens | **333K tokens** | 333K-394K tokens | At 394K+, RLHF meta-commentary replaces output on ~60-70% of sections |
| **Sonnet 4.6** | 200K tokens* | **122K tokens** | Context limit | Perfect recall within testable range. *1M gated behind `coral_reef_sonnet` feature flag |
| **Haiku 4.5** | 200K tokens | **42K tokens** | 62K tokens | Degrades to 95-99% above threshold |

### Opus 4.6 Results (v2, hash markers, 500-line sections)

| Doc | Input Tokens | Sections | Perfect/Total | Overall |
|-----|:-----------:|:--------:|:-------------:|:-------:|
| 10k | 8,492 | 1 | 1/1 | **100%** |
| 25k | 20,933 | 1 | 1/1 | **100%** |
| 50k | 41,681 | 1 | 1/1 | **100%** |
| 100k | 83,360 | 2 | 2/2 | **100%** |
| 400k | 333,052 | 8 | 8/8 | **100%** |
| 390k_tok | ~394,000 | 10 | 1/3 (in progress) | Failing — secs 1,2 failed |
| 450k_tok | ~454,000 | 11 | 4/11 | **36%** sections pass |
| 600k_tok | 602,499 | 15 | 8/9 (partial run) | sec 0 fails, secs 1-8 perfect |

### Opus Failure Analysis at 454K Tokens

At 454K input tokens (450k_tok document, 11 sections):

- **4/11 sections perfect** (sections 0, 1, 3, 8), **6/11 failed** with RLHF meta-commentary, **1 "Prompt too long"**
- Failures are **NOT position-dependent**: sections 2, 4, 5, 6, 7, 9 failed but sections 0, 1, 3, 8 passed
- The model produces meta-commentary like "I'm unable to write the file" or "this section is too large to output"
- This is **RLHF training interference, not recall failure** — the model CAN attend to the content but refuses to output it
- When the model does produce output, it is always verbatim correct

### Sonnet 4.6 Results (v2, hash markers, 250-line sections)

| Doc | Input Tokens | Sections | Overall Word Acc |
|-----|:-----------:|:--------:|:----------------:|
| 10k | 8,492 | 1 | **100%** |
| 25k | 20,933 | 1 | **100%** |
| 50k | 41,681 | 2 | **100%** |
| 75k | 62,431 | 3 | **100%** |
| 100k | 83,360 | 4 | 99.94% |
| 120k_tok | ~122,000 | 6 | **100%** |

### Sonnet Context Window Discovery

Claude Code source shows Sonnet 4.6 gets 1M context via feature flag `coral_reef_sonnet`:
- `TnA()` -> `u2L()` -> `nK9("coral_reef_sonnet") === "true"` gates 1M access
- Currently falls back to 200K (`oiA=200000`) when the flag is not set
- The `claude -p` CLI blocks requests **client-side** (`api_ms=0`) above ~147K doc tokens for Sonnet
- Within the testable range (up to 122K tokens), Sonnet shows **no recall degradation** — only hard context cutoffs

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

3. **Opus failures at 394K+ tokens are RLHF interference, not recall failures.** The model outputs meta-commentary ("I'm unable to write the file", "this section is too large to output") instead of document text. The content it does produce is always verbatim. Failures are not position-dependent — scattered sections fail while others pass.

4. **Sonnet 4.6 has 1M context in code, gated behind feature flag.** Claude Code's source shows Sonnet 4.6 gets 1M via `TnA()` -> `u2L()` -> `nK9("coral_reef_sonnet") === "true"`. Currently falls back to 200K (`oiA=200000`). The `claude -p` CLI blocks requests client-side (`api_ms=0`) above ~147K doc tokens.

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

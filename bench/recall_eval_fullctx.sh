#!/usr/bin/env bash
set -euo pipefail

# ===========================================================================
# Claude Code Full-Context Recall Fidelity Eval (v2 — hash markers)
#
# REAL recall test: sends the FULL document (with unique hash boundary
# markers injected) in every call. The model must locate the markers
# and reproduce the content between them — a combined needle-in-haystack
# retrieval + verbatim reproduction test.
#
# Architecture per call:
#   marked_document (8K-800K tokens) + prompt (~300 tokens) + output (≤128K) ≤ 1M
#
# Usage:
#   ./bench/recall_eval_fullctx.sh test_docs/100k_legal.txt
#   ./bench/recall_eval_fullctx.sh test_docs/400k_legal.txt
#   LINES_PER_SECTION=250 ./bench/recall_eval_fullctx.sh test_docs/100k_legal.txt
# ===========================================================================

SOURCE_FILE="${1:?Usage: $0 <source_file>}"

export CLAUDE_CODE_MAX_OUTPUT_TOKENS="${CLAUDE_CODE_MAX_OUTPUT_TOKENS:-128000}"

# Model selection (default: whatever claude CLI defaults to)
CLAUDE_MODEL="${CLAUDE_MODEL:-}"
MODEL_FLAG=""
MODEL_LABEL="default"
if [[ -n "$CLAUDE_MODEL" ]]; then
    MODEL_FLAG="--model $CLAUDE_MODEL"
    MODEL_LABEL="$CLAUDE_MODEL"
fi

WORKDIR="recall_workdir/fullctx_$(basename "$SOURCE_FILE" .txt)_${MODEL_LABEL}_$(date +%s)"

# How many lines per section to reproduce per call
LINES_PER_SECTION="${LINES_PER_SECTION:-500}"

echo "============================================================"
echo " FULL-CONTEXT RECALL FIDELITY EVAL (v2 — hash markers)"
echo "============================================================"
echo ""
echo "Source:            $SOURCE_FILE"
echo "Model:             $MODEL_LABEL"
echo "Max output tokens: $CLAUDE_CODE_MAX_OUTPUT_TOKENS"
echo "Lines per section: $LINES_PER_SECTION"
echo "Workdir:           $WORKDIR"
echo ""

if [[ ! -f "$SOURCE_FILE" ]]; then
    echo "ERROR: Source file not found: $SOURCE_FILE"
    exit 1
fi

SOURCE_CHARS=$(wc -c < "$SOURCE_FILE")
SOURCE_LINES=$(wc -l < "$SOURCE_FILE")
SOURCE_SHA256=$(sha256sum "$SOURCE_FILE" | cut -d' ' -f1)
EST_TOKENS=$((SOURCE_CHARS * 10 / 48))  # ~4.83 chars/token

echo "Source size:  $SOURCE_CHARS chars, $SOURCE_LINES lines, ~$EST_TOKENS tokens (est @ 4.83 c/tok)"
echo "Source SHA256: $SOURCE_SHA256"

if [[ $EST_TOKENS -gt 798000 ]]; then
    echo "WARNING: Document may exceed max input capacity (~798K tokens)"
fi

mkdir -p "$WORKDIR/sections"

# Calculate sections
NUM_SECTIONS=$(( (SOURCE_LINES + LINES_PER_SECTION - 1) / LINES_PER_SECTION ))
echo "Sections:     $NUM_SECTIONS (of $LINES_PER_SECTION lines each)"
echo ""

# Split source into section files for comparison (unmarked originals)
echo "--- Splitting source into sections ---"
split -l "$LINES_PER_SECTION" -d -a 3 "$SOURCE_FILE" "$WORKDIR/sections/section_"
for sec in "$WORKDIR/sections/"section_*; do
    sec_name=$(basename "$sec")
    sec_chars=$(wc -c < "$sec")
    sec_lines=$(wc -l < "$sec")
    echo "  $sec_name: $sec_lines lines, $sec_chars chars"
done

# Generate unique hash markers for each section boundary
echo ""
echo "--- Generating hash markers ---"
declare -a MARKER_HASHES
for sec in "$WORKDIR/sections/"section_*; do
    # Hash = sha256(section_content + section_index) truncated to 16 hex chars
    sec_hash=$(sha256sum "$sec" | cut -c1-16)
    MARKER_HASHES+=("$sec_hash")
    echo "  $(basename "$sec"): marker=$sec_hash"
done

# Build the marked document: inject boundary markers between sections
echo ""
echo "--- Building marked document ---"
MARKED_FILE="$WORKDIR/marked_source.txt"
> "$MARKED_FILE"

SECTION_IDX=0
for sec in "$WORKDIR/sections/"section_*; do
    hash="${MARKER_HASHES[$SECTION_IDX]}"
    echo "<<<SECTION_BEGIN:${hash}>>>" >> "$MARKED_FILE"
    cat "$sec" >> "$MARKED_FILE"
    # Ensure content ends with newline before end marker
    [[ $(tail -c1 "$sec" | wc -l) -eq 0 ]] && echo "" >> "$MARKED_FILE"
    echo "<<<SECTION_END:${hash}>>>" >> "$MARKED_FILE"
    SECTION_IDX=$((SECTION_IDX + 1))
done

MARKED_CHARS=$(wc -c < "$MARKED_FILE")
MARKED_LINES=$(wc -l < "$MARKED_FILE")
echo "Marked document: $MARKED_CHARS chars, $MARKED_LINES lines"

# Process each section — full marked document in context every time
echo ""
echo "--- Processing sections (full marked document in context each call) ---"
TOTAL_START=$(date +%s)

SECTION_IDX=0
for sec in "$WORKDIR/sections/"section_*; do
    sec_name=$(basename "$sec")
    output_file="$WORKDIR/sections/output_$(printf '%03d' $SECTION_IDX)"

    sec_lines=$(wc -l < "$sec")
    sec_chars=$(wc -c < "$sec")
    hash="${MARKER_HASHES[$SECTION_IDX]}"

    echo -n "  Section $SECTION_IDX [${hash}] ($sec_chars chars)... "
    SEC_START=$(date +%s)

    # Send FULL marked document + ask for content between specific markers
    cat "$MARKED_FILE" | claude -p $MODEL_FLAG \
        "The text above is a legal document with section boundary markers. Each section is delimited by unique hash markers in this format:
<<<SECTION_BEGIN:hash>>>
...section content...
<<<SECTION_END:hash>>>

YOUR TASK: Find the markers with hash ${hash} and reproduce EXACTLY the text between <<<SECTION_BEGIN:${hash}>>> and <<<SECTION_END:${hash}>>>. Do not include the marker lines themselves.

CRITICAL RULES:
1. Output ONLY the verbatim document text between those two markers. No other text.
2. Do NOT add any preamble, commentary, summary, explanation, or meta-text before, during, or after the content. Not a single word of your own.
3. Do NOT stop early. Do NOT truncate. Do NOT summarize. Reproduce the COMPLETE section even if it is very long. The section is approximately ${sec_chars} characters — output all of it.
4. Do NOT add content from outside the markers. Stop exactly at the end marker.
5. Do NOT use markdown formatting or code blocks.
6. Begin outputting the document text as your very first character of output." \
        --output-format text \
        > "$output_file" 2>/dev/null

    SEC_END=$(date +%s)
    SEC_ELAPSED=$((SEC_END - SEC_START))
    output_chars=$(wc -c < "$output_file")
    echo "done (${SEC_ELAPSED}s, $output_chars chars out)"

    SECTION_IDX=$((SECTION_IDX + 1))
done

TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))

# Reassemble
echo ""
echo "--- Reassembling ---"
cat "$WORKDIR/sections/"output_* > "$WORKDIR/reproduced.txt"
REPRO_CHARS=$(wc -c < "$WORKDIR/reproduced.txt")
REPRO_SHA256=$(sha256sum "$WORKDIR/reproduced.txt" | cut -d' ' -f1)
echo "Reproduced: $REPRO_CHARS chars"
echo "SHA256:     $REPRO_SHA256"

# Score
echo ""
echo "--- Scoring ---"
_SF="$SOURCE_FILE" _WD="$WORKDIR" _TE="$TOTAL_ELAPSED" _NS="$NUM_SECTIONS" _ML="$MODEL_LABEL" python3 << 'SCORING_EOF'
import difflib
import hashlib
import json
import os
from datetime import datetime

source_file = os.environ["_SF"]
workdir = os.environ["_WD"]
total_elapsed = int(os.environ["_TE"])
num_sections = int(os.environ["_NS"])
model_label = os.environ.get("_ML", "default")

original = open(source_file).read()
reproduced = open(os.path.join(workdir, "reproduced.txt")).read()

orig_hash = hashlib.sha256(original.encode()).hexdigest()
repro_hash = hashlib.sha256(reproduced.encode()).hexdigest()
exact = orig_hash == repro_hash

# Word-level (robust to insertions/deletions)
orig_words = original.split()
repro_words = reproduced.split()
matcher = difflib.SequenceMatcher(None, orig_words, repro_words)
matched = sum(b.size for b in matcher.get_matching_blocks())
word_acc = matched / len(orig_words) if orig_words else 1.0
opcodes = matcher.get_opcodes()
ins = sum(j2-j1 for t,i1,i2,j1,j2 in opcodes if t=="insert")
dels = sum(i2-i1 for t,i1,i2,j1,j2 in opcodes if t=="delete")
reps = sum(max(i2-i1,j2-j1) for t,i1,i2,j1,j2 in opcodes if t=="replace")

# Char-level via SequenceMatcher (handles shifts properly)
char_matcher = difflib.SequenceMatcher(None, original, reproduced)
char_similarity = char_matcher.ratio()

# Line-level
orig_lines = original.splitlines()
repro_lines = reproduced.splitlines()
line_matcher = difflib.SequenceMatcher(None, orig_lines, repro_lines)
line_similarity = line_matcher.ratio()

# First diff (positional)
first_diff = None
for i,(a,b) in enumerate(zip(original, reproduced)):
    if a != b:
        s = max(0,i-30)
        e = min(len(original),i+30)
        first_diff = {"pos": i, "pct": round(i/len(original)*100,2),
                      "expected": repr(original[s:e]), "got": repr(reproduced[s:e])}
        break
if first_diff is None and len(original) != len(reproduced):
    first_diff = {"pos": min(len(original),len(reproduced)),
                  "note": f"Length mismatch: {len(original)} vs {len(reproduced)}"}

print()
print("=" * 60)
print(" FULL-CONTEXT RECALL FIDELITY RESULTS (v2 — hash markers)")
print("=" * 60)
print()
match_str = "YES" if exact else "NO"
print(f"Exact match:       {match_str}")
print(f"Char similarity:   {char_similarity:.6%}")
print(f"Word accuracy:     {word_acc:.6%}")
print(f"Line similarity:   {line_similarity:.6%}")
print(f"Words:             {len(orig_words):,} -> {len(repro_words):,}")
print(f"Insertions:        {ins}")
print(f"Deletions:         {dels}")
print(f"Replacements:      {reps}")
print(f"Duration:          {total_elapsed}s ({total_elapsed//60}m {total_elapsed%60}s)")
print(f"Sections:          {num_sections}")
if first_diff:
    print(f"First diff at:     char {first_diff.get('pos','?')} ({first_diff.get('pct','?')}%)")
    if "expected" in first_diff:
        print(f"  Expected: {first_diff['expected'][:80]}")
        print(f"  Got:      {first_diff['got'][:80]}")
    if "note" in first_diff:
        print(f"  {first_diff['note']}")
print()

# Per-section scoring
print("--- Per-Section Fidelity ---")
section_files = sorted([f for f in os.listdir(os.path.join(workdir, "sections")) if f.startswith("section_")])
output_files = sorted([f for f in os.listdir(os.path.join(workdir, "sections")) if f.startswith("output_")])

section_results = []
for sf, of in zip(section_files, output_files):
    with open(os.path.join(workdir, "sections", sf)) as f:
        sec_orig = f.read()
    with open(os.path.join(workdir, "sections", of)) as f:
        sec_repro = f.read()

    sw_orig = sec_orig.split()
    sw_repro = sec_repro.split()
    sm = difflib.SequenceMatcher(None, sw_orig, sw_repro)
    smatched = sum(b.size for b in sm.get_matching_blocks())
    swa = smatched / len(sw_orig) if sw_orig else 1.0

    sc_sim = difflib.SequenceMatcher(None, sec_orig, sec_repro).ratio()

    sh = hashlib.sha256(sec_orig.encode()).hexdigest()
    rh = hashlib.sha256(sec_repro.encode()).hexdigest()
    exact_s = "YES" if sh == rh else "NO"

    print(f"  {sf}: exact={exact_s}  char_sim={sc_sim:.4%}  word_acc={swa:.4%}  ({len(sec_orig):,} -> {len(sec_repro):,} chars)")
    section_results.append({
        "section": sf, "exact": sh == rh,
        "char_similarity": round(sc_sim, 6), "word_accuracy": round(swa, 6),
        "original_chars": len(sec_orig), "reproduced_chars": len(sec_repro),
    })

# Save report
report = {
    "source_file": source_file,
    "source_chars": len(original),
    "reproduced_chars": len(reproduced),
    "protocol": "full-context-recall-v2-hash-markers",
    "model": model_label,
    "exact_match": exact,
    "char_similarity": round(char_similarity, 6),
    "word_accuracy": round(word_acc, 6),
    "line_similarity": round(line_similarity, 6),
    "insertions": ins, "deletions": dels, "replacements": reps,
    "sections": num_sections,
    "duration_s": total_elapsed,
    "section_results": section_results,
    "first_diff": first_diff,
    "timestamp": datetime.now().isoformat(),
}
with open(os.path.join(workdir, "report.json"), "w") as f:
    json.dump(report, f, indent=2)
print(f"\nReport: {os.path.join(workdir, 'report.json')}")
SCORING_EOF

echo ""
echo "Done. Full diff: diff $SOURCE_FILE $WORKDIR/reproduced.txt"

#!/usr/bin/env python3
"""Eval harness for tuning the local whisper.cpp backend against real recordings.

Re-transcribes a set of the owner's recordings through `whisper-cli` under
several decode configs (mainly the entropy threshold — the anti-loop trigger),
then scores each raw output for phrase loops, single-word loops, phantoms, and
content length, and shows the post-cleanup text. Used to pick the setting that
kills loops without denting accuracy.

Usage:
    python tools/eval_whisper.py            # runs the configured sweep
    python tools/eval_whisper.py --quick    # Julia only, baseline vs et1.0

stdout: a per-recording x per-config table + the cleaned tail of the Julia case.
Also writes tools/eval_report.json for the record.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dictate  # noqa: E402  (reuse the cleanup pipeline)

WHISPER_CLI = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
MODEL = os.path.expanduser("~/whisper.cpp/models/ggml-large-v3-turbo.bin")
ARCHIVE = os.path.expanduser("~/Desktop/Whisper Dictate Recordings")

# Decode configs. Sweep TEMPERATURE first: the loops are *confident* (the model
# predicts the repeat tokens with high probability), so the entropy-thold
# fallback never triggers — only raising the sampling temperature breaks the
# greedy loop. best-of/beam variants test whether pure sampling (bo1/beam0)
# behaves differently from beam search at a given temperature.
COMMON = ["--no-timestamps", "--language", "en"]
CONFIGS = [
    ("temp0.0_bo5",  ["--temperature", "0.0", "--best-of", "5", "--beam-size", "5"]),
    ("temp0.3_bo5",  ["--temperature", "0.3", "--best-of", "5", "--beam-size", "5"]),
    ("temp0.5_bo5",  ["--temperature", "0.5", "--best-of", "5", "--beam-size", "5"]),
    ("temp0.3_bo1",  ["--temperature", "0.3", "--best-of", "1", "--beam-size", "0"]),
    ("temp0.5_bo1",  ["--temperature", "0.5", "--best-of", "1", "--beam-size", "0"]),
]

# The key loop test case + a few clean moderate-length recordings for the
# no-regression check. (Filled in from the archive by --pick, or hard-coded.)
JULIA = "2026-07-16_10-47-50_907.wav"
RECORDINGS = [JULIA]  # + clean ones appended via --add


def _norm(w):
    return w.strip(".,!?;:;'\"-()").lower()


def detect_phrase_loops(text, max_unit=6, min_reps=3):
    """Return [(reps, 'phrase'), ...] for multi-word phrase loops in raw text."""
    words = text.split()
    n = len(words)
    norms = [_norm(w) for w in words]
    hits, i = [], 0
    while i < n:
        chosen = None
        max_len = min(max_unit, (n - i) // min_reps)
        for ulen in range(2, max_len + 1):
            unit = norms[i:i + ulen]
            reps, j = 1, i + ulen
            while j + ulen <= n and norms[j:j + ulen] == unit:
                reps += 1
                j += ulen
            if reps >= min_reps:
                chosen = (reps, j, " ".join(words[i:i + ulen]))
                break
        if chosen:
            hits.append((chosen[0], chosen[2]))
            i = chosen[1]
        else:
            i += 1
    return hits


def detect_single_loops(text, min_reps=4):
    """[(reps, word)] for single-word runs of min_reps+ (the stuck-token case)."""
    import re
    rx = re.compile(r"\b(\w+)(?:[,\s.]+\1){%d,}\b" % (min_reps - 1), re.IGNORECASE)
    out = []
    for m in rx.finditer(text):
        w = m.group(1)
        reps = 1 + len(re.findall(r"[,\s.]+", m.group(0)))
        out.append((reps, w))
    return out


def detect_phantoms(text):
    """Count occurrences of known phantom phrases as standalone tokens."""
    words = {_norm(w) for w in text.split()}
    return len(words & {p.split()[0] for p in dictate.HALLUCINATION_PHRASES
                        if " " not in p and p in words}) + sum(
        1 for p in dictate.HALLUCINATION_PHRASES if " " in p and p in text.lower())


def cleaned(text):
    return dictate._strip_trailing_phantom(
        dictate._collapse_phrase_repeats(
            dictate._collapse_consecutive_repeats(
                dictate._clean_transcript(text))))


def run_cli(wav, extra_flags):
    cmd = [WHISPER_CLI, "-m", MODEL, "-f", wav] + COMMON + extra_flags
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return "<timeout>", time.time() - t0, -1, "timeout"
    return r.stdout.strip(), time.time() - t0, r.returncode, r.stderr[-300:]


def score(text):
    loops = detect_phrase_loops(text)
    singles = detect_single_loops(text)
    c = cleaned(text)
    return {
        "words": len(text.split()),
        "phrase_loops": len(loops),
        "single_loops": len(singles),
        "loop_examples": [f"{r}x[{p[:30]}]" for r, p in (loops + singles)[:3]],
        "cleaned_words": len(c.split()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="Julia only, baseline vs et1.0")
    ap.add_argument("--add", action="append", default=[], help="extra recording .wav basename to include")
    args = ap.parse_args()

    configs = ([("baseline_et2.40", CONFIGS[0][1]), ("et1.00", CONFIGS[2][1])]
               if args.quick else CONFIGS)
    recs = RECORDINGS + args.add
    paths = [os.path.join(ARCHIVE, r) for r in recs]

    report = {}
    for name, flags in configs:
        print(f"\n=== config: {name}  (flags: {' '.join(flags)}) ===")
        for rec, path in zip(recs, paths):
            if not os.path.exists(path):
                print(f"  {rec}: MISSING"); continue
            text, dt, rc, err = run_cli(path, flags)
            if rc != 0:
                print(f"  {rec}: cli failed rc={rc} {err[-120:]}"); continue
            s = score(text)
            report.setdefault(name, {})[rec] = {**s, "secs": round(dt, 1),
                                                "tail": cleaned(text)[-80:]}
            print(f"  {rec[:24]:24} {s['words']:4d}w  loops={s['phrase_loops']+s['single_loops']}  "
                  f"{s['loop_examples']}  ({dt:.0f}s)")

    with open(os.path.join(os.path.dirname(__file__), "eval_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    print("\n=== Julia cleaned tail per config (does the loop die?) ===")
    for name, _ in configs:
        j = report.get(name, {}).get(JULIA, {})
        print(f"  {name:16} -> ...{j.get('tail', '<n/a>')}")


if __name__ == "__main__":
    main()

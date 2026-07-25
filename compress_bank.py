#!/usr/bin/env python3
"""Gzip every hidden test file in the bank in place: tests/hidden/*.in|*.out -> *.in.gz|*.out.gz,
removing the plain original. Idempotent (skips files already compressed).

Why: hidden tests dominate bank size (max-scale inputs are MBs each). At ~5-8x compression this keeps
the bank small enough to host 1000s of problems on Fly's free 3GB volume AND keeps the GitHub repo
lean. Sample/edge/source files stay plain (small, and read by author tooling). Bytes are written with
mtime=0 so re-running produces identical output (no git churn). Every reader (the app judge in
app/runner/problems.py and mutation_test.py) transparently decompresses, so judging is unaffected.

Usage:  python3 compress_bank.py [--dir <problems_dir>] [--dry-run]
"""
import gzip
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def gz_write(path_no_gz: str, data: bytes) -> None:
    with open(path_no_gz + ".gz", "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(data)


def main() -> int:
    bank = os.path.join(ROOT, "problems")
    dry = "--dry-run" in sys.argv
    for i, a in enumerate(sys.argv):
        if a == "--dir":
            bank = os.path.abspath(sys.argv[i + 1])
    n_files = before_total = after_total = 0
    for pid in sorted(os.listdir(bank)):
        hd = os.path.join(bank, pid, "tests", "hidden")
        if not os.path.isdir(hd):
            continue
        for fn in sorted(os.listdir(hd)):
            if not (fn.endswith(".in") or fn.endswith(".out")):
                continue  # already .gz, or something else
            p = os.path.join(hd, fn)
            data = open(p, "rb").read()
            before_total += len(data)
            n_files += 1
            if dry:
                continue
            gz_write(p, data)
            os.remove(p)
            after_total += os.path.getsize(p + ".gz")
    if dry:
        print(f"DRY RUN: {n_files} plain hidden files totalling {before_total // 1024} KB would be gzipped")
    else:
        ratio = (before_total / after_total) if after_total else 1.0
        print(f"compressed {n_files} hidden files: {before_total // 1024} KB -> "
              f"{after_total // 1024} KB ({ratio:.1f}x smaller)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

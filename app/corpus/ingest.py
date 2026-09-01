"""Ingest pipeline: Phase 2.1 acquire, 2.2 parse, 2.3 chunk.

Embeddings (Phase 2.4) are not run yet. `--refresh` re-fetches catalogued
Groww snapshots (scheduled re-ingest) instead of running acquire → parse → chunk.
"""

from __future__ import annotations

import argparse
import sys

from app.corpus.acquire import main as acquire_main
from app.corpus.chunk import main as chunk_main
from app.corpus.parse import main as parse_main
from app.corpus.refresh import main as refresh_main


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Intercept before argparse so `ingest --refresh --help` shows refresh flags.
    if "--refresh" in argv:
        return refresh_main([arg for arg in argv if arg != "--refresh"])

    parser = argparse.ArgumentParser(
        description="Ingest pipeline. Default: Phase 2.1 + 2.2 + 2.3 (no embeddings).",
    )
    parser.add_argument("--fetch-missing", action="store_true")
    parser.add_argument("--acquire-only", action="store_true")
    parser.add_argument("--parse-only", action="store_true")
    parser.add_argument("--chunk-only", action="store_true")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch every catalogued Groww snapshot, verify, then parse and chunk.",
    )
    args, rest = parser.parse_known_args(argv)
    if args.acquire_only:
        extra = ["--fetch-missing"] if args.fetch_missing else []
        return acquire_main(extra + rest)
    if args.parse_only:
        return parse_main(rest)
    if args.chunk_only:
        return chunk_main(rest)
    print("Phase 2.1: source identification and acquisition")
    extra = ["--fetch-missing"] if args.fetch_missing else []
    code = acquire_main(extra + rest)
    if code != 0:
        return code
    print("Phase 2.2: parsing and normalization")
    code = parse_main(rest)
    if code != 0:
        return code
    print("Phase 2.3: chunking")
    return chunk_main(rest)


if __name__ == "__main__":
    raise SystemExit(main())

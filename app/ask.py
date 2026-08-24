"""CLI: python -m app.ask "What is the expense ratio of HDFC Large Cap Fund Direct Growth?" """

from __future__ import annotations

import argparse
import json
import sys

from app.pipeline.orchestrator import ask


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Facts-only Ask CLI (Groww corpus, Groq formatter).")
    parser.add_argument("question", nargs="*", help="User question")
    args = parser.parse_args(argv)
    question = " ".join(args.question).strip()
    if not question:
        parser.print_help()
        return 2
    response = ask(question)
    json.dump(response.as_public_dict(), sys.stdout, ensure_ascii=True, indent=2)
    sys.stdout.write("\n")
    return 0 if response.type != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())

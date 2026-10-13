"""CLI for synthetic or reviewed structured inputs, not image OCR."""

import argparse
import json
import sys
from pathlib import Path

from .allocation import preview
from .domain import validate_receipt


def read_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("receipt")
    split = commands.add_parser("preview")
    split.add_argument("receipt")
    split.add_argument("plan")
    split.add_argument("members")
    args = parser.parse_args()
    try:
        receipt = read_json(args.receipt)
        result = ({"valid": True, "receiptId": validate_receipt(receipt)["receiptId"]}
                  if args.command == "validate" else
                  preview(receipt, read_json(args.plan), read_json(args.members)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

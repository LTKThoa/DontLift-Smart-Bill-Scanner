"""Local receipt OCR, review, allocation and benchmark CLI."""

import argparse
import json
import sys
from pathlib import Path

from .allocation import preview
from .domain import validate_receipt
from .extraction import extract_draft
from .review import review_draft
from .dataset import validate_manifest
from .evaluation import evaluate, prediction_from_draft


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
    scan = commands.add_parser("scan", help="run local OCR and write a review draft")
    scan.add_argument("image")
    scan.add_argument("--output", required=True)
    scan.add_argument("--model-dir", default="models")
    extract = commands.add_parser("extract", help="parse a saved OCR document")
    extract.add_argument("document")
    extract.add_argument("--output", required=True)
    review = commands.add_parser("review", help="apply explicit human correction")
    review.add_argument("draft")
    review.add_argument("correction")
    review.add_argument("--output", required=True)
    manifest = commands.add_parser("check-manifest", help="check dataset identity and split leakage")
    manifest.add_argument("manifest")
    manifest.add_argument("--verify-images", action="store_true")
    benchmark = commands.add_parser("evaluate", help="evaluate a frozen manifest split")
    benchmark.add_argument("manifest")
    benchmark.add_argument("labels")
    benchmark.add_argument("predictions")
    benchmark.add_argument("--split", choices=['train', 'validation', 'test'], default='test')
    benchmark.add_argument("--output", required=True)
    export = commands.add_parser("export-prediction", help="export an uncorrected OCR draft for evaluation")
    export.add_argument("manifest")
    export.add_argument("draft")
    export.add_argument("--sample-id", required=True)
    export.add_argument("--run-id", required=True)
    export.add_argument("--pipeline-version", required=True)
    export.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == 'check-manifest':
            result = validate_manifest(read_json(args.manifest), Path(args.manifest).resolve().parent,
                                       args.verify_images)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command in {'evaluate', 'export-prediction'}:
            if args.command == 'evaluate':
                result = evaluate(read_json(args.manifest), read_json(args.labels),
                                  read_json(args.predictions), args.split)
            else:
                result = prediction_from_draft(read_json(args.manifest), read_json(args.draft),
                    args.sample_id, args.run_id, args.pipeline_version)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', encoding='utf-8') as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
            print(json.dumps({'output': str(output), 'metrics': result.get('metrics'),
                              'warnings': result.get('warnings', [])}))
            return 0
        if args.command in {"scan", "extract", "review"}:
            if args.command == "scan":
                from .ocr import scan_image
                result = extract_draft(scan_image(args.image, args.model_dir))
            elif args.command == "extract":
                result = extract_draft(read_json(args.document))
            else:
                result = review_draft(read_json(args.draft), read_json(args.correction))
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', encoding='utf-8') as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
            print(json.dumps({'output': str(output), 'reviewStatus': result['reviewStatus']}))
            return 0
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

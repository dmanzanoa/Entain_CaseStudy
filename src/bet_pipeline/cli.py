from __future__ import annotations

import argparse

from bet_pipeline.build_features import run_build_features
from bet_pipeline.validate import run_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bet-pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate raw betting data")
    validate.add_argument("--input", required=True, help="Path to input bets.csv")
    validate.add_argument("--output", required=True, help="Directory for validation outputs")

    features = subparsers.add_parser("build-features", help="Build customer-level features")
    features.add_argument("--input", required=True, help="Path to input bets.csv")
    features.add_argument("--output", required=True, help="Directory for feature outputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        report = run_validation(args.input, args.output)
        print(f"Validated {report['total_rows']} rows: {report['valid_rows']} valid, {report['invalid_rows']} invalid")
        return 0
    if args.command == "build-features":
        features = run_build_features(args.input, args.output)
        print(f"Wrote customer features for {len(features)} customers")
        return 0
    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

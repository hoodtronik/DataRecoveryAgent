"""Command-line interface to image-file analysis. Never writes to source images."""

from __future__ import annotations

import argparse
import json
import sys
from .core import extract_candidates, hash_image, save_report, scan_image


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datarecoveryagent",
        description="Read-only signature triage of existing disk image files",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    hash_cmd = sub.add_parser("hash-image", help="Stream SHA-256 of a disk-image file")
    hash_cmd.add_argument("image")
    scan_cmd = sub.add_parser("scan", help="Scan an image for FLP and WAV candidates")
    scan_cmd.add_argument("image")
    scan_cmd.add_argument("--kinds", default="flp,wav", help="Comma-separated: flp,wav")
    scan_cmd.add_argument("--output", required=True, help="New JSON report path")
    extract_cmd = sub.add_parser("extract", help="Extract verified candidates from an image")
    extract_cmd.add_argument("image")
    extract_cmd.add_argument("report", help="Candidate JSON produced by scan")
    extract_cmd.add_argument("--outdir", required=True, help="Separate recovery output folder")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        if args.command == "hash-image":
            print(json.dumps(hash_image(args.image), indent=2))
        elif args.command == "scan":
            kinds = tuple(k.strip() for k in args.kinds.split(","))
            next_percentage = [10]

            def progress(done: int, total: int) -> None:
                percent = 100 if total == 0 else round(100 * done / total)
                if percent >= next_percentage[0]:
                    print(f"Scanned {min(percent, 100)}%", file=sys.stderr)
                    next_percentage[0] += 10

            report = scan_image(args.image, kinds=kinds, progress=progress)
            destination = save_report(report, args.output, args.image)
            print(json.dumps({
                "report": str(destination),
                "candidates": len(report["candidates"]),
                "warning": report["warning"],
            }, indent=2))
        elif args.command == "extract":
            report = extract_candidates(args.image, args.report, args.outdir)
            print(json.dumps({
                "files_extracted": report["files_extracted"],
                "output_folder": args.outdir,
                "warning": report["warning"],
            }, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

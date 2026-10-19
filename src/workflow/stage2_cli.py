"""Command-line interface for the Stage 2 spatial workflow.

The researcher must explicitly specify the UTC verification window.

This CLI delegates scientific computation and artifact management to
run_stage2(). It does not select temporal clusters, overwrite existing
results, or make automatic earthquake-related decisions.

Usage:
    python -m src.workflow.stage2_cli --help
"""

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .stage2_runner import run_stage2


def build_parser() -> argparse.ArgumentParser:
    """Create the Stage 2 command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="python -m src.workflow.stage2_cli",
        description=(
            "Run Stage 2 spatial verification for a researcher-selected "
            "explicit UTC window. Export positive/negative PNG maps "
            "and a spatial summary JSON."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    required = parser.add_argument_group(
        "required research inputs"
    )

    required.add_argument(
        "--manifest",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the existing Stage 1 Preparation Manifest JSON.",
    )

    required.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        metavar="PATH",
        help="Directory or dataset prefix expected by the GIM loader.",
    )

    required.add_argument(
        "--start-time",
        type=str,
        required=True,
        metavar="UTC",
        help="Explicit UTC window start, e.g. 2022-05-28T06:00:00Z.",
    )

    required.add_argument(
        "--end-time",
        type=str,
        required=True,
        metavar="UTC",
        help="Explicit UTC window end, e.g. 2022-05-29T05:00:00Z.",
    )

    required.add_argument(
        "--latitude",
        type=float,
        required=True,
        metavar="DEGREES",
        help="Earthquake epicenter latitude.",
    )

    required.add_argument(
        "--longitude",
        type=float,
        required=True,
        metavar="DEGREES",
        help="Earthquake epicenter longitude.",
    )

    required.add_argument(
        "--magnitude",
        type=float,
        required=True,
        metavar="MW",
        help="Earthquake magnitude used for preparation-radius metadata.",
    )

    optional = parser.add_argument_group(
        "optional analysis settings"
    )

    optional.add_argument(
        "--reference-days",
        type=int,
        default=15,
        metavar="N",
        help="Number of reference days.",
    )

    optional.add_argument(
        "--k",
        type=float,
        default=3.0,
        metavar="VALUE",
        help="Quartile-based anomaly threshold multiplier.",
    )

    optional.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Output directory inside the Preparation Manifest root. "
            "Default: <manifest-directory>/spatial."
        ),
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute Stage 2 and return a process exit code.

    Exit codes:
        0: Stage 2 completed successfully.
        1: Scientific workflow or filesystem failure.
        2: Invalid command-line arguments or research inputs.
        3: Existing output artifact conflict.
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = run_stage2(
            preparation_manifest_path=args.manifest,
            spatial_dataset_dir=args.dataset_dir,
            start_time=args.start_time,
            end_time=args.end_time,
            epicenter_latitude=args.latitude,
            epicenter_longitude=args.longitude,
            magnitude=args.magnitude,
            reference_days=args.reference_days,
            k=args.k,
            output_dir=args.output_dir,
        )

    except FileExistsError as exc:
        print(
            f"Stage 2 output conflict: {exc}",
            file=sys.stderr,
        )
        return 3

    except (ValueError, TypeError) as exc:
        print(
            f"Stage 2 invalid input: {exc}",
            file=sys.stderr,
        )
        return 2

    except Exception as exc:
        print(
            f"Stage 2 execution failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print()
    print("Stage 2 completed successfully.")
    print()
    print(f"Case ID: {result.plot_result.case_id}")
    print(
        "UTC window: "
        f"{result.workflow_result.window.start_time.isoformat()}"
    )
    print(
        "            "
        f"{result.workflow_result.window.end_time.isoformat()}"
    )
    print()
    print(f"Positive plot: {result.plot_result.positive_plot}")
    print(f"Negative plot: {result.plot_result.negative_plot}")
    print(f"Summary JSON:  {result.summary_path}")
    print()
    print(
        "Verification: visual inspection only "
        "(no automatic decision)."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Explicit live or scripted-fake read-only Agent run. Never runs A/B/C/D."""

import argparse
from pathlib import Path

from src.agent.scientific_evidence_tools import EvidenceTools, MODES, strict_json
from src.agent.scientific_review_agent import FakeModel, OpenAIModel, run_agent, save_run, validate_output_dir


QUESTIONS = dict(
    pre_spatial="Based only on temporal TEC anomalies and historical B+C evidence, which candidate window deserves further spatial verification, and what uncertainties support that recommendation?",
    post_spatial="How do the validated spatial experiments compare, what do differences imply about window selection, and what physical evidence is required before interpreting a possible earthquake relationship?",
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--model", help="Explicit researcher-configured OpenAI model identifier; required with --live")
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--question", help="Optional research question; evidence modes remain enforced")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="Explicit external API call; never used in ordinary tests")
    group.add_argument("--fake-script", type=Path, help="Local JSON array of scripted model call lists; NOT a genuine LLM run")
    args = parser.parse_args(argv)
    if args.live and not args.model:
        parser.error("--live requires an explicit --model")
    if args.output_dir.exists():
        parser.error("Output directory must be fresh")
    evidence = EvidenceTools(args.evidence_root, args.mode)
    validate_output_dir(args.output_dir, evidence)
    if args.live:
        model = OpenAIModel(args.model)
    else:
        if args.fake_script.stat().st_size > 128 * 1024:
            parser.error("Fake script exceeds operational byte limit")
        script = strict_json(args.fake_script.read_bytes())
        if type(script) is not list or len(script) > 10:
            parser.error("Fake script must be an array of at most ten call lists")
        model = FakeModel(script)
    run = run_agent(model, evidence, args.question or QUESTIONS[args.mode])
    print(save_run(args.output_dir, run, evidence))
    print("Status: " + run["status"] + "; live model called: " + str(model.config["live"]))


if __name__ == "__main__":
    main()

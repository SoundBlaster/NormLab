"""Capture every synthetic-v1 case with the two-stage local extraction pipeline."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "fixtures/parking-pilot/synthetic-v1"
SNAPSHOTS = {
    "runner-source.py": Path(__file__),
    "extractor-source.py": ROOT / "evaluation/two_stage.py",
    "anchor-source.py": ROOT / "evaluation/anchor.py",
    "dataset-manifest.json": DATASET / "manifest.json",
    "reviewer-expectations.json": DATASET / "reviewer-expectations.json",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_run_manifest(output: Path, records: list[dict]) -> None:
    (output / "run-manifest.json").write_text(
        json.dumps(
            {
                "schema": "normlab.synthetic-extraction-run/v1",
                "dataset": "synthetic-v1",
                "model": "openai/gpt-oss-20b",
                "provider": "lm-studio-openai-compatible",
                "pipeline": "literal-discovery-then-classification/v1",
                "attemptedCaseIds": [record["caseId"] for record in records],
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def write_manifest(output: Path, records: list[dict]) -> None:
    write_run_manifest(output, records)
    entries = [
        {"path": path.name, "sha256": digest(path.read_bytes())}
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "artifact-manifest.json"
    ]
    (output / "artifact-manifest.json").write_text(
        json.dumps(
            {
                "schema": "normlab.baseline-artifacts/v1",
                "signed": False,
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new output directory; must not exist"
    )
    parser.add_argument(
        "cases", nargs="*", help="optional case IDs; defaults to all 40 cases"
    )
    parser.add_argument(
        "--timeout", type=int, default=420, help="per-case timeout in seconds"
    )
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for destination, source in SNAPSHOTS.items():
        shutil.copyfile(source, output / destination)

    corpus = json.loads((DATASET / "manifest.json").read_text())
    expectations = json.loads((DATASET / "reviewer-expectations.json").read_text())
    corpus_cases = {case["id"]: case for case in corpus["cases"]}
    expectation_cases = {case["id"] for case in expectations["cases"]}
    if set(corpus_cases) != expectation_cases:
        raise ValueError(
            "Corpus manifest and reviewer expectations contain different case IDs"
        )
    selected = args.cases or [case["id"] for case in corpus["cases"]]
    if len(selected) != len(set(selected)) or not set(selected) <= set(corpus_cases):
        raise ValueError("Unknown or duplicate case ID")

    records = []
    extractor = ROOT / "evaluation/two_stage.py"
    try:
        for case_id in selected:
            case = corpus_cases[case_id]
            source_input = DATASET / case["inputFile"]
            input_path = output / f"{case_id}.input.json"
            shutil.copyfile(source_input, input_path)
            parsed_input = json.loads(input_path.read_text())
            narrative_digest = digest(parsed_input["narrative"].encode())
            if (
                narrative_digest != case["sourceDigest"]
                or parsed_input["sourceDigest"] != narrative_digest
            ):
                raise ValueError(f"Source digest mismatch for {case_id}")

            output_path = output / f"{case_id}.output.json"
            started = time.perf_counter()
            status, return_code, error = "completed", None, None
            try:
                result = subprocess.run(
                    [sys.executable, str(extractor), str(input_path), str(output_path)],
                    capture_output=True,
                    text=True,
                    timeout=args.timeout,
                    check=False,
                )
                return_code = result.returncode
                (output / f"{case_id}.stdout.txt").write_text(result.stdout)
                (output / f"{case_id}.stderr.txt").write_text(result.stderr)
                if return_code:
                    status = "provider-or-extractor-error"
                    error = f"extractor exited {return_code}"
            except subprocess.TimeoutExpired as exc:
                status = "timeout"
                error = f"exceeded {args.timeout} seconds"
                for suffix, value in [("stdout", exc.stdout), ("stderr", exc.stderr)]:
                    text = (
                        value.decode(errors="replace")
                        if isinstance(value, bytes)
                        else value or ""
                    )
                    (output / f"{case_id}.{suffix}.txt").write_text(text)
                (output / f"{case_id}.error.json").write_text(
                    json.dumps({"status": status, "error": error}, indent=2) + "\n"
                )
            record = {
                "caseId": case_id,
                "status": status,
                "returnCode": return_code,
                "error": error,
                "elapsedSeconds": round(time.perf_counter() - started, 3),
                "sourceDigest": narrative_digest,
            }
            records.append(record)
            write_run_manifest(output, records)
            print(
                f"{case_id}: {status} ({record['elapsedSeconds']}s)",
                flush=True,
            )
    except KeyboardInterrupt:
        write_manifest(output, records)
        print(
            "Interrupted; completed captures and partial run manifest saved.",
            file=sys.stderr,
        )
        return 130

    write_manifest(output, records)
    counts: dict[str, int] = {}
    for record in records:
        counts[record["status"]] = counts.get(record["status"], 0) + 1
    print(
        json.dumps({"output": str(output), "cases": len(records), "statuses": counts})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Capture the same four synthetic narratives through the LangExtract adapter."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else root / "experiments/parking-baseline/2026-10-05-langextract-gpt-oss-20b"
).resolve()
output.parent.mkdir(parents=True, exist_ok=True)
output.mkdir()  # Never overwrite previous evidence.
for source_file, snapshot_name in [
    (root / "evaluation/extract.py", "extractor-source.py"),
    (Path(__file__), "runner-source.py"),
]:
    (output / snapshot_name).write_bytes(source_file.read_bytes())
for case in ["P01", "P02", "P04", "P09"]:
    source = (root / f"fixtures/parking-pilot/reference/{case}.source.txt").read_text()
    request = {
        "narrative": source,
        "sourceDigest": hashlib.sha256(source.encode()).hexdigest(),
    }
    path = output / f"{case}.input.json"
    path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n")
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(root / "evaluation/extract.py"),
                str(path),
                str(output / f"{case}.output.json"),
            ],
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        (output / f"{case}.stdout.txt").write_text(result.stdout)
        (output / f"{case}.stderr.txt").write_text(result.stderr)
        print(case, "capture exit", result.returncode, flush=True)
        if result.returncode:
            break
    except subprocess.TimeoutExpired as exc:
        (output / f"{case}.error.json").write_text(
            json.dumps({"error": "timeout", "timeoutSeconds": exc.timeout}) + "\n"
        )
        print(case, "timeout; remaining cases unattempted", flush=True)
        break
entries = [
    {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for path in sorted(output.iterdir())
    if path.is_file()
]
(output / "artifact-manifest.json").write_text(
    json.dumps(
        {
            "schema": "normlab.baseline-artifacts/v1",
            "signed": False,
            "entries": entries,
            "extractorSha256": hashlib.sha256(
                (root / "evaluation/extract.py").read_bytes()
            ).hexdigest(),
            "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        indent=2,
    )
    + "\n"
)

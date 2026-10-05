"""Re-anchor captured extractions without model calls or modification of raw evidence."""

import hashlib
import json
import sys
from pathlib import Path

from anchor import anchor

source_dir, output = map(lambda p: Path(p).resolve(), sys.argv[1:3])
output.parent.mkdir(parents=True, exist_ok=True)
output.mkdir()
for case in ["P01", "P02", "P04", "P09"]:
    source_path = source_dir / f"{case}.output.json"
    raw = source_path.read_bytes()
    result = json.loads(raw)
    source = json.loads((source_dir / f"{case}.input.json").read_text())["narrative"]
    if hashlib.sha256(source.encode()).hexdigest() != result["sourceDigest"]:
        raise ValueError("Source drift")
    (output / f"{case}.original-output.json").write_bytes(raw)
    result["statements"], result["quarantine"], result["alignmentDecisions"] = anchor(
        result["rawExtractions"], source
    )
    result["derivation"] = {
        "mode": "offline-exact-reanchoring-no-inference",
        "parentRawDigest": hashlib.sha256(raw).hexdigest(),
        "parentDirectory": source_dir.name,
    }
    (output / f"{case}.output.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
for name in ["anchor.py", "reanchor_langextract.py"]:
    (output / name).write_bytes((Path(__file__).parent / name).read_bytes())
entries = [
    {"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in sorted(output.iterdir())
    if p.is_file()
]
(output / "artifact-manifest.json").write_text(
    json.dumps(
        {
            "schema": "normlab.baseline-artifacts/v1",
            "signed": False,
            "entries": entries,
        },
        indent=2,
    )
    + "\n"
)

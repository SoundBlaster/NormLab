"""V3 Stage 1 audit binds the frozen fixture catalog to the pinned runtime."""

import argparse
import json
from pathlib import Path

from audit_stage1_v2 import audit as audit_v2
from harness import artifact, digest, load_json, require

ROOT = Path(__file__).resolve().parents[1]


def audit(path):
    path = path.resolve()
    report = audit_v2(path)
    manifest, _ = load_json(path)
    definitions = artifact(path.parent, manifest["artifacts"]["definitions"])
    runtime_path = ROOT / "server/inference-prompts.json"
    runtime_raw = runtime_path.read_bytes()
    runtime = json.loads(runtime_raw)
    require(
        definitions == runtime["definitions"],
        "Frozen fixture catalog differs from pinned runtime definitions",
    )
    report.update(
        schema="normlab.stage1-audit-report/v3",
        runtimeCatalogSha256=digest(runtime_raw),
        auditorCodePins={
            name: digest((ROOT / name).read_bytes())
            for name in (
                "evaluation/audit_stage1.py",
                "evaluation/audit_stage1_v2.py",
                "evaluation/audit_stage1_v3.py",
            )
        },
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.manifest)
    if args.output:
        require(not args.output.exists(), "New report path required")
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()

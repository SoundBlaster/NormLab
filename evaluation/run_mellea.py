"""Run matched classification arms on one frozen discovery capture.

Offline by default. --live-local contacts LM Studio, and --live-jev additionally
permits billable TypeSafe verification. Does not touch hosted configuration.
"""

import argparse
import asyncio
import importlib.metadata
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

from mellea_candidate_v2 import (
    ARMS,
    DEFINITIONS,
    SEMANTIC_REQUIREMENT,
    bound_fragments,
    fixture_backend,
    run_candidate,
    sha,
)


def secret_file(path):
    if not path or not path.is_absolute():
        raise ValueError("Verifier key requires an absolute private file")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 8192:
        raise ValueError("Verifier key requires a private bounded file")
    key = path.read_text().rstrip("\n")
    if not key.isascii() or len(key) < 32 or any(c.isspace() for c in key):
        raise ValueError("Invalid verifier key file")
    return key


async def main(args):
    from mellea import MelleaSession

    request = json.loads(args.input.read_text())
    parent = json.loads(args.parent.read_text())
    bound_fragments(request, parent)
    versions = {"mellea": importlib.metadata.version("mellea")}
    fixture = json.loads(args.fixture.read_text()) if args.fixture else None
    if args.live_jev and not args.live_local:
        raise ValueError("Live verification requires explicit live generator selection")
    if not args.live_local and fixture is None:
        raise ValueError(
            "Offline mode requires --fixture with fixed candidates/verdicts"
        )
    if args.live_local and fixture is not None:
        raise ValueError("Live and fixture modes cannot be combined")
    if args.live_local and "jev" in args.arms and not args.live_jev:
        raise ValueError(
            "Jev arm needs --live-jev; use --arms baseline deterministic otherwise"
        )
    if not 0 < args.timeout <= 300:
        raise ValueError("Deadline contract")
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    (args.output / "input.json").write_bytes(args.input.read_bytes())
    (args.output / "discovery-parent.json").write_bytes(args.parent.read_bytes())
    for name in (
        "run_mellea.py",
        "mellea_candidate_v2.py",
        "classification_v3.py",
        "anchor.py",
    ):
        (args.output / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    records = []
    for arm in args.arms:
        provider = None
        if args.live_local:
            from mellea.backends.openai import OpenAIBackend

            backend = OpenAIBackend(
                model_id=args.model,
                base_url="http://127.0.0.1:1234/v1",
                api_key="local-only",
                max_retries=0,
                timeout=120,
                model_options={"temperature": 0, "seed": 42, "max_tokens": 8192},
            )
        else:
            backend = fixture_backend(fixture["candidates"])
        session = MelleaSession(backend=backend)
        verifier = None
        if arm == "jev":
            if args.live_jev:
                from mellea_jev import JevVerifier, TypeSafeProvider

                versions["mellea-jev-adapter"] = importlib.metadata.version(
                    "mellea-jev-adapter"
                )
                provider = TypeSafeProvider(
                    secret_file(args.jev_key_file), model=args.jev_model, timeout=10
                )
                verifier = JevVerifier(
                    provider,
                    SEMANTIC_REQUIREMENT,
                    reference=json.dumps(
                        {"fragments": parent["fragments"], "definitions": DEFINITIONS},
                        ensure_ascii=False,
                    ),
                    accept_at=0.90,
                    reject_at=0.10,
                )
            else:

                class FixtureVerifier:
                    def __init__(self):
                        self.index = 0

                    def evaluate(self, _text):
                        verdict = fixture["semanticVerdicts"][self.index]
                        self.index += 1
                        return SimpleNamespace(**verdict)

                verifier = FixtureVerifier()
        try:
            result = await run_candidate(
                session, request, parent, arm, verifier, args.timeout
            )
            result["dependencies"] = versions.copy()
            result["generator"] = {
                "mode": "live-local" if args.live_local else "fixture",
                "model": args.model if args.live_local else "dummy",
            }
            result["generationSettings"] = (
                {"temperature": 0, "seed": 42, "maxTokens": 8192}
                if args.live_local
                else None
            )
            result["semanticMode"] = (
                "live-jev"
                if args.live_jev and arm == "jev"
                else "fixture"
                if arm == "jev"
                else None
            )
            (args.output / f"{arm}.output.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            )
            records.append(
                {"arm": arm, "accepted": result["accepted"], "error": result["error"]}
            )
        finally:
            if provider:
                provider.close()
            if hasattr(backend, "aclose"):
                await backend.aclose()
    entries = [
        {"path": p.name, "sha256": sha(p.read_bytes())}
        for p in sorted(args.output.iterdir())
        if p.is_file()
    ]
    manifest = {
        "schema": "normlab.mellea-comparison/v2",
        "evidence": "live" if args.live_local else "offline-control-flow-only",
        "records": records,
        "entries": entries,
        "signed": False,
    }
    (args.output / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "evidence": manifest["evidence"],
                "records": records,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("parent", type=Path)
    parser.add_argument("output", type=Path, help="New artifact directory")
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--live-local", action="store_true")
    parser.add_argument("--live-jev", action="store_true")
    parser.add_argument("--jev-key-file", type=Path)
    parser.add_argument("--jev-model", default="jev-1.13.0")
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    parser.add_argument("--timeout", type=float, default=300)
    options = parser.parse_args()
    if len(set(options.arms)) != len(options.arms):
        parser.error("Duplicate arms")
    os.umask(0o077)
    asyncio.run(main(options))

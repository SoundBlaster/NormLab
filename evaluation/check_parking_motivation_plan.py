"""Validate exported motivation Choice tasks with the existing SDK-free consumer."""

import argparse
import json
from pathlib import Path

from categorical_runtime import validate_policy
from provider_config import require
from responses_runtime import validate_task


def check(directory):
    def read(path):
        return json.loads((directory / path).read_text(encoding="utf-8"))

    plan = read("plan.json")
    require(
        plan["schema"] == "normlab.parking-motivation-plan/v1"
        and plan["inferencePerformed"] is False,
        "Offline motivation plan required",
    )
    tasks = plan["verifier"]["tasks"]
    require(
        [t["id"] for t in tasks] == [f"M{i:02}" for i in range(1, 25)],
        "Frozen 24-case order required",
    )
    policy = read("verifier/policy.json")
    require(policy == plan["verifier"]["policy"], "Exported policy differs from plan")
    for entry in tasks:
        task = validate_task(read(f"verifier/{entry['id']}.json"))
        require(task == entry["task"], "Exported task differs from plan")
        validate_policy(task, policy)
    return {"status": "passed", "choiceTasks": len(tasks), "calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.directory)))

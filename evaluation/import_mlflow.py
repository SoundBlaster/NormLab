"""Import deterministic, offline NormLab reports into a local MLflow registry."""

import json
import os
import sys
from pathlib import Path

os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
import mlflow  # noqa: E402
from mlflow.genai.scorers import scorer  # noqa: E402


@scorer
def structure_gate(outputs):
    return outputs["gate"] is True


@scorer
def required_statements(outputs):
    return not outputs["missing"]


@scorer
def forbidden_inferences(outputs):
    return not outputs["unsupported"]


@scorer
def conflict_preserved(outputs):
    return outputs["conflictPass"]


def main():
    report_path = Path(sys.argv[1]).resolve()
    report = json.loads(report_path.read_text())
    if report["schema"] != "normlab.parking-evaluation-report/v1":
        raise ValueError("Unsupported evaluation report")
    root = Path(__file__).resolve().parents[1]
    storage = root / ".data" / "mlflow"
    storage.mkdir(parents=True, exist_ok=True)
    # All registry writes remain local; there is no implicit remote tracking endpoint.
    mlflow.set_tracking_uri("sqlite:///" + str(storage / "tracking.sqlite"))
    name = "NormLab parking extraction"
    experiment = mlflow.get_experiment_by_name(name)
    experiment_id = (
        experiment.experiment_id
        if experiment
        else mlflow.create_experiment(
            name, artifact_location=(storage / "artifacts").as_uri()
        )
    )
    for run in report["runs"]:
        with mlflow.start_run(experiment_id=experiment_id, run_name=run["name"]):
            mlflow.set_tags(
                {
                    "normlab.expectations_status": report["expectationsStatus"],
                    "normlab.review_stage": "before-human-correction",
                    "normlab.release_approved": "false",
                }
            )
            mlflow.log_params(
                {
                    "expectations_digest": report["expectationsDigest"],
                    "scorer_digest": report["scorerDigest"],
                    "source_artifact_manifest_digest": run["artifactManifestDigest"],
                }
            )
            mlflow.log_metrics(run["metrics"])
            mlflow.log_dict(run, "evaluation/run.json")
            mlflow.log_artifact(str(report_path), artifact_path="evaluation")
            mlflow.genai.evaluate(
                data=[
                    {
                        "inputs": {
                            "caseId": case["caseId"],
                            "sourceDigest": case["sourceDigest"],
                            "scope": case["scope"],
                            "origin": "offline-artifact-replay",
                        },
                        "outputs": case,
                    }
                    for case in run["cases"]
                ],
                scorers=[
                    structure_gate,
                    required_statements,
                    forbidden_inferences,
                    conflict_preserved,
                ],
            )
            print(run["name"], mlflow.active_run().info.run_id)


if __name__ == "__main__":
    main()

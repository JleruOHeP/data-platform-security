import json

from security_experts import build_bn_from_config, infer


def load_incident_model(file_path="incident_model.json"):
    with open(file_path, "r") as f:
        return json.load(f)


def build_incident_bn(incident_json, expert_risk_probabilities=None):
    return build_bn_from_config(incident_json, prior_overrides=expert_risk_probabilities)


def run_incident_layer(expert_results, incident_config):
    expert_priors = {}
    for result in expert_results:
        for node, probability in result.get("risk_priors", {}).items():
            expert_priors[node] = probability

    incident_model = build_incident_bn(incident_config, expert_priors)
    incident_targets = incident_config.get("targets", [])

    incident_results = []
    for target in incident_targets:
        p = infer(incident_model, target, {})
        incident_results.append({
            "incident": target,
            "probability": p,
        })

    return incident_results


INCIDENT_MODEL = load_incident_model()

import json

from security_experts import build_bn_from_config, infer


def load_incident_model(file_path="incident_model.json"):
    with open(file_path, "r") as f:
        return json.load(f)


def build_incident_bn(incident_json, expert_risk_probabilities=None):
    return build_bn_from_config(incident_json, prior_overrides=expert_risk_probabilities)


def get_incident_priors(expert_results):
    expert_priors = {}
    for result in expert_results:
        for node, probability in result.get("risk_priors", {}).items():
            expert_priors[node] = probability
    return expert_priors


def run_incident_layer(expert_results, incident_config):
    incident_model = build_incident_bn(incident_config, get_incident_priors(expert_results))
    incident_targets = incident_config.get("targets", [])

    incident_results = []
    for target in incident_targets:
        p = infer(incident_model, target, {})
        incident_results.append({
            "incident": target,
            "probability": p,
        })

    return incident_results


def find_top_incident_risk(expert_results, incident_config, incident_target):
    priors = get_incident_priors(expert_results)
    incident_cpds = incident_config.get("cpds", {})
    if incident_target not in incident_cpds:
        return None

    target_cfg = incident_cpds[incident_target]
    if target_cfg.get("type") != "cpt":
        return None

    evidences = target_cfg.get("evidence", [])
    if not evidences:
        return None

    base_model = build_incident_bn(incident_config, priors)
    base_prob = infer(base_model, incident_target, {})
    best = None
    best_delta = -1.0

    for risk_node in evidences:
        modified_priors = dict(priors)
        modified_priors[risk_node] = 0.0
        modified_model = build_incident_bn(incident_config, modified_priors)
        modified_prob = infer(modified_model, incident_target, {})
        delta = base_prob - modified_prob
        if delta > best_delta:
            best_delta = delta
            best = (risk_node, base_prob, modified_prob)

    return best


INCIDENT_MODEL = load_incident_model()

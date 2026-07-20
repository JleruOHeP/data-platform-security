import json

from security_experts import build_bn_from_config, infer


def load_business_model(file_path="business_outcomes.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_business_bn(business_json, incident_priors=None):
    return build_bn_from_config(business_json, prior_overrides=incident_priors)


def _normalize_incident_priors(incident_inputs):
    if isinstance(incident_inputs, dict):
        return {
            str(node): float(probability)
            for node, probability in incident_inputs.items()
            if node is not None
        }

    if isinstance(incident_inputs, list):
        priors = {}
        for item in incident_inputs:
            if isinstance(item, dict):
                incident_name = item.get("incident")
                probability = item.get("probability")
                if incident_name is not None and probability is not None:
                    priors[str(incident_name)] = float(probability)
        return priors

    return {}


def run_business_layer(incident_inputs, business_config):
    incident_priors = _normalize_incident_priors(incident_inputs)
    business_model = build_business_bn(business_config, incident_priors)
    business_targets = business_config.get("targets", [])

    business_results = []
    for target in business_targets:
        p = infer(business_model, target, {})
        business_results.append({
            "business_outcome": target,
            "probability": p,
        })

    return business_results


BUSINESS_MODEL = load_business_model()

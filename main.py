import json
import sys
from pathlib import Path

from evidence import normalize_evidence
from security_architect import INCIDENT_MODEL, run_incident_layer, find_top_incident_risk
from security_experts import EXPERTS, infer, analyze_evidence_contribution, find_expert_by_risk_node, find_top_control_for_risk


def run_mixture(evidence, weight_overrides=None):
    results = []

    for name, cfg in EXPERTS.items():
        model = cfg["model"]
        targets = cfg.get("targets", [])
        weight = cfg["weight"]
        if weight_overrides is not None:
            weight = weight_overrides.get(name, weight)
        risk_nodes = cfg.get("risk_nodes", [])
        target_results = []
        for t in targets:
            p = infer(model, t, evidence)
            target_results.append({"target": t, "probability": p})

        risk_priors = {node: infer(model, node, evidence) for node in risk_nodes}

        results.append({
            "expert": name,
            "targets": target_results,
            "weight": weight,
            "risk_priors": risk_priors,
        })

    total_weight = sum(r["weight"] for r in results)
    if total_weight == 0:
        raise ValueError("All expert weights are zero.")

    # compute a weighted aggregate final risk using each expert's max target probability
    final_risk_probability = sum(max((t["probability"] for t in r["targets"]), default=0.0) * r["weight"] for r in results) / total_weight
    incident_results = run_incident_layer(results, INCIDENT_MODEL)

    return {
        "per_expert": results,
        "final_risk_probability": final_risk_probability,
        "incident_results": incident_results,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path-to-json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    
    scenario = {}
    with open(input_path, 'r', encoding='utf-8') as f:
        scenario = json.load(f)

    evidence = normalize_evidence(scenario.get("evidence", {}))
    output = run_mixture(evidence, scenario.get("weight_overrides", {}))

    print("\n=== Expert Results ===")
    for r in output["per_expert"]:
        print(f"\nExpert: {r['expert']}")
        # compact: list all targets and probabilities on one line
        target_strs = [f"{t['target']}={t['probability']:.4f}" for t in r.get('targets', [])]
        print(f"  risks: {', '.join(target_strs) if target_strs else 'none'}")
        print(f"  weight: {r['weight']}")

    print("\n=== Final Risk ===")
    print(f"{output['final_risk_probability']:.4f}")

    print("\n=== Incident Level Results ===")
    for incident in output["incident_results"]:
        print(f"  {incident['incident']}: {incident['probability']:.4f}")

    result_path = Path(__file__).resolve().parent / "result.json"
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    top_incident = max(output["incident_results"], key=lambda i: i["probability"])
    top_choice = find_top_incident_risk(output["per_expert"], INCIDENT_MODEL, top_incident["incident"])

    if top_choice:
        risk_node, base_prob, modified_prob = top_choice
        expert_name, expert_cfg = find_expert_by_risk_node(risk_node)
        if expert_cfg:
            suggestion = find_top_control_for_risk(expert_cfg["model"], risk_node, evidence)
            if suggestion:
                control_name = suggestion[0]
                # re-run full inference with the suggested control implemented (set to 1)
                evidence_with_control = dict(evidence)
                evidence_with_control[control_name] = 1
                new_output = run_mixture(evidence_with_control)
                new_prob = None
                for inc in new_output.get("incident_results", []):
                    if inc.get("incident") == top_incident["incident"]:
                        new_prob = inc.get("probability")
                        break
                if new_prob is not None:
                    print(f"\nWith control {control_name} implemented, {top_incident['incident']} probability goes down to {new_prob:.4f}")
                else:
                    print(f"\nWith control {control_name} implemented, incident probability could not be determined.")
            else:
                print(f"\nNo specific control found, but {risk_node} is a key contributor to {top_incident['incident']} incident. Consider improving this area.")

    print(f"\nSaved results to {result_path}")


if __name__ == "__main__":
    main()

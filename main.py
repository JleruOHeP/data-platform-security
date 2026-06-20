import json
import sys
from pathlib import Path

from evidence import normalize_evidence
from security_architect import INCIDENT_MODEL, run_incident_layer
from security_experts import EXPERTS, infer, analyze_evidence_contribution


def run_mixture(evidence):
    results = []

    for name, cfg in EXPERTS.items():
        model = cfg["model"]
        target = cfg["target"]
        weight = cfg["weight"]
        risk_nodes = cfg.get("risk_nodes", [])

        p = infer(model, target, evidence)
        contributions = analyze_evidence_contribution(model, target, evidence)
        top_contributor = contributions[0] if contributions else None

        risk_priors = {
            node: infer(model, node, evidence)
            for node in risk_nodes
        }

        results.append({
            "expert": name,
            "target": target,
            "probability": p,
            "weight": weight,
            "risk_priors": risk_priors,
            "top_evidence": {
                "variable": top_contributor[0],
                "contribution": top_contributor[1],
            } if top_contributor else None,
            "evidence_analysis": [
                {"variable": var, "contribution": contrib}
                for var, contrib, _, _ in contributions
            ] if contributions else [],
        })

    total_weight = sum(r["weight"] for r in results)
    if total_weight == 0:
        raise ValueError("All expert weights are zero.")

    final_risk_probability = sum(r["probability"] * r["weight"] for r in results) / total_weight
    incident_results = run_incident_layer(results, INCIDENT_MODEL)

    max_contributor = max(results, key=lambda r: r["probability"] * r["weight"])

    return {
        "per_expert": results,
        "final_risk_probability": final_risk_probability,
        "top_contributor_expert": {
            "expert": max_contributor["expert"],
            "contribution": max_contributor["probability"] * max_contributor["weight"],
        },
        "incident_results": incident_results,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path-to-json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    
    user_evidence = {}
    with open(input_path, 'r', encoding='utf-8') as f:
        user_evidence = json.load(f)

    evidence = normalize_evidence(user_evidence)
    output = run_mixture(evidence)

    print("\n=== Expert Results ===")
    for r in output["per_expert"]:
        print(f"\nExpert: {r['expert']}")
        print(f"  Probability: {r['probability']:.4f}")
        print(f"  Weight: {r['weight']}")
        if r["top_evidence"]:
            print(f"  Top evidence contributor: {r['top_evidence']['variable']} (Δ={r['top_evidence']['contribution']:.4f})")
        if r["evidence_analysis"]:
            print("  All evidence impact:")
            for ea in r["evidence_analysis"]:
                print(f"    - {ea['variable']}: {ea['contribution']:.4f}")

    print("\n=== Final Risk ===")
    print(output["final_risk_probability"])

    print("\n=== Top Contributor Expert ===")
    print(output["top_contributor_expert"])

    print("\n=== Incident Level Results ===")
    for incident in output["incident_results"]:
        print(f"  {incident['incident']}: {incident['probability']:.4f}")

    result_path = Path(__file__).resolve().parent / "result.json"
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved results to {result_path}")


if __name__ == "__main__":
    main()

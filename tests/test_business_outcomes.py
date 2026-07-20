import unittest

from business_outcomes import run_business_layer


BUSINESS_MODEL = {
    "targets": ["REVENUE_IMPACT", "REGULATORY_IMPACT", "CUSTOMER_IMPACT"],
    "cpds": {
        "REVENUE_IMPACT": {"type": "cpt", "evidence": ["UNAUTHORIZED_ACCESS"], "values": [[0.9, 0.2], [0.1, 0.8]]},
        "REGULATORY_IMPACT": {"type": "cpt", "evidence": ["DATA_EXFILTRATION"], "values": [[0.95, 0.3], [0.05, 0.7]]},
        "CUSTOMER_IMPACT": {"type": "cpt", "evidence": ["SERVICE_DISRUPTION"], "values": [[0.9, 0.4], [0.1, 0.6]]},
    },
}


class BusinessOutcomesTests(unittest.TestCase):
    def test_business_layer_returns_probabilities_for_each_outcome(self):
        incident_priors = {
            "UNAUTHORIZED_ACCESS": 0.2,
            "DATA_EXFILTRATION": 0.1,
            "SERVICE_DISRUPTION": 0.3,
            "SUPPLY_CHAIN_COMPROMISE": 0.4,
        }

        results = run_business_layer(incident_priors, BUSINESS_MODEL)

        self.assertEqual([item["business_outcome"] for item in results], [
            "REVENUE_IMPACT",
            "REGULATORY_IMPACT",
            "CUSTOMER_IMPACT",
        ])

        for item in results:
            self.assertGreaterEqual(item["probability"], 0.0)
            self.assertLessEqual(item["probability"], 1.0)


if __name__ == "__main__":
    unittest.main()

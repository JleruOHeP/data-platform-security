import json
import unittest

from neo4j_store import Neo4jModelStore


class Result:
    def __init__(self, records): self.records = records
    def __iter__(self): return iter(self.records)
    def single(self): return self.records[0] if self.records else None


class Session:
    def __init__(self, records): self.records = records
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def run(self, _query, **params): return Result(self.records[params.get("layer", "default")])


class Driver:
    def __init__(self, records): self.records = records
    def session(self, **_): return Session(self.records)


def make_store(records):
    store = object.__new__(Neo4jModelStore)
    store.database = "neo4j"
    store.driver = Driver(records)
    return store


class Neo4jModelStoreTests(unittest.TestCase):
    def test_load_model_reconstructs_ordered_evidence_and_cpt(self):
        values = [[0.9, 0.2], [0.1, 0.8]]
        store = make_store({"incident": [{"nodes": [{
            "name": "INCIDENT", "node_type": "cpt",
            "values_json": json.dumps(values), "evidence": ["RISK"],
        }]}]})
        model = store.load_model("incident")
        self.assertEqual(model["targets"], ["INCIDENT"])
        self.assertEqual(model["cpds"]["INCIDENT"]["evidence"], ["RISK"])
        self.assertEqual(model["cpds"]["INCIDENT"]["values"], values)

    def test_load_control_registry_reads_alias_properties(self):
        store = make_store({"default": [{"name": "MFA", "aliases": ["2fa"]}]})
        self.assertEqual(store.load_control_registry(), {"MFA": {"aliases": ["2fa"]}})


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from seed_neo4j import EXPERTS, all_controls, write_controls_file


class SeedNeo4jTests(unittest.TestCase):
    def test_control_inventory_contains_every_expert_control(self):
        exported = {item["name"] for item in all_controls()}
        modeled = {
            control
            for expert in EXPERTS.values()
            for control in expert["controls"]
        }
        self.assertTrue(modeled.issubset(exported))
        self.assertEqual(len(exported), len(all_controls()))

    def test_controls_file_has_stable_interview_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path, count = write_controls_file(Path(directory) / "controls.json")
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(count, len(payload["controls"]))
        self.assertEqual(
            sorted(payload["controls"], key=lambda item: item["name"]),
            payload["controls"],
        )
        self.assertTrue(all(set(item) == {"name", "aliases"} for item in payload["controls"]))


if __name__ == "__main__":
    unittest.main()

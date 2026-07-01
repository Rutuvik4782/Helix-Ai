import unittest

from fastapi.testclient import TestClient

from main import app


LEGACY_SAMPLE = """try:
    risky()
except ValueError, exc:
    print exc
"""

TRUNCATED_LEGACY_SAMPLE = """def broken(values):
    print "start"
    for item in xrange(3):
"""


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_analyze_endpoint_returns_plan_and_ml_status(self):
        response = self.client.post("/analyze", json={"code": LEGACY_SAMPLE})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("analysis", payload)
        self.assertIn("plan", payload)
        self.assertIn("ml_reasoner", payload)
        self.assertTrue(payload["analysis"]["success"])
        self.assertEqual(payload["analysis"]["probable_source_version"], "Python 2.x / early legacy Python")

    def test_refactor_endpoint_returns_diff_and_validation(self):
        response = self.client.post("/refactor", json={"code": LEGACY_SAMPLE})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("new_code", payload)
        self.assertIn("diff", payload)
        self.assertIn("validation", payload)
        self.assertIn("except ValueError as exc", payload["new_code"])
        self.assertIn("print(exc)", payload["new_code"])
        self.assertTrue(payload["validation"]["success"])

    def test_refactor_rejects_incomplete_input_without_downloadable_output(self):
        response = self.client.post("/refactor", json={"code": TRUNCATED_LEGACY_SAMPLE})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertFalse(payload["validation"]["success"])
        self.assertEqual(payload["validation"]["stage"], "INPUT")
        self.assertFalse(payload["output_available"])
        self.assertEqual(payload["new_code"], "")
        self.assertEqual(payload["candidate_code"], "")
        self.assertIn("incomplete", payload["validation"]["error"])

    def test_health_and_model_status_endpoints(self):
        health = self.client.get("/health")
        model_status = self.client.get("/model-status")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(model_status.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertIn("available", model_status.json())

    def test_page_routes_render(self):
        landing = self.client.get("/")
        app_page = self.client.get("/app")

        self.assertEqual(landing.status_code, 200)
        self.assertEqual(app_page.status_code, 200)
        self.assertIn("text/html", landing.headers["content-type"])
        self.assertIn("text/html", app_page.headers["content-type"])

    def test_runs_endpoints_return_stored_history(self):
        refactor = self.client.post("/refactor", json={"code": LEGACY_SAMPLE})
        self.assertEqual(refactor.status_code, 200)
        run_id = refactor.json()["run_id"]

        runs = self.client.get("/runs?limit=5")
        single = self.client.get(f"/runs/{run_id}")

        self.assertEqual(runs.status_code, 200)
        self.assertEqual(single.status_code, 200)
        self.assertTrue(any(item["run_id"] == run_id for item in runs.json()["runs"]))
        self.assertEqual(single.json()["run_id"], run_id)


if __name__ == "__main__":
    unittest.main()

import os
import unittest

from streamlit.testing.v1 import AppTest


class DashboardSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ZTII_API_URL"] = "http://127.0.0.1:9"

    def test_all_primary_views_render_in_demo_mode(self):
        app = AppTest.from_file("dashboard/app.py")
        app.run(timeout=45)
        self.assertEqual(len(app.exception), 0)

        for page in ["Fleet Intelligence", "Alerts", "Provisioning", "Edge & PLC"]:
            app.radio[0].set_value(page).run(timeout=45)
            self.assertEqual(len(app.exception), 0, f"{page} failed to render")


if __name__ == "__main__":
    unittest.main()

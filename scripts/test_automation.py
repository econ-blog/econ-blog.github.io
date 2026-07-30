import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestScriptWireup(unittest.TestCase):
    def test_fetch_ga4_credentials_wireup(self):
        import fetch_ga4
        with patch.dict(os.environ, {"GA4_CREDENTIALS": "/tmp/custom_ga4.json"}):
            self.assertEqual(fetch_ga4.get_credentials_path(), "/tmp/custom_ga4.json")

    def test_fetch_gsc_credentials_and_site_url_wireup(self):
        import fetch_gsc
        with patch.dict(os.environ, {"GSC_CREDENTIALS": "/tmp/custom_gsc.json", "GSC_SITE_URL": "sc-domain:example.com"}):
            self.assertEqual(fetch_gsc.get_credentials_path(), "/tmp/custom_gsc.json")
            self.assertEqual(fetch_gsc.get_site_url(), "sc-domain:example.com")

if __name__ == "__main__":
    unittest.main()

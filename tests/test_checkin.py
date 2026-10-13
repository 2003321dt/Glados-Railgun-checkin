"""Pure unit tests; never contact the check-in service or use real Secrets."""
import logging
import os
import unittest
from unittest.mock import patch

import checkin


class ConfigTests(unittest.TestCase):
    def _config(self, **values):
        keys = ["GLADOS_COOKIES", "GLADOS_CLOUD_COOKIES",
                "RAILGUN_INFO_COOKIES", "GLADOS_VERBOSE"]
        with patch.dict(os.environ, {k: "" for k in keys} | values):
            return checkin.Config()

    def test_domain_specific_cookies_are_isolated(self):
        cfg = self._config(GLADOS_CLOUD_COOKIES="cloud-1&cloud-2",
                           RAILGUN_INFO_COOKIES="rail-1")
        self.assertEqual(cfg.cookies_by_domain["glados.cloud"], ["cloud-1", "cloud-2"])
        self.assertEqual(cfg.cookies_by_domain["railgun.info"], ["rail-1"])

    def test_partial_domain_config_does_not_fallback_to_legacy(self):
        cfg = self._config(GLADOS_COOKIES="legacy",
                           GLADOS_CLOUD_COOKIES="cloud-only")
        self.assertEqual(cfg.cookies_by_domain, {"glados.cloud": ["cloud-only"]})

    def test_legacy_remains_supported(self):
        cfg = self._config(GLADOS_COOKIES="old-1&old-2")
        self.assertEqual(cfg.cookies_by_domain["glados.cloud"], ["old-1", "old-2"])
        self.assertEqual(cfg.cookies_by_domain["railgun.info"], ["old-1", "old-2"])

    def test_no_cookies_returns_failure_exit_code(self):
        with patch.dict(os.environ, {
            "GLADOS_COOKIES": "", "GLADOS_CLOUD_COOKIES": "",
            "RAILGUN_INFO_COOKIES": "", "PUSHDEER_SENDKEY": ""
        }):
            self.assertEqual(checkin.main(), 1)

    def test_failed_checkin_returns_failure_exit_code(self):
        fake = checkin.CheckinResult(1, "glados.cloud",
                                      code=checkin.CheckinStatus.FAILURE)
        with patch.object(checkin.Checker, "checkin_all", autospec=True) as run, \
             patch.object(checkin.Checker, "format_results",
                          return_value=("failed", "failed", "failed")), \
             patch.object(checkin.Checker, "results", [fake], create=True):
            def set_result(self):
                self.results = [fake]
            run.side_effect = set_result
            with patch.dict(os.environ, {
                "GLADOS_COOKIES": "", "GLADOS_CLOUD_COOKIES": "fake",
                "RAILGUN_INFO_COOKIES": "", "PUSHDEER_SENDKEY": ""
            }):
                self.assertEqual(checkin.main(), 1)

    def test_repeat_is_success_exit_code(self):
        fake = checkin.CheckinResult(1, "glados.cloud",
                                      code=checkin.CheckinStatus.REPEAT)
        with patch.object(checkin.Checker, "checkin_all",
                          lambda self: self.results.append(fake)), \
             patch.object(checkin.Checker, "format_results",
                          return_value=("repeat", "repeat", "repeat")):
            with patch.dict(os.environ, {
                "GLADOS_COOKIES": "", "GLADOS_CLOUD_COOKIES": "fake",
                "RAILGUN_INFO_COOKIES": "", "PUSHDEER_SENDKEY": ""
            }):
                self.assertEqual(checkin.main(), 0)

    def test_denied_auth_is_safely_logged(self):
        api = checkin.API("glados.cloud", 1)
        with self.assertLogs(level="ERROR") as logs:
            result = api._parse_checkin({
                "code": -2, "message": "No permission secret-cookie-value"
            })
        api.close()
        self.assertEqual(result["code"], checkin.CheckinStatus.FAILURE)
        combined = "\\n".join(logs.output)
        self.assertIn("GLADOS_CLOUD_COOKIES", combined)
        self.assertNotIn("secret-cookie-value", combined)


if __name__ == "__main__":
    unittest.main()

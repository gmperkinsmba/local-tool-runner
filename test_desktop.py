"""Desktop boundary and packaging metadata checks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from build_desktop import APP_NAME, BUNDLE_ID, write_notices
from desktop_policy import navigation_policy


class DesktopTests(unittest.TestCase):
    def test_product_identity(self):
        self.assertEqual(APP_NAME, "Local Console")
        self.assertEqual(BUNDLE_ID, "io.github.gmperkinsmba.local-console")

    def test_notices_contain_verified_text_and_exclude_binary_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "notices.txt"
            write_notices(destination)
            notices = destination.read_text(encoding="utf-8")
        self.assertNotIn("\x00", notices)
        self.assertNotIn("copying.cpython-312-darwin.so.dSYM", notices)
        self.assertIn("Local Console desktop dependencies", notices)
        self.assertIn("Python runtime 3.12.14", notices)

    def test_server_bind_skips_reverse_dns_lookup(self):
        with patch("socket.getfqdn", side_effect=AssertionError("Reverse DNS must not block startup")):
            httpd = server.make_server(port=0)
        try:
            self.assertEqual(httpd.server_name, "127.0.0.1")
            self.assertGreater(httpd.server_port, 0)
        finally:
            httpd.server_close()

    def test_navigation_boundary(self):
        origin = "http://127.0.0.1:49125/"
        for url in [origin, origin + "app.js"]:
            self.assertEqual(navigation_policy(url, origin, False, False), "allow")
        self.assertEqual(navigation_policy("blob:" + origin + "export", origin, False, True), "download")
        for url in ["file:///etc/passwd", "javascript:alert(1)", "data:text/html,hello", "http://127.0.0.1:49126/", "http://127.0.0.1.evil.test:49125/", "http://user@127.0.0.1:49125/", "blob:https://evil.test/export"]:
            self.assertEqual(navigation_policy(url, origin, False, False), "cancel")
        self.assertEqual(navigation_policy("https://example.com", origin, True, False), "external")
        self.assertEqual(navigation_policy("https://example.com", origin, False, False), "cancel")


if __name__ == "__main__":
    unittest.main()

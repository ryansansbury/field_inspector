"""The release tools agree with the page, and the launch's checks hold. The GitHub description says what the page says,
the links point at the same places, the launch ships every file the build writes, the browser check serves the page
with the live site's headers, the launch trusts only the bytes Chrome saw, and the local copy answers the way the website
does, checked through urllib's real redirect and error handling with no socket. The release tools never ship, so a
public clone skips these."""
import contextlib
import http.client
import importlib.util
import io
import json
import re
import tempfile
import unittest
import urllib.request
import urllib.response
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import build
from app import page, words
from owner import browser_check

HERE = Path(__file__).resolve().parent.parent
TOOLS = HERE.joinpath("tools")
PAGE = {"index.html": b"<p>page</p>", "app.js": b"1", "app.css": b"p{}", "favicon.svg": b"<svg></svg>",
        "fonts/inter-latin.woff2": b"w", "photos/p01.jpg": b"j", "photos/thumbs/p01.jpg": b"t"}


def tool(name):
    spec = importlib.util.spec_from_file_location(f"release_{name}", str(TOOLS.joinpath(f"{name}.py")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Copy(urllib.request.HTTPHandler):
    """Every http request answered by the local copy's answer() in memory."""

    def __init__(self, answer, files):
        super().__init__()
        self.answer, self.files = answer, files

    def http_open(self, req):
        status, headers, body = self.answer(urlsplit(req.full_url).path, self.files)
        msg = http.client.HTTPMessage()
        for name, value in headers.items():
            msg[name] = value
        reply = urllib.response.addinfourl(io.BytesIO(body), msg, req.full_url, status)
        reply.msg = "reply"
        return reply


@unittest.skipUnless(TOOLS.joinpath("go_live.py").exists(), "the release tools never ship")
class Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.go, cls.serve = tool("go_live"), tool("serve")

    def test_description_says_what_the_page_says(self):
        d = self.go.DESCRIPTION
        self.assertTrue(d.startswith(words.load()["page.description"]))
        self.assertIn("synthetic", d)
        self.assertIsNone(re.search(r"\breal\b", d))
        self.assertLessEqual(len(d), 350, "GitHub's limit")

    def test_links_files_and_headers_agree(self):
        self.assertTrue(page.REPO.endswith("github.com/" + self.go.REPO))
        self.assertIn(self.go.LIVE, HERE.joinpath("README.md").read_text(encoding="utf-8"))
        self.assertLessEqual(set(build.SHIPPED) | {"code.js"}, set(self.go.SHIPS))
        self.assertEqual((browser_check.POLICY, browser_check.CACHE), (self.go.POLICY, self.go.CACHE))
        self.assertEqual(self.serve.go_live.POLICY, self.go.POLICY)

    def test_copy_answers_like_the_site(self):
        a = self.serve.answer
        status, headers, body = a("/field-inspector/?load=2", PAGE)
        self.assertEqual((status, body), (200, b"<p>page</p>"))
        self.assertEqual((headers["Content-Security-Policy"], headers["Cache-Control"]), (self.go.POLICY, self.go.CACHE))
        self.assertEqual(a("/field-inspector", PAGE)[:2], (308, {"Location": "/field-inspector/"}))
        self.assertEqual(a("/field-inspector/index.html", PAGE)[0], 308)
        self.assertEqual(a("/field-inspector/photos/p01.jpg", PAGE)[1]["Content-Type"], "image/jpeg")
        self.assertEqual(a("/field-inspector/../tools/go_live.py", PAGE)[0], 404)
        self.assertEqual(a("/photos/p01.jpg", PAGE)[0], 404)
        status, headers, _ = a("/", PAGE)
        self.assertEqual(status, 200)
        self.assertNotIn("Content-Security-Policy", headers)

    def check(self, served):
        """The launch's own site check, run against a copy serving these files, compared with PAGE as the build."""
        saved = self.go.OPENER
        self.go.OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), self.go.Follow308,
                                                     Copy(self.serve.answer, served))
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.go.check_site(PAGE, urlunsplit(("http", "127.0.0.1:9", "/field-inspector/", "", "")))
        finally:
            self.go.OPENER = saved

    def test_launch_check_passes_on_the_copy_and_follows_308s(self):
        self.check(PAGE)

    def test_launch_check_stops_on_a_file_that_differs(self):
        with self.assertRaises(SystemExit):
            self.check(dict(PAGE, **{"app.js": b"2"}))

    def test_launch_trusts_only_the_bytes_chrome_saw(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        saved = self.go.BUILD
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            root = Path(d)
            for rel, data in PAGE.items():
                root.joinpath("site", rel).parent.mkdir(parents=True, exist_ok=True)
                root.joinpath("site", rel).write_bytes(data)
            report = root.joinpath("owner", "out", "browser_check.json")
            report.parent.mkdir(parents=True)
            fresh = {"console_errors": 0, "files": browser_check.fingerprint(root.joinpath("site"))}
            self.go.BUILD = root
            try:
                report.write_text(json.dumps(fresh), encoding="utf-8")
                self.go.browser_checked(PAGE)
                with self.assertRaises(SystemExit):
                    self.go.browser_checked(dict(PAGE, **{"app.js": b"2"}))
                for stale in ({"console_errors": 0}, dict(fresh, console_errors=1), dict(fresh, page_scrolls=["1440x780-open"]),
                              dict(fresh, covered_values={"1440-heat-pump": ["refrigerant under #inset"]})):
                    report.write_text(json.dumps(stale), encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        self.go.browser_checked(PAGE)
            finally:
                self.go.BUILD = saved


if __name__ == "__main__":
    unittest.main()

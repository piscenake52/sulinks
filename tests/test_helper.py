"""helper(adminhelper.html)をブラウザで開く最低限の確認。通信はすべて遮断する。"""
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://helper.test/"


def route(r):
    if r.request.url.split("?")[0].split("#")[0] != HOST:
        return r.abort()
    body = ('<!doctype html><html lang="ja"><head><meta charset="utf-8"></head><body>'
            + (ROOT / "adminhelper.html").read_text(encoding="utf-8") + "</body></html>")
    r.fulfill(body=body, content_type="text/html; charset=utf-8")


class TestHelper(unittest.TestCase):
    def test_opens_and_switches_tabs(self):
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.route("**/*", route)
            pg.goto(HOST)
            for tab in ("logs", "songs", "setlist", "videos"):
                pg.click("#tabs button[data-k=%s]" % tab)
                self.assertTrue(pg.is_visible("#f_title"))
            self.assertEqual(errors, [])
            b.close()


if __name__ == "__main__":
    unittest.main()

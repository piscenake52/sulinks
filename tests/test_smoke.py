"""閲覧ページを実際に開く最低限の確認。INDEX_HTML を指定すると、分けた版を確認する。
通信はモック: このリポジトリの data/ と version.json はローカルのファイルを返し、ほかは遮断する。"""
import os
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
INDEX = Path(os.environ.get("INDEX_HTML") or ROOT / "index.html")
HOST = "https://site.test/"


def route(r):
    url = r.request.url.split("?")[0]
    if url.startswith(HOST):
        name = url[len(HOST):] or "index.html"
        f = INDEX if name == "index.html" else INDEX.parent / name
    else:
        tail = url.split("/main/")[-1] if "raw.githubusercontent.com" in url else ""
        f = ROOT / tail if tail == "version.json" or tail.startswith("data/") else None
    if f is None or not f.is_file():
        return r.abort()
    kind = {".html": "text/html", ".js": "text/javascript", ".json": "application/json"}.get(f.suffix, "text/plain")
    r.fulfill(body=f.read_bytes(), content_type=kind + "; charset=utf-8", headers={"access-control-allow-origin": "*"})


class TestSmoke(unittest.TestCase):
    def test_page_opens(self):
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.route("**/*", route)
            pg.goto(HOST + "index.html")
            pg.wait_for_timeout(3000)
            self.assertEqual(errors, [])
            self.assertGreater(len(pg.inner_text("body").strip()), 0)
            b.close()


if __name__ == "__main__":
    unittest.main()

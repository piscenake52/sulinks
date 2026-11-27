"""index.html を、GitHub Pages で公開する形に分ける。

使い方: python scripts/build_viewer.py index.html 出力フォルダ --url 公開先URL [--preview]

出力:
  viewer.js   <style> と本文を書き出し、本文のスクリプトを元の順に実行する
  loader.txt  Blogger に貼る内容(<head> の <style> 以外 + viewer.js の読み込み)
  index.html  loader.txt を単独で開ける確認ページ(--preview のときだけ。検索に出さない)

<head> の <style> 以外を変えたときは、Blogger の貼り直しが必要。
"""
import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

TOKEN = re.compile(r"<!--.*?-->|<script(?P<attr>[^>]*)>(?P<code>.*?)</script>", re.S)
VOID = set("area base br col embed hr img input link meta source track wbr".split())

# 読み込めなかったときの表示。Blogger に貼っても化けないように、日本語は文字参照にする
ERROR_HTML = (
    '<div id="pageLoadFail" hidden style="padding:24px 16px;text-align:center">'
    "&#12506;&#12540;&#12472;&#12434;&#35501;&#12415;&#36796;&#12417;&#12414;&#12379;&#12435;&#12391;&#12375;&#12383;&#12290;<br>"
    '<button type="button" onclick="location.reload()" style="margin-top:12px;padding:8px 20px">'
    "&#20877;&#35501;&#12415;&#36796;&#12415;</button></div>"
)


class BuildError(Exception):
    pass


class Depth(HTMLParser):
    """HTML のかたまりの中で、タグが閉じているかを調べる"""
    def __init__(self):
        super().__init__()
        self.stack, self.bad = [], False

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack.pop() != tag:
            self.bad = True


def check_closed(chunk):
    p = Depth()
    p.feed(chunk)
    p.close()
    if p.bad or p.stack:
        raise BuildError("<body> のスクリプトが要素の内側にあるか、タグが閉じていません: " + chunk.strip()[:80])


def split(html):
    """(head の style 以外, style の連結, [("html"|"js", 内容), ...]) に分ける。"""
    m = re.search(r"<head>(.*?)\n</head>\s*<body>(.*)</body>\s*</html>\s*$", html, re.S)
    if not m:
        raise BuildError("<head> ... </head> <body> ... </body> </html> の形になっていません(<body> に属性は付けられません)")
    head, body = m.group(1), m.group(2)
    style_re = re.compile(r"(?m)^<style[^>]*>.*?</style>[ \t]*\n?", re.S)  # 行の先頭の <style> が対象
    styles = [s.group(0) for s in style_re.finditer(head)]
    head_rest = style_re.sub("", head).strip("\n")
    parts, buf, pos = [], "", 0
    for t in TOKEN.finditer(body):
        buf += body[pos:t.start()]
        pos = t.end()
        if t.group("code") is None:      # コメントは捨てる
            continue
        attr = t.group("attr")
        kind = re.search(r"""type\s*=\s*["']?([^"'\s>]+)""", attr)
        if kind and kind.group(1).lower() not in ("text/javascript", "application/javascript"):
            if kind.group(1).lower() == "module":
                raise BuildError("<script type=module> には対応していません")
            buf += t.group(0)            # JSON などのデータは HTML として扱う
            continue
        if re.search(r"\ssrc\s*=", attr):
            raise BuildError("<body> の外部スクリプト(src)には対応していません")
        if buf.strip():
            check_closed(buf)
            parts.append(("html", buf.strip("\n")))
        buf = ""
        parts.append(("js", t.group("code")))
    buf += body[pos:]
    if buf.strip():
        check_closed(buf)
        parts.append(("html", buf.strip("\n")))
    if not any(k == "js" for k, _ in parts):
        raise BuildError("<body> にスクリプトがありません")
    return head_rest, "".join(styles), parts


def viewer_js(style, parts):
    # 自分の <script> の直前に順番に書き出す。スクリプトは1つずつ別の <script> にする
    # (元の index.html と同じく、1つが失敗しても次が動き、順番も同じになる)
    lines = ["/* index.html から scripts/build_viewer.py が作成。直接編集しない */",
             "(function () {",
             "var me = document.currentScript;",
             "function H(h) { me.insertAdjacentHTML('beforebegin', h); }",
             "function S(c) { var s = document.createElement('script'); s.textContent = c; me.parentNode.insertBefore(s, me); }"]
    if style:
        lines.append("H(%s);" % json.dumps(style))
    for kind, text in parts:
        lines.append("%s(%s);" % ("H" if kind == "html" else "S", json.dumps(text)))
    return "\n".join(lines) + "\n})();\n"


def loader(head_rest, url):
    origin = re.match(r"(https?://[^/]+)", url)
    src = (url.rstrip("/") + "/" if url else "") + "viewer.js"
    lines = ["<!-- loader: scripts/build_viewer.py -->", head_rest]
    if origin:
        lines.append('<link rel="preconnect" href="%s">' % origin.group(1))
    lines.append(ERROR_HTML)
    lines.append('<script charset="utf-8" src="%s" '
                 "onerror=\"document.getElementById('pageLoadFail').hidden=false\"></script>" % src)
    return "\n".join(lines) + "\n"


def preview_page(head_rest, url):
    return ('<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta name="robots" content="noindex, nofollow">\n<title>preview</title>\n</head>\n<body>\n'
            + loader(head_rest, url) + "</body>\n</html>\n")


def build(src, out, url="", preview=False):
    with open(src, encoding="utf-8") as f:
        head_rest, style, parts = split(f.read())
    os.makedirs(out, exist_ok=True)
    files = {"viewer.js": viewer_js(style, parts), "loader.txt": loader(head_rest, url)}
    if preview:
        files["index.html"] = preview_page(head_rest, url)
    for name, text in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return sorted(files)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--url", default="", help="viewer.js を置く場所(省略すると相対パス)")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args(argv)
    try:
        names = build(a.src, a.out, a.url, a.preview)
    except BuildError as e:
        print("build_viewer: " + str(e), file=sys.stderr)
        return 1
    print("%s: %s" % (a.out, ", ".join(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

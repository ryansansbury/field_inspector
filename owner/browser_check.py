"""The owner's machine only. Look at the page in real Chrome: screenshots, the line rule, overlaps, console errors and
network requests. Adapted from the Call Companion's browser check.

    bash owner/screenshots.sh              the real page (from the build folder)
    bash owner/screenshots.sh --preview    the preview on the drawn plates, for an early look

It opens the page in headless Chrome with a fresh profile and drives it over the DevTools pipe, once straight from the
file system and once from a small server on 127.0.0.1 at a free port. The server sends the security policy and cache
header the live site sends for the page, and the served pass walks every asset, the audit log, How it works with the
code view, and the tour, so Chrome enforces the policy on every kind of load. Anything the policy blocks counts as a
console error. Everything goes to owner/out/, which is gitignored:

    screens/card-1600.png          the page as a fresh load opens it at 1600 by 1000 with nothing clicked, the homepage
                                   card frame
    screens/1440-<asset>.png       every asset at 1440 by 900
    screens/<width>-open.png       the opening view at 1280, 1024 and 768, and at 1440x780, 1920x960 and 1280x640, the
                                   shapes of real browser windows
    screens/1440-<state>.png       each line position, the breaker edit, a read a person settled, the photo's own words, full
                                   size, the audit log, How it works (whole page) and the code view
    screens/1440-stepNN.png        each tour step
    screens/390-<screen>.png       the three phone screens and How it works on a phone
    layout.json                    last lines under 80% full, text overlapping text, boxes whose content spills,
                                   anything wider than the window, a tour step whose lit part is missing, off the
                                   screen, or moved by the lighting, a job view taller than its window (the job never
                                   scrolls the page), and a read value under the breaker inset or the zoom buttons,
                                   per shot
    console.json, network.json     anything the page logged as an error, and every request it made
    browser_check.json             the summary this prints

Full-page shots resize the viewport to the page's height, since capturing beyond the viewport distorted an earlier
project's shots. Standard library only.
"""
import argparse
import base64
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT.joinpath("site")
OUT = HERE.joinpath("out")
SHOTS = OUT.joinpath("screens")
APPS = Path("/").joinpath("Applications")
CHROMES = (APPS.joinpath("Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
           APPS.joinpath("Chromium.app", "Contents", "MacOS", "Chromium"))
TRAMPOLINE = 'exec "$@" 3<&0 4>&1 0</dev/null 1>&2'
SETTLE = 1.2
# The live site's headers for the page, the same as the release tool's (a test holds the two together while it's here).
POLICY = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
          "connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
CACHE = "public, max-age=0, must-revalidate"
POLICY_JS = ("document.addEventListener('securitypolicyviolation', function (e) { console.error('The security policy "
             "blocked ' + (e.blockedURI || 'an inline ' + e.effectiveDirective) + ' (' + e.effectiveDirective + ')'); });")
THREADS_JS = ("(function () { var p = document.querySelectorAll('#threads path.thread'), bad = 0; p.forEach(function (x) { "
              "if (/NaN/.test(x.getAttribute('d'))) { bad += 1; } }); return {threads: p.length, cross: "
              "document.querySelectorAll('#threads path.cross').length, bad: bad}; })()")
DARK_JS = ("(function () { var s = document.querySelector('.spot'); if (!s) { return 'nothing lit'; } "
           "var a = s.getBoundingClientRect(); s.classList.remove('spot'); var b = s.getBoundingClientRect(); "
           "s.classList.add('spot'); if (!a.width || !a.height) { return 'the lit part has no size'; } "
           "if (a.bottom <= 0 || a.top >= innerHeight || a.right <= 0 || a.left >= innerWidth) { "
           "return 'the lit part is off the screen'; } if (Math.abs(a.left - b.left) > 1 || Math.abs(a.top - b.top) > 1) { "
           "return 'the lit part moves when it lights'; } return null; })()")
# How it works opens the code view with it, and the code arrives as its own file, so the shots wait for it (5 s at most).
CODE_OPEN_JS = ("new Promise(function (done) { var n = 0; (function look() { var c = document.getElementById('codeview'); "
                "if ((c && !c.hidden) || ++n > 100) { done(!!c && !c.hidden); } else { setTimeout(look, 50); } })(); })")
SETTLE_JS = ("(function () { var a = document.querySelector('[data-accept]'); if (a) { a.click(); return 'accepted'; } "
             "var c = document.querySelector('[data-correct]'); if (!c) { return null; } "
             "var key = c.getAttribute('data-correct'), item = c.closest('[data-q]'); "
             "var asset = item.querySelector('[data-asset]').getAttribute('data-asset'); c.click(); "
             "document.querySelector(\"[data-fix-value='\" + key + \"']\").value = "
             "(FI.job.designs[asset] || {})[key.split('/')[1]] || '1'; "
             "document.querySelector(\"[data-save='\" + key + \"']\").click(); return 'corrected'; })()")
LAYOUT_JS = """(function () {
  var W = window.innerWidth, out = {wider_than_window: document.documentElement.scrollWidth > W + 1, overlaps: [],
    short_last_lines: [], spills: []};
  var job = !document.body.classList.contains('on-how');
  out.page_scrolls = job && document.documentElement.scrollHeight > window.innerHeight + 1;
  out.covered_values = [];
  if (job && !document.querySelector('#table.full')) {
    var blocks = ['#inset', '#zoomtools'].map(function (s) { return document.querySelector(s); }).filter(function (e) {
      return e && e.checkVisibility(); });
    document.querySelectorAll('#boxes .box').forEach(function (b) {
      var r = b.getBoundingClientRect();
      blocks.forEach(function (k) {
        var q = k.getBoundingClientRect();
        if (r.left < q.right - 1 && q.left < r.right - 1 && r.top < q.bottom - 1 && q.top < r.bottom - 1) {
          out.covered_values.push((b.getAttribute('data-field') || 'a value') + ' under #' + k.id);
        }
      });
    });
  }
  var root = document.body, boxes = new Map(), covers = [];
  function name(el) {
    return (el.id ? '#' + el.id : el.tagName.toLowerCase() + Array.prototype.map.call(el.classList, function (c) {
      return '.' + c; }).join('')).slice(0, 50);
  }
  function clip(el) {
    if (boxes.has(el)) { return boxes.get(el); }
    var b = {l: -1e9, t: -1e9, r: 1e9, b: 1e9};
    for (var a = el; a && a !== document.documentElement; a = a.parentElement) {
      var cs = getComputedStyle(a);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        var q = a.getBoundingClientRect();
        b = {l: Math.max(b.l, q.left), t: Math.max(b.t, q.top), r: Math.min(b.r, q.right), b: Math.min(b.b, q.bottom)};
      }
    }
    boxes.set(el, b);
    return b;
  }
  root.querySelectorAll('*').forEach(function (el) {
    if (el.closest('svg, .boxes, .ownwords') || !el.checkVisibility()) { return; }
    var cs = getComputedStyle(el);
    if (cs.position === 'sticky' || cs.position === 'fixed' || cs.position === 'absolute' && el.closest('.stage')) { covers.push(el); }
    if (out.spills.length >= 25 || el.closest('pre, .tree, .scroll, .jobline, .sr, #mini') || cs.display === 'inline' || !el.clientWidth) { return; }
    if (/x|both/.test(cs.scrollSnapType || '')) { return; }
    if (el.scrollWidth > el.clientWidth + 1) {
      var scrolls = cs.overflowX === 'auto' || cs.overflowX === 'scroll';
      out.spills.push(name(el) + ' by ' + (el.scrollWidth - el.clientWidth) + 'px' + (scrolls ? ' (scrolls)' : ''));
    }
  });
  function covered(el, f) {
    return covers.some(function (c) {
      if (c === el || c.contains(el)) { return false; }
      var q = c.getBoundingClientRect();
      return f.l < q.right && f.r > q.left && f.t < q.bottom && f.b > q.top;
    });
  }
  root.querySelectorAll('p, li, h2, h3').forEach(function (el) {
    if (el.closest('pre, .tree, .scroll, .boxes, .sheet li') || !el.checkVisibility() ||
        el.querySelector('button, input, select, label')) { return; }
    var r = document.createRange(); r.selectNodeContents(el);
    var rects = Array.prototype.filter.call(r.getClientRects(), function (x) { return x.width > 1; });
    if (rects.length < 2) { return; }
    var tops = {}, box = el.getBoundingClientRect();
    rects.forEach(function (x) { var k = Math.round(x.top); tops[k] = Math.max(tops[k] || 0, x.right); });
    var keys = Object.keys(tops).map(Number).sort(function (a, b) { return a - b; });
    if (keys.length < 2) { return; }
    var lastRight = tops[keys[keys.length - 1]], fill = (lastRight - box.left) / Math.max(1, box.width);
    var text = el.textContent.trim(), lines = keys.length;
    if (fill < 0.8) { out.short_last_lines.push({text: text.slice(-60), fill: Math.round(fill * 100), lines: lines,
      width: Math.round(box.width), chars: text.length, per_line: Math.round(text.length / (lines - 1 + fill))}); }
  });
  var frags = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node, range = document.createRange();
  while ((node = walker.nextNode())) {
    var el = node.parentElement;
    if (!/\\S/.test(node.data) || !el || el.closest('script, style, pre, .tree, .boxes, option') || !el.checkVisibility()) { continue; }
    var box = clip(el);
    range.selectNodeContents(node);
    Array.prototype.forEach.call(range.getClientRects(), function (x) {
      if (x.width < 1 || x.height < 1) { return; }
      var h = x.bottom - x.top, mid = (x.top + x.bottom) / 2;
      var f = {el: el, l: Math.max(x.left, box.l), r: Math.min(x.right, box.r), t: x.top + h * 0.2, b: x.bottom - h * 0.2,
        text: node.data.trim().slice(0, 40)};
      if (mid < box.t || mid > box.b || f.r - f.l < 1 || covered(el, f)) { return; }
      frags.push(f);
    });
  }
  frags.sort(function (a, b) { return a.t - b.t; });
  for (var i = 0; i < frags.length && out.overlaps.length < 20; i++) {
    for (var j = i + 1; j < frags.length && frags[j].t < frags[i].b; j++) {
      var f = frags[i], g = frags[j];
      if (f.el === g.el || f.el.contains(g.el) || g.el.contains(f.el)) { continue; }
      if (Math.min(f.r, g.r) - Math.max(f.l, g.l) > 2) { out.overlaps.push(f.text + ' / ' + g.text); }
    }
  }
  return out;
})()"""


def find_chrome(given=None):
    if given:
        return str(given)
    for p in CHROMES:
        if p.exists():
            return str(p)
    for n in ("google-chrome", "chromium"):
        if shutil.which(n):
            return shutil.which(n)
    raise SystemExit("Chrome wasn't found. Run again with --chrome and the path to the Chrome program.")


class CDP:
    """The DevTools protocol over Chrome's pipe: JSON messages, each ended by a zero byte."""

    def __init__(self, proc, on_event=None):
        self.proc, self.on_event = proc, on_event
        self.next_id, self.responses, self.events = 0, {}, []
        self.cond, self.wlock = threading.Condition(), threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            chunk = self.proc.stdout.read1(1 << 16)
            if not chunk:
                break
            buf += chunk
            while b"\0" in buf:
                raw, buf = buf.split(b"\0", 1)
                msg = json.loads(raw)
                with self.cond:
                    if "id" in msg:
                        self.responses[msg["id"]] = msg
                    else:
                        self.events.append(msg)
                    self.cond.notify_all()
                if "id" not in msg and self.on_event:
                    self.on_event(msg)

    def send(self, method, params=None, session=None, timeout=60):
        with self.cond:
            self.next_id += 1
            mid = self.next_id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        with self.wlock:
            self.proc.stdin.write(json.dumps(msg).encode() + b"\0")
            self.proc.stdin.flush()
        deadline = time.time() + timeout
        with self.cond:
            while mid not in self.responses:
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)
            reply = self.responses.pop(mid)
        if "error" in reply:
            raise RuntimeError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result", {})

    def mark(self):
        with self.cond:
            return len(self.events)

    def wait_event(self, method, session, since, timeout=60):
        deadline = time.time() + timeout
        with self.cond:
            while True:
                for e in self.events[since:]:
                    if e.get("method") == method and e.get("sessionId") == session:
                        return e
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)


class Browser:
    def __init__(self, chrome):
        self.requests, self.console, self.loads, self.size = [], [], 0, (1440, 900, False)
        profile = OUT.joinpath("chrome-profile")
        shutil.rmtree(profile, ignore_errors=True)
        flags = ["--headless=new", "--remote-debugging-pipe", f"--user-data-dir={profile}", "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--mute-audio",
                 "--disable-background-networking", "--disable-sync", "--disable-component-update",
                 "--allow-file-access-from-files"]
        self.log = OUT.joinpath("chrome.log").open("wb")
        self.proc = subprocess.Popen(["bash", "-c", TRAMPOLINE, "chrome", chrome, *flags], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log)
        self.cdp = CDP(self.proc, self.event)
        target = self.cdp.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.s = self.cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        for m in ("Page.enable", "Runtime.enable", "Network.enable", "Log.enable"):
            self.cdp.send(m, session=self.s)
        self.cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": POLICY_JS}, self.s)

    def event(self, e):
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            self.requests.append(p["request"]["url"])
        elif m == "Runtime.exceptionThrown":
            d = p["exceptionDetails"]
            self.console.append({"kind": "exception", "text": (d.get("exception") or {}).get("description") or d.get("text")})
        elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "assert"):
            self.console.append({"kind": "console.error", "text": " ".join(str(a.get("value", a.get("description")))
                                                                           for a in p.get("args", []))})
        elif m == "Log.entryAdded" and p["entry"].get("level") == "error":
            self.console.append({"kind": "log", "text": p["entry"].get("text"), "url": p["entry"].get("url")})

    def view(self, width, height, mobile=False):
        self.size = (width, height, mobile)
        self.cdp.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1,
                                                             "mobile": mobile}, self.s)

    def load(self, url):
        self.loads += 1
        base, mark, frag = url.partition("#")
        fresh = f"{base}{'&' if '?' in base else '?'}load={self.loads}{mark}{frag}"
        since = self.cdp.mark()
        self.cdp.send("Page.navigate", {"url": fresh}, self.s)
        self.cdp.wait_event("Page.loadEventFired", self.s, since)
        self.pause(SETTLE)

    def js(self, expr, wait=False):
        r = self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": wait}, self.s)
        if "exceptionDetails" in r:
            raise RuntimeError(f"{expr[:60]}: {r['exceptionDetails'].get('text')}")
        return r.get("result", {}).get("value")

    def pause(self, seconds):
        self.js(f"new Promise(r => requestAnimationFrame(() => setTimeout(r, {int(seconds * 1000)})))", wait=True)

    def click(self, selector, settle=SETTLE):
        self.js(f"(function () {{ var e = document.querySelector({json.dumps(selector)}); if (e) {{ e.click(); }} "
                f"return !!e; }})()")
        self.pause(settle)

    def shot(self, name, full=False):
        width, height, mobile = self.size
        if full:
            tall = int(self.js("Math.ceil(document.documentElement.scrollHeight)") or height)
            self.view(width, min(tall, 9000), mobile)
            self.pause(0.6)
        data = self.cdp.send("Page.captureScreenshot", {"format": "png"}, self.s, timeout=120)["data"]
        SHOTS.joinpath(f"{name}.png").write_bytes(base64.b64decode(data))
        layout = self.js(LAYOUT_JS) or {}
        layout["threads"] = self.js(THREADS_JS)
        if full:
            self.view(width, height, mobile)
            self.pause(0.4)
        return layout

    def close(self):
        try:
            self.cdp.send("Browser.close", timeout=10)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


class Quiet(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Content-Security-Policy", POLICY)
        self.send_header("Cache-Control", CACHE)
        super().end_headers()

    def log_message(self, *args):
        pass


def serve(root):
    handler = functools.partial(Quiet, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def desktop(b, url, layout):
    """The card frame, every asset, every control, How it works and the tour, at desktop sizes."""
    b.view(1600, 1000)
    b.load(url)
    layout["card-1600"] = b.shot("card-1600")
    assets = b.js("FI.job.assets.map(function (a) { return a.id; })") or []
    first = b.js("FIP.defaultAsset()")
    b.view(1440, 900)
    b.load(url)
    for a in assets:
        b.click(f"[data-asset='{a}']")
        layout[f"1440-{a}"] = b.shot(f"1440-{a}")
    b.click(f"[data-asset='{first}']")
    for pos in ("missing", "all", "partial"):
        b.click(f"[data-line='{pos}']")
        layout[f"1440-line-{pos}"] = b.shot(f"1440-line-{pos}")
    b.js(f"(function () {{ var i = document.querySelector(\"[data-design='{first}/breaker']\"); if (i) {{ i.value = '25'; "
         "i.dispatchEvent(new Event('input', {bubbles: true})); i.dispatchEvent(new Event('change', {bubbles: true})); } })()")
    b.pause(SETTLE)
    layout["1440-design-edit"] = b.shot("1440-design-edit")
    b.click("#reset")
    b.js(SETTLE_JS)
    b.pause(SETTLE)
    layout["1440-settled"] = b.shot("1440-settled")
    b.click("#own-words")
    layout["1440-words"] = b.shot("1440-words")
    b.click("#own-words")
    b.click("[data-zoom='full']")
    layout["1440-full"] = b.shot("1440-full")
    b.click("[data-zoom='fit']")
    b.click("#open-log")
    layout["1440-log"] = b.shot("1440-log")
    b.click("#close-log")
    b.click("#open-how")
    b.js(CODE_OPEN_JS, wait=True)
    layout["1440-how"] = b.shot("1440-how", full=True)
    b.js("document.getElementById('codeview').scrollIntoView()")
    layout["1440-code"] = b.shot("1440-code")
    b.click("#open-how")
    steps = int(b.js("FIP.steps") or 0)
    b.click("#tour-start")
    for n in range(1, steps + 1):
        layout[f"1440-step{n:02d}"] = b.shot(f"1440-step{n:02d}")
        layout[f"1440-step{n:02d}"]["dark"] = b.js(DARK_JS)
        b.click("[data-present='next']")
    for width, height, name in ((1280, 720, "1280-open"), (1024, 768, "1024-open"), (768, 1024, "768-open"),
                                (1440, 780, "1440x780-open"), (1920, 960, "1920x960-open"), (1280, 640, "1280x640-open")):
        b.view(width, height)
        b.load(url)
        layout[name] = b.shot(name)


def served(b, url, layout):
    """The page from the server under the live site's policy: every asset, the audit log, How it works with the code
    view, and the tour, then the opening view's shot."""
    b.view(1440, 900)
    b.load(url)
    for a in b.js("FI.job.assets.map(function (a) { return a.id; })") or []:
        b.click(f"[data-asset='{a}']", 0.4)
    for selector in ("#open-log", "#close-log", "#open-how", "#open-how", "#tour-start"):
        b.click(selector)
    for _ in range(int(b.js("FIP.steps") or 0)):
        b.click("[data-present='next']", 0.4)
    b.load(url)
    layout["1440-served"] = b.shot("1440-served")


def phone(b, url, layout):
    b.view(390, 844, mobile=True)
    b.load(url)
    for s in ("stage", "strip", "insp"):
        b.click(f"[data-screen='{s}']", 0.9)
        layout[f"390-{s}"] = b.shot(f"390-{s}")
    b.click("#open-how")
    b.js(CODE_OPEN_JS, wait=True)
    layout["390-how"] = b.shot("390-how", full=True)


def fingerprint(root=SITE):
    """Every file in the built page by its SHA-256, taken before Chrome loads anything, so the release tool can tell
    whether the page it ships is the page Chrome checked."""
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chrome")
    a = ap.parse_args(argv)
    if not SITE.joinpath("index.html").exists():
        raise SystemExit("Build the page first: python3 build.py")
    files = fingerprint()
    shutil.rmtree(SHOTS, ignore_errors=True)
    SHOTS.mkdir(parents=True)
    b = Browser(find_chrome(a.chrome))
    layout = {}
    httpd = None
    try:
        desktop(b, SITE.joinpath("index.html").as_uri(), layout)
        phone(b, SITE.joinpath("index.html").as_uri(), layout)
        httpd = serve(SITE)
        served(b, f"http://127.0.0.1:{httpd.server_address[1]}/index.html", layout)
    finally:
        b.close()
        if httpd:
            httpd.shutdown()
    outside = [u for u in b.requests if not (u.startswith("file:") or u.startswith("http://127.0.0.1:") or
                                             u.startswith("data:") or u == "about:blank")]
    OUT.joinpath("layout.json").write_text(json.dumps(layout, indent=1), encoding="utf-8")
    OUT.joinpath("console.json").write_text(json.dumps(b.console, indent=1), encoding="utf-8")
    OUT.joinpath("network.json").write_text(json.dumps(sorted(set(b.requests)), indent=1), encoding="utf-8")
    summary = {"shots": len(layout), "console_errors": len(b.console), "requests_outside": outside,
               "wider_than_window": [k for k, v in layout.items() if v.get("wider_than_window")],
               "overlaps": {k: v["overlaps"] for k, v in layout.items() if v.get("overlaps")},
               "short_last_lines": {k: v["short_last_lines"] for k, v in layout.items() if v.get("short_last_lines")},
               "spills": {k: v["spills"] for k, v in layout.items() if v.get("spills")},
               "bad_threads": [k for k, v in layout.items() if (v.get("threads") or {}).get("bad")],
               "tour_steps": {k: v["dark"] for k, v in layout.items() if v.get("dark")},
               "page_scrolls": [k for k, v in layout.items() if v.get("page_scrolls")],
               "covered_values": {k: v["covered_values"] for k, v in layout.items() if v.get("covered_values")}, "files": files}
    OUT.joinpath("browser_check.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"{summary['shots']} screenshots in owner/out/screens/. Console errors: {summary['console_errors']}. "
          f"Requests outside the page: {len(outside)}. Wider than the window: {len(summary['wider_than_window'])}. "
          f"Shots with overlapping text: {len(summary['overlaps'])}. Shots with short last lines: "
          f"{len(summary['short_last_lines'])}. Tour steps with a problem: {len(summary['tour_steps'])}. Job views that "
          f"scroll the page: {len(summary['page_scrolls'])}. Shots with a value under the inset or the zoom buttons: "
          f"{len(summary['covered_values'])}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

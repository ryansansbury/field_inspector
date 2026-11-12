"""site/index.html: the header, the light table's frame, and How it works, rendered from WORDS.md and the results.

The job, the photos, the reads and the checks are filled in by site/app.js from window.FI. How it works is rendered here,
since its scores, comparison, privacy result and recorded runs don't change in the browser. Nothing inline: no script or
style attributes, so the site's security policy holds. Every visible word comes from WORDS.md.
"""
from html import escape as esc_

from app.readme import SHOTS

MARK =('<svg width="28" height="28" viewBox="0 0 30 30" aria-hidden="true"><rect width="30" height="30" rx="8" '
        'fill="#f15a24"/><path d="M8 11V8h3M19 8h3v3M22 19v3h-3M11 22H8v-3" fill="none" stroke="#fff" '
        'stroke-width="2" stroke-linecap="round"/><rect x="11.5" y="12" width="7" height="6" rx="1" fill="none" '
        'stroke="#fff" stroke-width="1.8"/></svg>')
REPO = "https://github.com/ryansansbury/field_inspector"
HOME = "https://www.ryansansbury.com/"
LIVE = HOME + "field-inspector/"
# The link preview's image is the top 838 rows of the homepage card, which is 1.91 to 1 and needs no crop on LinkedIn.
SHARE = HOME + "images/share/field-inspector.png?v=1"


def esc(s):
    return esc_(str(s if s is not None else ""), quote=True)


def share(w):
    """The tags a shared link reads for its preview, in the same set the homepage uses."""
    title, text, alt = esc(w["page.title"]), esc(w["page.description"]), esc(dict(SHOTS)["job"])
    return (f"<link rel='canonical' href='{LIVE}'><meta property='og:type' content='website'>"
            f"<meta property='og:url' content='{LIVE}'><meta property='og:site_name' content='Ryan Sansbury'>"
            f"<meta property='og:title' content='{title}'><meta property='og:description' content='{text}'>"
            f"<meta property='og:image' content='{SHARE}'><meta property='og:image:width' content='1600'>"
            f"<meta property='og:image:height' content='838'><meta property='og:image:alt' content='{alt}'>"
            f"<meta name='twitter:card' content='summary_large_image'><meta name='twitter:title' content='{title}'>"
            f"<meta name='twitter:description' content='{text}'><meta name='twitter:image' content='{SHARE}'>")


def pct(x):
    return "" if x is None else f"{round(x * 100)}%"


def money(x):
    return "" if x is None else f"${x:.4f}" if x < 0.1 else f"${x:.2f}"


def table(head, rows, cls="tbl"):
    """A table in How it works. Each cell carries its column's name, so on a phone a table wider than three columns can
    become one labeled card per row (app.css), and a desktop shows the table as it was."""
    h = "".join(f"<th scope='col'>{esc(c)}</th>" for c in head)
    body = "".join("<tr>" + "".join(f"<td data-label='{esc(head[i]) if i < len(head) else ''}'>{esc(c)}</td>"
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    wide = " wide" if len(head) > 3 else ""
    return f"<div class='scroll'><table class='{cls}{wide}'><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>"


def header(w, data):
    preview = (f"<p class='preview-flag' title='{esc(w['page.preview'])}'>{esc(w['page.preview_short'])}</p>"
               if data["preview"] else "")
    return (
        f"<header class='top' id='top'><a class='brand' href='./'>{MARK}<b>{esc(w['page.title'])}</b>"
        f"<span>{esc(w.fill('page.subtitle', **data['cast']))}</span></a>"
        f"<div class='jobline' id='jobline'></div>{preview}<div class='grow'></div>"
        "<div class='counts' id='counts'></div>"
        f"<label class='picker'><span>{esc(w['top.model'])}</span><select id='model'></select></label>"
        f"<nav class='links' aria-label='Views'><button type='button' class='btn' id='open-how' data-how='{esc(w['top.how'])}' "
        f"data-back='{esc(w['top.back'])}'>{esc(w['top.how'])}</button>"
        f"<button type='button' class='btn' id='tour-start'>{esc(w['top.tour'])}</button></nav></header>"
    )


def work(w, foot):
    return (
        f"<main id='work' class='work'><h1 class='sr'>{esc(w['page.title'])}</h1>"
        f"<nav id='strip' class='strip' aria-label='{esc(w['strip.label'])}'></nav>"
        "<section id='stage' class='stage'><div class='cap'><b id='cap-title'></b>"
        "<span id='cap-note'></span></div><div id='table' class='desk'><div id='print' class='print'>"
        "<img id='photo' alt='' decoding='async'><div id='ownwords' class='ownwords' hidden></div>"
        "<div id='boxes' class='boxes'></div></div></div>"
        "<div class='zoomtools' id='zoomtools'><button type='button' data-zoom='fit'></button>"
        "<button type='button' data-zoom='full'></button><button type='button' id='own-words'></button></div>"
        "<div id='inset' class='insetcard' hidden><div class='mini' id='mini'>"
        "<img id='mini-photo' alt='' decoding='async'><div id='mini-boxes' class='boxes'></div></div>"
        "<p class='t' id='inset-title'></p><p class='s' id='inset-status'></p></div>"
        "</section>"
        "<aside id='insp' class='insp' tabindex='-1'><h2 id='h-reads'></h2><div id='reads'></div>"
        "<div class='line' id='line'><h2 id='h-line'></h2><div class='seg' id='seg' role='radiogroup' "
        "aria-labelledby='h-line'></div><p class='note' id='line-note'></p></div>"
        "<h2 id='h-checks'></h2><div id='checks'></div>"
        "<div class='queue'><h2 id='h-queue'></h2><div id='queue'></div></div>"
        f"<p class='resetrow'><button type='button' class='link' id='open-log'>{esc(w['top.log'])}</button>"
        "<button type='button' class='link' id='reset'></button></p>"
        f"<div class='foot-in'><p>{esc(foot)}</p><p>{links(w)}</p></div></aside>"
        "<svg id='threads' class='threads' aria-hidden='true'></svg></main>"
    )


def links(w):
    """The footer's two links, in the footer bar and at the end of a phone's checks screen."""
    return f"<a href='{HOME}'>{esc(w['page.by'])}</a> · <a href='{REPO}'>{esc(w['page.code'])}</a>"


def map_table(w):
    rows = [v.split(" | ") for v in w.table("how.map").values()]
    cols = w.table("how.map.cols")
    return table([cols["who"], cols["what"], cols["check"]], rows, "tbl map")


def scores_section(w, data, extra):
    scores = extra.get("scores") or {"models": {}}
    comparison = extra.get("comparison") or {}
    cols = w.table("how.scores.cols")
    labels = {m["id"]: m["label"] for m in data["models"]}
    rows = []
    for m in data["models"]:
        s = scores["models"].get(m["id"]) or {}
        t = s.get("test") or s.get("job") or {}
        if not t:
            continue
        line = t["line"]["partial"]
        rows.append([m["label"], pct(t["fields"]["accuracy"]), line["past"], t["checks"]["missed"], pct(line["share"]),
                     money(t.get("cost_per_photo")), t.get("seconds_per_photo")])
    out = (f"<h3>{esc(w['how.scores.title'])}</h3><p>{esc(w['how.scores'])}</p>" +
           (f"<p class='preview-note'>{esc(w['how.scores.preview'])}</p>" if data["preview"] else "") +
           table([cols[k] for k in ("model", "accuracy", "past", "missed", "share", "cost", "seconds")], rows))
    route = comparison.get("route") or data["route"]
    reasons = w.table("how.models.reasons")
    if comparison.get("route_reason") in reasons:
        out += (f"<p>{esc(w.fill('how.models.route', model=labels.get(route, route), reason=reasons[comparison['route_reason']]))} "
                f"{esc(w['how.models.rule'])}</p>")
    main = (scores["models"].get(route) or {}).get("test") or (scores["models"].get(route) or {}).get("job")
    if main:
        names = w.table("ui.fields")
        shots = w.table("ui.shots")
        by_field = [[names.get(f, f), pct(main["by_field"][f]["accuracy"]), main["by_field"][f]["key"]]
                    for f in data["fields"] if (main["by_field"].get(f) or {}).get("key")]
        by_shot = [[shots.get(s, s), pct(v["accuracy"]), v["key"]] for s, v in main["by_shot"].items() if v["key"]]
        fc = w.table("how.fields.cols")
        out += (f"<h3>{esc(w['how.fields.title'])}</h3><div class='pair'>" +
                table([fc["field"], cols["accuracy"], fc["values"]], by_field) +
                table([fc["shot"], cols["accuracy"], fc["values"]], by_shot) + "</div>")
        lc = w.table("how.line.cols")
        pos = w.table("how.line.positions")
        lrows = [[pos[p], f"{main['line'][p]['sent']} ({pct(main['line'][p]['share'])})", main["line"][p]["caught"],
                  main["line"][p]["past"]] for p in ("missing", "partial", "all")]
        out += (f"<h3>{esc(w['how.line.title'])}</h3><p>{esc(w['how.line'])}</p>" +
                table([lc["position"], lc["sent"], lc["caught"], lc["past"]], lrows))
    return out


def runs_section(w, extra):
    rows = extra.get("runs") or []
    rc = w.table("how.runs.cols")
    body = table([rc[k] for k in ("photo", "model", "date", "tokens", "cost", "seconds")], rows, "tbl runs") if rows else ""
    if body:
        body = f"<details class='more'><summary>{esc(w.fill('how.runs.show', n=len(rows)))}</summary>{body}</details>"
    return f"<h3>{esc(w['how.runs.title'])}</h3><p>{esc(w['how.runs'])}</p>{body}"


def how(w, data, extra):
    scan = extra.get("privacy") or {"photos": 0, "problems": []}
    rules = w.table("how.rules.list")
    featured = w.table("how.code.featured")
    cards = "".join(f"<button type='button' class='file' data-file='{esc(path)}'><b>{esc(path)}</b>"
                    f"<span>{esc(label)}</span></button>" for path, label in featured.items())
    return (
        f"<section id='how' class='how' hidden><div class='wrap'><h2>{esc(w['how.title'])}</h2>"
        f"<p class='lead'>{esc(w['how.intro'])}</p>"
        f"<h3>{esc(w['how.map.title'])}</h3>{map_table(w)}"
        f"<h3>{esc(w['how.pipeline.title'])}</h3><ol class='pipe'>" +
        "".join(f"<li>{esc(v)}</li>" for v in w.table("how.pipeline").values()) + "</ol>"
        f"<h3>{esc(w['how.privacy.title'])}</h3><p>{esc(w['how.privacy'])}</p>"
        f"<p>{esc(w.fill('how.privacy.scan', photos=scan['photos'], problems=len(scan['problems'])))}</p>"
        f"<h3>{esc(w['how.confirm.title'])}</h3><p>{esc(w['how.confirm'])}</p>"
        f"<h3>{esc(w['how.rules.title'])}</h3><p>{esc(w['how.rules'])}</p><ul class='rules'>" +
        "".join(f"<li>{esc(v)}</li>" for v in rules.values()) + "</ul>" +
        scores_section(w, data, extra) + runs_section(w, extra) +
        f"<h3>{esc(w['how.client.title'])}</h3><p>{esc(w['how.client'])}</p>"
        f"<h3>{esc(w['how.limits.title'])}</h3><p>{esc(w['how.limits'])}</p>"
        f"<h3>{esc(w['how.code.title'])}</h3><p>{esc(w['how.code'])}</p><div class='featured'>{cards}</div>"
        f"<div class='codeview' id='codeview' hidden><nav id='code-tree' class='tree'></nav>"
        f"<pre id='code-text' class='codetext' tabindex='0'></pre></div>"
        "</div></section>"
    )


def render(w, data, extra=None):
    extra = extra or {}
    foot = w["page.footer_preview"] if data["preview"] else w["page.footer"]
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='robots' content='index, follow'><meta name='referrer' content='no-referrer'>"
        f"<meta name='description' content='{esc(w['page.description'])}'>{share(w)}"
        f"<title>{esc(w['page.title'])}</title><link rel='icon' href='favicon.svg'><link rel='stylesheet' href='app.css'></head>"
        f"<body class='{'is-preview' if data['preview'] else ''}'><a class='skip' href='#insp'>{esc(w['page.skip'])}</a>" +
        header(w, data) + "<p id='say' class='sr' aria-live='polite'></p>" +
        f"<noscript><p class='noscript'>{esc(w['page.noscript'])}</p></noscript>" + work(w, foot) + how(w, data, extra) +
        "<aside id='log' class='sheet' hidden><div class='sheet-head'><h2 id='log-title'></h2>"
        "<button type='button' class='link' id='close-log'></button></div><ol id='log-rows'></ol></aside>"
        "<nav id='tabs' class='tabs' aria-label='Screens'></nav>"
        "<div id='presenter' class='presenter' hidden role='dialog' aria-live='polite'></div>"
        "<svg id='tour' class='tour' hidden aria-hidden='true'></svg>"
        f"<footer class='foot'><p>{esc(foot)}</p><p>{links(w)}</p></footer>"
        "<script src='normalize.js'></script><script src='rules.js'></script><script src='data.js'></script>"
        "<script src='app.js'></script></body></html>\n"
    )

/* The node click-through. It runs the built page's own scripts against a small DOM (dom.js) and works the job the way a
   visitor would: it opens every asset, moves the confidence line through all three positions, edits the design's breaker
   and capacity, accepts, corrects, approves an equal and calls a wrong unit, resets, opens the audit log, How it works and
   the code, walks the tour forward and back, and moves between the phone screens. It checks the counts, the states, the
   boxes, the threads and the log at every step, and that no word comes out blank. Exits 1 on any failed check.

       node tests/js/check_app.js [site folder]

   It can't see layout, color, motion or real timing. owner/browser_check.py covers those in real Chrome. */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const {Document} = require("./dom.js");

const SITE = path.resolve(process.argv[2] || path.join(__dirname, "..", "..", "site"));
const checks = [], errors = [];
function check(name, ok, detail) { checks.push({name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 300)}); }

const html = fs.readFileSync(path.join(SITE, "index.html"), "utf8");
const doc = new Document(html);
check("index.html parses with every tag closed", doc.errors.length === 0, doc.errors.slice(0, 3).join("; "));
check("no script, image or font comes from another site", !/\ssrc=['"](?:https?:)?\/\//.test(html) && !/<link(?![^>]*rel=['"]canonical['"])[^>]+href=['"](?:https?:)?\/\//.test(html));
check("no inline script or style", !/<script>(?!<\/script>)|<script[^>]*>[^<]+<\/script>| style=/.test(html));
const timers = [];
const win = {document: doc, innerWidth: 1600, innerHeight: 1000, addEventListener() {}, devicePixelRatio: 1,
  setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout(id) { if (id) { timers[id - 1] = null; } },
  location: {hash: "", protocol: "file:"}, history: {replaceState(s, t, url) { win.location.hash = url; }},
  scrollX: 0, scrollY: 0, JSON, Math, Date, Object, String, Array, Number, RegExp, parseFloat, encodeURIComponent, decodeURIComponent};
win.window = win;
const ctx = vm.createContext(win);
for (const name of ["normalize.js", "rules.js", "data.js", "code.js", "app.js"]) {
  try { vm.runInContext(fs.readFileSync(path.join(SITE, name), "utf8"), ctx, {filename: name}); }
  catch (e) { errors.push(name + " threw: " + (e && e.stack || e)); }
}
function flush() {
  for (let guard = 0; guard < 400 && timers.some(Boolean); guard++) {
    const i = timers.findIndex(Boolean), fn = timers[i];
    timers[i] = null;
    fn();
  }
}
const FI = win.FI, FIP = win.FIP;
const $ = (s) => doc.querySelector(s), $$ = (s) => doc.querySelectorAll(s);
const click = (el) => { doc.dispatch("click", el); flush(); };
const change = (el, value) => { el.value = value; doc.dispatch("input", el); doc.dispatch("change", el); flush(); };
const state = () => FIP.state();
const out = () => FIP.out();
const st = (id) => out().assets[id].state;
const chk = (id, rule) => out().assets[id].checks.filter((c) => c.rule === rule)[0];
function attempt(name, fn) { try { fn(); } catch (e) { errors.push(name + ": " + (e && e.stack || e)); } }
function S_last() { const rows = $$("#log-rows li span"); return rows.length ? rows[rows.length - 1].textContent : ""; }
function blank(text) { return /undefined|null|NaN|\{[a-z_]+\}/.test(text); }

if (FI && FIP) {
  const first = FIP.defaultAsset();
  const start = JSON.stringify(out().counts);
  attempt("opening", () => {
    flush();
    const a = FI.job.assets.filter((x) => x.id === state().asset)[0];
    check("the page opens on the asset with the cross-photo failure", a && a.breaker_photo && st(a.id) === "fail", state().asset);
    check("the opening asset's breaker check fails against the plate", chk(a.id, "breaker_max").status === "fail");
    check("the inset shows the breaker photo with its box", !$("#inset").hidden && $$("#mini-boxes .box").length === 1);
    check("the inset says the breaker is over the maximum", /against/.test($("#inset-status").textContent), $("#inset-status").textContent);
    check("the filmstrip lists every asset", $$("#strip [data-asset]").length === FI.job.assets.length);
    check("the header counts every state", /pass/.test($("#counts").textContent) && /fail/.test($("#counts").textContent));
    check("the model picker lists the recorded models", $$("#model option").length === FI.models.length);
    check("the job line names the technician", $("#jobline").textContent.indexOf(FI.cast.technician) >= 0, $("#jobline").textContent);
    check("the audit log opens with the read and the checks", state().log === 2, state().log);
    check("nothing on the opening screen is blank", !blank($("#work").textContent) && !blank($("#top").textContent),
      ($("#work").textContent.match(/undefined|null|NaN|\{[a-z_]+\}/) || [""])[0]);
  });
  attempt("access", () => {
    check("one h1 and the inspector's four headings", $$("h1").length === 1 && $$("#insp h2").length === 4);
    check("the skip link leads to the checks", $("a.skip") && $("a.skip").getAttribute("href") === "#insp" && !!$("#insp"));
    const states = FI.words.state;
    check("each thumbnail's name says its state, so color isn't the only cue",
      FI.job.assets.every((a) => $(`#strip [data-asset='${a.id}']`).textContent.indexOf(states[st(a.id)]) >= 0));
    const tabbable = $$("[data-line]").filter((b) => b.getAttribute("tabindex") === "0");
    check("the line's three positions take one stop in the tab order", tabbable.length === 1 &&
      tabbable[0].getAttribute("aria-checked") === "true");
    tabbable[0].focus();
    doc.dispatch("keydown", tabbable[0], {key: "ArrowRight"});
    flush();
    check("the arrow keys move the line and keep the focus on it", state().line === "missing" &&
      doc.activeElement && doc.activeElement.getAttribute("data-line") === "missing", state().line);
    check("the move is announced", /confidence line moved/.test($("#say").textContent), $("#say").textContent);
    click($("[data-line='partial']"));
    click($("#open-log"));
    check("opening the log moves the focus to its close button", doc.activeElement && doc.activeElement.id === "close-log");
    click($("#close-log"));
    check("closing it brings the focus back", doc.activeElement && doc.activeElement.id === "open-log",
      (doc.activeElement && (doc.activeElement.id || doc.activeElement.tagName)) + " hidden=" + $("#log").hidden);
  });
  attempt("every asset", () => {
    let ok = 0;
    for (const a of FI.job.assets) {
      click($(`[data-asset='${a.id}']`));
      const shown = FI.models.filter((m) => m.id === state().model)[0];
      const reads = shown.reads[a.photo] || {};
      const boxed = Object.keys(reads).filter((f) => reads[f].box && reads[f].status !== "absent").length;
      const good = state().asset === a.id && $$("#boxes .box").length === boxed && $$("#checks .chk").length ===
        (FI.job.designs[a.id].checks || []).length && $("#photo").getAttribute("src") === FI.photos[a.photo].src &&
        !blank($("#work").textContent) && $("#photo").getAttribute("alt").length > 10;
      ok += good ? 1 : 0;
      if (!good) { check(`asset ${a.id} draws its photo, boxes and checks`, false, `${$$("#boxes .box").length} boxes, ${boxed} reads`); }
    }
    check("every asset draws its photo, its boxes, its reads and its checks", ok === FI.job.assets.length, ok);
    click($(`[data-asset='${first}']`));
  });
  attempt("printed values", () => {
    const vals = $$("#checks .val").map((b) => b.textContent);
    const shown = FI.models.filter((x) => x.id === state().model)[0];
    const here = FI.job.assets.filter((x) => x.id === state().asset)[0];
    const printed = ((shown.reads[here.photo] || {}).model || {}).value || "";
    check("the checks show values the way the plate prints them", /-/.test(printed) && vals.some((v) => v.indexOf(printed) >= 0),
      printed + " in " + vals.join(" | "));
    const q = $$("#queue .q p").map((x) => x.textContent).join(" | ");
    check("the queue shows the printed model and the design's own wording", /DW-24P7/.test(q) && /DW-24P1/.test(q), q);
  });
  attempt("threads", () => {
    flush();
    const paths = $$("#threads path.thread");
    const boxed = $$("#reads .read").filter((r) => $(`#boxes [data-photo='${r.getAttribute("data-photo")}'][data-field='${r.getAttribute("data-field")}']`)).length;
    check("a thread runs from every boxed read to its box, plus the cross-photo thread", paths.length === boxed + 1, `${paths.length} threads, ${boxed} boxed reads`);
    check("the cross-photo thread is drawn as a failure", $$("#threads path.cross.fail").length === 1);
  });
  attempt("the confidence line", () => {
    const sent = {};
    for (const line of ["missing", "partial", "all"]) {
      click($(`[data-line='${line}']`));
      sent[line] = out().counts.sent;
      check(`the line moves to ${line}`, state().line === line && $(`[data-line='${line}']`).getAttribute("aria-checked") === "true");
    }
    check("moving the line sends more reads to a person", sent.missing <= sent.partial && sent.partial < sent.all, JSON.stringify(sent));
    check("at the top of the line every read goes to a person", sent.all === out().counts.reads);
    click($("[data-line='partial']"));
  });
  attempt("the design's breaker", () => {
    const before = state().log;
    const input = $(`[data-design='${first}/breaker']`);
    check("the breaker check carries the design's breaker as an input", !!input);
    change(input, "25");
    check("a 25 A design breaker passes the plate's maximum", chk(first, "breaker_max").status === "pass");
    check("and the breaker photo no longer matches the design", chk(first, "panel").status === "fail");
    check("so the failure moves to the panel and the asset stays red", st(first) === "fail");
    check("the edit writes one line in the log", state().log === before + 1, state().log - before);
    const again = $(`[data-design='${first}/breaker']`);
    check("the input keeps its new value after the rerun", again && again.value === "25", again && again.value);
  });
  attempt("the capacity edit", () => {
    const wh = FI.job.assets.filter((a) => (FI.job.designs[a.id].checks || []).indexOf("capacity") >= 0 && st(a.id) === "fail")[0];
    check("an asset fails on capacity", !!wh);
    if (!wh) { return; }
    click($(`[data-asset='${wh.id}']`));
    const plate = chk(wh.id, "capacity").inputs.filter((i) => i.from === "photo")[0].value;
    change($(`[data-design='${wh.id}/capacity']`), plate.replace(" GAL", " gallons"));
    check("matching the design to the plate turns the capacity check green", chk(wh.id, "capacity").status === "pass");
  });
  attempt("the person's queue", () => {
    const reads = out().queue.filter((q) => q.type === "read");
    const review = out().queue.filter((q) => q.type === "check");
    check("the queue holds a read and a model one character off", reads.length >= 1 && review.length >= 1, JSON.stringify(out().queue));
    const q = reads.filter((x) => $(`[data-accept='${x.photo}/${x.field}']`))[0] || reads[0], key = `${q.photo}/${q.field}`;
    if ($(`[data-accept='${key}']`)) {
      click($(`[data-accept='${key}']`));
    } else {
      doc.dispatch("click", $(`[data-correct='${key}']`));
      $(`[data-fix-value='${key}']`).value = FI.job.designs[q.asset][q.field] || "1";
      click($(`[data-save='${key}']`));
    }
    check("the decision is announced", $("#say").textContent === S_last(), $("#say").textContent);
    check("settling a read takes it off the queue", !out().queue.some((x) => x.photo === q.photo && x.field === q.field));
    check("and settles its asset", st(q.asset) !== "person" || out().assets[q.asset].queued.length === 0);
    const r = review[0];
    click($(`[data-approve='${r.asset}']`));
    check("approving an equal passes the model check", chk(r.asset, "model").why === "approved_by_person" && chk(r.asset, "model").status === "pass");
    check("the log records both decisions with the reviewer's name", $("#log-rows").textContent.split(FI.cast.reviewer).length >= 3);
  });
  attempt("correct a read", () => {
    const k = `${FI.job.assets.filter((a) => a.id === first)[0].photo}/max_breaker`;
    click($("#reset"));
    check("reset puts the job back", JSON.stringify(out().counts) === start, JSON.stringify(out().counts));
    click($("[data-line='all']"));
    doc.dispatch("click", $(`[data-correct='${k}']`));
    const fix = $(`[data-fix='${k}']`);
    check("correct opens a field for what the photo shows", fix && !fix.hidden);
    $(`[data-fix-value='${k}']`).value = "30";
    click($(`[data-save='${k}']`));
    check("a corrected maximum of 30 A lets the 30 A breaker pass", chk(first, "breaker_max").status === "pass");
    click($(`[data-asset='${first}']`));
    check("the corrected box is drawn as settled by a person", $$("#boxes .box.person").length >= 1,
      $$("#boxes .box").map((b) => b.className).join(" | ") + " asset " + state().asset);
    click($("#reset"));
  });
  attempt("an unreadable read", () => {
    click($("#reset"));
    click($("[data-line='all']"));
    const q = out().queue.filter((x) => x.type === "read")[0];
    const m = FI.models.filter((x) => x.id === state().model)[0];
    const k = `${q.photo}/${q.field}`, before = m.reads[q.photo][q.field];
    m.reads[q.photo][q.field] = {status: "unreadable", why: "unreadable"};
    click($("#reset"));
    const item = $(`#queue [data-q='${k}']`);
    check("a read the AI couldn't make out offers a correction and no accept",
      item && !item.querySelector("[data-accept]") && item.querySelector("[data-correct]") && !blank(item.textContent), k);
    if (before === undefined) { delete m.reads[q.photo][q.field]; } else { m.reads[q.photo][q.field] = before; }
    click($("#reset"));
  });
  attempt("wrong unit", () => {
    const r = out().queue.filter((q) => q.type === "check")[0];
    click($(`[data-wrong='${r.asset}']`));
    check("calling the wrong unit fails the model check and turns the asset red", chk(r.asset, "model").why === "wrong_unit" && st(r.asset) === "fail");
    click($("#reset"));
  });
  attempt("the audit log", () => {
    click($("#open-log"));
    check("the audit log opens with its rows", !$("#log").hidden && $$("#log-rows li").length >= 3);
    click($("#close-log"));
    check("and closes", $("#log").hidden);
  });
  attempt("how it works and the code", () => {
    check("How it works and the tour sit side by side as two buttons", $("#open-how").getAttribute("class") === "btn" &&
      $("#tour-start").getAttribute("class") === "btn" && $("#open-how").parentNode === $("#tour-start").parentNode);
    click($("#open-how"));
    check("How it works opens in place of the job", state().view === "how" && !$("#how").hidden && $("#work").hidden);
    check("How it works shows the scoreboard and the five featured files", $$("#how table").length >= 3 && $$("#how .featured [data-file]").length === 5);
    check("the code view is already open on the confirmation step, with no button to open it",
      !$("#codeview").hidden && /confirmation step/.test($("#code-text").textContent) && !$("#open-code"));
    click($("#how [data-file='engine/rules.py']"));
    check("a featured file opens in the code view", state().code === "engine/rules.py" && /installer's design rules/.test($("#code-text").textContent));
    click($("#open-how"));
    check("and the job comes back", state().view === "job" && !$("#work").hidden);
    click($("#open-how"));
    check("How it works opens again on the file last read", !$("#codeview").hidden && state().code === "engine/rules.py" &&
      /installer's design rules/.test($("#code-text").textContent));
    click($("#open-how"));
  });
  attempt("the tour", () => {
    click($("#tour-start"));
    check("the tour moves the focus to its next button", doc.activeElement && doc.activeElement.getAttribute("data-present") === "next");
    let ok = 0;
    for (let n = 1; n <= FIP.steps; n++) {
      const box = $("#presenter");
      if (state().present === n && !box.hidden && $$(".spot").length === 1 && !blank(box.textContent) && box.textContent.length > 40) { ok += 1; }
      if (n < FIP.steps) { click($("[data-present='next']")); }
    }
    check("every tour step spotlights one thing and explains it", ok === FIP.steps, `${ok} of ${FIP.steps}`);
    click($("[data-present='back']"));
    check("back steps the tour back", state().present === FIP.steps - 1);
    click($("[data-present='close']"));
    check("closing the tour clears the spotlight", state().present === 0 && $$(".spot").length === 0 && $("#presenter").hidden);
    check("and gives the focus back to the tour button", doc.activeElement && doc.activeElement.id === "tour-start");
    if (state().view !== "job") { click($("#open-how")); }
  });
  attempt("the brand", () => {
    const other = FI.job.assets.map((a) => a.id).filter((id) => id !== first)[0];
    click($(`#strip [data-asset='${other}']`));
    click($("#open-log"));
    click($("#open-how"));
    let ev = doc.dispatch("click", $(".brand"));
    flush();
    check("the brand stays in the app and goes back to the job as it opens", ev.defaultPrevented && state().view === "job" &&
      state().asset === first && $("#log").hidden && !$("#work").hidden, JSON.stringify(state()));
    click($("#tour-start"));
    ev = doc.dispatch("click", $(".brand"));
    flush();
    check("the brand ends the tour", ev.defaultPrevented && state().present === 0 && $$(".spot").length === 0);
    ev = doc.dispatch("click", $(".brand"), {metaKey: true});
    check("a command-click on the brand opens the app's own address", !ev.defaultPrevented && $(".brand").getAttribute("href") === "./");
  });
  attempt("the footer", () => {
    const bar = $("footer.foot p"), inner = $("#insp .foot-in p");
    check("the checks screen ends with the footer for a phone", bar && inner && inner.textContent === bar.textContent &&
      $$("#insp .foot-in a").length === 2);
  });
  attempt("the phone screens", () => {
    for (const s of ["strip", "insp", "stage"]) {
      click($(`[data-screen='${s}']`));
      check(`the ${s} tab marks its screen`, state().screen === s && $(`[data-screen='${s}']`).getAttribute("aria-current") === "true");
    }
  });
  attempt("the address", () => {
    check("the address carries the asset, the model and the line", /a=.+&m=.+&l=partial/.test(win.location.hash), win.location.hash);
  });
}

check("the page's scripts ran without errors", errors.length === 0, errors.join(" | "));
const failed = checks.filter((c) => !c.ok);
failed.forEach((c) => console.log(`FAIL ${c.name} ${c.detail}`));
console.log(`${checks.length - failed.length} of ${checks.length} page checks pass`);
process.exit(failed.length ? 1 : 0);

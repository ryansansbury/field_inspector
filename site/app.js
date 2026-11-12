/* The Field Inspector's page script. It opens the job, draws each photo with its boxes, runs the installer's design
   rules through site/rules.js on every change, and keeps the person's queue and the audit log. Everything comes from
   window.FI (site/data.js), every word from WORDS.md, and nothing calls the network. A classic script with no framework,
   and no inline styles, since positions are set through each element's style property after it's drawn. */
(function (win) {
  "use strict";
  var doc = win.document, FI = win.FI, R = win.FIRules, N = win.FINorm;
  if (!FI || !R || !N || !doc) { return; }
  var U = FI.words;
  var FIP = win.FIP = {};
  var S = {asset: null, model: FI.route, line: FI.line["default"], person: {reads: {}, checks: {}}, designs: null,
    view: "job", zoom: "fit", words: false, present: 0, screen: "stage", log: [], out: null, hot: null, code: false};
  var EDITABLE = ["model", "capacity", "refrigerant", "volts", "phase", "breaker"];
  var KIND_OF = {model: "code", capacity: "capacity", refrigerant: "refrigerant", volts: "volts", phase: "phase", breaker: "amps"};

  /* ------------------------------------------------------------------ helpers */
  function $(sel, root) { return (root || doc).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(sel)); }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[c];
    });
  }
  function word(key, fill) {
    var t = U[key];
    if (t === undefined) { throw new Error("no words entry for ui." + key); }
    return String(t).replace(/\{(\w+)\}/g, function (m, k) { return fill && fill[k] !== undefined ? fill[k] : m; });
  }
  function row(key, name, fill) {
    var t = (U[key] || {})[name];
    if (t === undefined) { return name; }
    return String(t).replace(/\{(\w+)\}/g, function (m, k) { return fill && fill[k] !== undefined ? fill[k] : m; });
  }
  function lower(s) { s = String(s || ""); return s.charAt(0).toLowerCase() + s.slice(1); }
  function cap(s) { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); }
  function copy(x) { return JSON.parse(JSON.stringify(x)); }
  function calm() { return !!(win.matchMedia && win.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function phone() { return !!(win.matchMedia && win.matchMedia("(max-width: 900px)").matches); }
  function raf(fn) { return (win.requestAnimationFrame || function (f) { return win.setTimeout(f, 16); })(fn); }
  function f1(x) { return String(Math.round(x * 10) / 10); }
  function clock() { var d = new Date(); return (d.getHours() % 12 || 12) + "." + ("0" + d.getMinutes()).slice(-2); }

  /* ------------------------------------------------------------------ the data */
  function model() { return FI.models.filter(function (m) { return m.id === S.model; })[0] || FI.models[0]; }
  function asset(id) { return FI.job.assets.filter(function (a) { return a.id === id; })[0]; }
  function kind(a) { return row("kinds", a.kind); }
  function field(f) { return row("fields", f); }
  function reads(photo) { return model().reads[photo] || {}; }
  function run() {
    S.out = R.evaluate({assets: FI.job.assets, designs: S.designs}, model().reads, S.person, S.line, FI.cfg);
    return S.out;
  }
  function stateOf(id) { return S.out.assets[id].state; }
  function checksOf(id) { return S.out.assets[id].checks; }
  function settled(photo, f) {
    var act = S.person.reads[photo + "/" + f];
    return act ? act : null;
  }
  function shown(photo, f) {
    var act = settled(photo, f), r = reads(photo)[f] || {};
    return act && act.action === "correct" ? act.value : r.value;
  }
  function failing(a) {
    var out = {};
    checksOf(a.id).forEach(function (c) {
      if (c.status !== "fail" || c.waits.length) { return; }
      c.inputs.forEach(function (i) { if (i.from === "photo") { out[i.photo + "/" + i.field] = 1; } });
    });
    return out;
  }
  function firstAsset() {
    var as = FI.job.assets, i;
    for (i = 0; i < as.length; i++) {
      if (as[i].breaker_photo && checksOf(as[i].id).some(function (c) {
        return (c.rule === "breaker_max" || c.rule === "panel") && c.status === "fail";
      })) { return as[i].id; }
    }
    for (i = 0; i < as.length; i++) { if (stateOf(as[i].id) === "fail") { return as[i].id; } }
    return as[0].id;
  }

  /* ------------------------------------------------------------------ the address */
  function writeHash() {
    var h = "#a=" + S.asset + "&m=" + S.model + "&l=" + S.line + (S.view === "how" ? "&v=how" : "") +
      (S.present ? "&t=" + S.present : "");
    if (win.history && win.history.replaceState) { win.history.replaceState(null, "", h); }
  }
  function readHash(h) {
    var out = {};
    String(h || "").replace(/^#/, "").split("&").forEach(function (p) {
      var kv = p.split("=");
      if (kv.length === 2) { out[kv[0]] = decodeURIComponent(kv[1]); }
    });
    if (out.m && FI.models.some(function (m) { return m.id === out.m; })) { S.model = out.m; }
    if (out.l && R.SENT[out.l]) { S.line = out.l; }
    run();
    if (out.a && asset(out.a)) { S.asset = out.a; }
    if (out.v === "how") { S.view = "how"; }
    return out;
  }

  /* ------------------------------------------------------------------ the header and the filmstrip */
  function weekday(iso) {
    var p = String(iso || "").split("-");
    if (p.length !== 3) { return ""; }
    return row("weekdays", String(new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])).getUTCDay()));
  }
  function renderTop() {
    var c = S.out.counts, cast = FI.cast;
    $("#jobline").innerHTML = "<span class='l1'><b>" + esc(word("top.job", {number: FI.job.number})) + "</b><span>" +
      esc(word("top.by", {technician: cast.technician, weekday: weekday(FI.job.day)})) + "</span></span><span class='l2'>" +
      esc(word("top.kind")) + "</span>";
    $("#counts").innerHTML = "<span class='st pass'>✓ " + esc(word("count.pass", {n: c.pass})) + "</span><span class='st fail'>✕ " +
      esc(word("count.fail", {n: c.fail})) + "</span><span class='st review'>● " + esc(word("count.person", {n: c.person})) + "</span>";
    var sel = $("#model");
    if (!sel.innerHTML) {
      sel.innerHTML = FI.models.map(function (m) { return "<option value='" + esc(m.id) + "'>" + esc(m.label) + "</option>"; }).join("");
    }
    sel.value = S.model;
    $$("option", sel).forEach(function (o) {
      if (o.getAttribute("value") === S.model) { o.setAttribute("selected", ""); } else { o.removeAttribute("selected"); }
    });
  }
  function renderStrip() {
    $("#strip").innerHTML = FI.job.assets.map(function (a) {
      var p = FI.photos[a.photo], on = a.id === S.asset;
      return "<button type='button' class='th st-" + stateOf(a.id) + (on ? " on" : "") + "' data-asset='" + esc(a.id) +
        "' aria-current='" + (on ? "true" : "false") + "'><img src='" + esc(p.thumb) + "' alt='' loading='lazy'><i></i><span>" +
        esc(kind(a)) + "<span class='sr'> " + esc(row("state", stateOf(a.id))) + "</span></span></button>";
    }).join("");
  }

  /* ------------------------------------------------------------------ the light table */
  function boxHtml(cls, b, attrs, tag) {
    return "<div class='box " + cls + "' data-box='" + b.join(",") + "'" + (attrs || "") + ">" +
      (tag ? "<span class='tag'>" + esc(tag) + "</span>" : "") + "</div>";
  }
  function place(root) {
    $$("[data-box]", root).forEach(function (el) {
      var b = el.getAttribute("data-box").split(",").map(parseFloat);
      el.style.left = (b[0] * 100) + "%";
      el.style.top = (b[1] * 100) + "%";
      el.style.width = ((b[2] - b[0]) * 100) + "%";
      el.style.height = ((b[3] - b[1]) * 100) + "%";
    });
  }
  function boxClass(photo, f, r, fails) {
    var act = settled(photo, f);
    if (fails[photo + "/" + f]) { return "fail"; }
    if (act) { return "person"; }
    return "lv-" + (r.level || "missing") + (r.approx ? " approx" : "");
  }
  function photoBoxes(photo, a) {
    var rs = reads(photo), fails = failing(a), out = "";
    Object.keys(rs).forEach(function (f) {
      var r = rs[f];
      if (!r.box || r.status === "absent") { return; }
      var v = shown(photo, f), cls = boxClass(photo, f, r, fails);
      out += boxHtml(cls, r.box, " data-field='" + esc(f) + "' data-photo='" + esc(photo) + "'",
        field(f) + (cls === "fail" && v ? " " + v : ""));
    });
    return out;
  }
  function renderStage() {
    var a = asset(S.asset), p = FI.photos[a.photo], rs = reads(a.photo), idx = FI.job.assets.indexOf(a) + 1;
    var vals = Object.keys(rs).filter(function (f) { return rs[f].status !== "absent"; });
    var found = vals.filter(function (f) { return rs[f].level === "found"; }).length;
    $("#cap-title").innerHTML = esc(word("stage.caption", {kind: kind(a), place: row("places", a.place)})) +
      " <span class='count'>· " + esc(word("stage.count", {n: idx, total: FI.job.assets.length})) + "</span>";
    $("#cap-note").textContent = word("stage.note", {seconds: f1((model().seconds || {})[a.photo] || 0), found: found, total: vals.length});
    var img = $("#photo");
    if (img.getAttribute("src") !== p.src) { img.setAttribute("src", p.src); }
    img.setAttribute("alt", word("stage.alt", {kind: lower(kind(a)), shot: row("shots", p.shot)}));
    img.setAttribute("width", p.w);
    img.setAttribute("height", p.h);
    $("#boxes").innerHTML = photoBoxes(a.photo, a);
    $("#boxes").classList.toggle("fresh", S.drawn !== S.asset && !calm());
    S.drawn = S.asset;
    $("#ownwords").innerHTML = S.words ? p.words.map(function (w) {
      return "<div class='word' data-box='" + w.slice(1).join(",") + "' title='" + esc(w[0]) + "'></div>";
    }).join("") : "";
    $("#ownwords").hidden = !S.words;
    place($("#print"));
    $$("[data-zoom]").forEach(function (b) {
      b.textContent = word("zoom." + b.getAttribute("data-zoom"));
      b.classList.toggle("on", b.getAttribute("data-zoom") === S.zoom);
      b.setAttribute("aria-pressed", b.getAttribute("data-zoom") === S.zoom ? "true" : "false");
    });
    $("#own-words").textContent = word(S.words ? "zoom.words_off" : "zoom.words");
    $("#own-words").setAttribute("aria-pressed", S.words ? "true" : "false");
    renderInset(a);
    sizePrint();
  }
  function sizePrint() {
    var a = asset(S.asset), p = FI.photos[a.photo], desk = $("#table"), pr = $("#print");
    if (!desk || !pr) { return; }
    desk.classList.toggle("full", S.zoom === "full");
    if (S.zoom === "full" || phone()) { pr.style.width = S.zoom === "full" ? p.w + "px" : ""; pr.style.height = ""; return; }
    var r = desk.getBoundingClientRect(), border = 24;
    var scale = Math.min((r.width - border - 24) / p.w, (r.height - border - 24) / p.h);
    if (!(scale > 0)) { return; }
    scale = clearOf(scale, r, p);
    pr.style.width = Math.round(p.w * scale + border) + "px";
    pr.style.height = Math.round(p.h * scale + border) + "px";
  }
  /* The largest scale, down to about 60% of the fit, at which no read value or the tag above it sits under the breaker
     inset or the zoom buttons. The print stays centered on the table, so shrinking it pulls every corner inward. */
  function clearOf(scale, r, p) {
    var cs = win.getComputedStyle ? win.getComputedStyle($("#table")) : null;
    var padTop = cs ? parseFloat(cs.paddingTop) || 0 : 0, padBottom = cs ? parseFloat(cs.paddingBottom) || 0 : 0;
    var cx = r.left + r.width / 2, cy = r.top + padTop + (r.height - padTop - padBottom) / 2;
    var blocks = ["#inset", "#zoomtools"].map(function (s) { return $(s); }).filter(function (el) { return el && !el.hidden; })
      .map(function (el) { return el.getBoundingClientRect(); });
    var vals = $$("#boxes .box").map(function (b) { return (b.getAttribute("data-box") || "").split(",").map(Number); })
      .filter(function (b) { return b.length === 4; });
    function hit(s) {
      var w = p.w * s, h = p.h * s, left = cx - w / 2, top = cy - h / 2;
      return vals.some(function (b) {
        var v = {left: left + b[0] * w, right: left + b[2] * w, top: top + b[1] * h - 18, bottom: top + b[3] * h};
        return blocks.some(function (k) { return over(v, k); });
      });
    }
    for (var i = 0, s = scale; i < 13; i++, s *= 0.96) { if (!hit(s)) { return s; } }
    return scale;
  }
  function insetFacts(a) {
    var cs = checksOf(a.id), max = null, installed = null, over = false;
    cs.forEach(function (c) {
      c.inputs.forEach(function (i) {
        if (i.field === "max_breaker" && i.from === "photo") { max = i.value; }
        if (i.field === "breaker" && i.from === "photo") { installed = i.value; }
      });
      if ((c.rule === "breaker_max" || c.rule === "panel") && c.status === "fail") { over = true; }
    });
    return {max: max, installed: installed, over: over};
  }
  function renderInset(a) {
    var box = $("#inset");
    if (!a.breaker_photo || !FI.photos[a.breaker_photo]) { box.hidden = true; return; }
    var p = FI.photos[a.breaker_photo], r = reads(a.breaker_photo).breaker || {}, facts = insetFacts(a);
    box.hidden = false;
    box.classList.toggle("over", facts.over);
    var status = facts.over && facts.max ? word("inset.over", {installed: facts.installed || "?", max: facts.max}) :
      word("inset.ok", {installed: facts.installed || "?"});
    $("#inset-title").textContent = word("inset.title");
    $("#inset-status").textContent = status;
    var img = $("#mini-photo");
    if (img.getAttribute("src") !== p.src) { img.setAttribute("src", p.src); }
    img.setAttribute("alt", word("inset.alt", {kind: lower(kind(a))}));
    $("#mini-boxes").innerHTML = r.box ? boxHtml(facts.over ? "fail" : boxClass(a.breaker_photo, "breaker", r, {}), r.box,
      " data-field='breaker' data-photo='" + esc(a.breaker_photo) + "'", "") : "";
    cropInset(p, r.box);
  }
  function cropInset(p, b) {
    var mini = $("#mini"), img = $("#mini-photo"), boxes = $("#mini-boxes");
    var r = mini.getBoundingClientRect(), W = r.width || 300, H = r.height || 130;
    b = b || [0.4, 0.4, 0.6, 0.6];
    var bw = (b[2] - b[0]) * p.w, bh = (b[3] - b[1]) * p.h;
    var k = Math.min(W * 0.34 / bw, H * 0.5 / bh, 4);
    var cx = (b[0] + b[2]) / 2 * p.w * k, cy = (b[1] + b[3]) / 2 * p.h * k;
    var left = W / 2 - cx, top = H / 2 - cy;
    [img, boxes].forEach(function (el) {
      el.style.width = Math.round(p.w * k) + "px";
      el.style.height = Math.round(p.h * k) + "px";
      el.style.left = Math.round(left) + "px";
      el.style.top = Math.round(top) + "px";
    });
    place(boxes);
  }

  /* ------------------------------------------------------------------ the inspector */
  function levelText(photo, f, r) {
    var act = settled(photo, f);
    if (act) { return row("levels", "person"); }
    if (r.status === "absent") { return cap(row("why", "absent")); }
    var why = r.held ? row("why", "held") : row("why", r.why || "none", {seen: r.seen || ""});
    return (r.level || "missing") === "missing" ? cap(why) : row("levels", r.level) + " " + why;
  }
  function renderReads(a) {
    var rs = reads(a.photo), need = needed(a), out = "";
    Object.keys(rs).sort(function (x, y) { return FI.fields.indexOf(x) - FI.fields.indexOf(y); }).forEach(function (f) {
      var r = rs[f];
      if (r.status === "absent" && need.indexOf(f) < 0) { return; }
      var act = settled(a.photo, f), lv = act ? "person" : r.status === "absent" ? "missing" : (r.level || "missing");
      var v = shown(a.photo, f);
      out += "<div class='read lv-" + lv + "' data-field='" + esc(f) + "' data-photo='" + esc(a.photo) + "' tabindex='0'>" +
        "<span class='k'>" + esc(field(f)) + "</span><span class='v'>" + esc(v || word("check.none")) + "</span><span class='conf'><span class='bar'><i></i></span>" +
        "<span class='lvl'>" + esc(levelText(a.photo, f, r)) + "</span></span></div>";
    });
    $("#reads").innerHTML = out;
  }
  function needed(a) {
    var out = [];
    (S.designs[a.id].checks || []).forEach(function (rule) {
      var r = FI.cfg.rules[rule];
      if (rule === "panel" || !r) { return; }
      r.fields.forEach(function (f) { if ((r.optional || []).indexOf(f) < 0 && out.indexOf(f) < 0) { out.push(f); } });
    });
    return out;
  }
  function renderLine() {
    var pos = U["line.positions"], order = ["all", "partial", "missing"], at = order.indexOf(S.line);
    $("#seg").innerHTML = ["found", "partial", "missing"].map(function (lv, i) {
      var key = order[i], shaded = i >= at;
      return "<button type='button' role='radio' class='" + (shaded ? "on" : "") + "' data-line='" + key + "' aria-checked='" +
        (key === S.line ? "true" : "false") + "' tabindex='" + (key === S.line ? "0" : "-1") + "'>" + esc(pos[lv === "found" ? "all" : lv]) + "</button>";
    }).join("");
    $("#line-note").textContent = word("line.note", {sent: S.out.counts.sent, reads: S.out.counts.reads});
  }
  function inputHtml(a, i, c) {
    if (i.from === "design") {
      if (EDITABLE.indexOf(i.field) < 0) { return ""; }
      var raw = S.designs[a.id][i.field];
      return "<label class='inp'><span>" + esc(word("check.design")) + "</span><input class='in' data-design='" + esc(a.id + "/" + i.field) +
        "' value='" + esc(raw === undefined || raw === null ? "" : raw) + "' aria-label='" + esc(word("check.design") + " " + field(i.field)) + "'></label>";
    }
    var label = i.photo === a.photo ? word("check.plate") : word("check.photo");
    var waits = c.waits.indexOf(i.photo + "/" + i.field) >= 0, printed = i.value ? shown(i.photo, i.field) || i.value : "";
    return "<button type='button' class='val" + (waits ? " waits" : "") + "' data-field='" + esc(i.field) + "' data-photo='" + esc(i.photo) + "'><span>" +
      esc(label) + "</span>" + esc(printed || word("check.none")) + "</button>";
  }
  function renderChecks(a) {
    $("#checks").innerHTML = checksOf(a.id).map(function (c) {
      var st = c.status;
      var optional = (FI.cfg.rules[c.rule] || {}).optional || [];
      var idle = optional.filter(function (f) { return c.inputs.every(function (i) { return i.field !== f || !i.value; }); });
      var ins = c.inputs.filter(function (i) { return idle.indexOf(i.field) < 0; })
        .map(function (i) { return inputHtml(a, i, c); }).filter(Boolean).join("");
      return "<div class='chk st-" + st + "' data-rule='" + esc(c.rule) + "'><p class='name'>" + esc(row("rules", c.rule)) +
        "<span class='st " + (st === "pass" ? "pass" : st === "fail" ? "fail" : "review") + "'>" + esc(row("status", st)) + "</span></p>" +
        (ins ? "<div class='ins'>" + ins + "</div>" : "") + "<p class='why'>" + esc(row("check.why", c.why)) + "</p>" +
        (c.waits.length ? "<p class='waits'>" + esc(word("check.waits")) + "</p>" : "") + "</div>";
    }).join("");
  }
  function queueText(q) {
    if (q.type === "check") {
      var c = checksOf(q.asset).filter(function (x) { return x.rule === q.rule; })[0], d = "", p = "";
      c.inputs.forEach(function (i) {
        if (i.from === "design") { d = S.designs[q.asset][i.field] || i.value; } else { p = shown(i.photo, i.field) || i.value; }
      });
      return {title: word("queue.check", {asset: kind(asset(q.asset))}), body: word("queue.design", {plate: p, design: d})};
    }
    var r = reads(q.photo)[q.field] || {status: "absent"};
    var why = r.status === "absent" ? row("why", "absent") : r.held ? row("why", "held") : row("why", r.why || "none", {seen: r.seen || ""});
    return {title: word("queue.read", {field: field(q.field), asset: lower(kind(asset(q.asset)))}),
      body: r.value ? word("queue.readas", {value: r.value, why: why}) : word("queue.noread", {why: cap(why)})};
  }
  function renderQueue() {
    var qs = S.out.queue;
    if (!qs.length) { $("#queue").innerHTML = "<p class='empty'>" + esc(word("insp.queue_empty")) + "</p>"; return; }
    $("#queue").innerHTML = qs.map(function (q) {
      var t = queueText(q), key = q.type === "check" ? q.asset + "/" + q.rule : q.photo + "/" + q.field;
      var blind = q.type !== "check" && (reads(q.photo)[q.field] || {}).status === "unreadable";
      var acts = q.type === "check" ?
        "<button type='button' class='a' data-approve='" + esc(q.asset) + "'>" + esc(word("queue.approved")) + "</button>" +
        "<button type='button' data-wrong='" + esc(q.asset) + "'>" + esc(word("queue.wrong")) + "</button>" :
        (blind ? "" : "<button type='button' class='a' data-accept='" + esc(key) + "'>" + esc(word("queue.accept")) + "</button>") +
        "<button type='button'" + (blind ? " class='a'" : "") + " data-correct='" + esc(key) + "'>" + esc(word("queue.correct")) + "</button>" +
        "<span class='fix' data-fix='" + esc(key) + "' hidden><input data-fix-value='" + esc(key) + "' placeholder='" +
        esc(word("queue.placeholder")) + "' aria-label='" + esc(word("queue.placeholder")) + "'><button type='button' data-save='" +
        esc(key) + "'>" + esc(word("queue.save")) + "</button></span>";
      return "<div class='q" + (q.asset === S.asset ? " here" : "") + "' data-q='" + esc(key) + "'><button type='button' class='qt' data-asset='" +
        esc(q.asset) + "'>" + esc(t.title) + "</button><p>" + esc(t.body) + "</p><div class='acts'>" + acts + "</div></div>";
    }).join("");
  }
  function renderInspector() {
    var a = asset(S.asset);
    $("#h-reads").textContent = word("insp.reads");
    $("#h-line").textContent = word("insp.line");
    $("#h-checks").textContent = word("insp.checks");
    $("#h-queue").textContent = word("insp.queue");
    $("#reset").textContent = word("insp.reset");
    renderReads(a);
    renderLine();
    renderChecks(a);
    renderQueue();
  }

  /* ------------------------------------------------------------------ the audit log */
  function log(who, text) {
    S.log.push({who: who, text: text, at: clock()});
    renderLog();
    var say = $("#say");
    if (say) { say.textContent = text; }
  }
  function firstLog() {
    var m = model(), c = S.out.counts;
    S.log = [];
    log("ai", word("log.read", {model: m.label, n: Object.keys(m.reads).length, date: m.date || FI.built}));
    log("code", word("log.checks", {pass: c.pass, fail: c.fail, person: c.person}));
  }
  function renderLog() {
    var el = $("#log-rows");
    if (!el) { return; }
    $("#log-title").textContent = word("log.title");
    $("#close-log").textContent = word("log.close");
    el.innerHTML = S.log.length ? S.log.map(function (e) {
      return "<li class='who-" + esc(e.who) + "'><time>" + esc(e.at) + "</time><b>" + esc(row("log.who", e.who, {reviewer: FI.cast.reviewer})) +
        "</b><span>" + esc(e.text) + "</span></li>";
    }).join("") : "<li>" + esc(word("log.empty")) + "</li>";
  }

  /* ------------------------------------------------------------------ the threads */
  /* A curve from each read in the inspector to its box on the photo, and a bold one from the plate's maximum to the
     breaker in the inset when the circuit check fails. A thread lights when its read or its box is pointed at. */
  var T = {queued: false};
  function soonThreads() {
    if (T.queued) { return; }
    T.queued = true;
    raf(function () { T.queued = false; drawThreads(); drawTour(); });
  }
  function curve(ax, ay, bx, by, cls, key) {
    var g = (bx - ax) * 0.5;
    return "<path class='thread " + cls + "' data-k='" + esc(key) + "' d='M" + f1(ax) + " " + f1(ay) + " C" + f1(ax + g) + " " + f1(ay) + " " +
      f1(bx - g) + " " + f1(by) + " " + f1(bx) + " " + f1(by) + "'/><circle class='tdot " + cls + "' cx='" + f1(ax) + "' cy='" + f1(ay) +
      "' r='3'/><circle class='tdot " + cls + "' cx='" + f1(bx) + "' cy='" + f1(by) + "' r='3'/>";
  }
  function over(a, b) { return a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1; }
  function fitTags() {
    /* A tag that would cover another value or tag on a dense plate waits until its read is pointed at. A failing
       value's tag always shows, set smaller and closer to its box when the room above it is tight. */
    var boxes = $$("#boxes .box"), shown = [];
    var tags = $$("#boxes .tag").sort(function (x, y) {
      return (y.parentNode.classList.contains("fail") ? 1 : 0) - (x.parentNode.classList.contains("fail") ? 1 : 0);
    });
    function hits(t) {
      var r = t.getBoundingClientRect();
      return boxes.some(function (b) { return b !== t.parentNode && over(r, b.getBoundingClientRect()); }) ||
        shown.some(function (s) { return over(r, s); });
    }
    tags.forEach(function (t) {
      t.classList.remove("tight");
      t.classList.remove("snug");
      if (hits(t)) { t.classList.add(t.parentNode.classList.contains("fail") ? "snug" : "tight"); }
      if (!t.classList.contains("tight")) { shown.push(t.getBoundingClientRect()); }
    });
  }
  function drawThreads() {
    var svg = $("#threads"), work = $("#work");
    if (S.view === "job") { fitTags(); }
    if (!svg || !work || S.view !== "job" || phone() || !work.getBoundingClientRect) { if (svg) { svg.innerHTML = ""; } return; }
    var w = work.getBoundingClientRect(), out = "";
    var stage = $("#stage").getBoundingClientRect(), desk = $("#table").getBoundingClientRect(), pane = $("#insp").getBoundingClientRect();
    $$("#reads .read").forEach(function (rowEl) {
      var key = rowEl.getAttribute("data-photo") + "/" + rowEl.getAttribute("data-field");
      var box = $("#boxes [data-photo='" + rowEl.getAttribute("data-photo") + "'][data-field='" + rowEl.getAttribute("data-field") + "']");
      if (!box) { return; }
      var rr = rowEl.getBoundingClientRect(), br = box.getBoundingClientRect();
      var rowMid = rr.top + rr.height / 2, boxMid = br.top + br.height / 2;
      if (!rr.height || br.right < stage.left || br.left > stage.right) { return; }
      if (rowMid < pane.top || rowMid > pane.bottom || boxMid < desk.top || boxMid > desk.bottom) { return; }
      out += curve(br.right - w.left, br.top + br.height / 2 - w.top, rr.left - w.left, rr.top + rr.height / 2 - w.top,
        box.className.replace("box", "").trim(), key);
    });
    var a = asset(S.asset), facts = insetFacts(a);
    var maxBox = $("#boxes [data-field='max_breaker']"), brk = $("#mini-boxes [data-field='breaker']");
    if (a.breaker_photo && maxBox && brk && !$("#inset").hidden) {
      var m = maxBox.getBoundingClientRect(), k = brk.getBoundingClientRect(), mMid = m.top + m.height / 2;
      if (mMid >= desk.top && mMid <= desk.bottom) {
        out += curve(m.right - w.left, mMid - w.top, k.left - w.left, k.top + k.height / 2 - w.top,
          "cross" + (facts.over ? " fail" : ""), "cross");
      }
    }
    svg.setAttribute("viewBox", "0 0 " + f1(w.width) + " " + f1(w.height));
    svg.innerHTML = out;
    svg.classList.toggle("fresh", T.last !== S.asset && !calm());
    T.last = S.asset;
    if (S.hot) { light(S.hot); }
  }
  function light(key) {
    S.hot = key;
    $$(".hot").forEach(function (el) { el.classList.remove("hot"); });
    if (!key) { return; }
    var parts = key.split("/");
    $$("[data-photo='" + parts[0] + "'][data-field='" + parts[1] + "']").forEach(function (el) { el.classList.add("hot"); });
    $$("#threads [data-k='" + key + "']").forEach(function (el) { el.classList.add("hot"); });
  }

  /* ------------------------------------------------------------------ rendering and actions */
  function renderAll() {
    run();
    renderTop();
    renderStrip();
    renderStage();
    renderInspector();
    renderLog();
    renderTabs();
    showView();
    writeHash();
    soonThreads();
  }
  function select(id) {
    if (!asset(id)) { return; }
    S.asset = id;
    renderAll();
    if (phone()) { toScreen("stage", true); }
  }
  function keepFocus(attr, value, fn) {
    var el = doc.activeElement, caret = el && el.selectionStart;
    fn();
    var again = $("[" + attr + "='" + value + "']");
    if (again && again.focus) {
      again.focus();
      if (caret !== undefined && caret !== null && again.setSelectionRange) { again.setSelectionRange(caret, caret); }
    }
  }
  /* Typing reruns the checks on every keystroke, and the log gets one line when the edit is done, with the value from
     before the typing started. */
  function setDesign(key, value, commit) {
    var parts = key.split("/"), d = S.designs[parts[0]];
    S.editing = S.editing || {};
    if (!(key in S.editing)) { S.editing[key] = d[parts[1]]; }
    d[parts[1]] = value;
    keepFocus("data-design", key, renderAll);
    if (commit) {
      var before = S.editing[key];
      delete S.editing[key];
      if (String(before) !== String(value)) {
        log("person", word("log.design", {field: lower(field(parts[1])), asset: lower(kind(asset(parts[0]))),
          before: before === undefined || before === null || before === "" ? "·" : before, after: value || "·"}));
      }
    }
  }
  function act(key, action, value) {
    var parts = key.split("/"), photo = parts[0], f = parts[1], r = reads(photo)[f] || {};
    var owner = FI.job.assets.filter(function (a) { return a.photo === photo || a.breaker_photo === photo; })[0];
    var who = {reviewer: FI.cast.reviewer, field: lower(field(f)), asset: lower(kind(owner))};
    if (action === "correct") {
      S.person.reads[key] = {action: "correct", value: value};
      log("person", r.value ? word("log.correct", Object.assign(who, {before: r.value, after: value})) :
        word("log.typed", Object.assign(who, {after: value})));
    } else {
      S.person.reads[key] = {action: "accept"};
      log("person", r.status === "read" ? word("log.accept", Object.assign(who, {value: r.value})) : word("log.absent", who));
    }
    renderAll();
  }
  function decide(assetId, choice) {
    var c = checksOf(assetId).filter(function (x) { return x.rule === "model"; })[0], plate = "", design = "";
    c.inputs.forEach(function (i) {
      if (i.from === "design") { design = S.designs[assetId][i.field] || i.value; } else { plate = shown(i.photo, i.field) || i.value; }
    });
    S.person.checks[assetId + "/model"] = choice;
    var fill = {reviewer: FI.cast.reviewer, asset: lower(kind(asset(assetId))), value: plate, design: design};
    log("person", word(choice === "approved" ? "log.approved" : "log.wrong", fill));
    renderAll();
  }
  function setLine(line) {
    if (!R.SENT[line] || line === S.line) { return; }
    S.line = line;
    renderAll();
    log("person", word("log.line", {sent: S.out.counts.sent}));
  }
  function setModel(id) {
    S.model = id;
    S.person = {reads: {}, checks: {}};
    renderAll();
    log("person", word("log.model", {model: model().label}));
  }
  function reset() {
    S.person = {reads: {}, checks: {}};
    S.designs = copy(FI.job.designs);
    S.line = FI.line["default"];
    run();
    firstLog();
    log("person", word("log.reset"));
    renderAll();
  }

  /* ------------------------------------------------------------------ views, the log sheet and the code */
  function showView() {
    var how = S.view === "how";
    $("#how").hidden = !how;
    $("#work").hidden = how;
    var b = $("#open-how");
    b.textContent = how ? b.getAttribute("data-back") : b.getAttribute("data-how");
    doc.body.classList.toggle("on-how", how);
    renderTabs();
    /* The code view opens with How it works, on the file last read or the confirmation step. */
    if (how) { openFile(S.code || "engine/confirm.py"); }
  }
  function setView(v) {
    S.view = v;
    showView();
    writeHash();
    soonThreads();
    if (v === "how" && doc.body) { doc.body.scrollTop = 0; if (doc.scrollingElement) { doc.scrollingElement.scrollTop = 0; } }
  }
  function openLog(on, keep) {
    var was = !$("#log").hidden;
    $("#log").hidden = !on;
    renderLog();
    if (keep) { return; }
    if (on && !was) { $("#close-log").focus(); }
    if (!on && was) { $("#open-log").focus(); }
  }
  function loadCode(then) {
    if (win.FICODE) { then(); return; }
    var s = doc.createElement("script");
    s.setAttribute("src", "code.js");
    s.onload = then;
    doc.head.appendChild(s);
  }
  function openFile(path) {
    loadCode(function () {
      var C = win.FICODE;
      if (!C || !C.files[path]) { return; }
      $("#codeview").hidden = false;
      $("#code-tree").innerHTML = Object.keys(C.files).sort().map(function (p) {
        return "<button type='button' class='" + (p === path ? "on" : "") + "' data-file='" + esc(p) + "'>" + esc(p) + "</button>";
      }).join("");
      $("#code-text").textContent = C.files[path];
      S.code = path;
    });
  }

  /* ------------------------------------------------------------------ the tour */
  var STEPS = [
    function () { setView("job"); openLog(false, true); return "#strip"; },
    function () { setView("job"); openLog(false, true); return "#print"; },
    function () { setView("job"); openLog(false); select(defaultAsset()); return "#inset"; },
    function () { setView("job"); openLog(false, true); return "#reads"; },
    function () { setView("job"); openLog(false, true); return "#line"; },
    function () { setView("job"); openLog(false, true); return "#queue"; },
    function () { setView("job"); openLog(false, true); return "#checks"; },
    function () { setView("job"); openLog(false, true); return ".picker"; },
    function () { setView("job"); openLog(true, true); return "#log"; },
    function () { openLog(false, true); setView("how"); return "#how h3"; }
  ];
  var DEFAULT = null;
  function defaultAsset() { return DEFAULT; }
  function present(n) {
    var box = $("#presenter");
    $$(".spot").forEach(function (e) { e.classList.remove("spot"); });
    if (!n) {
      S.present = 0;
      box.hidden = true;
      $("#tour").setAttribute("hidden", "");
      doc.body.classList.remove("touring");
      writeHash();
      soonThreads();
      $("#tour-start").focus();
      return;
    }
    S.present = n;
    var focus = $(STEPS[n - 1]()), r = focus && focus.getBoundingClientRect ? focus.getBoundingClientRect() : null;
    var tall = win.innerHeight || 0;
    if (focus) {
      focus.classList.add("spot");
      if (r && (r.top < 0 || r.bottom > tall) && focus.scrollIntoView) { focus.scrollIntoView({block: "nearest"}); }
    }
    box.classList.toggle("up", !!(r && tall && r.top + r.height / 2 > tall * 0.5));
    box.innerHTML = "<h3>" + esc(row("present.titles", String(n))) + "</h3><p>" + esc(row("present.texts", String(n))) + "</p><div class='row'><span>" +
      esc(word("present.step", {n: n, total: STEPS.length})) + "</span><button type='button' class='btn' data-present='back'" +
      (n === 1 ? " disabled" : "") + ">" + esc(word("present.back")) + "</button><button type='button' class='btn primary' data-present='next'>" +
      esc(n === STEPS.length ? word("present.done") : word("present.next")) + "</button><button type='button' class='link' data-present='close'>" +
      esc(word("present.close")) + "</button></div>";
    box.hidden = false;
    doc.body.classList.add("touring");
    writeHash();
    soonThreads();
    var nextButton = $("[data-present='next']", box);
    if (nextButton) { nextButton.focus(); }
  }
  function setHole(rect, b) {
    ["x", "y", "width", "height"].forEach(function (k, i) {
      var v = f1([b.x, b.y, b.w, b.h][i]);
      rect.setAttribute(k, v);
      if (rect.style) { rect.style[k] = v + "px"; }
    });
  }
  function drawTour() {
    var svg = $("#tour"), focus = S.present ? $(".spot") : null;
    if (!svg) { return; }
    if (!focus || !focus.getBoundingClientRect) { svg.setAttribute("hidden", ""); return; }
    if (!$("#tour-cut", svg)) {
      svg.innerHTML = "<defs><mask id='tour-cut' maskUnits='userSpaceOnUse'><rect class='all' fill='#fff' x='0' y='0'/>" +
        "<rect class='hole' rx='12' fill='#000' x='0' y='0' width='0' height='0'/></mask></defs><rect class='shade all' x='0' y='0' mask='url(#tour-cut)'/>";
    }
    svg.removeAttribute("hidden");
    var W = f1(win.innerWidth || 0), H = f1(win.innerHeight || 0), r = focus.getBoundingClientRect();
    $$(".all", svg).forEach(function (el) { el.setAttribute("width", W); el.setAttribute("height", H); });
    setHole($(".hole", svg), {x: r.left - 8, y: r.top - 8, w: r.width + 16, h: r.height + 16});
    svg.classList.toggle("glide", !calm());
  }

  /* ------------------------------------------------------------------ the phone */
  var SCREENS = ["strip", "stage", "insp"];
  function renderTabs() {
    /* How it works covers the job, so no screen is marked while it's open. */
    var at = S.view === "how" ? "" : S.screen;
    $("#tabs").innerHTML = SCREENS.map(function (s) {
      return "<button type='button' data-screen='" + s + "' class='" + (at === s ? "on" : "") + "' aria-current='" +
        (at === s ? "true" : "false") + "'>" + esc(row("tabs", s)) + "</button>";
    }).join("");
  }
  function toScreen(name, smooth) {
    if (SCREENS.indexOf(name) < 0) { return; }
    S.screen = name;
    renderTabs();
    var work = $("#work");
    if (!phone() || !work || !work.clientWidth) { return; }
    var left = SCREENS.indexOf(name) * work.clientWidth;
    if (work.scrollTo) { work.scrollTo({left: left, behavior: smooth && !calm() ? "smooth" : "auto"}); } else { work.scrollLeft = left; }
  }

  /* The brand goes back to the job as it opens: the photo the page starts on, nothing open over it, fit to the table, at
     the top. The person's decisions, the model and the line stay as they are. */
  function home() {
    if (S.present) { present(0); }
    openLog(false, true);
    S.zoom = "fit";
    S.words = false;
    setView("job");
    select(DEFAULT);
    if (doc.scrollingElement) { doc.scrollingElement.scrollTop = 0; }
  }

  /* ------------------------------------------------------------------ events */
  function on(type, fn) { doc.addEventListener(type, fn); }
  on("click", function (e) {
    var t = e.target, el;
    if (!t || !t.closest) { return; }
    if ((el = t.closest(".brand"))) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) { return; }
      if (e.preventDefault) { e.preventDefault(); }
      home();
      return;
    }
    if ((el = t.closest("[data-asset]"))) { select(el.getAttribute("data-asset")); return; }
    if ((el = t.closest("[data-zoom]"))) { S.zoom = el.getAttribute("data-zoom"); renderStage(); soonThreads(); return; }
    if ((el = t.closest("#own-words"))) { S.words = !S.words; renderStage(); soonThreads(); return; }
    if ((el = t.closest("[data-line]"))) { setLine(el.getAttribute("data-line")); return; }
    if ((el = t.closest("[data-accept]"))) { act(el.getAttribute("data-accept"), "accept"); return; }
    if ((el = t.closest("[data-correct]"))) {
      var fix = $("[data-fix='" + el.getAttribute("data-correct") + "']");
      if (fix) { fix.hidden = false; var inp = $("input", fix); if (inp && inp.focus) { inp.focus(); } }
      return;
    }
    if ((el = t.closest("[data-save]"))) {
      var key = el.getAttribute("data-save"), v = ($("[data-fix-value='" + key + "']") || {}).value || "";
      if (String(v).trim()) { act(key, "correct", String(v).trim()); }
      return;
    }
    if ((el = t.closest("[data-approve]"))) { decide(el.getAttribute("data-approve"), "approved"); return; }
    if ((el = t.closest("[data-wrong]"))) { decide(el.getAttribute("data-wrong"), "wrong_unit"); return; }
    if ((el = t.closest(".val[data-field]"))) { light(el.getAttribute("data-photo") + "/" + el.getAttribute("data-field")); return; }
    if ((el = t.closest("#open-log"))) { openLog($("#log").hidden); return; }
    if ((el = t.closest("#close-log"))) { openLog(false); return; }
    if ((el = t.closest("#open-how"))) { setView(S.view === "how" ? "job" : "how"); return; }
    if ((el = t.closest("#tour-start"))) { present(1); return; }
    if ((el = t.closest("[data-present]"))) {
      var p = el.getAttribute("data-present");
      present(p === "close" ? 0 : p === "back" ? Math.max(1, S.present - 1) : S.present >= STEPS.length ? 0 : S.present + 1);
      return;
    }
    if ((el = t.closest("#reset"))) { reset(); return; }
    if ((el = t.closest("[data-file]"))) { openFile(el.getAttribute("data-file")); return; }
    if ((el = t.closest("[data-screen]"))) {
      /* On a phone a tab tapped in How it works goes back to the job, straight to that screen. */
      var fromHow = S.view === "how";
      if (fromHow) { setView("job"); }
      toScreen(el.getAttribute("data-screen"), !fromHow);
    }
  });
  on("change", function (e) {
    var t = e.target;
    if (!t) { return; }
    if (t.id === "model") { setModel(t.value); return; }
    if (t.hasAttribute && t.hasAttribute("data-design")) { setDesign(t.getAttribute("data-design"), t.value, true); }
  });
  on("input", function (e) {
    var t = e.target;
    if (t && t.hasAttribute && t.hasAttribute("data-design")) { setDesign(t.getAttribute("data-design"), t.value, false); }
  });
  on("keydown", function (e) {
    var t = e.target, tag = t && t.tagName;
    if (e.key === "Escape") { if (S.present) { present(0); } else { openLog(false); } return; }
    if (t && t.hasAttribute && t.hasAttribute("data-fix-value") && e.key === "Enter") {
      var key = t.getAttribute("data-fix-value");
      if (String(t.value).trim()) { act(key, "correct", String(t.value).trim()); }
      return;
    }
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") { return; }
    if (t && t.hasAttribute && t.hasAttribute("data-line") && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].indexOf(e.key) >= 0) {
      var order = ["all", "partial", "missing"], at = order.indexOf(S.line) + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1);
      if (at >= 0 && at < order.length) { setLine(order[at]); $("[data-line='" + order[at] + "']").focus(); }
      if (e.preventDefault) { e.preventDefault(); }
      return;
    }
    if (S.view === "job" && ["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight"].indexOf(e.key) >= 0 && t && t.closest && t.closest("#strip")) {
      var ids = FI.job.assets.map(function (a) { return a.id; }), i = ids.indexOf(S.asset);
      i += e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : -1;
      if (i >= 0 && i < ids.length) {
        select(ids[i]);
        var b = $("[data-asset='" + ids[i] + "']", $("#strip"));
        if (b && b.focus) { b.focus(); }
      }
      if (e.preventDefault) { e.preventDefault(); }
    }
  });
  on("mouseover", function (e) {
    var t = e.target, el = t && t.closest ? t.closest("[data-field][data-photo]") : null;
    light(el ? el.getAttribute("data-photo") + "/" + el.getAttribute("data-field") : null);
  });
  on("focusin", function (e) {
    var t = e.target, el = t && t.closest ? t.closest("[data-field][data-photo]") : null;
    if (el) { light(el.getAttribute("data-photo") + "/" + el.getAttribute("data-field")); }
  });
  if (win.addEventListener) {
    win.addEventListener("resize", function () {
      sizePrint(); renderInset(asset(S.asset)); soonThreads();
      // A turn of the phone changes each screen's width, so the marked screen is lined up again.
      if (phone()) { toScreen(S.screen, false); }
    });
    win.addEventListener("hashchange", function () { readHash(win.location.hash); renderAll(); });
  }
  var work = $("#work");
  if (work && work.addEventListener) {
    work.addEventListener("scroll", function () {
      if (!phone() || !work.clientWidth) { return; }
      var name = SCREENS[Math.max(0, Math.min(2, Math.round(work.scrollLeft / work.clientWidth)))];
      if (name !== S.screen) { S.screen = name; renderTabs(); }
    });
  }
  var photo = $("#photo");
  if (photo && photo.addEventListener) { photo.addEventListener("load", function () { sizePrint(); soonThreads(); }); }
  ["#insp", "#table"].forEach(function (s) {
    var pane = $(s);
    if (pane && pane.addEventListener) { pane.addEventListener("scroll", soonThreads); }
  });

  /* ------------------------------------------------------------------ the start */
  function begin() {
    S.designs = copy(FI.job.designs);
    run();
    DEFAULT = firstAsset();
    S.asset = DEFAULT;
    var h = readHash(win.location ? win.location.hash : "");
    firstLog();
    renderAll();
    // On a phone the three screens sit side by side, so the one the tabs mark has to be scrolled to at the start.
    if (phone()) { toScreen(S.screen, false); }
    if (h.t && +h.t >= 1 && +h.t <= STEPS.length) { present(+h.t); }
  }
  FIP.state = function () {
    return {asset: S.asset, model: S.model, line: S.line, view: S.view, zoom: S.zoom, words: S.words, present: S.present,
      screen: S.screen, log: S.log.length, code: S.code};
  };
  FIP.out = function () { return S.out; };
  FIP.steps = STEPS.length;
  FIP.present = present;
  FIP.select = select;
  FIP.defaultAsset = function () { return DEFAULT; };
  begin();
})(window);

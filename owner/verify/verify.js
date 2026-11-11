/* The verification page's script. It loads the draft read, lets a person confirm each photo's values, masks and tags, and
   saves the whole state to data/key_draft.json through owner/verify.py after every change. It runs only on the owner's machine,
   for one sitting. */
"use strict";
(function () {
  var S = {d: null, photos: {}, cur: null, draw: false, sel: -1, act: null, timer: null};
  var MIN = 0.004;
  function $(s) { return document.querySelector(s); }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[c];
    });
  }
  function draftOf(id) { return S.d.drafts[id] || {}; }
  function modelCanon(id) { var m = (draftOf(id).draft || {}).model; return m ? m.canon : ""; }
  function clamp(v) { return Math.max(0, Math.min(1, v)); }
  function typing(e) { var t = e.target && e.target.tagName; return t === "INPUT" || t === "SELECT" || t === "TEXTAREA"; }

  /* ------------------------------------------------------------------ state */
  function fresh(id) {
    var dr = draftOf(id), fields = {};
    S.d.fields.forEach(function (f) {
      var v = (dr.draft || {})[f.id];
      fields[f.id] = v ? {value: v.value, box: v.box} : null;
    });
    return {status: "open", plate: "", kind: "", shot: "straight", fields: fields, checked_people: false,
      masks: (dr.masks || []).map(function (m) { return m.box.slice(); }), dropped_why: ""};
  }
  function init(d) {
    S.d = d;
    var saved = (d.saved && d.saved.photos) || {};
    d.ids.forEach(function (id) { S.photos[id] = saved[id] || fresh(id); });
    var open = d.ids.filter(function (id) { return S.photos[id].status === "open"; });
    show(open[0] || d.ids[0]);
  }
  function save() {
    window.clearTimeout(S.timer);
    S.timer = window.setTimeout(function () {
      fetch("/api/save", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({photos: S.photos})})
        .then(function (r) { return r.ok ? r.json() : r.text().then(function (t) { throw new Error(t); }); })
        .then(function (j) { var s = $("#saved"); s.className = ""; s.textContent = "Saved at " + j.saved_at.slice(11); })
        .catch(function (e) { var s = $("#saved"); s.className = "bad"; s.textContent = "Not saved: " + e.message; });
    }, 400);
  }
  function propagate(id) {
    var canon = modelCanon(id), p = S.photos[id];
    if (!canon) { return; }
    S.d.ids.forEach(function (o) {
      var q = S.photos[o];
      if (o === id || q.status !== "open" || modelCanon(o) !== canon) { return; }
      if (!q.plate) { q.plate = p.plate; }
      if (!q.kind) { q.kind = p.kind; }
    });
  }
  function problems(id) {
    var p = S.photos[id], out = [];
    if (!p.plate) { out.push("name the plate"); }
    if (!p.kind) { out.push("choose the equipment"); }
    S.d.fields.forEach(function (f) {
      var v = p.fields[f.id];
      if (v && !String(v.value).trim()) { out.push(f.name + " needs a value or \"not on it\""); }
    });
    if (draftOf(id).people && !p.checked_people) { out.push("tick that no person shows, or drop the photo"); }
    return out;
  }
  function next() {
    var ids = S.d.ids, i = ids.indexOf(S.cur);
    for (var k = 1; k <= ids.length; k++) {
      var id = ids[(i + k) % ids.length];
      if (S.photos[id].status === "open") { show(id); return; }
    }
    show(S.cur);
  }

  /* ------------------------------------------------------------------ drawing */
  function pct(v) { return (v * 100).toFixed(3) + "%"; }
  function place(b) { return "left:" + pct(b[0]) + ";top:" + pct(b[1]) + ";width:" + pct(b[2] - b[0]) + ";height:" + pct(b[3] - b[1]); }
  function show(id) {
    S.cur = id;
    S.sel = -1;
    var img = $("#photo");
    img.src = "/photo/" + id + ".jpg";
    img.alt = id;
    renderList();
    renderForm();
    renderBoxes();
  }
  function renderList() {
    var icons = {open: "○", done: "✓", dropped: "✕"}, done = 0, dropped = 0;
    $("#list").innerHTML = S.d.ids.map(function (id) {
      var p = S.photos[id];
      done += p.status === "done" ? 1 : 0;
      dropped += p.status === "dropped" ? 1 : 0;
      return "<button type='button' data-id='" + id + "' class='" + (id === S.cur ? "on" : "") + "'><i>" + icons[p.status] +
        "</i>" + id + "<small>" + esc(p.plate) + "</small></button>";
    }).join("");
    var left = S.d.ids.length - done - dropped;
    $("#progress").textContent = done + " of " + S.d.ids.length + " confirmed, " + dropped + " dropped" +
      (left ? ", " + left + " to go" : ". Every photo is settled, so press Control-C in the terminal.");
  }
  function renderBoxes() {
    var p = S.photos[S.cur], dr = draftOf(S.cur), out = "";
    if ($("#show-words").checked) {
      (dr.words || []).forEach(function (w) { out += "<div class='box word' style='" + place(w.box) + "'></div>"; });
    }
    if ($("#show-values").checked) {
      S.d.fields.forEach(function (f) {
        var v = p.fields[f.id];
        if (v && v.box) { out += "<div class='box value' style='" + place(v.box) + "'><span>" + esc(f.name) + "</span></div>"; }
      });
    }
    p.masks.forEach(function (m, i) {
      out += "<div class='box mask" + (i === S.sel ? " sel" : "") + "' data-mask='" + i + "' style='" + place(m) +
        "'><b data-del='" + i + "' title='Remove this mask'>×</b><u data-size='" + i + "'></u></div>";
    });
    $("#boxes").innerHTML = out;
    $("#boxes").classList.toggle("drawing", S.draw);
    $("#draw").classList.toggle("on", S.draw);
  }
  function renderForm() {
    var id = S.cur, p = S.photos[id], dr = draftOf(id), h = "<h2>" + id + "</h2>";
    if (dr.people) {
      if (!p.checked_people && p.status !== "dropped") {
        h += "<div class='warn'>Vision saw a face or a person here. Look closely, then tick the box below or drop the photo.</div>";
      }
      h += "<label><input type='checkbox' data-k='checked_people'" + (p.checked_people ? " checked" : "") +
        "> No person, room or identifier shows</label>";
    }
    var names = [];
    S.d.ids.forEach(function (o) { var n = S.photos[o].plate; if (n && names.indexOf(n) < 0) { names.push(n); } });
    h += "<h3>The plate</h3><label class='row'>Plate name<input type='text' list='plates' data-k='plate' value='" + esc(p.plate) +
      "' placeholder='Water heater'></label><p class='hint'>Name it by what it is, never by its maker.</p><datalist id='plates'>" +
      names.map(function (n) { return "<option value='" + esc(n) + "'>"; }).join("") + "</datalist>";
    h += "<label class='row'>Equipment<select data-k='kind'><option value=''>Choose</option>" + S.d.kinds.map(function (k) {
      return "<option" + (p.kind === k ? " selected" : "") + ">" + esc(k) + "</option>";
    }).join("") + "</select></label>";
    h += "<h3>The shot</h3><div class='shots'>" + S.d.shots.map(function (s) {
      return "<label><input type='radio' name='shot' data-k='shot' value='" + s + "'" + (p.shot === s ? " checked" : "") + "> " + s + "</label>";
    }).join("") + "</div>";
    h += "<h3>What the plate prints</h3>";
    S.d.fields.forEach(function (f) {
      var v = p.fields[f.id];
      h += "<div class='field'><span>" + esc(f.name) + "</span><input type='text' data-f='" + f.id + "' value='" + esc(v ? v.value : "") +
        "'" + (v ? "" : " disabled") + "><label><small><input type='checkbox' data-absent='" + f.id + "'" + (v ? "" : " checked") +
        "> not on it</small></label></div>";
    });
    h += "<h3>Masks</h3><p class='hint'>" + p.masks.length + " on this photo. Cover every maker's name and logo, serial number, " +
      "sticker, address, phone number, web address, certification mark, patent number, barcode and QR code.</p>";
    h += "<div class='actions'><button type='button' class='primary' id='confirm'>Confirm and next</button>" +
      "<select id='why'><option value=''>Drop because</option><option>blurry or unreadable</option>" +
      "<option>shows a person, a room or an identifier</option><option>a duplicate</option></select>" +
      "<button type='button' id='drop'>Drop this photo</button>" +
      (p.status !== "open" ? "<button type='button' id='reopen'>Reopen</button>" : "") + "</div><div class='problem' id='problem'></div>";
    if (p.status === "done") { h += "<p class='hint'>Confirmed.</p>"; }
    if (p.status === "dropped") { h += "<p class='hint'>Dropped: " + esc(p.dropped_why) + "</p>"; }
    $("#form").innerHTML = h;
  }

  /* ------------------------------------------------------------------ events */
  function frac(e) {
    var r = $("#photo").getBoundingClientRect();
    return [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)];
  }
  function confirmPhoto() {
    var bad = problems(S.cur);
    if (bad.length) { $("#problem").textContent = "Before confirming, " + bad.join(", ") + "."; return; }
    S.photos[S.cur].status = "done";
    save();
    next();
  }
  document.addEventListener("input", function (e) {
    var t = e.target, p = S.photos[S.cur];
    if (t.hasAttribute("data-f")) {
      var old = p.fields[t.getAttribute("data-f")];
      p.fields[t.getAttribute("data-f")] = {value: t.value, box: old ? old.box : null};
      save();
    } else if (t.getAttribute("data-k") === "plate") {
      p.plate = t.value;
      propagate(S.cur);
      renderList();
      save();
    }
  });
  document.addEventListener("change", function (e) {
    var t = e.target, p = S.photos[S.cur], k = t.getAttribute("data-k");
    if (t.hasAttribute("data-absent")) {
      var f = t.getAttribute("data-absent");
      p.fields[f] = t.checked ? null : {value: "", box: null};
      renderForm();
      renderBoxes();
      save();
    } else if (k === "kind" || k === "shot") {
      p[k] = t.value;
      propagate(S.cur);
      save();
    } else if (k === "checked_people") {
      p.checked_people = t.checked;
      renderForm();
      save();
    } else if (t.id === "show-words" || t.id === "show-values") {
      renderBoxes();
    }
  });
  document.addEventListener("click", function (e) {
    var t = e.target, p = S.photos[S.cur], b = t.closest ? t.closest("button") : null;
    if (t.hasAttribute("data-del")) {
      p.masks.splice(+t.getAttribute("data-del"), 1);
      S.sel = -1;
      renderBoxes();
      renderForm();
      save();
    } else if (b && b.hasAttribute("data-id")) {
      show(b.getAttribute("data-id"));
    } else if (b && b.id === "draw") {
      S.draw = !S.draw;
      renderBoxes();
    } else if (b && b.id === "confirm") {
      confirmPhoto();
    } else if (b && b.id === "drop") {
      p.status = "dropped";
      p.dropped_why = $("#why").value || "dropped";
      save();
      next();
    } else if (b && b.id === "reopen") {
      p.status = "open";
      save();
      renderList();
      renderForm();
    }
  });
  document.addEventListener("mousedown", function (e) {
    var t = e.target, p = S.photos[S.cur];
    if (!S.d || !t || !t.closest || !t.closest("#boxes") || t.hasAttribute("data-del")) { return; }
    var at = frac(e);
    if (t.hasAttribute("data-size")) {
      S.act = {kind: "size", i: +t.getAttribute("data-size")};
    } else if (t.closest(".mask")) {
      var i = +t.closest(".mask").getAttribute("data-mask");
      S.sel = i;
      S.act = {kind: "move", i: i, from: at, start: p.masks[i].slice()};
    } else if (S.draw) {
      p.masks.push([at[0], at[1], at[0], at[1]]);
      S.sel = p.masks.length - 1;
      S.act = {kind: "new", i: S.sel, from: at};
    } else {
      return;
    }
    e.preventDefault();
    renderBoxes();
  });
  document.addEventListener("mousemove", function (e) {
    if (!S.act) { return; }
    var m = S.photos[S.cur].masks[S.act.i], at = frac(e);
    if (S.act.kind === "new") {
      m[0] = Math.min(S.act.from[0], at[0]); m[2] = Math.max(S.act.from[0], at[0]);
      m[1] = Math.min(S.act.from[1], at[1]); m[3] = Math.max(S.act.from[1], at[1]);
    } else if (S.act.kind === "size") {
      m[2] = Math.max(m[0] + MIN, at[0]);
      m[3] = Math.max(m[1] + MIN, at[1]);
    } else {
      var w = S.act.start[2] - S.act.start[0], h = S.act.start[3] - S.act.start[1];
      var x = clamp(S.act.start[0] + at[0] - S.act.from[0]), y = clamp(S.act.start[1] + at[1] - S.act.from[1]);
      x = Math.min(x, 1 - w);
      y = Math.min(y, 1 - h);
      m[0] = x; m[1] = y; m[2] = x + w; m[3] = y + h;
    }
    renderBoxes();
  });
  document.addEventListener("mouseup", function () {
    if (!S.act) { return; }
    var masks = S.photos[S.cur].masks, m = masks[S.act.i];
    if (S.act.kind === "new" && (m[2] - m[0] < MIN || m[3] - m[1] < MIN)) { masks.splice(S.act.i, 1); S.sel = -1; }
    S.act = null;
    renderBoxes();
    renderForm();
    save();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !typing(e))) { e.preventDefault(); confirmPhoto(); return; }
    if (typing(e)) { return; }
    if ((e.key === "Delete" || e.key === "Backspace") && S.sel >= 0) {
      S.photos[S.cur].masks.splice(S.sel, 1);
      S.sel = -1;
      renderBoxes();
      renderForm();
      save();
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      var ids = S.d.ids, i = ids.indexOf(S.cur) + (e.key === "ArrowDown" ? 1 : -1);
      if (i >= 0 && i < ids.length) { show(ids[i]); }
      e.preventDefault();
    }
  });
  fetch("/api/state").then(function (r) { return r.json(); }).then(init).catch(function (e) {
    $("#saved").className = "bad";
    $("#saved").textContent = "Couldn't load the photos: " + e.message;
  });
})();

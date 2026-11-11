/* The page's copy of engine/rules.py: the installer's design rules run on the reads, so editing the design, moving the
   confidence line and the person's accept or correct all rerun the checks live. It returns exactly what the Python
   returns for the same job, reads, decisions and line, and tests/js/check_rules.js proves it on the parity vectors.
   No verdict stands on a read that's waiting for a person. */
(function (root, make) {
  if (typeof module === "object" && module.exports) { module.exports = make(require("./normalize.js")); }
  else { root.FIRules = make(root.FINorm); }
})(this, function (norm) {
  "use strict";
  var SENT = {missing: ["missing"], partial: ["partial", "missing"], all: ["found", "partial", "missing"]};

  function needed(design, cfg) {
    var out = [];
    (design.checks || []).forEach(function (rule) {
      if (rule === "panel") { return; }
      var optional = cfg.rules[rule].optional || [];
      cfg.rules[rule].fields.forEach(function (f) {
        if (out.indexOf(f) < 0 && optional.indexOf(f) < 0) { out.push(f); }
      });
    });
    return out;
  }
  function readState(photo, field, reads, person, line, need) {
    var r = (reads[photo] || {})[field] || {status: "absent"};
    var act = (person.reads || {})[photo + "/" + field];
    if (act && act.action === "correct") { return [act.value === undefined ? null : act.value, "person", true]; }
    if (act && r.status !== "unreadable") {
      return [r.status === "read" ? (r.value === undefined ? null : r.value) : null, "person", true];
    }
    var level;
    if (r.status === "read" && r.value) { level = r.level || "missing"; }
    else if (r.status === "unreadable" || need) { level = "missing"; }
    else { return [null, null, true]; }
    var value = r.status === "read" ? (r.value === undefined ? null : r.value) : null;
    return [value, level, SENT[line].indexOf(level) < 0];
  }
  function voltsFit(plate, design, classes) {
    var ratings = plate.split("/").map(parseFloat), parts = design.split("/");
    for (var i = 0; i < parts.length; i++) {
      var d = parts[i], range = classes[d] || [parseFloat(d), parseFloat(d)];
      if (!ratings.some(function (r) { return range[0] <= r && r <= range[1]; })) { return false; }
    }
    return true;
  }
  function check(rule, asset, design, reads, person, line, cfg) {
    var kinds = cfg.kinds, photo = asset.photo, inputs = [], waits = [];
    function plate(field, on, need) {
      var p = on || photo, st = readState(p, field, reads, person, line, need === undefined ? true : need);
      var c = st[0] ? norm.canon(kinds[field], st[0]) : null;
      inputs.push({from: "photo", photo: p, field: field, value: c, level: st[1]});
      if (!st[2]) { waits.push(p + "/" + field); }
      return c;
    }
    function want(field, kind) {
      var c = design[field] ? norm.canon(kind, design[field]) : null;
      inputs.push({from: "design", field: field, value: c});
      return c;
    }
    function out(status, why) { return {rule: rule, status: status, why: why, inputs: inputs, waits: waits}; }
    var d, p;
    if (rule === "readable") {
      var r = reads[photo] || {};
      var got = Object.keys(r).filter(function (f) { return r[f].status === "read" && r[f].value; });
      return got.length ? out("pass", "read") : out("fail", "nothing_read");
    }
    if (rule === "panel") {
      if (!asset.breaker_photo) { return out("skipped", "no_breaker_photo"); }
      d = want("breaker", "amps");
      p = plate("breaker", asset.breaker_photo);
    } else if (rule === "volts") {
      d = want("volts", "volts");
      p = plate("volts");
      var dp = want("phase", "phase"), pp = plate("phase", null, false);
      if (p === null || d === null) { return out("unknown", "no_read"); }
      if (dp && pp && dp !== pp) { return out("fail", "phase"); }
      return voltsFit(p, d, cfg.volt_classes) ? out("pass", "fits") : out("fail", "volts");
    } else if (rule === "breaker_max" || rule === "breaker_min") {
      d = want("breaker", "amps");
      p = plate(rule === "breaker_max" ? "max_breaker" : "mca");
      if (p === null || d === null) { return out("unknown", "no_read"); }
      var ok = rule === "breaker_max" ? parseFloat(d) <= parseFloat(p) : parseFloat(d) >= parseFloat(p);
      return ok ? out("pass", "within") : out("fail", rule === "breaker_max" ? "over" : "under");
    } else {
      d = want(rule, kinds[rule]);
      p = plate(rule);
    }
    if (p === null || d === null) {
      var act = (person.reads || {})[photo + "/" + rule];
      var blind = ((reads[photo] || {})[rule] || {}).status === "unreadable";
      if (act && act.action === "accept" && p === null && !blind) { return out("skipped", "absent_confirmed"); }
      return out("unknown", "no_read");
    }
    if (p === d) { return out("pass", "equal"); }
    if (rule === "model") {
      var approved = (design.approved || []).map(function (a) { return norm.canon("code", a); });
      if (approved.indexOf(p) >= 0) { return out("pass", "approved"); }
      var decided = (person.checks || {})[asset.id + "/model"];
      if (decided === "approved") { return out("pass", "approved_by_person"); }
      if (decided === "wrong_unit") { return out("fail", "wrong_unit"); }
      if (norm.distance(p, d) === 1) { return out("review", "one_off"); }
    }
    return out("fail", "differs");
  }
  function evaluate(job, reads, person, line, cfg) {
    person = person || {};
    var assets = {}, queue = [], counts = {pass: 0, fail: 0, person: 0, reads: 0, sent: 0};
    job.assets.forEach(function (asset) {
      var design = job.designs[asset.id];
      var checks = (design.checks || []).map(function (rule) { return check(rule, asset, design, reads, person, line, cfg); });
      var need = needed(design, cfg), queued = [];
      var photos = [asset.photo].concat(asset.breaker_photo ? [asset.breaker_photo] : []);
      photos.forEach(function (p) {
        var main = p === asset.photo, seen = {};
        Object.keys(reads[p] || {}).concat(main ? need : ["breaker"]).forEach(function (f) { seen[f] = 1; });
        Object.keys(seen).sort().forEach(function (field) {
          var st = readState(p, field, reads, person, line, main ? need.indexOf(field) >= 0 : field === "breaker");
          if (st[1] === null) { return; }
          counts.reads += 1;
          if (!st[2]) {
            counts.sent += 1;
            queued.push(p + "/" + field);
            queue.push({type: "read", asset: asset.id, photo: p, field: field, level: st[1]});
          }
        });
      });
      checks.forEach(function (c) {
        if (c.status === "review") { queue.push({type: "check", asset: asset.id, rule: c.rule}); }
      });
      var state;
      if (checks.some(function (c) { return c.status === "fail" && !c.waits.length; })) { state = "fail"; }
      else if (queued.length || checks.some(function (c) { return c.status === "review" || c.status === "unknown" || c.waits.length; })) {
        state = "person";
      } else { state = "pass"; }
      counts[state] += 1;
      assets[asset.id] = {state: state, checks: checks, queued: queued};
    });
    return {assets: assets, queue: queue, counts: counts};
  }
  return {evaluate: evaluate, check: check, voltsFit: voltsFit, SENT: SENT};
});

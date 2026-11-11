/* The verification page's click-through, run before the verification sitting so a broken script never wastes it. It
   loads owner/verify/index.html into the small DOM with a made-up draft of three photos, then fills a value, marks a
   field absent, names a plate (and watches the name carry to the other shot of the same plate), draws, moves, resizes
   and removes a mask, refuses to confirm an unfinished photo, confirms and drops photos, and checks every save it sends.
   Exits 1 on any failed check.

       node tests/js/check_verify.js */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const {Document} = require("./dom.js");

const ROOT = path.resolve(__dirname, "..", "..");
const checks = [];
function check(name, ok, detail) { checks.push({name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 300)}); }

const draft = (model, extra) => Object.assign({w: 1568, h: 1176, people: 0, words: [{text: model, box: [0.4, 0.1, 0.6, 0.15]}],
  draft: {model: {value: model, canon: model.replace(/-/g, ""), box: [0.4, 0.1, 0.6, 0.15]}},
  masks: [{box: [0.1, 0.05, 0.3, 0.1], why: "lettering"}]}, extra || {});
const STATE = {
  fields: [{id: "model", name: "Model", kind: "code"}, {id: "volts", name: "Volts", kind: "volts"}, {id: "mca", name: "Min. circuit", kind: "amps"}],
  shots: ["straight", "angled", "glare", "low light"], kinds: ["heat pump", "water heater", "other"],
  ids: ["p01", "p02", "p03"],
  drafts: {p01: draft("HPX-36B2"), p02: draft("HPX-36B2"), p03: draft("EWH-50T2", {people: 1})},
  saved: null,
};
const saves = [];
const html = fs.readFileSync(path.join(ROOT, "owner", "verify", "index.html"), "utf8");
const doc = new Document(html);
check("the page parses with every tag closed", doc.errors.length === 0, doc.errors.slice(0, 3).join("; "));
const timers = [];
const win = {document: doc, setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout(id) { if (id) { timers[id - 1] = null; } },
  fetch(url, opts) {
    if (url === "/api/state") { return Promise.resolve({json: () => Promise.resolve(JSON.parse(JSON.stringify(STATE)))}); }
    saves.push(JSON.parse(opts.body));
    return Promise.resolve({ok: true, json: () => Promise.resolve({ok: true, saved_at: "2026-11-10T09:00:00"})});
  }, JSON, Promise, Math, String, Object, Array};
win.window = win;
vm.createContext(win);
let error = null;
try { vm.runInContext(fs.readFileSync(path.join(ROOT, "owner", "verify", "verify.js"), "utf8"), win, {filename: "verify.js"}); }
catch (e) { error = e; }
const $ = (s) => doc.querySelector(s), $$ = (s) => doc.querySelectorAll(s);
const tick = () => new Promise((r) => setImmediate(r));
async function settle() {
  for (let i = 0; i < 6; i++) {
    await tick();
    while (timers.some(Boolean)) { const k = timers.findIndex(Boolean), fn = timers[k]; timers[k] = null; fn(); }
  }
}
const send = (type, el, extra) => doc.dispatch(type, el, extra);
const last = () => saves[saves.length - 1].photos;

(async () => {
  check("the script loads", !error, error && error.stack);
  await settle();
  check("the list shows every photo", $$("#list [data-id]").length === 3);
  check("the first photo opens with its draft value", $("[data-f='model']") && $("[data-f='model']").getAttribute("value") === "HPX-36B2");
  check("a field with no draft starts as not on the plate", $("[data-absent='mca']").hasAttribute("checked"));
  check("the proposed mask is drawn", $$("#boxes .mask").length === 1);

  send("click", $("#confirm"));
  await settle();
  check("an unnamed plate can't be confirmed", /name the plate/.test($("#problem").textContent), $("#problem").textContent);

  const plate = $("[data-k='plate']");
  plate.value = "Outdoor unit";
  send("input", plate);
  const kind = $("[data-k='kind']");
  kind.value = "heat pump";
  send("change", kind);
  const volts = $("[data-absent='volts']");
  volts.removeAttribute("checked"); volts.checked = false;
  send("change", volts);
  const vin = $("[data-f='volts']");
  vin.value = "208/230";
  send("input", vin);
  await settle();
  check("a typed value is saved", last().p01.fields.volts && last().p01.fields.volts.value === "208/230", JSON.stringify(last().p01.fields));
  check("the plate's name carries to the other shot of the same model", last().p02.plate === "Outdoor unit" && last().p03.plate === "");

  send("click", $("#draw"));
  send("mousedown", $("#boxes"), {clientX: 10, clientY: 2});
  send("mousemove", doc.body, {clientX: 50, clientY: 12});
  send("mouseup", doc.body);
  await settle();
  check("dragging on the photo draws a mask", last().p01.masks.length === 2, JSON.stringify(last().p01.masks));
  const drawn = last().p01.masks[1];
  check("the mask lands where it was drawn, in fractions", Math.abs(drawn[0] - 0.1) < 1e-9 && Math.abs(drawn[2] - 0.5) < 1e-9 &&
    Math.abs(drawn[1] - 0.1) < 1e-9 && Math.abs(drawn[3] - 0.6) < 1e-9, JSON.stringify(drawn));
  send("click", $("#draw"));
  send("mousedown", $("[data-mask='1']"), {clientX: 10, clientY: 2});
  send("mousemove", doc.body, {clientX: 20, clientY: 4});
  send("mouseup", doc.body);
  await settle();
  const moved = last().p01.masks[1];
  check("dragging a mask moves it and keeps its size", Math.abs(moved[0] - 0.2) < 1e-9 && Math.abs(moved[2] - moved[0] - 0.4) < 1e-9, JSON.stringify(moved));
  send("mousedown", $("[data-size='1']"), {clientX: 20, clientY: 4});
  send("mousemove", doc.body, {clientX: 90, clientY: 18});
  send("mouseup", doc.body);
  await settle();
  check("dragging the corner resizes it", Math.abs(last().p01.masks[1][2] - 0.9) < 1e-9, JSON.stringify(last().p01.masks[1]));
  send("click", $("[data-del='0']"));
  await settle();
  check("the x removes a mask", last().p01.masks.length === 1);

  send("click", $("#confirm"));
  await settle();
  check("a finished photo confirms and the next one opens", last().p01.status === "done" && $("h2").textContent === "p02");
  check("the second shot arrives with its plate already named", $("[data-k='plate']").getAttribute("value") === "Outdoor unit");
  const k2 = $("[data-k='kind']");
  send("click", $("#confirm"));
  await settle();
  check("the second shot confirms", last().p02.status === "done" && $("h2").textContent === "p03", k2 && k2.value);

  check("a photo where Vision saw a person shows the warning", /face or a person/.test($("#form").textContent));
  const p3 = $("[data-k='plate']");
  p3.value = "Water heater";
  send("input", p3);
  const k3 = $("[data-k='kind']");
  k3.value = "water heater";
  send("change", k3);
  send("click", $("#confirm"));
  await settle();
  check("it can't be confirmed until someone looks", last().p03.status === "open" && /person/.test($("#problem").textContent), $("#problem").textContent);
  const why = $("#why");
  why.value = "shows a person, a room or an identifier";
  send("click", $("#drop"));
  await settle();
  check("dropping records the reason", last().p03.status === "dropped" && /person/.test(last().p03.dropped_why));
  check("every photo is settled", /Every photo is settled/.test($("#progress").textContent), $("#progress").textContent);
  check("every save holds every photo with a shot and a status", saves.every((s) => Object.keys(s.photos).length === 3 &&
    Object.values(s.photos).every((x) => STATE.shots.indexOf(x.shot) >= 0 && ["open", "done", "dropped"].indexOf(x.status) >= 0)));

  const failed = checks.filter((c) => !c.ok);
  failed.forEach((c) => console.log(`FAIL ${c.name} ${c.detail}`));
  console.log(`${checks.length - failed.length} of ${checks.length} verification page checks pass`);
  process.exit(failed.length ? 1 : 0);
})();

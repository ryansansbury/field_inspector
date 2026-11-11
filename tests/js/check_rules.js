/* Run site/normalize.js and site/rules.js on tests/vectors/rules.json and compare with what engine/normalize.py and
   engine/rules.py returned. Prints the first disagreements and exits 1 if there are any.

     node tests/js/check_rules.js */
"use strict";
const fs = require("fs");
const path = require("path");
const here = path.resolve(__dirname, "..", "..");
const N = require(path.join(here, "site", "normalize.js"));
const R = require(path.join(here, "site", "rules.js"));
const v = JSON.parse(fs.readFileSync(path.join(here, "tests", "vectors", "rules.json"), "utf8"));

function canon(x) {
  if (Array.isArray(x)) { return x.map(canon); }
  if (x && typeof x === "object") {
    const out = {};
    for (const k of Object.keys(x).sort()) { out[k] = canon(x[k]); }
    return out;
  }
  return x;
}

let bad = 0;
const say = (line) => { if (bad <= 8) { console.log(line); } };
for (const c of v.normalize) {
  const got = N.canon(c.kind, c.text);
  if (got !== c.want) { bad += 1; say(`FAIL normalize ${c.kind} ${JSON.stringify(c.text)}: ${got} against ${c.want}`); }
}
for (const c of v.distance) {
  const got = N.distance(c.a, c.b);
  if (got !== c.want) { bad += 1; say(`FAIL distance ${c.a} ${c.b}: ${got} against ${c.want}`); }
}
v.rules.forEach((c, i) => {
  const got = JSON.stringify(canon(R.evaluate(c.job, c.reads, c.person, c.line, v.cfg)));
  const want = JSON.stringify(canon(c.want));
  if (got !== want) {
    bad += 1;
    let at = 0;
    while (at < got.length && got[at] === want[at]) { at += 1; }
    say(`FAIL rules case ${i}: ...${got.slice(Math.max(0, at - 80), at + 80)} against ...${want.slice(Math.max(0, at - 80), at + 80)}`);
  }
});
console.log(`Parity: ${v.normalize.length} normalizing cases, ${v.distance.length} distances and ${v.rules.length} rules cases, ` +
  (bad ? `${bad} disagree` : "all agree"));
process.exit(bad ? 1 : 0);

/* The page's copy of engine/normalize.py: a value as printed into its canonical form by field kind, so a person's typed
   correction or an edited design value compares with the reads exactly as the build compared them. Numbers stay
   strings and unit changes move the decimal point as text, and only ASCII ranges appear in the patterns, so this file
   and the Python give the same answer for every input. tests/js/check_rules.js proves it on the parity vectors. */
(function (root, make) {
  if (typeof module === "object" && module.exports) { module.exports = make(); } else { root.FINorm = make(); }
})(this, function () {
  "use strict";
  var PHASE_SIGNS = ["Ø", "ø", "Φ", "φ", "ϕ"];
  var LOOKALIKES = {"А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
    "Х": "X", "У": "Y", "І": "I", "Ј": "J", "Ѕ": "S", "а": "a", "е": "e", "к": "k", "м": "m", "о": "o",
    "р": "p", "с": "c", "т": "t", "х": "x", "у": "y", "і": "i", "ј": "j", "ѕ": "s", "Α": "A", "Β": "B",
    "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T",
    "Υ": "Y", "Χ": "X", "ο": "o"};
  var VOLT_MIN = 90, VOLT_MAX = 600;
  var NUM = "(?:[0-9]+(?:\\.[0-9]+)?|\\.[0-9]+)";
  var UNITS = {GALLONS: "GAL", GALLON: "GAL", GALS: "GAL", GAL: "GAL", "BTU/HR": "BTUH", "BTU/H": "BTUH", BTUH: "BTUH",
    BTU: "BTUH", MBH: "MBH", KW: "KW", WATTS: "W", WATT: "W", W: "W", TONS: "TON", TON: "TON", L: "L"};
  var ORDER = ["GAL", "BTUH", "KW", "TON", "L"];
  var CAPACITY = "(" + NUM + ") ?(GALLONS|GALLON|GALS|GAL|BTU ?/ ?HR|BTU ?/ ?H|BTUH|BTU|MBH|KW|WATTS|WATT|W|TONS|TON|L)(?![A-Z])";
  var REFRIGERANT = "(?:^|[^A-Z0-9])(?:R|HFC|HCFC|HFO|HC) ?-? ?([0-9]{2,4}[A-Z]{0,2})(?![A-Z0-9])";
  var PHASE_DIGIT = "(?:^|[^0-9.])([13])(?=[^0-9.]|$)";

  function all(pattern, text) {
    var re = new RegExp(pattern, "g"), out = [], m;
    while ((m = re.exec(text)) !== null) { out.push(m); }
    return out;
  }
  function clean(text) {
    var t = String(text === null || text === undefined ? "" : text);
    PHASE_SIGNS.forEach(function (s) { t = t.split(s).join("PH"); });
    t = t.split("").map(function (ch) { return LOOKALIKES[ch] || ch; }).join("");
    t = t.toUpperCase().replace(/[^A-Z0-9.,/ -]/g, " ");
    return t.split(/\s+/).filter(Boolean).join(" ");
  }
  function dropThousands(t) {
    for (;;) {
      var out = t.replace(/([0-9]),([0-9]{3})(?![0-9])/g, "$1$2");
      if (out === t) { return out; }
      t = out;
    }
  }
  function number(s) {
    var m = /^([0-9]*)(?:\.([0-9]*))?$/.exec(s || "");
    if (!m || !(m[1] || m[2])) { return null; }
    var whole = m[1].replace(/^0+/, "") || "0", frac = (m[2] || "").replace(/0+$/, "");
    return whole + (frac ? "." + frac : "");
  }
  function shift(num, places) {
    var dot = num.indexOf("."), whole = dot < 0 ? num : num.slice(0, dot), frac = dot < 0 ? "" : num.slice(dot + 1);
    var digits = whole + frac, point = whole.length + places;
    if (point <= 0) { digits = new Array(2 - point).join("0") + digits; point = 1; }
    if (point > digits.length) { digits += new Array(point - digits.length + 1).join("0"); }
    return number(digits.slice(0, point) + "." + digits.slice(point));
  }
  function numbersIn(t) { return t.match(new RegExp(NUM, "g")) || []; }
  function code(text) { return clean(text).replace(/[^A-Z0-9]/g, "") || null; }
  function volts(text) {
    var t = dropThousands(clean(text)), found = [];
    all("(" + NUM + ")( ?)([A-Z]?)", t).forEach(function (m) {
      if (m[3] && m[3] !== "V") { return; }
      var v = number(m[1]);
      if (v !== null && parseFloat(v) >= VOLT_MIN && parseFloat(v) <= VOLT_MAX && found.indexOf(v) < 0) { found.push(v); }
    });
    if (!found.length) { return null; }
    return found.sort(function (a, b) { return parseFloat(a) - parseFloat(b); }).join("/");
  }
  function phase(text) {
    var t = clean(text), found = {};
    all(PHASE_DIGIT, t).forEach(function (m) { found[m[1]] = 1; });
    var words = t.replace(/-/g, " ").split(/\s+/).filter(Boolean);
    if (words.indexOf("SINGLE") >= 0) { found["1"] = 1; }
    if (words.indexOf("THREE") >= 0) { found["3"] = 1; }
    var keys = Object.keys(found);
    return keys.length === 1 ? keys[0] : null;
  }
  function amps(text) {
    var distinct = [];
    numbersIn(dropThousands(clean(text))).forEach(function (n) {
      var v = number(n);
      if (v !== null && distinct.indexOf(v) < 0) { distinct.push(v); }
    });
    return distinct.length === 1 ? distinct[0] : null;
  }
  function capacityPairs(text) {
    var out = [];
    all(CAPACITY, dropThousands(clean(text))).forEach(function (m) {
      var n = number(m[1]), unit = m[2].replace(/ /g, "");
      unit = UNITS[unit] || unit;
      if (n === null) { return; }
      if (unit === "W") { n = shift(n, -3); unit = "KW"; } else if (unit === "MBH") { n = shift(n, 3); unit = "BTUH"; }
      out.push(n + " " + unit);
    });
    return out;
  }
  function capacity(text) {
    var pairs = capacityPairs(text);
    for (var i = 0; i < ORDER.length; i++) {
      for (var j = 0; j < pairs.length; j++) {
        var p = pairs[j];
        if (p.slice(-(ORDER[i].length + 1)) === " " + ORDER[i]) { return p; }
      }
    }
    return null;
  }
  function refrigerant(text) {
    var found = all(REFRIGERANT, clean(text));
    return found.length ? "R" + found[0][1] : null;
  }
  var CANON = {code: code, volts: volts, phase: phase, amps: amps, capacity: capacity, refrigerant: refrigerant};
  function canon(kind, text) {
    if (!CANON[kind]) { throw new Error("unknown kind " + kind); }
    if (text === null || text === undefined) { return null; }
    return CANON[kind](text);
  }
  function distance(a, b) {
    var prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) { prev.push(j); }
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      for (j = 1; j <= b.length; j++) {
        cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
      }
      prev = cur;
    }
    return prev[b.length];
  }
  return {clean: clean, dropThousands: dropThousands, number: number, shift: shift, canon: canon, distance: distance};
});

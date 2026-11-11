/* A small DOM for the node check. It parses the built page, answers the selectors app.js uses, and reports
   any tag that doesn't close, so the same parse doubles as the markup check. It is not a browser. Layout,
   styles and the network don't exist here, and owner/screenshots.sh covers those in real Chrome. */
"use strict";

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);
const RAW = new Set(["script", "style", "textarea", "title"]);
const ENTITIES = {amp: "&", lt: "<", gt: ">", quot: "\"", apos: "'", nbsp: " "};

function decode(s) {
  if (s.indexOf("&") < 0) { return s; }
  return s.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (m, e) => {
    if (e[0] === "#") { return String.fromCodePoint(e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)); }
    return ENTITIES[e.toLowerCase()] === undefined ? m : ENTITIES[e.toLowerCase()];
  });
}

function escText(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

class Text {
  constructor(data) { this.nodeType = 3; this.data = data; this.parentNode = null; }
  get textContent() { return this.data; }
}

class Element {
  constructor(tag, attrs, doc) {
    this.nodeType = 1;
    this.localName = tag.toLowerCase();
    this.tagName = tag.toUpperCase();
    this.attrs = new Map(attrs || []);
    this.childNodes = [];
    this.parentNode = null;
    this.ownerDocument = doc;
    this.style = {};
    this._value = null;
  }
  get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
  get parentElement() { return this.parentNode && this.parentNode.nodeType === 1 && this.parentNode.localName !== "#document" ? this.parentNode : null; }
  after(n) {
    const p = this.parentNode, i = p.childNodes.indexOf(this);
    if (n.parentNode) { n.parentNode.removeChild(n); }
    n.parentNode = p;
    p.childNodes.splice(i + 1, 0, n);
  }
  remove() { if (this.parentNode) { this.parentNode.removeChild(this); } }
  get firstElementChild() { return this.children[0] || null; }
  getAttribute(n) { return this.attrs.has(n) ? this.attrs.get(n) : null; }
  setAttribute(n, v) { this.attrs.set(n, String(v)); }
  hasAttribute(n) { return this.attrs.has(n); }
  removeAttribute(n) { this.attrs.delete(n); }
  get id() { return this.getAttribute("id") || ""; }
  get className() { return this.getAttribute("class") || ""; }
  set className(v) { this.setAttribute("class", v); }
  get classList() {
    const el = this, list = () => el.className.split(/\s+/).filter(Boolean);
    return {
      contains: (c) => list().includes(c),
      add: (...cs) => { const s = new Set(list()); cs.forEach((c) => s.add(c)); el.className = [...s].join(" "); },
      remove: (...cs) => { el.className = list().filter((x) => !cs.includes(x)).join(" "); },
      toggle: (c, force) => {
        const has = list().includes(c), want = force === undefined ? !has : !!force;
        if (want && !has) { el.classList.add(c); }
        if (!want && has) { el.classList.remove(c); }
        return want;
      },
    };
  }
  get hidden() { return this.hasAttribute("hidden"); }
  set hidden(v) { if (v) { this.setAttribute("hidden", ""); } else { this.removeAttribute("hidden"); } }
  get open() { return this.hasAttribute("open"); }
  set open(v) { if (v) { this.setAttribute("open", ""); } else { this.removeAttribute("open"); } }
  get name() { return this.getAttribute("name") || ""; }
  get value() {
    if (this._value !== null) { return this._value; }
    if (this.localName === "select") {
      const opts = this.querySelectorAll("option");
      const sel = opts.find((o) => o.hasAttribute("selected")) || opts[0];
      return sel ? (sel.hasAttribute("value") ? sel.getAttribute("value") : sel.textContent) : "";
    }
    if (this.localName === "textarea") { return this.textContent; }
    return this.getAttribute("value") || "";
  }
  set value(v) { this._value = String(v); }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(""); }
  set textContent(v) { this.childNodes = []; if (String(v) !== "") { this.appendChild(new Text(String(v))); } }
  get innerHTML() { return this.childNodes.map(serialize).join(""); }
  set innerHTML(html) {
    this.childNodes.forEach((n) => { n.parentNode = null; });
    this.childNodes = [];
    parseInto(this, String(html), this.ownerDocument, this.ownerDocument.errors, "innerHTML of <" + this.localName + ">");
  }
  appendChild(n) {
    if (n.parentNode) { n.parentNode.removeChild(n); }
    n.parentNode = this;
    this.childNodes.push(n);
    return n;
  }
  removeChild(n) {
    const i = this.childNodes.indexOf(n);
    if (i >= 0) { this.childNodes.splice(i, 1); }
    n.parentNode = null;
    return n;
  }
  replaceChild(fresh, old) {
    const i = this.childNodes.indexOf(old);
    if (i < 0) { throw new Error("replaceChild: not a child"); }
    if (fresh.parentNode) { fresh.parentNode.removeChild(fresh); }
    this.childNodes[i] = fresh;
    fresh.parentNode = this;
    old.parentNode = null;
    return old;
  }
  querySelectorAll(sel) {
    const m = compile(sel), out = [];
    walk(this, (el) => { if (m(el)) { out.push(el); } });
    return out;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  matches(sel) { return compile(sel)(this); }
  closest(sel) {
    const m = compile(sel);
    for (let el = this; el && el.nodeType === 1; el = el.parentNode) { if (m(el)) { return el; } }
    return null;
  }
  get ownerSVGElement() {
    for (let el = this.parentNode; el && el.nodeType === 1; el = el.parentNode) { if (el.localName === "svg") { return el; } }
    return null;
  }
  scrollIntoView() { this.ownerDocument.scrolled.push(this); }
  getBoundingClientRect() { return {left: 0, top: 0, width: 100, height: 20, right: 100, bottom: 20}; }
  get offsetWidth() { return 100; }
  focus() { this.ownerDocument.activeElement = this; }
}

function walk(root, fn) {
  const stack = root.childNodes.slice().reverse();
  while (stack.length) {
    const n = stack.pop();
    if (n.nodeType !== 1) { continue; }
    fn(n);
    for (let i = n.childNodes.length - 1; i >= 0; i--) { stack.push(n.childNodes[i]); }
  }
}

function serialize(n) {
  if (n.nodeType === 3) { return escText(n.data); }
  const attrs = [...n.attrs].map(([k, v]) => " " + k + (v === "" ? "" : "=\"" + v.replace(/&/g, "&amp;").replace(/"/g, "&quot;") + "\"")).join("");
  if (VOID.has(n.localName)) { return "<" + n.localName + attrs + ">"; }
  return "<" + n.localName + attrs + ">" + n.childNodes.map(serialize).join("") + "</" + n.localName + ">";
}

/* ------------------------------------------------------------------ selectors: tag, #id, .class, [attr], [attr="v"],
   descendant combinators and comma lists, which is all app.js asks for */
const CACHE = new Map();
function splitOutside(s, sep) {
  const out = [];
  let depth = 0, quote = null, cur = "";
  for (const ch of s) {
    if (quote) { if (ch === quote) { quote = null; } cur += ch; continue; }
    if (ch === "\"" || ch === "'") { quote = ch; cur += ch; continue; }
    if (ch === "[") { depth++; }
    if (ch === "]") { depth--; }
    if (depth === 0 && (sep === " " ? /\s/.test(ch) : ch === sep)) { if (cur) { out.push(cur); } cur = ""; continue; }
    cur += ch;
  }
  if (cur) { out.push(cur); }
  return out;
}
function parseCompound(s) {
  const c = {tag: null, id: null, classes: [], attrs: []};
  let rest = s, m;
  if ((m = /^([a-zA-Z][\w-]*|\*)/.exec(rest))) { c.tag = m[1] === "*" ? null : m[1].toLowerCase(); rest = rest.slice(m[0].length); }
  while (rest) {
    if ((m = /^#([\w-]+)/.exec(rest))) { c.id = m[1]; } else if ((m = /^\.([\w-]+)/.exec(rest))) { c.classes.push(m[1]); } else if (
      (m = /^\[([\w-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\]]*)))?\]/.exec(rest))) {
      c.attrs.push([m[1], m[2] !== undefined ? m[2] : m[3] !== undefined ? m[3] : m[4] !== undefined ? m[4] : null]);
    } else { throw new Error("The node check's selector engine doesn't support " + JSON.stringify(s)); }
    rest = rest.slice(m[0].length);
  }
  return c;
}
function matchCompound(el, c) {
  if (el.nodeType !== 1) { return false; }
  if (c.tag && el.localName !== c.tag) { return false; }
  if (c.id && el.getAttribute("id") !== c.id) { return false; }
  for (const k of c.classes) { if (!el.classList.contains(k)) { return false; } }
  for (const [n, v] of c.attrs) {
    if (!el.hasAttribute(n)) { return false; }
    if (v !== null && el.getAttribute(n) !== v) { return false; }
  }
  return true;
}
function matchComplex(el, parts) {
  if (!matchCompound(el, parts[parts.length - 1])) { return false; }
  let i = parts.length - 2;
  for (let cur = el.parentNode; i >= 0 && cur && cur.nodeType === 1; cur = cur.parentNode) {
    if (matchCompound(cur, parts[i])) { i--; }
  }
  return i < 0;
}
function compile(sel) {
  if (!CACHE.has(sel)) {
    const groups = splitOutside(sel, ",").map((g) => splitOutside(g.trim(), " ").map(parseCompound));
    CACHE.set(sel, (el) => groups.some((g) => matchComplex(el, g)));
  }
  return CACHE.get(sel);
}

/* ------------------------------------------------------------------ the parser */
const TAG = /[a-zA-Z][\w:-]*/y, ATTR = /[^\s=>/]+/y, UNQUOTED = /[^\s>]+/y, SPACE = /\s*/y;
function sticky(re, s, i) { re.lastIndex = i; const m = re.exec(s); return m ? m[0] : null; }

function parseInto(root, html, doc, errors, where) {
  const stack = [root], lower = html.toLowerCase();
  const top = () => stack[stack.length - 1];
  const report = (msg) => { if (errors) { errors.push(where + ": " + msg); } };
  let i = 0;
  while (i < html.length) {
    const lt = html.indexOf("<", i);
    if (lt < 0 || lt > i) {
      const end = lt < 0 ? html.length : lt;
      top().appendChild(new Text(decode(html.slice(i, end))));
      i = end;
      continue;
    }
    if (html.startsWith("<!--", i)) { const j = html.indexOf("-->", i + 4); i = j < 0 ? html.length : j + 3; continue; }
    if (html.startsWith("<!", i)) { i = html.indexOf(">", i) + 1; continue; }
    if (html[i + 1] === "/") {
      const j = html.indexOf(">", i), tag = html.slice(i + 2, j).trim().toLowerCase();
      i = j + 1;
      let k = stack.length - 1;
      while (k > 0 && stack[k].localName !== tag) { k--; }
      if (k === 0) { report("a stray </" + tag + ">"); continue; }
      if (k !== stack.length - 1) { report("<" + top().localName + "> isn't closed before </" + tag + ">"); }
      stack.length = k;
      continue;
    }
    const tag = sticky(TAG, html, i + 1);
    if (!tag) { top().appendChild(new Text("<")); i += 1; continue; }
    let j = i + 1 + tag.length, selfClose = false;
    const attrs = [];
    for (;;) {
      j += sticky(SPACE, html, j).length;
      if (j >= html.length) { report("<" + tag + "> runs off the end"); break; }
      if (html[j] === ">") { j++; break; }
      if (html[j] === "/" && html[j + 1] === ">") { selfClose = true; j += 2; break; }
      const name = sticky(ATTR, html, j);
      if (!name) { report("a bad attribute in <" + tag + ">"); j++; continue; }
      j += name.length;
      let value = "";
      const sp = sticky(SPACE, html, j).length;
      if (html[j + sp] === "=") {
        j += sp + 1;
        j += sticky(SPACE, html, j).length;
        const q = html[j];
        if (q === "\"" || q === "'") {
          const e = html.indexOf(q, j + 1);
          value = html.slice(j + 1, e);
          j = e + 1;
        } else {
          value = sticky(UNQUOTED, html, j) || "";
          j += value.length;
        }
      }
      attrs.push([name, decode(value)]);
    }
    const el = new Element(tag, attrs, doc);
    top().appendChild(el);
    i = j;
    const t = tag.toLowerCase();
    if (selfClose || VOID.has(t)) { continue; }
    if (RAW.has(t)) {
      const end = lower.indexOf("</" + t, i);
      if (end < 0) { report("<" + t + "> never closes"); i = html.length; continue; }
      if (end > i) { el.childNodes.push(Object.assign(new Text(t === "textarea" || t === "title" ? decode(html.slice(i, end)) : html.slice(i, end)), {parentNode: el})); }
      i = html.indexOf(">", end) + 1;
      continue;
    }
    stack.push(el);
  }
  if (stack.length > 1) { report("these never close: " + stack.slice(1).map((e) => "<" + e.localName + ">").join(" ")); }
}

class Document {
  constructor(html) {
    this.listeners = {};
    this.scrolled = [];
    this.errors = [];
    this.activeElement = null;
    this.readyState = "loading";
    this.root = new Element("#document", [], this);
    parseInto(this.root, html, this, this.errors, "index.html");
    this.documentElement = this.root.querySelector("html");
    this.head = this.root.querySelector("head");
    this.body = this.root.querySelector("body");
  }
  getElementById(id) {
    let found = null;
    walk(this.root, (el) => { if (!found && el.getAttribute("id") === id) { found = el; } });
    return found;
  }
  querySelector(sel) { return this.root.querySelector(sel); }
  querySelectorAll(sel) { return this.root.querySelectorAll(sel); }
  createElement(tag) { return new Element(tag, [], this); }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  removeEventListener(type, fn) {
    const l = this.listeners[type] || [], i = l.indexOf(fn);
    if (i >= 0) { l.splice(i, 1); }
  }
  dispatch(type, target, extra) {
    const ev = Object.assign({type: type, target: target, defaultPrevented: false, clientX: 40, clientY: 40,
      preventDefault() { this.defaultPrevented = true; }}, extra || {});
    for (const fn of (this.listeners[type] || []).slice()) { fn(ev); }
    return ev;
  }
}

module.exports = {Document, Element, Text, parseInto, compile};

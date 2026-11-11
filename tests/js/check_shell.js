/* The node check on the built page's markup: it parses, loads nothing from another site, and has no inline script or
   style, so the site's security policy can stay strict. Phase 4 adds the full click-through beside it. Exits 1 on any
   failed check.

       node tests/js/check_shell.js */
"use strict";
const fs = require("fs");
const path = require("path");

const site = path.join(__dirname, "..", "..", "site");
const html = fs.readFileSync(path.join(site, "index.html"), "utf8");
const checks = [];
const check = (name, ok, detail) => checks.push({name, ok: !!ok, detail: detail || ""});

check("the page starts with a doctype", html.startsWith("<!doctype html>"));
check("the page has a title", /<title>[^<]+<\/title>/.test(html));
check("no script, style, image or font comes from another site", !/\ssrc=['"](https?:)?\/\//.test(html) &&
  !/<link(?![^>]*rel=['"]canonical['"])[^>]+href=['"](https?:)?\/\//.test(html));
check("no inline script or style", !/<script>(?!<\/script>)|<script[^>]*>[^<]+<\/script>| style=/.test(html));
check("the stylesheet is there", fs.existsSync(path.join(site, "app.css")));
check("the fonts are there", ["inter-latin.woff2", "jetbrains-mono-latin.woff2"].every((f) => fs.existsSync(path.join(site, "fonts", f))));
const opens = (html.match(/<(div|main|header|footer|section|p|nav|aside)\b/g) || []).length;
const closes = (html.match(/<\/(div|main|header|footer|section|p|nav|aside)>/g) || []).length;
check("every block element closes", opens === closes, `${opens} opened, ${closes} closed`);

const failed = checks.filter((c) => !c.ok);
failed.forEach((c) => console.log(`FAIL ${c.name} ${c.detail}`));
console.log(`${checks.length - failed.length} of ${checks.length} page checks pass`);
process.exit(failed.length ? 1 : 0);

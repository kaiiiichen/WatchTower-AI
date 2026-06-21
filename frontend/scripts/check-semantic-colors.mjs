#!/usr/bin/env node
/**
 * Fails if semantic Tailwind hues appear outside semantic-colors.ts.
 * Neutrals (zinc) and theme accent hex in globals.css are allowed.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const SRC = join(ROOT, "src");
const ALLOWLIST = new Set(["src/lib/semantic-colors.ts"]);

const HUES =
  "rose|emerald|amber|sky|yellow|orange|red|green|blue|cyan|teal|lime|violet|purple|pink|fuchsia|indigo";
const PATTERN = new RegExp(
  String.raw`\b(text|bg|border|ring|from|to|via|fill|stroke|decoration)-(${HUES})-\d`,
  "g"
);

function walk(dir, files = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, files);
    else if (/\.(tsx|ts)$/.test(name)) files.push(path);
  }
  return files;
}

const violations = [];

for (const file of walk(SRC)) {
  const rel = relative(ROOT, file).replaceAll("\\", "/");
  if (ALLOWLIST.has(rel)) continue;

  const content = readFileSync(file, "utf8");
  const lines = content.split("\n");
  lines.forEach((line, i) => {
    PATTERN.lastIndex = 0;
    const matches = [...line.matchAll(PATTERN)];
    for (const m of matches) {
      violations.push({ file: rel, line: i + 1, match: m[0] });
    }
  });
}

if (violations.length) {
  console.error("\n❌ Semantic color policy: use SEMANTIC_COLORS from @/lib/style-maps\n");
  console.error("   Raw Tailwind hue classes are only allowed in src/lib/semantic-colors.ts\n");
  for (const v of violations) {
    console.error(`   ${v.file}:${v.line}  →  ${v.match}`);
  }
  console.error("\n   See frontend/AGENTS.md and .cursor/rules/semantic-colors.mdc\n");
  process.exit(1);
}

console.log("✓ semantic color check passed");

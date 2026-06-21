<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# WatchTower frontend — agent guide

## Semantic colors (read this before any UI work)

**Do not add raw Tailwind color utilities** (`text-rose-600`, `bg-emerald-50`, `border-amber-200`, …) in components, pages, or `style-maps.ts`.

All product semantics (status tints, callouts, charts) use the **Detection Gap palette** in **`src/lib/semantic-colors.ts`**, re-exported via **`src/lib/style-maps.ts`**.

Card chrome (mag-card borders, cream/dark backgrounds, bronze `--accent`) is independent of this palette.

### Quick reference

```tsx
import {
  SEMANTIC_COLORS,  // rose | emerald | amber | sky
  semantic,          // semantic("rose").text
  PROVIDER_OK,       // operational / QA pass green (Provider cards)
  SEVERITY_COLORS,   // alert info → sky, warning → amber, critical → rose
  STATUS_STYLES,     // provider status dots + labels
  VERDICT_STYLES,    // local diagnostics verdicts
} from "@/lib/style-maps";
```

Each hue exposes: `inset` · `accent` · `text` · `textStrong` · `textEmphasis` · `textOnTint` · `dot` · `bar` · `barSoft` · `chip`.

### Hue → meaning (matches Detection Gap)

| Hue | Use for |
|-----|---------|
| `rose` | errors, critical alerts, down, fail, major outage, problem stats |
| `emerald` | success, operational, resolved, pass, WatchTower value callouts |
| `amber` | warnings, degraded, user impact, delays, rate limits, partial issues |
| `sky` | info, maintenance, official response, histogram bars |

Neutrals (`zinc-*`, `var(--background)`, `var(--accent)`) are not part of this palette.

### Examples

```tsx
// Tinted callout (Detection Gap style)
<div className={`mag-card-inset ${SEMANTIC_COLORS.rose.inset}`}>
  <span className={SEMANTIC_COLORS.rose.textStrong}>42%</span>
</div>

// Provider-matching green
<span className={PROVIDER_OK.text}>Pass</span>
```

### Changing colors

Edit **`src/lib/semantic-colors.ts` only**. Then run:

```bash
npm run lint:colors
```

### Enforcement

- Cursor rule: `.cursor/rules/semantic-colors.mdc`
- CI/local: `npm run lint:colors` (also runs as part of `npm run lint`)

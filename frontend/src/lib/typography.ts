/** Site-wide type scale: 12 → 16 → 20 px (arithmetic progression, d = 4). */

export const TYPE_SCALE = {
  sm: 12,
  md: 16,
  lg: 20,
  stat: 28,
} as const;

const family = { fontFamily: "'Nunito'" } as const;

export const typeSm = { ...family, fontWeight: 400, fontSize: TYPE_SCALE.sm, lineHeight: 1.5 } as const;
export const typeSmSemibold = {
  ...family,
  fontWeight: 600,
  fontSize: TYPE_SCALE.sm,
  lineHeight: 1.45,
} as const;
export const typeMd = { ...family, fontWeight: 400, fontSize: TYPE_SCALE.md, lineHeight: 1.65 } as const;
export const typeMdSemibold = {
  ...family,
  fontWeight: 600,
  fontSize: TYPE_SCALE.md,
  lineHeight: 1.4,
} as const;
export const typeLg = { ...family, fontWeight: 600, fontSize: TYPE_SCALE.lg, lineHeight: 1.25 } as const;
export const typeLgLight = {
  ...family,
  fontWeight: 300,
  fontSize: TYPE_SCALE.lg,
  lineHeight: 1.2,
} as const;

/** Hero metrics (Detection gap backtest figures). */
export const typeStat = {
  ...family,
  fontWeight: 600,
  fontSize: TYPE_SCALE.stat,
  lineHeight: 1.1,
} as const;

export const monoSm = {
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: TYPE_SCALE.sm,
  lineHeight: 1.4,
} as const;

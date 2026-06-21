/** Minimal satellite mark — uses site CSS vars (--accent, --foreground, --background). */

type Props = {
  size?: number;
  className?: string;
  /** Show downward signal arcs (monitoring / radar). */
  showSignal?: boolean;
  /** Show partial orbit arc. */
  showOrbit?: boolean;
};

export default function WatchTowerLogo({
  size = 32,
  className = "",
  showSignal = true,
  showOrbit = true,
}: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      {showOrbit ? (
        <path
          d="M36 8A20 20 0 0 0 8 36"
          stroke="var(--accent)"
          strokeOpacity={0.35}
          strokeWidth={1.75}
          strokeLinecap="round"
        />
      ) : null}

      {/* Solar panels */}
      <rect
        x={3}
        y={21}
        width={11}
        height={7}
        rx={1.5}
        className="fill-zinc-400/40 dark:fill-zinc-500/35"
      />
      <rect
        x={34}
        y={21}
        width={11}
        height={7}
        rx={1.5}
        className="fill-zinc-400/40 dark:fill-zinc-500/35"
      />
      <line
        x1={14}
        y1={24.5}
        x2={17}
        y2={24.5}
        stroke="var(--accent)"
        strokeOpacity={0.5}
        strokeWidth={1.25}
        strokeLinecap="round"
      />
      <line
        x1={31}
        y1={24.5}
        x2={34}
        y2={24.5}
        stroke="var(--accent)"
        strokeOpacity={0.5}
        strokeWidth={1.25}
        strokeLinecap="round"
      />

      {/* Bus */}
      <rect x={14} y={19} width={20} height={11} rx={3} fill="var(--accent)" />
      <circle cx={24} cy={24.5} r={2.75} fill="var(--background)" />

      {/* Antenna */}
      <path
        d="M24 19V13.5"
        stroke="var(--accent)"
        strokeWidth={1.75}
        strokeLinecap="round"
      />
      <circle cx={24} cy={12} r={2.25} fill="var(--accent)" />

      {showSignal ? (
        <>
          <path
            d="M18.5 35.5C20.8 33.2 27.2 33.2 29.5 35.5"
            stroke="var(--accent)"
            strokeWidth={1.75}
            strokeLinecap="round"
          />
          <path
            d="M15.5 39.5C19.5 35 28.5 35 32.5 39.5"
            stroke="var(--accent)"
            strokeOpacity={0.55}
            strokeWidth={1.75}
            strokeLinecap="round"
          />
        </>
      ) : null}
    </svg>
  );
}

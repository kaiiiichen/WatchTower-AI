// Dependency-free SVG line chart for latency history.
// Keeps the skeleton lean; swap for recharts later if richer interaction is needed.

interface Props {
  data: { t: string; ms: number }[];
  color?: string;
  height?: number;
}

export default function LatencyChart({
  data,
  color = "#34d399",
  height = 56,
}: Props) {
  if (data.length < 2) return null;

  const width = 240;
  const pad = 4;
  const xs = data.map((_, i) => (i / (data.length - 1)) * (width - pad * 2) + pad);
  const max = Math.max(...data.map((d) => d.ms));
  const min = Math.min(...data.map((d) => d.ms));
  const range = Math.max(1, max - min);
  const ys = data.map(
    (d) => height - pad - ((d.ms - min) / range) * (height - pad * 2)
  );

  const path = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ");
  const area = `${path} L${xs[xs.length - 1]},${height} L${xs[0]},${height} Z`;

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="block"
    >
      <path d={area} fill={color} fillOpacity={0.12} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

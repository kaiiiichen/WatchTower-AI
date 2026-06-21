import type { Alert } from "@/lib/types";
import { SEVERITY_STYLES } from "@/lib/style-maps";

// Renders the "Agent" action chain as a narrative card.
export default function AlertBanner({ alert }: { alert: Alert }) {
  return (
    <div className={`rounded-2xl border p-5 ${SEVERITY_STYLES[alert.severity]}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-white/60">
          {alert.severity}
        </span>
        <h3 className="text-base font-semibold text-white">{alert.title}</h3>
        {alert.communityConfirmed ? (
          <span className="rounded-full bg-rose-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-300">
            ◉ Confirmed widespread · unacknowledged
          </span>
        ) : null}
        {alert.officialAcknowledged ? (
          <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-300">
            ✓ Official acknowledged
          </span>
        ) : null}
      </div>

      <p className="mt-3 text-sm leading-relaxed text-white/80">{alert.insight}</p>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Field label="Whose problem?" value={alert.attribution} />
        <Field label="Est. recovery" value={alert.recoveryEta} />
        <Field label="Recommended fallback" value={alert.recommendedAlternative} />
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-black/20 p-3">
      <div className="text-xs font-medium text-white/40">{label}</div>
      <div className="mt-1 text-sm text-white/90">{value}</div>
    </div>
  );
}

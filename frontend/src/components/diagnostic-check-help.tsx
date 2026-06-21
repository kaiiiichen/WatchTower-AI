import { diagnosticCheckHelp } from "@/lib/diagnostic-check-help";
import HoverTip from "./hover-tip";

export default function DiagnosticCheckHelp({ check }: { check: string }) {
  const help = diagnosticCheckHelp(check);
  if (!help) return null;

  return (
    <HoverTip tip={help} placement="top" align="center">
      <button
        type="button"
        aria-label={`What does the ${check} check mean?`}
        className="help-icon"
      >
        ?
      </button>
    </HoverTip>
  );
}

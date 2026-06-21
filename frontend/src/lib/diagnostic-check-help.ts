/** Plain-language explanations for local diagnostic checks (dns · tcp · key). */
export const DIAGNOSTIC_CHECK_HELP: Record<string, string> = {
  dns: "Resolves the provider’s API hostname to an IP address. Failure usually points to local DNS, VPN, or firewall issues — not a provider-wide outage.",
  tcp: "Opens a TCP connection to the API on port 443. Confirms your network can reach the host; this is not a full API request and does not use your key.",
  key: "Sends a lightweight authenticated request with your API key. Failure often means a missing, invalid, or expired key — not necessarily a service outage.",
};

export function diagnosticCheckHelp(check: string): string | undefined {
  return DIAGNOSTIC_CHECK_HELP[check.toLowerCase()];
}

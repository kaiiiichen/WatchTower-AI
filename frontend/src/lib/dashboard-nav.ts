export type PageSection = "dashboard" | "diagnostics" | "about";

export type NavItem = {
  id: PageSection;
  label: string;
  anchor: string;
};

export const PAGE_NAV: NavItem[] = [
  { id: "dashboard", label: "Dashboard", anchor: "section-dashboard" },
  { id: "diagnostics", label: "Diagnostics", anchor: "section-diagnostics" },
  { id: "about", label: "About", anchor: "section-about" },
];

export function navItem(id: PageSection): NavItem {
  return PAGE_NAV.find((n) => n.id === id) ?? PAGE_NAV[0];
}

export function scrollToSection(anchor: string) {
  const el = document.getElementById(anchor);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

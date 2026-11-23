export type ThemePref = "light" | "dark" | "system";

const STORAGE = "dj_theme_pref";

export function getThemePref(): ThemePref {
  const v = localStorage.getItem(STORAGE);
  if (v === "light" || v === "dark" || v === "system") return v;
  return "system";
}

export function setThemePref(mode: ThemePref): void {
  localStorage.setItem(STORAGE, mode);
  applyTheme();
}

export function applyTheme(): void {
  const pref = getThemePref();
  const dark =
    pref === "dark" ||
    (pref === "system" && typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
}

export function initTheme(): void {
  applyTheme();
  if (typeof window === "undefined") return;
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (getThemePref() === "system") applyTheme();
  });
}

import { create } from "zustand";

export type ThemeMode = "light" | "dark";
export type ColorTheme = "emerald" | "violet" | "ocean" | "indigo" | "rose";

interface ThemeState {
  theme: ThemeMode;
  colorTheme: ColorTheme;
  toggleTheme: () => void;
  setTheme: (theme: ThemeMode) => void;
  setColorTheme: (colorTheme: ColorTheme) => void;
}

const STORAGE_KEY = "meeting-workspace-theme";
const COLOR_STORAGE_KEY = "meeting-workspace-color-theme";

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "dark";

  const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
  if (saved === "light" || saved === "dark") {
    return saved;
  }

  return "dark";
}

function getInitialColorTheme(): ColorTheme {
  if (typeof window === "undefined") return "emerald";

  const saved = localStorage.getItem(COLOR_STORAGE_KEY) as ColorTheme | null;
  if (saved && ["emerald", "violet", "ocean", "indigo", "rose"].includes(saved)) {
    return saved;
  }

  return "emerald";
}

function applyThemeClass(theme: ThemeMode) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  localStorage.setItem(STORAGE_KEY, theme);
}

function applyColorTheme(color: ColorTheme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-color-theme", color);
  localStorage.setItem(COLOR_STORAGE_KEY, color);
}

export const useThemeStore = create<ThemeState>((set, get) => {
  const initialTheme = getInitialTheme();
  const initialColorTheme = getInitialColorTheme();

  applyThemeClass(initialTheme);
  applyColorTheme(initialColorTheme);

  return {
    theme: initialTheme,
    colorTheme: initialColorTheme,
    toggleTheme: () => {
      const nextTheme = get().theme === "dark" ? "light" : "dark";
      applyThemeClass(nextTheme);
      set({ theme: nextTheme });
    },
    setTheme: (theme: ThemeMode) => {
      applyThemeClass(theme);
      set({ theme });
    },
    setColorTheme: (colorTheme: ColorTheme) => {
      applyColorTheme(colorTheme);
      set({ colorTheme });
    },
  };
});

import { create } from "zustand";

type ThemeMode = "light" | "dark";

interface ThemeState {
  theme: ThemeMode;
  toggleTheme: () => void;
  setTheme: (theme: ThemeMode) => void;
}

const STORAGE_KEY = "meeting-workspace-theme";

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  
  const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
  if (saved === "light" || saved === "dark") {
    return saved;
  }
  
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  
  return "light";
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

export const useThemeStore = create<ThemeState>((set, get) => {
  const initialTheme = getInitialTheme();
  applyThemeClass(initialTheme);

  return {
    theme: initialTheme,
    toggleTheme: () => {
      const nextTheme = get().theme === "dark" ? "light" : "dark";
      applyThemeClass(nextTheme);
      set({ theme: nextTheme });
    },
    setTheme: (theme: ThemeMode) => {
      applyThemeClass(theme);
      set({ theme });
    },
  };
});

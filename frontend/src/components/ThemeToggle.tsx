import { useState, useRef, useEffect } from "react";
import { Sun, Moon, Palette, Check } from "lucide-react";
import { useThemeStore, type ColorTheme } from "../store/themeStore";

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

const COLOR_OPTIONS: { id: ColorTheme; label: string; dot: string }[] = [
  { id: "emerald", label: "Cyber Emerald", dot: "bg-emerald-500" },
  { id: "violet", label: "Electric Violet", dot: "bg-violet-500" },
  { id: "ocean", label: "Ocean Teal", dot: "bg-teal-500" },
  { id: "indigo", label: "Classic Indigo", dot: "bg-indigo-500" },
  { id: "rose", label: "Sunset Rose", dot: "bg-rose-500" },
];

export default function ThemeToggle({ className = "", showLabel = false }: ThemeToggleProps) {
  const { theme, toggleTheme, colorTheme, setColorTheme } = useThemeStore();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const isDark = theme === "dark";

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={menuRef} className={`relative inline-flex items-center gap-1 ${className}`}>
      {/* Light / Dark Mode Toggle */}
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
        title={`Switch to ${isDark ? "light" : "dark"} mode`}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all duration-200 cursor-pointer ${
          isDark
            ? "bg-slate-800 border-slate-700 text-amber-400 hover:bg-slate-700 hover:text-amber-300"
            : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-xs"
        }`}
      >
        {isDark ? (
          <Sun className="w-3.5 h-3.5 transition-transform hover:rotate-45" />
        ) : (
          <Moon className="w-3.5 h-3.5 transition-transform hover:-rotate-12" />
        )}
        {showLabel && <span>{isDark ? "Light" : "Dark"}</span>}
      </button>

      {/* Color Palette Menu Button */}
      <button
        type="button"
        onClick={() => setIsMenuOpen(!isMenuOpen)}
        title="Customize Project Color Theme"
        className={`inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border text-xs font-semibold transition-all duration-200 cursor-pointer ${
          isDark
            ? "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white"
            : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-xs"
        }`}
      >
        <Palette className="w-3.5 h-3.5 text-indigo-400" />
        <span
          className={`h-2 w-2 rounded-full ${
            COLOR_OPTIONS.find((c) => c.id === colorTheme)?.dot || "bg-emerald-500"
          }`}
        />
      </button>

      {/* Dropdown Menu for Selecting Color Theme */}
      {isMenuOpen && (
        <div className="absolute right-0 top-full mt-2 z-50 w-44 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-slate-800 dark:bg-slate-900 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Accent Theme
          </div>
          <div className="space-y-0.5 mt-1">
            {COLOR_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                onClick={() => {
                  setColorTheme(opt.id);
                  setIsMenuOpen(false);
                }}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition cursor-pointer ${
                  colorTheme === opt.id
                    ? "bg-indigo-50 font-bold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400"
                    : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${opt.dot} shadow-xs`} />
                  <span>{opt.label}</span>
                </div>
                {colorTheme === opt.id && <Check className="h-3 w-3 text-indigo-500" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

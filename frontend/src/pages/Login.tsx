import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle,
  Eye,
  EyeOff,
  Flame,
  Loader2,
  Lock,
  Mail,
  Sparkles,
  User,
} from "lucide-react";

import { apiClient } from "../api/client";
import { useAuthStore } from "../store/authStore";
import ThemeToggle from "../components/ThemeToggle";

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    email: string;
    full_name: string | null;
    is_guest?: boolean;
  };
}

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialMode = searchParams.get("tab") === "register" ? "register" : "login";

  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const setAuth = useAuthStore((state) => state.setAuth);
  const continueAsGuest = useAuthStore((state) => state.continueAsGuest);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        // Register new permanent account
        await apiClient.post("/auth/register", {
          email,
          password,
          full_name: fullName.trim() || undefined,
        });

        // Automatically log in after registration
        const loginResponse = await apiClient.post<LoginResponse>("/auth/login", {
          email,
          password,
        });

        const { access_token, user } = loginResponse.data;
        setAuth(access_token, user, false);
      } else {
        // Sign in to existing account
        const loginResponse = await apiClient.post<LoginResponse>("/auth/login", {
          email,
          password,
        });

        const { access_token, user } = loginResponse.data;
        setAuth(access_token, user, false);
      }

      navigate("/");
    } catch (err: any) {
      const message =
        err?.response?.data?.detail ??
        (mode === "register" ? "Unable to create account" : "Invalid email or password");
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGuestMode() {
    setError("");
    setGuestLoading(true);
    try {
      await continueAsGuest();
      navigate("/");
    } catch {
      setError("Unable to start guest session. Please try again.");
    } finally {
      setGuestLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 px-4 py-12 transition-colors duration-150">
      <div className="w-full max-w-md">
        {/* Top actions: back and theme toggle */}
        <div className="mb-4 flex items-center justify-between">
          <button
            onClick={() => navigate("/")}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 transition hover:text-slate-900 dark:hover:text-white cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Home
          </button>

          <ThemeToggle />
        </div>

        <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white p-8 shadow-xl dark:border-slate-800 dark:bg-slate-900 transition-colors">
          {/* Header */}
          <div className="mb-6 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-md shadow-indigo-500/20">
              <Sparkles className="h-6 w-6" />
            </div>

            <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              {mode === "login" ? "Welcome back" : "Create your account"}
            </h1>

            <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
              {mode === "login"
                ? "Sign in to access your permanent meeting transcripts and AI insights"
                : "Get permanent storage for your recordings, summaries, and action items"}
            </p>
          </div>

          {/* Mode Tabs */}
          <div className="mb-6 flex rounded-xl bg-slate-100 p-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError("");
              }}
              className={`flex-1 rounded-lg py-2 transition cursor-pointer ${
                mode === "login"
                  ? "bg-white text-slate-900 shadow-xs dark:bg-slate-700 dark:text-white"
                  : "hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setError("");
              }}
              className={`flex-1 rounded-lg py-2 transition cursor-pointer ${
                mode === "register"
                  ? "bg-white text-slate-900 shadow-xs dark:bg-slate-700 dark:text-white"
                  : "hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              Create Account
            </button>
          </div>

          {error && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-600 dark:border-red-800/40 dark:bg-red-950/40 dark:text-red-300">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    required
                    placeholder="Alex Morgan"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3.5 text-xs text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3.5 text-xs text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-10 text-xs text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full rounded-xl bg-indigo-600 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-600/30 transition hover:bg-indigo-500 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-1.5"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {mode === "login" ? "Signing In..." : "Creating Account..."}
                </>
              ) : mode === "login" ? (
                "Sign In to Workspace"
              ) : (
                "Create Permanent Account"
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200 dark:border-slate-800" />
            </div>
            <span className="relative bg-white px-2 text-[10px] uppercase tracking-wider text-slate-400 dark:bg-slate-900">
              Or Try Instantly
            </span>
          </div>

          {/* Ephemeral Guest Mode Option */}
          <div className="rounded-2xl border border-amber-300/60 bg-amber-50/60 p-4 dark:border-amber-400/20 dark:bg-amber-400/5">
            <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800 dark:text-amber-400">
              <Flame className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
              Try Without Creating Account
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300">
              Explore immediate meeting upload, speech-to-text, and summaries. <strong>Data is temporary and wiped upon exit.</strong>
            </p>

            <button
              type="button"
              onClick={handleGuestMode}
              disabled={guestLoading}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl border border-amber-500/40 bg-white py-2 text-xs font-bold text-amber-900 shadow-2xs transition hover:bg-amber-100 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200 dark:hover:bg-amber-400/20 disabled:opacity-50 cursor-pointer"
            >
              {guestLoading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Setting up Guest Session...
                </>
              ) : (
                <>
                  <CheckCircle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                  Launch Guest Mode (Ephemeral)
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  Brain,
  CheckCircle2,
  Database,
  FileAudio,
  Flame,
  Loader2,
  Mail,
  Milestone,
  Play,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { useAuthStore } from "../store/authStore";
import ThemeToggle from "../components/ThemeToggle";

export default function LandingPage() {
  const navigate = useNavigate();
  const continueAsGuest = useAuthStore((state) => state.continueAsGuest);
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleStartGuest() {
    setGuestLoading(true);
    try {
      await continueAsGuest();
      navigate("/");
    } catch (e) {
      console.error("Guest session error", e);
    } finally {
      setGuestLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 selection:bg-indigo-500 selection:text-white transition-colors duration-150">
      {/* Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 dark:border-slate-800/80 dark:bg-slate-900/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 text-white shadow-md shadow-indigo-500/20">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="text-base font-extrabold tracking-tight text-slate-900 dark:text-white">
                AI Meeting Workspace
              </span>
              <span className="ml-2 hidden rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 sm:inline-block">
                Intelligence Platform
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Dark/Light Mode Switcher */}
            <ThemeToggle />

            {/* Try Without Account Button */}
            <button
              onClick={handleStartGuest}
              disabled={guestLoading}
              className="hidden rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs font-semibold text-amber-700 dark:text-amber-300 transition hover:bg-amber-500/20 sm:inline-flex items-center gap-1.5 cursor-pointer"
            >
              {guestLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Flame className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
              )}
              Try Without Account
            </button>

            {/* Log In Button */}
            <button
              onClick={() => navigate("/login")}
              className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 transition hover:bg-slate-100 dark:hover:bg-slate-700 cursor-pointer"
            >
              Sign In
            </button>

            {/* Create Account Button */}
            <button
              onClick={() => navigate("/login?tab=register")}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-indigo-600/30 transition hover:bg-indigo-500 cursor-pointer"
            >
              Create Account
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden px-6 pt-16 pb-20 sm:pt-24 sm:pb-32">
        {/* Glow backdrop */}
        <div className="pointer-events-none absolute -top-40 left-1/2 -z-10 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-gradient-to-tr from-indigo-500/20 to-purple-500/20 blur-3xl" />

        <div className="mx-auto max-w-5xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3.5 py-1 text-xs font-semibold text-indigo-700 dark:text-indigo-300">
            <Brain className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
            Speech AI • Diarization • LLM Summaries • Vector RAG
          </div>

          <h1 className="mt-6 text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-6xl sm:leading-tight">
            Transform Recorded Meetings into{" "}
            <span className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 dark:from-indigo-400 dark:via-purple-300 dark:to-pink-400 bg-clip-text text-transparent">
              Searchable Knowledge
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-slate-600 dark:text-slate-300 sm:text-lg">
            Upload meeting audio or video, generate speech-to-text with speaker diarization,
            extract action items and decisions, sync audio playback with transcripts,
            and chat with your historical meetings using an AI Assistant.
          </p>

          {/* Dual Entry Choices */}
          <div className="mx-auto mt-12 grid max-w-3xl gap-5 sm:grid-cols-2 text-left">
            {/* Option 1: Guest Mode */}
            <div className="relative flex flex-col justify-between rounded-3xl border border-amber-400/40 bg-gradient-to-b from-amber-500/10 to-white/70 dark:border-amber-400/30 dark:from-amber-400/5 dark:to-transparent p-6 backdrop-blur-sm shadow-xs transition hover:border-amber-500/60 dark:hover:border-amber-400/50 hover:shadow-lg hover:shadow-amber-500/5">
              <div>
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400">
                  <Flame className="h-4 w-4" />
                  Option 1: Ephemeral Trial
                </div>
                <h3 className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
                  Try Without Creating Account
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  Zero setup required. Try all features immediately.
                </p>
                <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-500/10 dark:border-amber-400/20 dark:bg-amber-400/10 p-3 text-[11px] text-amber-900 dark:text-amber-200">
                  <strong className="block font-semibold">Privacy & Storage Notice:</strong>
                  Data is temporary. Once you close this site, your guest session and data will vanish completely.
                </div>
              </div>

              <button
                onClick={handleStartGuest}
                disabled={guestLoading}
                className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 px-4 py-3 text-xs font-bold text-slate-950 shadow-md shadow-amber-500/20 transition hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 cursor-pointer"
              >
                {guestLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Launching Guest Mode...
                  </>
                ) : (
                  <>
                    Explore as Guest (No Account)
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>

            {/* Option 2: Permanent Account */}
            <div className="relative flex flex-col justify-between rounded-3xl border border-indigo-200 bg-gradient-to-b from-indigo-50/70 to-white/70 dark:border-indigo-500/40 dark:from-indigo-500/10 dark:to-transparent p-6 backdrop-blur-sm shadow-xs transition hover:border-indigo-400 hover:shadow-lg hover:shadow-indigo-500/10">
              <div>
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-400">
                  <ShieldCheck className="h-4 w-4" />
                  Option 2: Permanent Workspace
                </div>
                <h3 className="mt-2 text-xl font-bold text-slate-900 dark:text-white">
                  Create Account / Sign In
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  Save all your meetings, recordings, transcripts, and AI insights permanently.
                </p>
                <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-[11px] text-indigo-900 dark:border-indigo-500/20 dark:bg-indigo-500/10 dark:text-indigo-200">
                  <strong className="block font-semibold">Permanent Database Storage:</strong>
                  Your recordings, speaker maps, action items, and cross-meeting RAG index remain safely preserved.
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-2">
                <button
                  onClick={() => navigate("/login?tab=register")}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-xs font-bold text-white shadow-md shadow-indigo-600/30 transition hover:bg-indigo-500 cursor-pointer"
                >
                  Create Permanent Account
                  <ArrowRight className="h-4 w-4" />
                </button>
                <button
                  onClick={() => navigate("/login")}
                  className="text-center text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer"
                >
                  Already have an account? Sign in
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Architecture & Pipeline Showcase */}
      <section className="border-y border-slate-200 bg-slate-100/70 dark:border-slate-800 dark:bg-slate-950/60 px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              Core Technical Architecture
            </h2>
            <p className="mt-2 text-3xl font-extrabold text-slate-900 dark:text-white">
              End-to-End Meeting Intelligence Pipeline
            </p>
            <p className="mx-auto mt-3 max-w-2xl text-xs text-slate-600 dark:text-slate-400">
              From raw audio ingestion to vector embeddings and conversational retrieval.
            </p>
          </div>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                step: "01",
                icon: FileAudio,
                title: "Audio Processing",
                desc: "Upload MP3, WAV, M4A, or MP4. Asynchronous processing with Celery and Range streaming.",
              },
              {
                step: "02",
                icon: Users,
                title: "Speech & Diarization",
                desc: "Whisper word-level speech-to-text combined with Pyannote speaker clustering and stabilization.",
              },
              {
                step: "03",
                icon: Brain,
                title: "AI Summaries & Actions",
                desc: "Automatic executive briefs, action items with owners and deadlines, and decision tracking.",
              },
              {
                step: "04",
                icon: Bot,
                title: "Vector Search & RAG",
                desc: "Semantic chunking and embeddings. Ask natural language questions with [MM:SS] citations.",
              },
            ].map((item, idx) => {
              const Icon = item.icon;
              return (
                <div
                  key={idx}
                  className="relative rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/60 p-6 shadow-xs"
                >
                  <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                    {item.step}
                  </span>
                  <div className="mt-3 flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                    {item.desc}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              Product Capabilities
            </h2>
            <p className="mt-2 text-3xl font-extrabold text-slate-900 dark:text-white">
              Everything Needed for Modern Meeting Intelligence
            </p>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                icon: Play,
                title: "Synchronized Playback",
                desc: "Jump straight from any transcript line, action item, or AI response directly to the exact second in the audio recording.",
              },
              {
                icon: CheckCircle2,
                title: "Action Item Extraction",
                desc: "Tasks, assignees, priorities, and deadlines are extracted automatically with interactive checkbox tracking.",
              },
              {
                icon: Milestone,
                title: "Decision Tracking",
                desc: "Centralized log of key agreements, architectural choices, and team consensus with timestamp references.",
              },
              {
                icon: Bot,
                title: "RAG AI Assistant",
                desc: "Ask questions across a single meeting or hundreds of past meetings. Answers cite exact [MM:SS] timestamps.",
              },
              {
                icon: Mail,
                title: "Follow-Up Emails",
                desc: "Generate complete, polished meeting recap emails with action items and recipients in a single click.",
              },
              {
                icon: Database,
                title: "Storage Choice",
                desc: "Guest mode for private zero-storage exploration, or permanent account storage with PostgreSQL.",
              },
            ].map((f, i) => {
              const Icon = f.icon;
              return (
                <div
                  key={i}
                  className="rounded-2xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/40 p-6 shadow-xs transition hover:border-indigo-300 dark:hover:border-slate-700"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-indigo-600 dark:bg-slate-800 dark:text-indigo-400">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h4 className="mt-4 font-bold text-slate-900 dark:text-white">{f.title}</h4>
                  <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                    {f.desc}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA Footer */}
      <footer className="border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950 px-6 py-12 text-center">
        <h3 className="text-xl font-bold text-slate-900 dark:text-white">
          Get Started with AI Meeting Workspace
        </h3>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          Choose to test instantly as a guest or create an account for permanent storage.
        </p>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <button
            onClick={handleStartGuest}
            disabled={guestLoading}
            className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-5 py-2.5 text-xs font-bold text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 cursor-pointer"
          >
            {guestLoading ? "Starting Guest..." : "Try Without Account (Guest Demo)"}
          </button>
          <button
            onClick={() => navigate("/login?tab=register")}
            className="rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-600/30 hover:bg-indigo-500 cursor-pointer"
          >
            Create Permanent Account
          </button>
        </div>

        <p className="mt-8 text-[11px] text-slate-500">
          AI Meeting Workspace © 2026. Built with Speech AI, Diarization, and RAG.
        </p>
      </footer>
    </div>
  );
}

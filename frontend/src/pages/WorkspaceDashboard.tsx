import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  Calendar,
  CheckSquare,
  FileAudio,
  Flame,
  LogOut,
  Plus,
  ShieldCheck,
  Sparkles,
  Video,
} from "lucide-react";
import axios from "axios";

import { createMeeting, getMeetings, type Meeting } from "../api/meetings";
import { useAuthStore } from "../store/authStore";
import { MeetingAssistantDrawer } from "../components/meetings/MeetingAssistantDrawer";
import ThemeToggle from "../components/ThemeToggle";

export default function WorkspaceDashboard() {
  const navigate = useNavigate();
  const { user, isGuest, logout } = useAuthStore();

  const [backendStatus, setBackendStatus] = useState("Checking...");
  const [recentMeetings, setRecentMeetings] = useState<Meeting[]>([]);
  const [loadingMeetings, setLoadingMeetings] = useState(true);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);

  useEffect(() => {
    axios
      .get("http://localhost:8000/api/health")
      .then((res) => {
        setBackendStatus(res.data.message || "Connected");
      })
      .catch(() => {
        setBackendStatus("Backend unavailable");
      });

    getMeetings()
      .then((data) => setRecentMeetings(data.slice(0, 4)))
      .catch(() => {})
      .finally(() => setLoadingMeetings(false));
  }, []);

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  async function handleLaunchInstantMeeting() {
    try {
      const now = new Date();
      const formatted = now.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
      const newMeeting = await createMeeting({
        title: `Live Meeting - ${formatted}`,
        description: "Live session with camera, mic, real-time transcription, and live recording.",
        meeting_date: now.toISOString(),
      });
      navigate(`/meetings/${newMeeting.id}/room`);
    } catch (err) {
      console.error("Failed to launch instant meeting:", err);
      navigate("/meetings");
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 pb-20 transition-colors duration-150">
      {/* Guest Mode Notice Banner */}
      {isGuest && (
        <div className="border-b border-amber-300 bg-amber-50 px-6 py-2.5 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-200">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Flame className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>
                <strong>Guest Mode Active:</strong> You are exploring in a temporary session. Any meetings, recordings, or transcripts created here will <strong>vanish once you close this site</strong>.
              </span>
            </div>
            <button
              onClick={() => navigate("/login?tab=register")}
              className="inline-flex items-center gap-1 rounded-lg bg-amber-600 px-3 py-1 font-semibold text-white shadow-2xs transition hover:bg-amber-700 cursor-pointer"
            >
              <ShieldCheck className="h-3.5 w-3.5" />
              Create Account to Save Permanently
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 transition-colors">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-xs">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 dark:text-white">
                AI Meeting Workspace
              </h1>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                {isGuest ? "Guest Explorer Session" : "Personal Workspace"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Health Pill */}
            <div className="flex items-center gap-2 text-xs">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  backendStatus.toLowerCase().includes("connect")
                    ? "bg-emerald-500"
                    : "bg-amber-500 animate-pulse"
                }`}
              />
              <span className="hidden font-medium text-slate-600 dark:text-slate-400 sm:inline">
                {backendStatus}
              </span>
            </div>

            {/* Dark/Light mode toggle */}
            <ThemeToggle />

            {/* Launch Instant Meet button */}
            <button
              onClick={handleLaunchInstantMeeting}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 cursor-pointer"
              title="Launch a live Google Meet-style room"
            >
              <Video className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Launch Meet</span>
            </button>

            {/* Ask AI button */}
            <button
              onClick={() => setIsAssistantOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 cursor-pointer"
            >
              <Bot className="h-3.5 w-3.5" />
              Ask AI
            </button>

            {/* User Profile & Sign Out */}
            <div className="flex items-center gap-2 border-l border-slate-200 dark:border-slate-800 pl-3">
              <div className="hidden flex-col text-right sm:flex">
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  {user?.full_name || "Guest User"}
                </span>
                <span className="text-[10px] text-slate-400">
                  {user?.email || "ephemeral"}
                </span>
              </div>

              <button
                onClick={handleLogout}
                className="inline-flex items-center gap-1 rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200 cursor-pointer"
                title={isGuest ? "Exit Guest Mode (wipes temporary data)" : "Sign Out"}
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace Body */}
      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Welcome Banner */}
        <section className="mb-8">
          <h2 className="text-2xl font-extrabold text-slate-900 dark:text-white sm:text-3xl">
            Welcome, {user?.full_name?.split(" ")[0] || "Explorer"}!
          </h2>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-400 sm:text-sm">
            Manage your meetings, track extracted action items and decisions, and query previous discussions with your AI Assistant.
          </p>
        </section>

        {/* Action Cards */}
        <section className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div
            onClick={handleLaunchInstantMeeting}
            className="group cursor-pointer rounded-2xl border border-emerald-200 bg-white p-6 shadow-2xs transition hover:border-emerald-400 hover:shadow-md dark:border-emerald-900/50 dark:bg-slate-900 dark:hover:border-emerald-500/50"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400 transition group-hover:bg-emerald-600 group-hover:text-white">
              <Video className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">Live Meeting Room</h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
              Host Google Meet-style calls with live speech-to-text, auto-recording, and instant AI insights.
            </p>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              Launch Room <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
            </div>
          </div>

          <div
            onClick={() => navigate("/meetings")}
            className="group cursor-pointer rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs transition hover:border-indigo-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-500/50"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400 transition group-hover:bg-indigo-600 group-hover:text-white">
              <Calendar className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">Meetings</h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
              View, upload recordings, and inspect speaker-aware transcripts.
            </p>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400">
              Open Meetings <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
            </div>
          </div>

          <div
            onClick={() => navigate("/action-items")}
            className="group cursor-pointer rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs transition hover:border-amber-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-amber-500/50"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400 transition group-hover:bg-amber-600 group-hover:text-white">
              <CheckSquare className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">Action Items</h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
              Track tasks, assignees, priorities, and deadlines across sessions.
            </p>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-amber-600 dark:text-amber-400">
              View Action Items <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
            </div>
          </div>

          <div
            onClick={() => setIsAssistantOpen(true)}
            className="group cursor-pointer rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs transition hover:border-purple-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-purple-500/50"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400 transition group-hover:bg-purple-600 group-hover:text-white">
              <Bot className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">RAG AI Assistant</h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
              Ask natural language questions citing exact timestamp references.
            </p>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-purple-600 dark:text-purple-400">
              Ask Questions <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
            </div>
          </div>
        </section>

        {/* Recent Meetings Section */}
        <section className="mt-10">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">Recent Meetings</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">Your latest recorded discussions and summaries.</p>
            </div>
            <button
              onClick={() => navigate("/meetings")}
              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 cursor-pointer"
            >
              View all meetings <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {loadingMeetings ? (
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-32 animate-pulse rounded-2xl bg-slate-200/70 dark:bg-slate-800/60" />
              ))}
            </div>
          ) : recentMeetings.length === 0 ? (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 p-8 text-center bg-white dark:bg-slate-900">
              <FileAudio className="mx-auto h-8 w-8 text-slate-400" />
              <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-300">No meetings recorded yet</p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Create a meeting and upload an audio or video file to see transcripts and summaries.
              </p>
              <button
                onClick={() => navigate("/meetings")}
                className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-500 cursor-pointer"
              >
                <Plus className="h-4 w-4" />
                Create First Meeting
              </button>
            </div>
          ) : (
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {recentMeetings.map((m) => (
                <div
                  key={m.id}
                  onClick={() => navigate(`/meetings/${m.id}`)}
                  className="cursor-pointer rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs transition hover:border-indigo-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400">
                        ID #{m.id}
                      </span>
                      {m.owner_id === user?.id ? (
                        <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">
                          Host
                        </span>
                      ) : (
                        <span className="rounded-md bg-purple-50 px-2 py-0.5 text-[10px] font-bold text-purple-700 dark:bg-purple-500/10 dark:text-purple-400">
                          Attended
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] font-medium capitalize text-slate-500 dark:text-slate-400">
                      {m.status.replace("_", " ")}
                    </span>
                  </div>
                  <h4 className="mt-3 font-bold text-slate-900 dark:text-white line-clamp-1">{m.title}</h4>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                    {m.description || "No description provided."}
                  </p>
                  <div className="mt-4 flex items-center justify-between border-t border-slate-100 dark:border-slate-800 pt-2 text-[10px] text-slate-400">
                    <span>{m.meeting_date ? new Date(m.meeting_date).toLocaleDateString() : "Undated"}</span>
                    <span className="font-semibold text-indigo-600 dark:text-indigo-400">View details →</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Global AI Assistant Drawer */}
      <MeetingAssistantDrawer
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
        onJumpToTime={() => {}}
      />
    </div>
  );
}

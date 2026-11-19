import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Calendar,
  Flame,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
  Video,
} from "lucide-react";

import {
  createMeeting,
  deleteMeeting,
  getMeetings,
  type Meeting,
} from "../api/meetings";
import { useAuthStore } from "../store/authStore";
import ThemeToggle from "../components/ThemeToggle";

export default function Meetings() {
  const navigate = useNavigate();
  const { user, accessToken, isGuest } = useAuthStore();

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [meetingDate, setMeetingDate] = useState("");

  async function loadMeetings() {
    try {
      setLoading(true);
      setError("");

      const data = await getMeetings();
      setMeetings(data);
    } catch {
      setError("Unable to load meetings. Please check your connection.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!accessToken) {
      navigate("/login");
      return;
    }
    loadMeetings();
  }, [accessToken]);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!title.trim()) {
      return;
    }

    try {
      setCreating(true);
      setError("");

      await createMeeting({
        title: title.trim(),
        description: description.trim() || undefined,
        meeting_date: meetingDate
          ? new Date(meetingDate).toISOString()
          : undefined,
      });

      setTitle("");
      setDescription("");
      setMeetingDate("");
      setShowCreateForm(false);

      await loadMeetings();
    } catch {
      setError("Unable to create meeting.");
    } finally {
      setCreating(false);
    }
  }

  async function handleLaunchInstantMeeting() {
    try {
      setCreating(true);
      setError("");
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
    } catch {
      setError("Unable to launch instant meeting.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(meetingId: number) {
    const confirmed = window.confirm(
      "Are you sure you want to delete this meeting?",
    );

    if (!confirmed) {
      return;
    }

    try {
      setError("");

      await deleteMeeting(meetingId);

      setMeetings((current) =>
        current.filter((meeting) => meeting.id !== meetingId),
      );
    } catch {
      setError("Unable to delete meeting.");
    }
  }

  function formatDate(date: string | null) {
    if (!date) {
      return "No date";
    }

    return new Date(date).toLocaleString();
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 pb-20 transition-colors duration-150">
      {/* Guest Mode Banner */}
      {isGuest && (
        <div className="border-b border-amber-300 bg-amber-50 px-6 py-2 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-200">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <Flame className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>
                <strong>Guest Mode:</strong> Meetings created here are temporary and will vanish once you close this site.
              </span>
            </div>
            <button
              onClick={() => navigate("/login?tab=register")}
              className="inline-flex items-center gap-1 font-bold text-amber-900 dark:text-amber-300 underline hover:text-amber-950 dark:hover:text-amber-100 cursor-pointer"
            >
              <ShieldCheck className="h-3.5 w-3.5" />
              Save Permanently
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 transition-colors">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => navigate("/")}
              className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Dashboard
            </button>
            <ThemeToggle />
          </div>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                Meetings Workspace
              </h1>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Manage your recorded sessions, transcripts, and intelligence reports.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleLaunchInstantMeeting}
                disabled={creating}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 disabled:opacity-50 cursor-pointer"
                title="Launch a live Google Meet-style call"
              >
                <Video className="h-4 w-4" />
                Start Live Meet
              </button>

              <button
                onClick={() => setShowCreateForm((prev) => !prev)}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 cursor-pointer"
              >
                <Plus className="h-4 w-4" />
                {showCreateForm ? "Cancel" : "New Meeting"}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Error message */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-600 dark:border-red-800/40 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Create meeting form */}
        {showCreateForm && (
          <div className="mb-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 transition-colors">
            <h2 className="text-base font-bold text-slate-900 dark:text-white mb-1">
              Create New Meeting
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Add details for the meeting you want to record, transcribe, and summarize.
            </p>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Q4 Strategy Review"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Optional meeting agenda, notes, or goals"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Meeting Date & Time
                </label>
                <input
                  type="datetime-local"
                  value={meetingDate}
                  onChange={(e) => setMeetingDate(e.target.value)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:focus:border-indigo-500"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 disabled:opacity-50 cursor-pointer"
                >
                  {creating ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Save Meeting"
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Meeting List */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-500 dark:text-slate-400">
            <Loader2 className="mr-2 h-5 w-5 animate-spin text-indigo-600 dark:text-indigo-400" />
            Loading meetings...
          </div>
        ) : meetings.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center dark:border-slate-800 dark:bg-slate-900">
            <Calendar className="mx-auto h-8 w-8 text-slate-400" />
            <h3 className="mt-3 text-sm font-bold text-slate-800 dark:text-slate-200">
              No meetings found
            </h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Create your first meeting above to upload audio recordings and generate summaries.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {meetings.map((meeting) => (
              <div
                key={meeting.id}
                className="group relative flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-indigo-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400">
                        ID #{meeting.id}
                      </span>
                      {meeting.owner_id === user?.id ? (
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
                      {meeting.status.replace("_", " ")}
                    </span>
                  </div>

                  <h3 className="mt-3 text-base font-bold text-slate-900 dark:text-white line-clamp-1">
                    {meeting.title}
                  </h3>

                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                    {meeting.description || "No description provided."}
                  </p>
                </div>

                <div className="mt-6 border-t border-slate-100 dark:border-slate-800 pt-3">
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span>{formatDate(meeting.meeting_date)}</span>

                    <div className="flex items-center gap-2">
                      {meeting.owner_id === user?.id && (
                        <button
                          onClick={() => handleDelete(meeting.id)}
                          className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400 cursor-pointer"
                          title="Delete meeting"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}

                      <button
                        onClick={() => navigate(`/meetings/${meeting.id}`)}
                        className="rounded-lg bg-indigo-50 px-2.5 py-1 font-semibold text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-500/10 dark:text-indigo-400 dark:hover:bg-indigo-500/20 cursor-pointer"
                      >
                        Open →
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

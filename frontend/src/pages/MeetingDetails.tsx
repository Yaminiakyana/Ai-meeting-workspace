import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Bot,
  Brain,
  CheckCircle2,
  CheckSquare,
  Clock3,
  FileAudio,
  Loader2,
  Mail,
  Milestone,
  Play,
  Search,
  Upload,
  UserRound,
} from "lucide-react";

import {
  generateMeetingSummary,
  getMeeting,
  getMeetingInsights,
  getRecordings,
  getTranscript,
  uploadRecording,
} from "../api/meetings";
import type {
  ActionItem,
  Decision,
  Meeting,
  MeetingSummary,
  Recording,
  TranscriptSegment,
} from "../api/meetings";

import { ActionItemsList } from "../components/meetings/ActionItemsList";
import { AudioPlayerBar } from "../components/meetings/AudioPlayerBar";
import { DecisionsList } from "../components/meetings/DecisionsList";
import { FollowupEmailModal } from "../components/meetings/FollowupEmailModal";
import { MeetingAssistantDrawer } from "../components/meetings/MeetingAssistantDrawer";
import { SummaryView } from "../components/meetings/SummaryView";
import ThemeToggle from "../components/ThemeToggle";

function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return "Unknown size";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatProcessingStatus(status: string): string {
  switch (status) {
    case "uploaded":
    case "processing":
      return "Processing";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

function getProcessingStatusClasses(status: string): string {
  switch (status) {
    case "completed":
      return "bg-green-50 text-green-700 border-green-200 dark:bg-green-950/40 dark:text-green-300 dark:border-green-800/50";
    case "uploaded":
    case "processing":
      return "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/50";
    case "failed":
      return "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800/50";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";
  }
}

function getSpeakerClasses(index: number) {
  const styles = [
    {
      container: "border-indigo-200 bg-indigo-50/40 dark:border-indigo-900/50 dark:bg-indigo-950/20",
      badge: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300",
      active: "ring-2 ring-indigo-500 bg-indigo-50/80 dark:bg-indigo-950/50 shadow-md",
    },
    {
      container: "border-emerald-200 bg-emerald-50/40 dark:border-emerald-900/50 dark:bg-emerald-950/20",
      badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300",
      active: "ring-2 ring-emerald-500 bg-emerald-50/80 dark:bg-emerald-950/50 shadow-md",
    },
    {
      container: "border-amber-200 bg-amber-50/40 dark:border-amber-900/50 dark:bg-amber-950/20",
      badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300",
      active: "ring-2 ring-amber-500 bg-amber-50/80 dark:bg-amber-950/50 shadow-md",
    },
    {
      container: "border-purple-200 bg-purple-50/40 dark:border-purple-900/50 dark:bg-purple-950/20",
      badge: "bg-purple-100 text-purple-700 dark:bg-purple-900/60 dark:text-purple-300",
      active: "ring-2 ring-purple-500 bg-purple-50/80 dark:bg-purple-950/50 shadow-md",
    },
  ];
  return styles[index % styles.length];
}

export default function MeetingDetails() {
  const { meetingId } = useParams();
  const navigate = useNavigate();
  const id = Number(meetingId);

  // Meeting data
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);

  // Insights
  const [summary, setSummary] = useState<MeetingSummary | null>(null);
  const [actionItems, setActionItems] = useState<ActionItem[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [generatingSummary, setGeneratingSummary] = useState(false);

  // Audio Playback & Synchronization
  const [activeRecordingId, setActiveRecordingId] = useState<number | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekTimestamp, setSeekTimestamp] = useState<number | null>(null);

  // UI state
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"summary" | "actions" | "decisions" | "transcript">("summary");
  const [transcriptSearch, setTranscriptSearch] = useState("");
  const [speakerFilter, setSpeakerFilter] = useState<string>("all");

  // Modals & Drawers
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);

  const transcriptContainerRef = useRef<HTMLDivElement | null>(null);

  // Load meeting data & insights
  async function loadMeetingData() {
    try {
      const [meetingRes, recordingsRes, transcriptRes, insightsRes] = await Promise.all([
        getMeeting(id),
        getRecordings(id),
        getTranscript(id),
        getMeetingInsights(id).catch(() => null),
      ]);

      setMeeting(meetingRes);
      setRecordings(recordingsRes);
      setTranscript(transcriptRes);

      if (recordingsRes.length > 0 && !activeRecordingId) {
        setActiveRecordingId(recordingsRes[0].id);
      }

      // Check for insights
      if (insightsRes) {
        if (insightsRes.summary) {
          setSummary(insightsRes.summary);
        }
        if (insightsRes.action_items) {
          setActionItems(insightsRes.action_items);
        }
        if (insightsRes.decisions) {
          setDecisions(insightsRes.decisions);
        }
      }
    } catch {
      setError("Unable to load meeting details.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMeetingData();
  }, [id]);

  // Auto-poll while any recording is processing so transcripts, summary, and action items populate seamlessly
  useEffect(() => {
    const hasPending = recordings.some(
      (r) => r.processing_status === "uploaded" || r.processing_status === "processing"
    );
    if (!hasPending) return;

    const pollTimer = setInterval(async () => {
      try {
        const [recs, trans, insights] = await Promise.all([
          getRecordings(id),
          getTranscript(id).catch(() => []),
          getMeetingInsights(id).catch(() => null),
        ]);
        setRecordings(recs);
        if (trans && trans.length > 0) {
          setTranscript(trans);
        }
        if (insights) {
          if (insights.summary) setSummary(insights.summary);
          if (insights.action_items) setActionItems(insights.action_items);
          if (insights.decisions) setDecisions(insights.decisions);
        }
      } catch (pollErr) {
        console.warn("Polling meeting details notice:", pollErr);
      }
    }, 3000);

    return () => clearInterval(pollTimer);
  }, [id, recordings]);

  // Upload recording
  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setError("");
      await uploadRecording(id, file);
      await loadMeetingData();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Unable to upload recording.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  // Trigger Summary generation
  async function handleGenerateSummary(forceRegenerate: boolean = false) {
    setGeneratingSummary(true);
    setError("");
    try {
      const res = await generateMeetingSummary(id, forceRegenerate);
      setSummary(res.summary);
      setActionItems(res.action_items);
      setDecisions(res.decisions);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to generate summary.");
    } finally {
      setGeneratingSummary(false);
    }
  }

  // Handle jump to time
  function handleJumpToTime(seconds: number) {
    setSeekTimestamp(seconds);
  }

  // Speakers map
  const speakerMap = useMemo(() => {
    const map = new Map<string, number>();
    transcript.forEach((s) => {
      if (s.speaker_label && !map.has(s.speaker_label)) {
        map.set(s.speaker_label, map.size);
      }
    });
    return map;
  }, [transcript]);

  // Filtered transcript segments
  const filteredTranscript = useMemo(() => {
    return transcript.filter((seg) => {
      const matchesSearch =
        !transcriptSearch ||
        seg.text.toLowerCase().includes(transcriptSearch.toLowerCase()) ||
        (seg.speaker_label && seg.speaker_label.toLowerCase().includes(transcriptSearch.toLowerCase()));
      const matchesSpeaker =
        speakerFilter === "all" || seg.speaker_label === speakerFilter;
      return matchesSearch && matchesSpeaker;
    });
  }, [transcript, transcriptSearch, speakerFilter]);

  // Find currently active segment
  const activeSegmentId = useMemo(() => {
    const match = transcript.find(
      (s) => currentTime >= s.start_time && currentTime <= s.end_time,
    );
    return match ? match.id : null;
  }, [transcript, currentTime]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 transition-colors">
        <div className="flex items-center gap-3 text-slate-600 dark:text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin text-indigo-600 dark:text-indigo-400" />
          Loading AI Meeting Workspace...
        </div>
      </div>
    );
  }

  if (!meeting) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-8 transition-colors">
        <div className="mx-auto max-w-4xl rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-800/40 dark:bg-red-950/40 dark:text-red-300">
          {error || "Meeting not found."}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 pb-20 transition-colors duration-150">
      {/* Top Header */}
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/95 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-900/95 transition-colors">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div>
              <button
                type="button"
                onClick={() => navigate("/meetings")}
                className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 transition hover:text-slate-900 dark:hover:text-white cursor-pointer"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Meetings
              </button>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                {meeting.title}
              </h1>
              {meeting.description && (
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {meeting.description}
                </p>
              )}
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap items-center gap-2.5">
              <ThemeToggle />

              <button
                onClick={() => setIsEmailModalOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 cursor-pointer"
              >
                <Mail className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                Follow-Up Email
              </button>

              <button
                onClick={() => setIsAssistantOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-700 cursor-pointer"
              >
                <Bot className="h-4 w-4" />
                Ask AI Assistant
              </button>

              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50/50 px-3.5 py-2 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-900/60">
                {uploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    Upload Recording
                  </>
                )}
                <input
                  type="file"
                  accept="audio/*,video/*"
                  className="hidden"
                  disabled={uploading}
                  onChange={handleUpload}
                />
              </label>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto max-w-7xl px-6 py-6">
        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-medium text-red-700 dark:border-red-800/40 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Audio Player Bar */}
        {recordings.length > 0 && (
          <AudioPlayerBar
            meetingId={id}
            recordings={recordings}
            activeRecordingId={activeRecordingId}
            onSelectRecording={(recId) => setActiveRecordingId(recId)}
            seekTimestamp={seekTimestamp}
            onTimeUpdate={(time) => setCurrentTime(time)}
          />
        )}

        {/* Overview Stats */}
        <section className="mb-6 grid gap-4 grid-cols-2 md:grid-cols-4">
          <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-2xs dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-indigo-50 p-2 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400">
                <FileAudio className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Recordings</p>
                <p className="text-lg font-bold text-slate-900 dark:text-white">{recordings.length}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-2xs dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-emerald-50 p-2 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                <Clock3 className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Transcript Segments</p>
                <p className="text-lg font-bold text-slate-900 dark:text-white">{transcript.length}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-2xs dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-amber-50 p-2 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400">
                <CheckSquare className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Action Items</p>
                <p className="text-lg font-bold text-slate-900 dark:text-white">{actionItems.length}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-2xs dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-purple-50 p-2 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400">
                <Milestone className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Decisions Made</p>
                <p className="text-lg font-bold text-slate-900 dark:text-white">{decisions.length}</p>
              </div>
            </div>
          </div>
        </section>

        {/* Tab Navigation */}
        <div className="mb-6 flex border-b border-slate-200 dark:border-slate-800 text-sm font-semibold">
          {[
            { id: "summary", label: "AI Summary", icon: Brain, count: summary ? "1" : "0" },
            { id: "actions", label: "Action Items", icon: CheckSquare, count: actionItems.length },
            { id: "decisions", label: "Decisions", icon: Milestone, count: decisions.length },
            { id: "transcript", label: "Transcript & Sync", icon: Clock3, count: transcript.length },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 border-b-2 px-5 py-3 transition cursor-pointer ${
                  isActive
                    ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                    : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    isActive
                      ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
                      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        {activeTab === "summary" && (
          <SummaryView
            summary={summary}
            loading={generatingSummary}
            onGenerate={handleGenerateSummary}
          />
        )}

        {activeTab === "actions" && (
          <ActionItemsList
            meetingId={id}
            actionItems={actionItems}
            onActionItemsChange={(items) => setActionItems(items)}
            onJumpToTime={handleJumpToTime}
          />
        )}

        {activeTab === "decisions" && (
          <DecisionsList
            decisions={decisions}
            onJumpToTime={handleJumpToTime}
          />
        )}

        {activeTab === "transcript" && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 transition-colors">
            {/* Search & Speaker Filter Bar */}
            <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search spoken text or speaker..."
                  value={transcriptSearch}
                  onChange={(e) => setTranscriptSearch(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 py-1.5 text-xs text-slate-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
                />
              </div>

              {/* Speaker filter */}
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-500 dark:text-slate-400">Filter Speaker:</span>
                <select
                  value={speakerFilter}
                  onChange={(e) => setSpeakerFilter(e.target.value)}
                  className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-900 outline-none dark:border-slate-300 dark:bg-white dark:text-black"
                >
                  <option value="all">All Speakers ({speakerMap.size})</option>
                  {Array.from(speakerMap.keys()).map((spk) => (
                    <option key={spk} value={spk}>
                      {spk}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {filteredTranscript.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
                {transcript.length === 0
                  ? "Transcript will appear here once audio processing finishes."
                  : "No transcript segments match your search criteria."}
              </div>
            ) : (
              <div
                ref={transcriptContainerRef}
                className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[600px] overflow-y-auto pr-2"
              >
                {filteredTranscript.map((segment) => {
                  const speakerIndex = segment.speaker_label
                    ? speakerMap.get(segment.speaker_label) ?? 0
                    : 0;
                  const speakerStyles = getSpeakerClasses(speakerIndex);
                  const isCurrentlyPlaying = activeSegmentId === segment.id;

                  return (
                    <div
                      key={segment.id}
                      className={`p-4 transition rounded-xl my-1 ${
                        isCurrentlyPlaying
                          ? speakerStyles.active
                          : "hover:bg-slate-50/80 dark:hover:bg-slate-850"
                      }`}
                    >
                      <div className="flex gap-4">
                        {/* Timestamp Button (Seeks Audio) */}
                        <button
                          type="button"
                          onClick={() => handleJumpToTime(segment.start_time)}
                          className={`mt-0.5 inline-flex items-center gap-1 font-mono text-xs font-bold transition cursor-pointer ${
                            isCurrentlyPlaying
                              ? "text-indigo-800 dark:text-indigo-300"
                              : "text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-200"
                          }`}
                          title="Click to jump audio playback here"
                        >
                          <Play className="h-3 w-3 fill-current" />
                          {formatTimestamp(segment.start_time)}
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${speakerStyles.badge}`}
                            >
                              <UserRound className="h-2.5 w-2.5" />
                              {segment.speaker_label || "Speaker"}
                            </span>
                            {segment.language && (
                              <span className="text-[10px] text-slate-400 uppercase">
                                {segment.language}
                              </span>
                            )}
                          </div>

                          <p className="mt-2 text-xs leading-relaxed text-slate-800 dark:text-slate-200">
                            {segment.text}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Recordings List Section */}
        <section className="mt-10">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Uploaded Recordings
            </h2>
            <span className="text-xs text-slate-400">
              {recordings.length} file(s)
            </span>
          </div>

          <div className="space-y-2">
            {recordings.map((recording) => (
              <div
                key={recording.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-2xs dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="flex items-center gap-3">
                  <FileAudio className="h-5 w-5 text-slate-400" />
                  <div>
                    <p className="text-xs font-bold text-slate-900 dark:text-white">
                      {recording.file_name}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      {formatFileSize(recording.file_size)} •{" "}
                      {recording.duration_seconds
                        ? `${formatTimestamp(recording.duration_seconds)} duration`
                        : "Processing duration..."}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveRecordingId(recording.id);
                      handleJumpToTime(0);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-900/60 cursor-pointer"
                    title="Play recording audio"
                  >
                    <Play className="h-3 w-3 fill-indigo-600 dark:fill-indigo-400" />
                    Play
                  </button>
                  {recording.processing_status === "completed" && (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                  )}
                  {["uploaded", "processing"].includes(recording.processing_status) && (
                    <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />
                  )}
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${getProcessingStatusClasses(
                      recording.processing_status,
                    )}`}
                  >
                    {formatProcessingStatus(recording.processing_status)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* Meeting AI Assistant Drawer */}
      <MeetingAssistantDrawer
        meetingId={id}
        meetingTitle={meeting.title}
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
        onJumpToTime={handleJumpToTime}
      />

      {/* Follow-up Email Modal */}
      <FollowupEmailModal
        meetingId={id}
        isOpen={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
    </div>
  );
}

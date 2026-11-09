import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  Clock3,
  ExternalLink,
  Filter,
  Loader2,
  UserCheck,
} from "lucide-react";
import type { ActionItem } from "../api/meetings";
import { getAllActionItems, updateActionItem } from "../api/meetings";
import ThemeToggle from "../components/ThemeToggle";

export default function ActionItemsPage() {
  const navigate = useNavigate();
  const [actionItems, setActionItems] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "pending" | "completed">("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  useEffect(() => {
    async function fetchItems() {
      try {
        const data = await getAllActionItems();
        setActionItems(data);
      } catch (err) {
        console.error("Failed to load action items:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchItems();
  }, []);

  const toggleStatus = async (item: ActionItem) => {
    const nextStatus = item.status === "completed" ? "pending" : "completed";
    setUpdatingId(item.id);

    setActionItems((prev) =>
      prev.map((a) => (a.id === item.id ? { ...a, status: nextStatus } : a)),
    );

    try {
      await updateActionItem(item.meeting_id, item.id, { status: nextStatus });
    } catch (e) {
      console.error(e);
      // Revert on error
      setActionItems((prev) =>
        prev.map((a) => (a.id === item.id ? { ...a, status: item.status } : a)),
      );
    } finally {
      setUpdatingId(null);
    }
  };

  const filtered = actionItems.filter((item) => {
    if (filter === "pending" && item.status !== "pending") return false;
    if (filter === "completed" && item.status !== "completed") return false;
    if (priorityFilter !== "all" && item.priority.toLowerCase() !== priorityFilter.toLowerCase()) return false;
    return true;
  });

  const priorityStyles: Record<string, string> = {
    high: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800/40",
    medium: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/40",
    low: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/40",
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 pb-20 transition-colors duration-150">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 transition-colors">
        <div className="mx-auto max-w-7xl px-6 py-5">
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

          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                Action Items Repository
              </h1>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Centralized tracker of tasks, commitments, and deadlines across all meetings.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400">
                {filtered.length} task(s)
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Filters */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-2xs dark:border-slate-800 dark:bg-slate-900 transition-colors">
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            {(["all", "pending", "completed"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                className={`rounded-md px-3 py-1.5 capitalize transition cursor-pointer ${
                  filter === tab
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                    : "hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 text-xs">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-slate-500 dark:text-slate-400">Priority:</span>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-slate-900 outline-none dark:border-slate-300 dark:bg-white dark:text-black"
            >
              <option value="all">All Priorities</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-500 dark:text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin text-indigo-600 dark:text-indigo-400 mr-2" />
            Loading action items...
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center dark:border-slate-800 dark:bg-slate-900">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">No action items found.</p>
            <p className="mt-1 text-xs text-slate-400">
              Action items extracted from meeting transcripts will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((item) => {
              const isCompleted = item.status === "completed";
              const priorityClass =
                priorityStyles[item.priority.toLowerCase()] || priorityStyles.medium;

              return (
                <div
                  key={item.id}
                  className={`flex flex-col justify-between gap-4 rounded-xl border p-4 transition md:flex-row md:items-center ${
                    isCompleted
                      ? "border-slate-100 bg-slate-50/50 opacity-70 dark:border-slate-800/60 dark:bg-slate-900/40"
                      : "border-slate-200 bg-white shadow-2xs hover:border-indigo-200 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => toggleStatus(item)}
                      disabled={updatingId === item.id}
                      className="mt-0.5 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer"
                    >
                      {isCompleted ? (
                        <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                      ) : (
                        <Circle className="h-5 w-5 hover:text-indigo-600 dark:hover:text-indigo-400" />
                      )}
                    </button>

                    <div>
                      <p
                        className={`text-sm font-medium ${
                          isCompleted
                            ? "text-slate-500 line-through dark:text-slate-500"
                            : "text-slate-900 dark:text-white"
                        }`}
                      >
                        {item.description}
                      </p>

                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                        <span
                          className={`rounded-md border px-2 py-0.5 font-medium uppercase text-[10px] ${priorityClass}`}
                        >
                          {item.priority}
                        </span>

                        {item.assignee_name && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            <UserCheck className="h-3 w-3" />
                            {item.assignee_name}
                          </span>
                        )}

                        {item.due_date && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            <Clock3 className="h-3 w-3" />
                            {new Date(item.due_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => navigate(`/meetings/${item.meeting_id}`)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 cursor-pointer"
                  >
                    View Meeting
                    <ExternalLink className="h-3 w-3" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

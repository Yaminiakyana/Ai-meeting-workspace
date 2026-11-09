import { useState } from "react";
import { CheckCircle2, Circle, Clock3, Play, UserCheck } from "lucide-react";
import type { ActionItem } from "../../api/meetings";
import { updateActionItem } from "../../api/meetings";

interface ActionItemsListProps {
  meetingId: number;
  actionItems: ActionItem[];
  onActionItemsChange: (items: ActionItem[]) => void;
  onJumpToTime: (seconds: number) => void;
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export const ActionItemsList: React.FC<ActionItemsListProps> = ({
  meetingId,
  actionItems,
  onActionItemsChange,
  onJumpToTime,
}) => {
  const [filter, setFilter] = useState<"all" | "pending" | "completed">("all");
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const toggleStatus = async (item: ActionItem) => {
    const nextStatus = item.status === "completed" ? "pending" : "completed";
    setUpdatingId(item.id);

    // Optimistic update
    const updated = actionItems.map((a) =>
      a.id === item.id ? { ...a, status: nextStatus } : a,
    );
    onActionItemsChange(updated);

    try {
      await updateActionItem(meetingId, item.id, { status: nextStatus });
    } catch (e) {
      console.error("Failed to update action item status", e);
      // Revert on error
      onActionItemsChange(actionItems);
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredItems = actionItems.filter((item) => {
    if (filter === "pending") return item.status === "pending";
    if (filter === "completed") return item.status === "completed";
    return true;
  });

  const priorityStyles: Record<string, string> = {
    high: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800/40",
    medium: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/40",
    low: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/40",
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 transition-colors">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">Action Items</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Tasks, commitments, and owners extracted from the meeting.
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex rounded-lg bg-slate-100 p-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
          {(["all", "pending", "completed"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`rounded-md px-3 py-1 capitalize transition cursor-pointer ${
                filter === tab
                  ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                  : "hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {filteredItems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
          No {filter !== "all" ? filter : ""} action items found.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const isCompleted = item.status === "completed";
            const priorityClass =
              priorityStyles[item.priority.toLowerCase()] ||
              priorityStyles.medium;

            return (
              <div
                key={item.id}
                className={`flex flex-col justify-between gap-3 rounded-xl border p-4 transition md:flex-row md:items-center ${
                  isCompleted
                    ? "border-slate-100 bg-slate-50/60 opacity-75 dark:border-slate-800/60 dark:bg-slate-900/40"
                    : "border-slate-200 bg-white hover:border-indigo-200 hover:shadow-xs dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
                }`}
              >
                <div className="flex items-start gap-3">
                  <button
                    onClick={() => toggleStatus(item)}
                    disabled={updatingId === item.id}
                    className="mt-0.5 text-slate-400 transition hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer"
                    title={isCompleted ? "Mark pending" : "Mark completed"}
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
                          : "text-slate-800 dark:text-slate-200"
                      }`}
                    >
                      {item.description}
                    </p>

                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      {/* Priority */}
                      <span
                        className={`rounded-md border px-2 py-0.5 font-medium uppercase text-[10px] ${priorityClass}`}
                      >
                        {item.priority}
                      </span>

                      {/* Owner / Assignee */}
                      {item.assignee_name && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                          <UserCheck className="h-3 w-3" />
                          {item.assignee_name}
                        </span>
                      )}

                      {/* Due date */}
                      {item.due_date && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                          <Clock3 className="h-3 w-3" />
                          {new Date(item.due_date).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {item.source_start_time !== null && item.source_start_time !== undefined && (
                  <button
                    onClick={() => onJumpToTime(item.source_start_time!)}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-900/60 cursor-pointer"
                    title="Jump to recording moment"
                  >
                    <Play className="h-3 w-3 fill-indigo-600 dark:fill-indigo-400" />
                    {formatTimestamp(item.source_start_time)}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

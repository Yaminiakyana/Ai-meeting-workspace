import { apiClient } from "./client";
import { useAuthStore } from "../store/authStore";

export interface Meeting {
  id: number;
  owner_id: number;
  title: string;
  description: string | null;
  meeting_date: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CreateMeetingRequest {
  title: string;
  description?: string;
  meeting_date?: string;
}

export interface UpdateMeetingRequest {
  title?: string;
  description?: string | null;
  meeting_date?: string | null;
  status?: string;
}

export interface TranscriptSegment {
  id: number;
  meeting_id: number;
  recording_id: number | null;
  speaker_label: string | null;
  speaker_name: string | null;
  text: string;
  start_time: number;
  end_time: number;
  sequence_number: number;
  language: string | null;
}

export interface Recording {
  id: number;
  meeting_id: number;
  file_name: string;
  storage_key: string;
  content_type: string | null;
  file_size: number | null;
  duration_seconds: number | null;
  processing_status: string;
  processing_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MeetingSummary {
  id: number;
  meeting_id: number;
  summary: string;
  model_name: string;
  generated_at: string;
  updated_at: string;
}

export interface ActionItem {
  id: number;
  meeting_id: number;
  owner_id: number | null;
  assignee_name?: string | null;
  description: string;
  due_date: string | null;
  status: string; // "pending" | "completed"
  priority: string; // "high" | "medium" | "low"
  source_start_time: number | null;
  source_end_time: number | null;
  created_at: string;
  updated_at: string;
}

export interface Decision {
  id: number;
  meeting_id: number;
  description: string;
  decision_type: string | null;
  source_start_time: number | null;
  source_end_time: number | null;
  created_at: string;
}

export interface MeetingInsights {
  summary: MeetingSummary | null;
  action_items: ActionItem[];
  decisions: Decision[];
}

export interface FollowupEmail {
  subject: string;
  body: string;
  recipients: string[];
}

export interface Citation {
  meeting_id: number;
  meeting_title: string;
  speaker: string | null;
  start_time: number;
  end_time: number;
  text: string;
}

export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantChatResponse {
  answer: string;
  citations: Citation[];
  sources_count: number;
}

export interface SearchResultItem {
  meeting_id: number;
  meeting_title: string;
  speaker: string | null;
  start_time: number;
  end_time: number;
  text: string;
  similarity_score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResultItem[];
  total: number;
}

// ============================================================
// API Calls
// ============================================================

export async function getMeetings(): Promise<Meeting[]> {
  const response = await apiClient.get<Meeting[]>("/meetings");
  return response.data;
}

export async function getMeeting(meetingId: number): Promise<Meeting> {
  const response = await apiClient.get<Meeting>(`/meetings/${meetingId}`);
  return response.data;
}

export async function createMeeting(data: CreateMeetingRequest): Promise<Meeting> {
  const response = await apiClient.post<Meeting>("/meetings", data);
  return response.data;
}

export async function updateMeeting(
  meetingId: number,
  data: UpdateMeetingRequest,
): Promise<Meeting> {
  const response = await apiClient.patch<Meeting>(`/meetings/${meetingId}`, data);
  return response.data;
}

export async function deleteMeeting(meetingId: number): Promise<void> {
  await apiClient.delete(`/meetings/${meetingId}`);
}

export async function uploadRecording(
  meetingId: number,
  file: File,
): Promise<Recording> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<Recording>(
    `/meetings/${meetingId}/recordings`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );

  return response.data;
}

export async function getRecordings(meetingId: number): Promise<Recording[]> {
  const response = await apiClient.get<Recording[]>(`/meetings/${meetingId}/recordings`);
  return response.data;
}

export async function deleteRecording(
  meetingId: number,
  recordingId: number,
): Promise<void> {
  await apiClient.delete(`/meetings/${meetingId}/recordings/${recordingId}`);
}

export async function getTranscript(
  meetingId: number,
): Promise<TranscriptSegment[]> {
  const response = await apiClient.get<TranscriptSegment[]>(
    `/meetings/${meetingId}/transcript`,
  );
  return response.data;
}

export function getRecordingStreamUrl(meetingId: number, recordingId: number): string {
  const token = useAuthStore.getState().accessToken || localStorage.getItem("access_token");
  const base = "http://localhost:8000/api";
  return `${base}/meetings/${meetingId}/recordings/${recordingId}/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

// ============================================================
// Summaries, Action Items & Decisions
// ============================================================

export async function getMeetingInsights(
  meetingId: number,
): Promise<MeetingInsights> {
  const response = await apiClient.get<MeetingInsights>(
    `/meetings/${meetingId}/insights`,
  );
  return response.data;
}

export async function generateMeetingSummary(
  meetingId: number,
  forceRegenerate: boolean = false,
): Promise<MeetingInsights> {
  const response = await apiClient.post<MeetingInsights>(
    `/meetings/${meetingId}/summary/generate`,
    { force_regenerate: forceRegenerate },
  );
  return response.data;
}

export async function updateActionItem(
  meetingId: number,
  actionItemId: number,
  data: Partial<ActionItem>,
): Promise<ActionItem> {
  const response = await apiClient.patch<ActionItem>(
    `/meetings/${meetingId}/action-items/${actionItemId}`,
    data,
  );
  return response.data;
}

export async function generateFollowupEmail(
  meetingId: number,
  customInstructions?: string,
): Promise<FollowupEmail> {
  const response = await apiClient.post<FollowupEmail>(
    `/meetings/${meetingId}/followup-email`,
    { custom_instructions: customInstructions },
  );
  return response.data;
}

export async function getAllActionItems(): Promise<ActionItem[]> {
  const response = await apiClient.get<ActionItem[]>("/action-items");
  return response.data;
}

// ============================================================
// Assistant & RAG
// ============================================================

export async function askMeetingAssistant(
  question: string,
  meetingId?: number,
  history: AssistantMessage[] = [],
): Promise<AssistantChatResponse> {
  const response = await apiClient.post<AssistantChatResponse>(
    "/assistant/chat",
    {
      question,
      meeting_id: meetingId ?? null,
      history,
    },
  );
  return response.data;
}

export async function getLiveInsights(
  meetingId: number,
  text: string,
  meetingTitle?: string,
): Promise<{ action_items: any[]; decisions: any[] }> {
  const response = await apiClient.post<{ action_items: any[]; decisions: any[] }>(
    `/meetings/${meetingId}/live-insights`,
    { text, meeting_title: meetingTitle },
  );
  return response.data;
}

export async function saveLiveTranscripts(
  meetingId: number,
  segments: {
    text: string;
    start_time: number;
    end_time: number;
    speaker_label?: string;
    speaker_name?: string;
    sequence_number?: number;
  }[],
): Promise<{ saved_segments: number }> {
  const response = await apiClient.post<{ saved_segments: number }>(
    `/meetings/${meetingId}/live-transcript`,
    { segments },
  );
  return response.data;
}

export async function searchTranscripts(
  query: string,
  meetingId?: number,
): Promise<SearchResponse> {
  const response = await apiClient.get<SearchResponse>("/assistant/search", {
    params: {
      q: query,
      meeting_id: meetingId ?? undefined,
    },
  });
  return response.data;
}



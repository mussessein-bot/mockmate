export type Language = "zh" | "en";
export type InterviewType = "behavioral" | "technical" | "graduate";
export type InterviewMode = "preset" | "dynamic";
export type InterviewInterface = "voice" | "text";
export type PersonaType = "sarah" | "marcus" | "alex";
export type InterviewState =
  | "INIT"
  | "OPENING"
  | "BEHAVIORAL"
  | "DEEP_DIVE"
  | "TECHNICAL"
  | "CLOSING"
  | "COMPLETED";

export interface DimensionScore {
  dimension: string;
  score: number;
  feedback: string;
}

export interface SentenceAnnotation {
  text: string;
  label: "good" | "vague" | "weak" | "ok";
  comment: string;
}

export interface AnswerCritique {
  highlights: string[];
  improvements: string[];
}

export interface EvaluationResult {
  question_index: number;
  question_text: string;
  answer_transcript: string;
  dimension_scores: DimensionScore[];
  overall_score: number;
  is_probe: boolean;
  is_probe_triggered: boolean;
  probe_reason: string | null;
  model_answer: string | null;
  sentence_annotations: SentenceAnnotation[] | null;
  answer_critique: AnswerCritique | null;
}

export interface SessionSummary {
  total_score: number;
  grade: string;
  ai_summary: string;
  active_dimensions: string[];
  radar_data: Record<string, number>;
  dimension_details: Record<
    string,
    {
      score: number;
      analysis: string;
      suggestions: string;
      best_question_index: number;
      worst_question_index: number;
    }
  >;
  per_question: EvaluationResult[];
}

export interface CreateSessionPayload {
  name: string;
  target_role: string;
  target_company?: string;
  job_description?: string;
  job_analysis?: JobAnalysisResponse;
  resume_text?: string;
  language: Language;
  interview_type: InterviewType;
  interview_mode: InterviewMode;
  interview_interface: InterviewInterface;
  persona: PersonaType;
}

export interface StartResponse {
  interviewer_text: string;
  audio_url: string;
  state: InterviewState;
  question_count: number;
  active_dimensions: string[];
}

export interface RespondResponse {
  interviewer_text: string;
  audio_url: string;
  state: InterviewState;
  question_count: number;
  is_probe: boolean;
  probe_reason: string | null;
  active_dimensions: string[];
  evaluation: EvaluationResult | null;
  should_end: boolean;
}

export interface JobAnalysisDimension {
  name: string;
  description: string;
  weight: string;
}

export interface JobAnalysisResponse {
  core_dimensions: JobAnalysisDimension[];
  interview_style: string;
  key_tips: string;
  summary: string;
}

export interface ExtractedQuestion {
  category: string;
  question: string;
}

export interface WebSearchAnalyzeResponse extends JobAnalysisResponse {
  extracted_questions: ExtractedQuestion[];
  search_available: boolean;
}

export interface CorrectionResponse {
  new_question: string;
  audio_url: string;
  question_count: number;
}

// localStorage history record
export interface HistoryRecord {
  session_id: string;
  date: string;
  target_role: string;
  interview_type: InterviewType;
  persona: PersonaType;
  total_score: number;
  grade: string;
  summary_text: string;
  radar_data: Record<string, number>;
}

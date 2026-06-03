"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  ResponsiveContainer, Tooltip,
} from "recharts";
import { api } from "@/lib/api";
import { saveHistory } from "@/lib/storage";
import type { SessionSummary, EvaluationResult } from "@/lib/types";

const GRADE_COLOR: Record<string, string> = {
  "优秀": "text-emerald-600",
  "良好": "text-[#6366F1]",
  "一般": "text-amber-600",
  "待提升": "text-red-500",
  "Excellent": "text-emerald-600",
  "Good": "text-[#6366F1]",
  "Average": "text-amber-600",
  "Needs Work": "text-red-500",
};

const DIM_NAMES: Record<string, string> = {
  relevance: "相关性",
  structure: "结构性",
  specificity: "具体性",
  impact: "影响力",
  expression: "表达",
  leadership: "领导力",
  collaboration: "协作",
  execution: "执行力",
  resilience: "抗压",
  data_thinking: "数据思维",
  tech_depth: "技术深度",
  logic: "逻辑",
  learning: "学习力",
  innovation: "创新",
  academic: "学术潜力",
};

export default function FeedbackPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDim, setSelectedDim] = useState<string | null>(null);
  const [savedToHistory, setSavedToHistory] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getFeedback(sessionId)
      .then(setSummary)
      .catch(() => api.finalize(sessionId).then(setSummary))
      .finally(() => setLoading(false));
  }, [sessionId]);

  async function handleExportPDF() {
    const el = reportRef.current;
    if (!el) return;
    const html2pdf = (await import("html2pdf.js")).default;
    html2pdf()
      .set({
        margin: 10,
        filename: `MockMate_Report_${sessionId.slice(0, 8)}.pdf`,
        html2canvas: { scale: 2 },
        jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      })
      .from(el)
      .save();
  }

  function handleSave() {
    if (!summary) return;
    saveHistory({
      session_id: sessionId,
      date: new Date().toISOString().slice(0, 10),
      target_role: "",
      interview_type: "behavioral",
      persona: "sarah",
      total_score: summary.total_score,
      grade: summary.grade,
      summary_text: summary.ai_summary,
      radar_data: summary.radar_data,
    });
    setSavedToHistory(true);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-[#6366F1] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[#6B7280]">正在生成反馈报告...</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center">
        <p className="text-[#6B7280]">无法加载反馈报告</p>
      </div>
    );
  }

  const radarData = summary.active_dimensions.map((dim) => ({
    dim: DIM_NAMES[dim] ?? dim,
    key: dim,
    score: (summary.radar_data[dim] ?? 0) * 10,
  }));

  const selectedDetail = selectedDim ? summary.dimension_details[selectedDim] : null;

  return (
    <div className="min-h-screen bg-[#FAFAFA] pb-20">
      {/* Header */}
      <div className="bg-white border-b border-[#E5E7EB] px-6 py-4 flex items-center justify-between">
        <span className="font-bold text-[#6366F1]">MockMate</span>
        <span className="text-sm text-[#6B7280]">面试反馈报告</span>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6" ref={reportRef}>
        {/* Score header */}
        <div className="bg-white rounded-xl border border-[#E5E7EB] p-6 shadow-sm">
          <div className="flex items-center gap-4 mb-4">
            <div className="text-5xl font-bold text-[#111827]">
              {summary.total_score.toFixed(0)}
              <span className="text-2xl text-[#6B7280]">/100</span>
            </div>
            <div className={`text-2xl font-bold ${GRADE_COLOR[summary.grade] ?? "text-[#6366F1]"}`}>
              {summary.grade}
            </div>
          </div>
          <p className="text-[#6B7280] text-sm leading-relaxed">{summary.ai_summary}</p>
        </div>

        {/* Radar + Detail */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Radar */}
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-6 shadow-sm">
            <h3 className="font-semibold text-[#111827] mb-4">能力雷达图</h3>
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis
                  dataKey="dim"
                  tick={{ fontSize: 11, fill: "#6B7280", cursor: "pointer" }}
                  onClick={(e: any) => {
                    const item = radarData.find((d) => d.dim === e.value);
                    if (item) setSelectedDim(item.key);
                  }}
                />
                <Radar
                  name="分数"
                  dataKey="score"
                  stroke="#6366F1"
                  fill="#6366F1"
                  fillOpacity={0.25}
                  dot={{ r: 4, fill: "#6366F1", cursor: "pointer" }}
                  onClick={(e: any) => {
                    if (e?.payload?.key) setSelectedDim(e.payload.key);
                  }}
                />
                <Tooltip
                  formatter={(v: unknown) => [`${Number(v).toFixed(1)}/100`, "分数"]}
                  labelFormatter={(l) => l}
                />
              </RadarChart>
            </ResponsiveContainer>
            <p className="text-xs text-[#9CA3AF] text-center mt-2">点击维度查看详情</p>
          </div>

          {/* Dimension detail */}
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-6 shadow-sm">
            {selectedDim && selectedDetail ? (
              <div>
                <h3 className="font-semibold text-[#111827] mb-1">
                  {DIM_NAMES[selectedDim] ?? selectedDim}
                </h3>
                <div className="text-3xl font-bold text-[#6366F1] mb-4">
                  {selectedDetail.score.toFixed(1)}<span className="text-base text-[#6B7280]">/10</span>
                </div>
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="font-medium text-[#374151] mb-1">你的表现</p>
                    <p className="text-[#6B7280] leading-relaxed">{selectedDetail.analysis || "暂无分析"}</p>
                  </div>
                  <div>
                    <p className="font-medium text-[#374151] mb-1">改进建议</p>
                    <p className="text-[#6B7280] leading-relaxed">{selectedDetail.suggestions}</p>
                  </div>
                  <div className="flex gap-4 text-xs">
                    <span className="text-emerald-600">★ 最佳：第{selectedDetail.best_question_index}题</span>
                    <span className="text-red-500">↓ 最需改进：第{selectedDetail.worst_question_index}题</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-[#9CA3AF] text-sm text-center">
                点击左侧雷达图中的<br />任意维度查看详情
              </div>
            )}
          </div>
        </div>

        {/* Question cards */}
        <div>
          <h3 className="font-semibold text-[#111827] mb-4">题目回顾</h3>
          <div className="space-y-4">
            {summary.per_question.map((ev) => (
              <QuestionCard key={ev.question_index} ev={ev} />
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 flex-wrap">
          <button
            onClick={() => router.push("/setup")}
            className="flex-1 bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold py-3 rounded-xl transition-colors"
          >
            再来一场
          </button>
          <button
            onClick={handleSave}
            disabled={savedToHistory}
            className="flex-1 border border-[#6366F1] text-[#6366F1] hover:bg-[#EEF2FF] disabled:border-[#E5E7EB] disabled:text-[#9CA3AF] font-semibold py-3 rounded-xl transition-colors"
          >
            {savedToHistory ? "已保存 ✓" : "保存记录"}
          </button>
          <button
            onClick={handleExportPDF}
            className="flex-1 border border-[#E5E7EB] text-[#6B7280] hover:bg-[#F9FAFB] font-semibold py-3 rounded-xl transition-colors"
          >
            导出 PDF
          </button>
          <button
            onClick={() => router.push("/")}
            className="flex-1 border border-[#E5E7EB] text-[#6B7280] hover:bg-[#F9FAFB] font-semibold py-3 rounded-xl transition-colors"
          >
            返回首页
          </button>
        </div>
      </div>
    </div>
  );
}

function QuestionCard({ ev }: { ev: EvaluationResult }) {
  const [showTranscript, setShowTranscript] = useState(false);
  const [showModel, setShowModel] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-[#E5E7EB] overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-[#F3F4F6]">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-xs font-medium text-[#9CA3AF]">
              Q{ev.question_index} {ev.is_probe && <span className="text-[#F59E0B]">🔶 追问</span>}
            </span>
            <span className="text-sm text-[#111827] font-medium">{ev.question_text}</span>
          </div>
          <span className="text-lg font-bold text-[#6366F1] shrink-0">
            {ev.overall_score.toFixed(1)}<span className="text-xs text-[#9CA3AF]">/10</span>
          </span>
        </div>
        {ev.probe_reason && (
          <p className="text-xs text-[#D97706] mt-1">追问原因：{ev.probe_reason}</p>
        )}
      </div>

      {/* Dimension scores */}
      <div className="px-5 py-3 flex flex-wrap gap-2 border-b border-[#F3F4F6]">
        {ev.dimension_scores.map((ds) => (
          <span
            key={ds.dimension}
            className="text-xs bg-[#F3F4F6] text-[#374151] px-2 py-1 rounded-md"
            title={ds.feedback}
          >
            {DIM_NAMES[ds.dimension] ?? ds.dimension} {ds.score.toFixed(0)}
          </span>
        ))}
      </div>

      {/* Expandable sections */}
      <div className="px-5 py-2 space-y-1">
        <button
          onClick={() => setShowTranscript((v) => !v)}
          className="text-xs text-[#6366F1] hover:underline w-full text-left py-1"
        >
          {showTranscript ? "▲ 收起" : "▼"} 我的回答
        </button>
        {showTranscript && (
          <p className="text-sm text-[#6B7280] bg-[#F9FAFB] rounded-lg p-3 leading-relaxed">
            {ev.answer_transcript}
          </p>
        )}

        {ev.model_answer && (
          <>
            <button
              onClick={() => setShowModel((v) => !v)}
              className="text-xs text-[#10B981] hover:underline w-full text-left py-1"
            >
              {showModel ? "▲ 收起" : "▼"} 查看示范回答
            </button>
            {showModel && (
              <div className="text-sm text-[#374151] bg-[#F0FDF4] rounded-lg p-3 leading-relaxed border border-emerald-100 prose prose-sm max-w-none prose-p:my-1 prose-li:my-0">
                <ReactMarkdown>{ev.model_answer}</ReactMarkdown>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

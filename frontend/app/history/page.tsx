"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getHistory, deleteHistory } from "@/lib/storage";
import type { HistoryRecord } from "@/lib/types";

const TYPE_LABELS: Record<string, string> = {
  behavioral: "行为面",
  technical: "技术面",
  graduate: "研究生面",
};

const GRADE_COLOR: Record<string, string> = {
  "优秀": "bg-emerald-100 text-emerald-700",
  "良好": "bg-[#EEF2FF] text-[#6366F1]",
  "一般": "bg-amber-100 text-amber-700",
  "待提升": "bg-red-100 text-red-600",
};

export default function HistoryPage() {
  const router = useRouter();
  const [records, setRecords] = useState<HistoryRecord[]>([]);

  useEffect(() => {
    setRecords(getHistory());
  }, []);

  function handleDelete(id: string) {
    deleteHistory(id);
    setRecords(getHistory());
  }

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      <div className="bg-white border-b border-[#E5E7EB] px-6 py-4 flex items-center justify-between">
        <Link href="/" className="font-bold text-[#6366F1]">MockMate</Link>
        <span className="text-sm text-[#6B7280]">历史记录</span>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-[#111827] mb-6">面试历史</h1>

        {records.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-6xl mb-4">📋</div>
            <p className="text-[#6B7280] mb-6">还没有面试记录</p>
            <Link
              href="/setup"
              className="bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold px-6 py-3 rounded-xl transition-colors"
            >
              开始第一场面试
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {records.map((r) => (
              <div
                key={r.session_id}
                className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-[#111827]">{r.target_role || "未知职位"}</span>
                      <span className="text-xs text-[#9CA3AF]">
                        {TYPE_LABELS[r.interview_type] ?? r.interview_type}
                      </span>
                    </div>
                    <p className="text-xs text-[#9CA3AF] mb-3">{r.date}</p>
                    <p className="text-sm text-[#6B7280] line-clamp-2">{r.summary_text}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-2xl font-bold text-[#111827]">
                      {r.total_score.toFixed(0)}
                    </div>
                    <div className={`text-xs font-medium px-2 py-0.5 rounded-full mt-1 ${GRADE_COLOR[r.grade] ?? "bg-gray-100 text-gray-600"}`}>
                      {r.grade}
                    </div>
                  </div>
                </div>

                <div className="flex gap-2 mt-4">
                  <Link
                    href={`/feedback/${r.session_id}`}
                    className="flex-1 text-center text-sm bg-[#EEF2FF] text-[#6366F1] hover:bg-[#E0E7FF] font-medium py-2 rounded-lg transition-colors"
                  >
                    查看报告
                  </Link>
                  <button
                    onClick={() => handleDelete(r.session_id)}
                    className="text-sm text-[#9CA3AF] hover:text-[#EF4444] border border-[#E5E7EB] hover:border-[#EF4444] px-4 py-2 rounded-lg transition-colors"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CategoryScoreBar from "@/components/CategoryScoreBar";
import {
  CATEGORIES,
  CATEGORY_LABELS,
  QUESTIONS,
  SCALE_OPTIONS,
  type Category,
} from "@/lib/questions";
import type { Level } from "@/lib/scoring";
import { getSupabaseBrowserClient } from "@/lib/supabase";

interface ResponseDetail {
  session: {
    id: string;
    status: string;
    completed_at: string | null;
    started_at: string;
    respondents: {
      name: string;
      company_name: string;
      position: string;
      industry: string;
      employee_count: string;
      email: string;
      phone: string | null;
      lead_source: string;
    } | null;
  };
  answers: { question_no: number; category: Category; score: number }[];
  category_scores: {
    category: Category;
    total_score: number;
    level: Level;
  }[];
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AdminResponseDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ResponseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      const supabase = getSupabaseBrowserClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        router.replace("/admin/login");
        return;
      }
      const response = await fetch(`/api/admin/responses/${params.id}`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (response.status === 401) {
        router.replace("/admin/login");
        return;
      }
      if (!response.ok) {
        setError(
          response.status === 404
            ? "回答が見つかりません"
            : "詳細の取得に失敗しました"
        );
        return;
      }
      setDetail(await response.json());
    };
    load();
  }, [router, params.id]);

  if (error) {
    return (
      <main className="flex-1 px-6 py-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <p className="text-red-500 mb-4">{error}</p>
          <Link href="/admin/responses" className="text-navy underline">
            回答一覧へ戻る
          </Link>
        </div>
      </main>
    );
  }

  if (!detail) {
    return (
      <main className="flex-1 px-6 py-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <p className="text-gray-500">読み込み中...</p>
        </div>
      </main>
    );
  }

  const respondent = detail.session.respondents;
  const scoreByCategory = new Map(
    detail.category_scores.map((score) => [score.category, score])
  );
  const answerByQuestionNo = new Map(
    detail.answers.map((answer) => [answer.question_no, answer.score])
  );
  const scaleLabel = (score: number | undefined) =>
    SCALE_OPTIONS.find((option) => option.value === score)?.label ?? "-";

  return (
    <main className="flex-1 px-6 py-8 bg-gray-50">
      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <Link
            href="/admin/responses"
            className="text-sm text-navy underline"
          >
            ← 回答一覧へ戻る
          </Link>
        </div>

        {/* 回答者情報 */}
        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-navy">
              {respondent?.name ?? "-"}{" "}
              <span className="text-base font-normal text-gray-500">
                様
              </span>
            </h1>
            <span className="inline-block px-3 py-1 rounded bg-gray-100 text-gray-700 text-sm">
              {detail.session.status}
            </span>
          </div>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">会社名</dt>
              <dd>{respondent?.company_name ?? "-"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">役職</dt>
              <dd>{respondent?.position ?? "-"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">業種</dt>
              <dd>{respondent?.industry ?? "-"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">従業員数</dt>
              <dd>{respondent?.employee_count ?? "-"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">メール</dt>
              <dd className="break-all">{respondent?.email ?? "-"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">電話番号</dt>
              <dd>{respondent?.phone || "-"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">きっかけ</dt>
              <dd>{respondent?.lead_source ?? "-"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 text-gray-500 shrink-0">回答日</dt>
              <dd>
                {formatDate(
                  detail.session.completed_at ?? detail.session.started_at
                )}
              </dd>
            </div>
          </dl>
        </section>

        {/* カテゴリ別スコア */}
        <section>
          <h2 className="text-lg font-bold text-navy mb-4">
            カテゴリ別スコア
          </h2>
          <div className="space-y-3">
            {CATEGORIES.map((category) => {
              const score = scoreByCategory.get(category);
              return (
                <CategoryScoreBar
                  key={category}
                  label={CATEGORY_LABELS[category]}
                  score={score?.total_score ?? 0}
                  maxScore={20}
                  level={score?.level ?? "低"}
                />
              );
            })}
          </div>
          <p className="text-xs text-gray-500 mt-3">
            レベル判定: 低（0〜7） / 中（8〜13） / 高（14〜20）
          </p>
        </section>

        {/* 全25問の回答 */}
        <section>
          <h2 className="text-lg font-bold text-navy mb-4">全25問の回答</h2>
          <div className="bg-white border border-gray-200 rounded-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-navy text-white text-left">
                  <th className="px-4 py-3 font-medium w-16">No.</th>
                  <th className="px-4 py-3 font-medium">質問文</th>
                  <th className="px-4 py-3 font-medium w-56">回答</th>
                </tr>
              </thead>
              <tbody>
                {QUESTIONS.map((question) => {
                  const score = answerByQuestionNo.get(question.no);
                  return (
                    <tr
                      key={question.no}
                      className="border-t border-gray-100"
                    >
                      <td className="px-4 py-3 text-gray-500">
                        {question.no}
                      </td>
                      <td className="px-4 py-3 leading-relaxed">
                        {question.text}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="font-bold text-navy mr-2">
                          {score ?? "-"}
                        </span>
                        <span className="text-gray-600">
                          {scaleLabel(score)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}

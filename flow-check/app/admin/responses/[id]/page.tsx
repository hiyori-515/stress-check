"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CategoryScoreBar from "@/components/CategoryScoreBar";
import RadarScoreChart from "@/components/RadarScoreChart";
import FinalAssessmentSection from "@/components/FinalAssessmentSection";
import InterviewNotesSection from "@/components/InterviewNotesSection";
import type { HypothesisReport } from "@/lib/hypothesis";
import {
  CATEGORIES,
  CATEGORY_LABELS,
  QUESTIONS,
  SCALE_OPTIONS,
  type Category,
} from "@/lib/questions";
import type { Level } from "@/lib/scoring";
import { STATUS_OPTIONS } from "@/lib/status";
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

interface StoredHypothesis extends HypothesisReport {
  generated_at: string;
}

type Tab = "detail" | "digest";

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
  const [token, setToken] = useState<string | null>(null);
  const [detail, setDetail] = useState<ResponseDetail | null>(null);
  const [hypothesis, setHypothesis] = useState<StoredHypothesis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("detail");

  const [status, setStatus] = useState<string>("");
  const [statusSaving, setStatusSaving] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const [checkedQuestions, setCheckedQuestions] = useState<Set<number>>(
    new Set()
  );

  const [hasClientComment, setHasClientComment] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

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
      const accessToken = session.access_token;
      setToken(accessToken);

      const [detailResponse, hypothesisResponse] = await Promise.all([
        fetch(`/api/admin/responses/${params.id}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        }),
        fetch(`/api/admin/hypothesis/${params.id}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        }),
      ]);

      if (detailResponse.status === 401) {
        router.replace("/admin/login");
        return;
      }
      if (!detailResponse.ok) {
        setError(
          detailResponse.status === 404
            ? "回答が見つかりません"
            : "詳細の取得に失敗しました"
        );
        return;
      }
      const detailBody = (await detailResponse.json()) as ResponseDetail;
      setDetail(detailBody);
      setStatus(detailBody.session.status);

      if (hypothesisResponse.ok) {
        const hypothesisBody = await hypothesisResponse.json();
        setHypothesis(hypothesisBody.hypothesis);
      }
    };
    load();
  }, [router, params.id]);

  const handleStatusChange = async (nextStatus: string) => {
    if (!token) return;
    const previous = status;
    setStatus(nextStatus);
    setStatusSaving(true);
    setStatusError(null);
    const response = await fetch(
      `/api/admin/responses/${params.id}/status`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: nextStatus }),
      }
    );
    setStatusSaving(false);
    if (!response.ok) {
      setStatus(previous);
      setStatusError("ステータスの更新に失敗しました");
    }
  };

  const handleGenerate = async () => {
    if (!token) return;
    setGenerating(true);
    setGenerateError(null);
    const response = await fetch("/api/admin/hypothesis/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ session_id: params.id }),
    });
    setGenerating(false);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setGenerateError(body?.error ?? "レポートの生成に失敗しました");
      return;
    }
    const body = await response.json();
    setHypothesis(body.hypothesis);
  };

  const handleGeneratePdf = async () => {
    if (!token) return;
    setPdfLoading(true);
    setPdfError(null);
    const response = await fetch(`/api/admin/report/${params.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    setPdfLoading(false);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setPdfError(body?.error ?? "PDFの生成に失敗しました");
      return;
    }
    const blob = await response.blob();
    setPdfUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(blob);
    });
  };

  const toggleQuestion = (index: number) => {
    setCheckedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

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

        {/* 回答者情報 + ステータス */}
        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4 gap-4">
            <h1 className="text-xl font-bold text-navy">
              {respondent?.name ?? "-"}{" "}
              <span className="text-base font-normal text-gray-500">様</span>
            </h1>
            <div className="flex items-center gap-2">
              <label htmlFor="status" className="text-sm text-gray-500">
                ステータス
              </label>
              <select
                id="status"
                value={status}
                onChange={(e) => handleStatusChange(e.target.value)}
                disabled={statusSaving}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy disabled:opacity-50"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {statusError && (
            <p className="text-sm text-red-500 mb-3">{statusError}</p>
          )}
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

        {/* タブ切り替え */}
        <div className="flex border-b border-gray-200" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "detail"}
            onClick={() => setTab("detail")}
            className={`px-6 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === "detail"
                ? "border-navy text-navy"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            詳細ビュー
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "digest"}
            onClick={() => setTab("digest")}
            className={`px-6 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === "digest"
                ? "border-navy text-navy"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            要点ビュー
          </button>
        </div>

        {tab === "detail" ? (
          <>
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
              <p className="text-xs text-gray-500 mt-1">
                ※スコアが高いほど、その領域に詰まりが集中しています
              </p>
            </section>

            {/* AI仮説レポート */}
            <section className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4 gap-4">
                <h2 className="text-lg font-bold text-navy">
                  AI仮説レポート
                </h2>
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={generating}
                  className="bg-navy hover:bg-navy-dark text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                >
                  {generating
                    ? "生成中..."
                    : hypothesis
                      ? "仮説レポートを再生成"
                      : "仮説レポートを生成"}
                </button>
              </div>
              {generateError && (
                <p className="text-sm text-red-500 mb-4">{generateError}</p>
              )}
              {!hypothesis ? (
                <p className="text-sm text-gray-500">
                  まだ生成されていません。「仮説レポートを生成」を押すと、回答内容をもとにAIが面談前の仮説を整理します。
                </p>
              ) : (
                <div className="space-y-5 text-sm">
                  <p className="text-xs text-gray-500">
                    生成日時: {formatDate(hypothesis.generated_at)}
                  </p>
                  <div>
                    <h3 className="font-bold text-navy mb-1">回答サマリー</h3>
                    <p className="whitespace-pre-wrap leading-relaxed">
                      {hypothesis.summary}
                    </p>
                  </div>
                  <div>
                    <h3 className="font-bold text-navy mb-1">
                      カテゴリ別傾向
                    </h3>
                    <p className="whitespace-pre-wrap leading-relaxed">
                      {hypothesis.category_trends}
                    </p>
                  </div>
                  <div>
                    <h3 className="font-bold text-navy mb-1">仮説</h3>
                    <ul className="list-disc pl-5 space-y-1">
                      {hypothesis.hypotheses.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3 className="font-bold text-navy mb-1">
                      面談で確認したい問い
                    </h3>
                    <ul className="list-disc pl-5 space-y-1">
                      {hypothesis.interview_questions.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3 className="font-bold text-navy mb-1">
                      最初に整えるとよさそうなポイント
                    </h3>
                    <ul className="list-disc pl-5 space-y-1">
                      {hypothesis.first_steps.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </section>

            {/* 全25問の回答 */}
            <section>
              <h2 className="text-lg font-bold text-navy mb-4">
                全25問の回答
              </h2>
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
          </>
        ) : (
          /* 要点ビュー（面談中に参照する用・1画面完結） */
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-white border border-gray-200 rounded-xl p-6">
              <h2 className="text-lg font-bold text-navy mb-2">
                カテゴリ別スコア
              </h2>
              <RadarScoreChart scores={detail.category_scores} />

              <h2 className="text-lg font-bold text-navy mt-6 mb-3">仮説</h2>
              {hypothesis ? (
                <ul className="list-disc pl-5 space-y-2 text-sm">
                  {hypothesis.hypotheses.slice(0, 3).map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500">
                  仮説レポートが未生成です。詳細ビューから生成してください。
                </p>
              )}
            </section>

            <section className="bg-white border border-gray-200 rounded-xl p-6">
              <h2 className="text-lg font-bold text-navy mb-4">
                面談で確認したい問い
              </h2>
              {hypothesis ? (
                <ul className="space-y-3">
                  {hypothesis.interview_questions.map((question, i) => (
                    <li key={i}>
                      <label className="flex items-start gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={checkedQuestions.has(i)}
                          onChange={() => toggleQuestion(i)}
                          className="mt-1 w-4 h-4 accent-[#1a365d]"
                        />
                        <span
                          className={`text-sm leading-relaxed ${
                            checkedQuestions.has(i)
                              ? "line-through text-gray-400"
                              : ""
                          }`}
                        >
                          {question}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500">
                  仮説レポートが未生成です。詳細ビューから生成してください。
                </p>
              )}
              <p className="text-xs text-gray-400 mt-4">
                ※チェックは画面上のみで、保存されません
              </p>
            </section>
          </div>
        )}

        {/* タブの外・常に表示 */}
        {token && (
          <>
            <InterviewNotesSection sessionId={params.id} token={token} />
            <FinalAssessmentSection
              sessionId={params.id}
              token={token}
              onClientCommentChange={setHasClientComment}
            />

            {/* PDFレポート */}
            <section className="bg-white border border-gray-200 rounded-xl p-6">
              <h2 className="text-lg font-bold text-navy mb-4">
                PDFレポート
              </h2>
              <p className="text-sm text-gray-600 mb-4">
                経営者にお渡しするレポートを生成します。カテゴリ別スコアと「経営者向けコメント」が掲載されます。
              </p>
              <div className="flex items-center gap-4 flex-wrap">
                <button
                  type="button"
                  onClick={handleGeneratePdf}
                  disabled={!hasClientComment || pdfLoading}
                  className="bg-navy hover:bg-navy-dark text-white font-bold px-6 py-2 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {pdfLoading ? "生成中..." : "PDFレポートを生成"}
                </button>
                {!hasClientComment && (
                  <p className="text-sm text-gray-500">
                    経営者向けコメントを入力してからPDFを生成できます
                  </p>
                )}
                {pdfUrl && (
                  <a
                    href={pdfUrl}
                    download={`flow-check-report-${params.id.slice(0, 8)}.pdf`}
                    className="border border-navy text-navy font-bold px-6 py-2 rounded-lg hover:bg-navy-light transition-colors"
                  >
                    PDFをダウンロード
                  </a>
                )}
              </div>
              {pdfError && (
                <p className="text-sm text-red-500 mt-3">{pdfError}</p>
              )}
              {pdfUrl && (
                <iframe
                  src={pdfUrl}
                  title="PDFレポートプレビュー"
                  className="w-full mt-6 border border-gray-200 rounded-lg"
                  style={{ height: "640px" }}
                />
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}

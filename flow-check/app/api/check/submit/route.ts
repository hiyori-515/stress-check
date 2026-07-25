import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";
import type { Profile } from "@/lib/profile";
import {
  EMPLOYEE_COUNT_OPTIONS,
  INDUSTRY_OPTIONS,
  LEAD_SOURCE_OPTIONS,
  TOTAL_QUESTIONS,
} from "@/lib/questions";
import {
  categoryForQuestion,
  computeCategoryScores,
  type AnswerInput,
} from "@/lib/scoring";
import {
  createAdminClient,
  describeSupabaseError,
} from "@/lib/supabase-admin";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface SubmitBody {
  profile: Profile;
  answers: AnswerInput[];
}

function validate(body: SubmitBody): string | null {
  const { profile, answers } = body;
  if (!profile || typeof profile !== "object") return "回答者情報がありません";

  const requiredText: (keyof Profile)[] = ["name", "company_name", "position"];
  for (const field of requiredText) {
    if (typeof profile[field] !== "string" || !profile[field].trim()) {
      return `必須項目が未入力です: ${field}`;
    }
  }
  if (typeof profile.email !== "string" || !EMAIL_PATTERN.test(profile.email.trim())) {
    return "メールアドレスの形式が正しくありません";
  }
  if (!INDUSTRY_OPTIONS.includes(profile.industry as (typeof INDUSTRY_OPTIONS)[number])) {
    return "業種の値が不正です";
  }
  if (
    !EMPLOYEE_COUNT_OPTIONS.includes(
      profile.employee_count as (typeof EMPLOYEE_COUNT_OPTIONS)[number]
    )
  ) {
    return "従業員数の値が不正です";
  }
  if (
    !LEAD_SOURCE_OPTIONS.includes(
      profile.lead_source as (typeof LEAD_SOURCE_OPTIONS)[number]
    )
  ) {
    return "きっかけの値が不正です";
  }

  if (!Array.isArray(answers) || answers.length !== TOTAL_QUESTIONS) {
    return `回答は${TOTAL_QUESTIONS}問すべて必要です`;
  }
  const seen = new Set<number>();
  for (const answer of answers) {
    if (
      !Number.isInteger(answer.question_no) ||
      answer.question_no < 1 ||
      answer.question_no > TOTAL_QUESTIONS
    ) {
      return "質問番号が不正です";
    }
    if (seen.has(answer.question_no)) return "質問番号が重複しています";
    seen.add(answer.question_no);
    if (!Number.isInteger(answer.score) || answer.score < 0 || answer.score > 4) {
      return "回答値が不正です";
    }
  }
  return null;
}

export async function POST(request: Request) {
  let body: SubmitBody;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "リクエストボディが不正です" },
      { status: 400 }
    );
  }

  const validationError = validate(body);
  if (validationError) {
    return NextResponse.json({ error: validationError }, { status: 400 });
  }

  const { profile, answers } = body;

  let supabase;
  try {
    supabase = createAdminClient();
  } catch (error) {
    console.error("supabase client init failed:", error);
    return NextResponse.json(
      {
        error: "サーバー設定に問題があります",
        code: "env_missing",
        hint: error instanceof Error ? error.message : "環境変数を確認してください",
      },
      { status: 500 }
    );
  }

  // IDはアプリ側で採番する。挿入直後のSELECT(RETURNING)を不要にすることで、
  // 読み取りを認証済みのみに限定しているRLSポリシー下でも確実に保存できる。
  const respondentId = randomUUID();
  const sessionId = randomUUID();

  const fail = (
    step: string,
    error: { code?: string; message?: string } | null
  ) => {
    const { code, hint } = describeSupabaseError(error);
    console.error(`${step} insert failed:`, { code, error });
    return NextResponse.json(
      { error: "回答の保存に失敗しました", step, code, hint },
      { status: 500 }
    );
  };

  // 1. 回答者を登録
  const { error: respondentError } = await supabase.from("respondents").insert({
    id: respondentId,
    name: profile.name.trim(),
    company_name: profile.company_name.trim(),
    position: profile.position.trim(),
    industry: profile.industry,
    employee_count: profile.employee_count,
    email: profile.email.trim(),
    phone: profile.phone?.trim() || null,
    lead_source: profile.lead_source,
  });
  if (respondentError) return fail("respondents", respondentError);

  // 2. 診断セッションを登録
  const { error: sessionError } = await supabase
    .from("diagnostic_sessions")
    .insert({
      id: sessionId,
      respondent_id: respondentId,
      status: "未面談",
      completed_at: new Date().toISOString(),
    });
  if (sessionError) return fail("diagnostic_sessions", sessionError);

  // 3. 個別回答を登録（categoryはquestion_noから自動判定）
  const { error: answersError } = await supabase.from("answers").insert(
    answers.map((answer) => ({
      session_id: sessionId,
      question_no: answer.question_no,
      category: categoryForQuestion(answer.question_no),
      score: answer.score,
    }))
  );
  if (answersError) return fail("answers", answersError);

  // 4. カテゴリ別スコアを集計して登録
  const categoryScores = computeCategoryScores(answers);
  const { error: scoresError } = await supabase.from("category_scores").insert(
    categoryScores.map((score) => ({
      session_id: sessionId,
      category: score.category,
      total_score: score.total_score,
      level: score.level,
    }))
  );
  if (scoresError) return fail("category_scores", scoresError);

  return NextResponse.json({ ok: true, session_id: sessionId });
}

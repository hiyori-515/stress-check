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
import { createAdminClient } from "@/lib/supabase-admin";

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
  const supabase = createAdminClient();

  // 1. 回答者を登録
  const { data: respondent, error: respondentError } = await supabase
    .from("respondents")
    .insert({
      name: profile.name.trim(),
      company_name: profile.company_name.trim(),
      position: profile.position.trim(),
      industry: profile.industry,
      employee_count: profile.employee_count,
      email: profile.email.trim(),
      phone: profile.phone?.trim() || null,
      lead_source: profile.lead_source,
    })
    .select("id")
    .single();

  if (respondentError || !respondent) {
    console.error("respondents insert failed:", respondentError);
    return NextResponse.json(
      { error: "回答の保存に失敗しました" },
      { status: 500 }
    );
  }

  // 2. 診断セッションを登録
  const { data: session, error: sessionError } = await supabase
    .from("diagnostic_sessions")
    .insert({
      respondent_id: respondent.id,
      status: "未面談",
      completed_at: new Date().toISOString(),
    })
    .select("id")
    .single();

  if (sessionError || !session) {
    console.error("diagnostic_sessions insert failed:", sessionError);
    return NextResponse.json(
      { error: "回答の保存に失敗しました" },
      { status: 500 }
    );
  }

  // 3. 個別回答を登録（categoryはquestion_noから自動判定）
  const { error: answersError } = await supabase.from("answers").insert(
    answers.map((answer) => ({
      session_id: session.id,
      question_no: answer.question_no,
      category: categoryForQuestion(answer.question_no),
      score: answer.score,
    }))
  );

  if (answersError) {
    console.error("answers insert failed:", answersError);
    return NextResponse.json(
      { error: "回答の保存に失敗しました" },
      { status: 500 }
    );
  }

  // 4. カテゴリ別スコアを集計して登録
  const categoryScores = computeCategoryScores(answers);
  const { error: scoresError } = await supabase.from("category_scores").insert(
    categoryScores.map((score) => ({
      session_id: session.id,
      category: score.category,
      total_score: score.total_score,
      level: score.level,
    }))
  );

  if (scoresError) {
    console.error("category_scores insert failed:", scoresError);
    return NextResponse.json(
      { error: "回答の保存に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ ok: true, session_id: session.id });
}

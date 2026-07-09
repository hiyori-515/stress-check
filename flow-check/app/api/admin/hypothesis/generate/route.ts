import Anthropic from "@anthropic-ai/sdk";
import { NextResponse } from "next/server";
import {
  buildHypothesisPrompt,
  parseHypothesisResponse,
} from "@/lib/hypothesis";
import type { CategoryScore } from "@/lib/scoring";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function POST(request: Request) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  let body: { session_id?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "リクエストボディが不正です" },
      { status: 400 }
    );
  }
  const sessionId = body.session_id;
  if (!sessionId || typeof sessionId !== "string") {
    return NextResponse.json(
      { error: "session_idが必要です" },
      { status: 400 }
    );
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey || apiKey === "PLACEHOLDER") {
    return NextResponse.json(
      {
        error:
          "ANTHROPIC_API_KEYが設定されていません。環境変数を設定してから再度お試しください。",
      },
      { status: 500 }
    );
  }

  const supabase = createAdminClient();

  // 回答データ一式を取得
  const [sessionResult, answersResult, scoresResult] = await Promise.all([
    supabase
      .from("diagnostic_sessions")
      .select("id, respondents(name, company_name, position, industry, employee_count)")
      .eq("id", sessionId)
      .maybeSingle(),
    supabase
      .from("answers")
      .select("question_no, score")
      .eq("session_id", sessionId)
      .order("question_no", { ascending: true }),
    supabase
      .from("category_scores")
      .select("category, total_score, level")
      .eq("session_id", sessionId),
  ]);

  if (sessionResult.error || answersResult.error || scoresResult.error) {
    console.error(
      "hypothesis data fetch failed:",
      sessionResult.error ?? answersResult.error ?? scoresResult.error
    );
    return NextResponse.json(
      { error: "回答データの取得に失敗しました" },
      { status: 500 }
    );
  }
  const session = sessionResult.data;
  // 型定義未生成のため、埋め込みリレーションは配列/オブジェクト両対応で正規化する
  const respondent = Array.isArray(session?.respondents)
    ? session?.respondents[0]
    : session?.respondents;
  if (!respondent || answersResult.data.length === 0) {
    return NextResponse.json(
      { error: "回答が見つかりません" },
      { status: 404 }
    );
  }

  const prompt = buildHypothesisPrompt(
    respondent,
    answersResult.data,
    scoresResult.data as CategoryScore[]
  );

  const anthropic = new Anthropic({ apiKey });
  let responseText: string;
  try {
    const message = await anthropic.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 4096,
      messages: [{ role: "user", content: prompt }],
    });
    responseText = message.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");
  } catch (error) {
    if (error instanceof Anthropic.AuthenticationError) {
      return NextResponse.json(
        { error: "ANTHROPIC_API_KEYが無効です。設定を確認してください。" },
        { status: 500 }
      );
    }
    if (error instanceof Anthropic.RateLimitError) {
      return NextResponse.json(
        { error: "AI APIのレート制限に達しました。しばらく待って再度お試しください。" },
        { status: 500 }
      );
    }
    if (error instanceof Anthropic.APIConnectionError) {
      return NextResponse.json(
        { error: "AI APIに接続できませんでした。ネットワークを確認してください。" },
        { status: 500 }
      );
    }
    console.error("anthropic request failed:", error);
    return NextResponse.json(
      { error: "レポートの生成に失敗しました" },
      { status: 500 }
    );
  }

  let report;
  try {
    report = parseHypothesisResponse(responseText);
  } catch (error) {
    console.error("hypothesis parse failed:", error, responseText);
    return NextResponse.json(
      { error: "レポートの解析に失敗しました。再度お試しください。" },
      { status: 500 }
    );
  }

  // session_idはUNIQUE。再生成時は上書き保存する
  const { data: saved, error: saveError } = await supabase
    .from("ai_hypothesis")
    .upsert(
      {
        session_id: sessionId,
        summary: report.summary,
        category_trends: report.category_trends,
        hypotheses: report.hypotheses,
        interview_questions: report.interview_questions,
        first_steps: report.first_steps,
        raw_response: responseText,
        generated_at: new Date().toISOString(),
      },
      { onConflict: "session_id" }
    )
    .select(
      "session_id, summary, category_trends, hypotheses, interview_questions, first_steps, generated_at"
    )
    .single();

  if (saveError || !saved) {
    console.error("ai_hypothesis upsert failed:", saveError);
    return NextResponse.json(
      { error: "レポートの保存に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ hypothesis: saved });
}

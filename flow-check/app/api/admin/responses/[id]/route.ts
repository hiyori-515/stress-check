import { NextResponse } from "next/server";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  const { id } = await params;
  const supabase = createAdminClient();

  const { data: session, error: sessionError } = await supabase
    .from("diagnostic_sessions")
    .select("id, status, completed_at, started_at, respondents(*)")
    .eq("id", id)
    .maybeSingle();

  if (sessionError) {
    console.error("response detail failed:", sessionError);
    return NextResponse.json(
      { error: "詳細の取得に失敗しました" },
      { status: 500 }
    );
  }
  if (!session) {
    return NextResponse.json(
      { error: "回答が見つかりません" },
      { status: 404 }
    );
  }

  const [answersResult, scoresResult] = await Promise.all([
    supabase
      .from("answers")
      .select("question_no, category, score")
      .eq("session_id", id)
      .order("question_no", { ascending: true }),
    supabase
      .from("category_scores")
      .select("category, total_score, level")
      .eq("session_id", id),
  ]);

  if (answersResult.error || scoresResult.error) {
    console.error(
      "response detail failed:",
      answersResult.error ?? scoresResult.error
    );
    return NextResponse.json(
      { error: "詳細の取得に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({
    session,
    answers: answersResult.data,
    category_scores: scoresResult.data,
  });
}

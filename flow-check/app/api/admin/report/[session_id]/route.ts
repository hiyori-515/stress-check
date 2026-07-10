import { renderToBuffer } from "@react-pdf/renderer";
import { NextResponse } from "next/server";
import {
  buildReportDocument,
  type ReportScore,
} from "@/components/ReportDocument";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ session_id: string }> }
) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  const { session_id } = await params;
  const supabase = createAdminClient();

  const [sessionResult, scoresResult, assessmentResult] = await Promise.all([
    supabase
      .from("diagnostic_sessions")
      .select("id, completed_at, started_at, respondents(name, company_name)")
      .eq("id", session_id)
      .maybeSingle(),
    supabase
      .from("category_scores")
      .select("category, total_score, level")
      .eq("session_id", session_id),
    supabase
      .from("final_assessment")
      .select("client_facing_comment")
      .eq("session_id", session_id)
      .maybeSingle(),
  ]);

  if (sessionResult.error || scoresResult.error || assessmentResult.error) {
    console.error(
      "report data fetch failed:",
      sessionResult.error ?? scoresResult.error ?? assessmentResult.error
    );
    return NextResponse.json(
      { error: "レポートデータの取得に失敗しました" },
      { status: 500 }
    );
  }

  const session = sessionResult.data;
  const respondent = Array.isArray(session?.respondents)
    ? session?.respondents[0]
    : session?.respondents;
  if (!session || !respondent) {
    return NextResponse.json(
      { error: "回答が見つかりません" },
      { status: 404 }
    );
  }

  const clientComment =
    assessmentResult.data?.client_facing_comment?.trim() ?? "";
  if (!clientComment) {
    return NextResponse.json(
      {
        error:
          "経営者向けコメントが未入力です。最終見立ての「経営者向けコメント」を入力してからPDFを生成してください。",
      },
      { status: 400 }
    );
  }

  const conductedOn = new Date(
    session.completed_at ?? session.started_at
  ).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  let pdfBuffer: Buffer;
  try {
    pdfBuffer = await renderToBuffer(
      buildReportDocument({
        name: respondent.name,
        companyName: respondent.company_name,
        conductedOn,
        scores: (scoresResult.data ?? []) as ReportScore[],
        clientComment,
      })
    );
  } catch (error) {
    console.error("pdf render failed:", error);
    return NextResponse.json(
      { error: "PDFの生成に失敗しました" },
      { status: 500 }
    );
  }

  return new NextResponse(new Uint8Array(pdfBuffer), {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="flow-check-report.pdf"`,
      "Cache-Control": "no-store",
    },
  });
}

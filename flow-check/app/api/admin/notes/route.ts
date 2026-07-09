import { NextResponse } from "next/server";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function POST(request: Request) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  let body: {
    session_id?: string;
    note_text?: string;
    interview_date?: string | null;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "リクエストボディが不正です" },
      { status: 400 }
    );
  }

  if (!body.session_id || typeof body.session_id !== "string") {
    return NextResponse.json(
      { error: "session_idが必要です" },
      { status: 400 }
    );
  }
  if (typeof body.note_text !== "string" || !body.note_text.trim()) {
    return NextResponse.json(
      { error: "メモを入力してください" },
      { status: 400 }
    );
  }
  if (body.interview_date && !/^\d{4}-\d{2}-\d{2}$/.test(body.interview_date)) {
    return NextResponse.json(
      { error: "面談日の形式が不正です" },
      { status: 400 }
    );
  }

  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("interview_notes")
    .insert({
      session_id: body.session_id,
      note_text: body.note_text.trim(),
      interview_date: body.interview_date || null,
    })
    .select("id, session_id, note_text, interview_date, created_at")
    .single();

  if (error || !data) {
    console.error("interview_notes insert failed:", error);
    return NextResponse.json(
      { error: "メモの保存に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ note: data });
}

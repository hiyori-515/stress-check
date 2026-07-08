import { NextResponse } from "next/server";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function GET(request: Request) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("diagnostic_sessions")
    .select(
      "id, status, completed_at, started_at, respondents(name, company_name, position, industry)"
    )
    .order("completed_at", { ascending: false, nullsFirst: false });

  if (error) {
    console.error("responses list failed:", error);
    return NextResponse.json(
      { error: "一覧の取得に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ responses: data });
}

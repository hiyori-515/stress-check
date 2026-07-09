import { NextResponse } from "next/server";
import { STATUS_OPTIONS } from "@/lib/status";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  let body: { status?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "リクエストボディが不正です" },
      { status: 400 }
    );
  }
  if (
    !body.status ||
    !STATUS_OPTIONS.includes(body.status as (typeof STATUS_OPTIONS)[number])
  ) {
    return NextResponse.json(
      { error: "ステータスの値が不正です" },
      { status: 400 }
    );
  }

  const { id } = await params;
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("diagnostic_sessions")
    .update({ status: body.status })
    .eq("id", id)
    .select("id, status")
    .maybeSingle();

  if (error) {
    console.error("status update failed:", error);
    return NextResponse.json(
      { error: "ステータスの更新に失敗しました" },
      { status: 500 }
    );
  }
  if (!data) {
    return NextResponse.json(
      { error: "回答が見つかりません" },
      { status: 404 }
    );
  }

  return NextResponse.json({ session: data });
}

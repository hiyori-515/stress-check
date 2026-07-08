"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getSupabaseBrowserClient } from "@/lib/supabase";

interface ResponseRow {
  id: string;
  status: string;
  completed_at: string | null;
  started_at: string;
  respondents: {
    name: string;
    company_name: string;
    position: string;
    industry: string;
  } | null;
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  const date = new Date(iso);
  return date.toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AdminResponsesPage() {
  const router = useRouter();
  const [rows, setRows] = useState<ResponseRow[] | null>(null);
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
      const response = await fetch("/api/admin/responses", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (response.status === 401) {
        router.replace("/admin/login");
        return;
      }
      if (!response.ok) {
        setError("一覧の取得に失敗しました");
        return;
      }
      const body = await response.json();
      setRows(body.responses);
    };
    load();
  }, [router]);

  const handleLogout = useCallback(async () => {
    const supabase = getSupabaseBrowserClient();
    await supabase.auth.signOut();
    router.replace("/admin/login");
  }, [router]);

  return (
    <main className="flex-1 px-6 py-8 bg-gray-50">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-navy">回答一覧</h1>
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-gray-800 underline"
          >
            ログアウト
          </button>
        </div>

        {error && <p className="text-red-500 mb-4">{error}</p>}

        {rows === null && !error ? (
          <p className="text-gray-500">読み込み中...</p>
        ) : rows && rows.length === 0 ? (
          <p className="text-gray-500">まだ回答がありません。</p>
        ) : (
          rows && (
            <div className="bg-white border border-gray-200 rounded-xl overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-navy text-white text-left">
                    <th className="px-4 py-3 font-medium">回答日</th>
                    <th className="px-4 py-3 font-medium">会社名</th>
                    <th className="px-4 py-3 font-medium">お名前</th>
                    <th className="px-4 py-3 font-medium">役職</th>
                    <th className="px-4 py-3 font-medium">業種</th>
                    <th className="px-4 py-3 font-medium">ステータス</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      onClick={() => router.push(`/admin/responses/${row.id}`)}
                      className="border-t border-gray-100 hover:bg-navy-light cursor-pointer"
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        {formatDate(row.completed_at ?? row.started_at)}
                      </td>
                      <td className="px-4 py-3">
                        {row.respondents?.company_name ?? "-"}
                      </td>
                      <td className="px-4 py-3">
                        {row.respondents?.name ?? "-"}
                      </td>
                      <td className="px-4 py-3">
                        {row.respondents?.position ?? "-"}
                      </td>
                      <td className="px-4 py-3">
                        {row.respondents?.industry ?? "-"}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs">
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </main>
  );
}

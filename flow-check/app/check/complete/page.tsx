"use client";

import { useEffect, useState } from "react";
import RadarScoreChart from "@/components/RadarScoreChart";
import { RESULT_SESSION_STORAGE_KEY } from "@/lib/profile";
import type { Category } from "@/lib/questions";
import type { Level } from "@/lib/scoring";

interface CategoryScore {
  category: Category;
  total_score: number;
  level: Level;
}

export default function CompletePage() {
  const [scores, setScores] = useState<CategoryScore[] | null>(null);

  useEffect(() => {
    const load = async () => {
      const sessionId = sessionStorage.getItem(RESULT_SESSION_STORAGE_KEY);
      if (!sessionId) return;
      try {
        const response = await fetch(`/api/check/scores/${sessionId}`);
        if (!response.ok) return;
        const body = await response.json();
        if (Array.isArray(body.scores) && body.scores.length === 5) {
          setScores(body.scores);
        }
      } catch {
        // 取得に失敗してもチャートを出さないだけ。回答者にエラーは見せない
      }
    };
    load();
  }, []);

  return (
    <main className="flex-1 flex items-center justify-center px-4 py-12">
      <div className="max-w-xl w-full text-center">
        <h1 className="text-3xl font-bold text-navy mb-8">
          ご回答ありがとうございます。
        </h1>

        {scores && (
          <section className="mb-10">
            <h2 className="text-lg font-bold text-navy mb-1">
              組織の流れ 現在地
            </h2>
            <div className="mx-auto w-full max-w-[400px]">
              <RadarScoreChart
                scores={scores}
                variant="respondent"
                height={300}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              低 0〜7 ／ 中 8〜13 ／ 高 14〜20
            </p>
          </section>
        )}

        <section>
          <h2 className="text-lg font-bold text-navy mb-3">この後の流れ</h2>
          {/* 親がtext-centerのため、inline-blockでリスト自体を中央に置きつつ本文は左揃え */}
          <ol className="inline-block text-left list-decimal list-inside text-gray-700 leading-relaxed space-y-1">
            <li>ご回答内容を弊社で分析</li>
            <li>担当者より面談日程をご案内</li>
            <li>フィードバック面談（30分）</li>
          </ol>
        </section>
      </div>
    </main>
  );
}

"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/questions";
import type { Level } from "@/lib/scoring";

const NAVY = "#1a365d";
const HIGH_RED = "#dc2626";
const LABEL_GRAY = "#374151";

/**
 * admin      : 黒川さんが読む用。高スコアを赤で強調し、目盛りも表示する
 * respondent : 回答者本人が見る用。解釈につながる強調はせず、数値の可視化のみ
 */
type Variant = "admin" | "respondent";

interface RadarScoreChartProps {
  scores: { category: Category; total_score: number; level: Level }[];
  variant?: Variant;
  /** チャートの高さ(px)。モバイルでラベルが切れないよう呼び出し側で調整できる */
  height?: number;
}

interface AngleTickProps {
  x?: number | string;
  y?: number | string;
  textAnchor?: "middle" | "start" | "end" | "inherit";
  payload?: { value?: string };
}

export default function RadarScoreChart({
  scores,
  variant = "admin",
  height = 320,
}: RadarScoreChartProps) {
  const isAdmin = variant === "admin";
  const scoreByCategory = new Map(scores.map((s) => [s.category, s]));
  const data = CATEGORIES.map((category) => {
    const score = scoreByCategory.get(category);
    return {
      label: CATEGORY_LABELS[category],
      score: score?.total_score ?? 0,
      level: score?.level ?? ("低" as Level),
    };
  });

  const renderAngleTick = (props: unknown) => {
    const { x = 0, y = 0, textAnchor, payload } = props as AngleTickProps;
    const item = data.find((d) => d.label === payload?.value);
    // 回答者向けでは高スコアを強調しない（強調自体が解釈になるため）
    const emphasize = isAdmin && item?.level === "高";
    // 最上部の軸だけは2行目がチャート側に伸びて頂点と重なるため、全体を持ち上げる
    const isTop = textAnchor === "middle";
    return (
      <text
        x={x}
        y={y}
        textAnchor={textAnchor}
        fill={emphasize ? HIGH_RED : LABEL_GRAY}
        fontSize={12}
        fontWeight={emphasize ? 700 : 400}
      >
        <tspan x={x} dy={isTop ? -16 : 0}>
          {item?.label}
        </tspan>
        <tspan x={x} dy="14" fontSize={11}>
          {item?.score}/20
        </tspan>
      </text>
    );
  };

  return (
    <div data-testid="radar-score-chart">
      <ResponsiveContainer width="100%" height={height}>
        <RadarChart data={data} outerRadius="62%">
          <PolarGrid gridType="polygon" stroke="#d1d5db" />
          <PolarAngleAxis dataKey="label" tick={renderAngleTick} />
          <PolarRadiusAxis
            domain={[0, 20]}
            tickCount={5}
            tick={isAdmin ? { fontSize: 9, fill: "#9ca3af" } : false}
            axisLine={false}
          />
          <Radar
            dataKey="score"
            stroke={NAVY}
            strokeWidth={2}
            fill={NAVY}
            fillOpacity={0.35}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
      {isAdmin && (
        <p className="text-xs text-gray-500 mt-2">
          ※外側に広がっている領域ほど、詰まりが集中しています
        </p>
      )}
    </div>
  );
}

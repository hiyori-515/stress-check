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

interface RadarScoreChartProps {
  scores: { category: Category; total_score: number; level: Level }[];
}

interface AngleTickProps {
  x?: number | string;
  y?: number | string;
  textAnchor?: "middle" | "start" | "end" | "inherit";
  payload?: { value?: string };
}

export default function RadarScoreChart({ scores }: RadarScoreChartProps) {
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
    const isHigh = item?.level === "高";
    return (
      <text
        x={x}
        y={y}
        textAnchor={textAnchor}
        fill={isHigh ? HIGH_RED : "#374151"}
        fontSize={12}
        fontWeight={isHigh ? 700 : 400}
      >
        <tspan x={x} dy="0">
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
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart data={data} outerRadius="65%">
          <PolarGrid gridType="polygon" stroke="#d1d5db" />
          <PolarAngleAxis dataKey="label" tick={renderAngleTick} />
          <PolarRadiusAxis
            domain={[0, 20]}
            tickCount={5}
            tick={{ fontSize: 9, fill: "#9ca3af" }}
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
      <p className="text-xs text-gray-500 mt-2">
        ※外側に広がっている領域ほど、詰まりが集中しています
      </p>
    </div>
  );
}

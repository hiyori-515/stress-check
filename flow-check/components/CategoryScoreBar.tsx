import type { Level } from "@/lib/scoring";

interface CategoryScoreBarProps {
  label: string;
  score: number;
  maxScore: number;
  level: Level;
}

export default function CategoryScoreBar({
  label,
  score,
  maxScore,
  level,
}: CategoryScoreBarProps) {
  const percent = Math.round((score / maxScore) * 100);
  const isHigh = level === "高";
  return (
    <div
      className={`p-4 rounded-lg border ${
        isHigh ? "border-gold bg-gold-light" : "border-gray-200 bg-white"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span
          className={`font-medium ${isHigh ? "text-navy font-bold" : "text-gray-800"}`}
        >
          {label}
        </span>
        <span className="text-sm">
          <span className={`font-bold ${isHigh ? "text-navy" : "text-gray-800"}`}>
            {score}
          </span>
          <span className="text-gray-500">/{maxScore}</span>
          <span
            className={`ml-3 inline-block px-2 py-0.5 rounded text-xs font-bold ${
              isHigh
                ? "bg-gold text-white"
                : level === "中"
                  ? "bg-navy-light text-navy"
                  : "bg-gray-100 text-gray-600"
            }`}
          >
            {level}
          </span>
        </span>
      </div>
      <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${isHigh ? "bg-gold" : "bg-navy"}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

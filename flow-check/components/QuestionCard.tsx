import { SCALE_OPTIONS, type Question } from "@/lib/questions";

interface QuestionCardProps {
  question: Question;
  selected: number | undefined;
  onSelect: (value: number) => void;
}

export default function QuestionCard({
  question,
  selected,
  onSelect,
}: QuestionCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 sm:p-8">
      <p className="text-sm text-gray-500 mb-2">Q{question.no}</p>
      <p className="text-lg sm:text-xl font-medium text-gray-900 leading-relaxed mb-6">
        {question.text}
      </p>
      <div className="space-y-3" role="radiogroup" aria-label={`質問${question.no}の回答`}>
        {SCALE_OPTIONS.map((option) => {
          const isSelected = selected === option.value;
          return (
            <label
              key={option.value}
              className={`flex items-center gap-3 p-3 sm:p-4 rounded-lg border cursor-pointer transition-colors ${
                isSelected
                  ? "border-navy bg-navy-light"
                  : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <input
                type="radio"
                name={`question-${question.no}`}
                value={option.value}
                checked={isSelected}
                onChange={() => onSelect(option.value)}
                className="w-4 h-4 accent-[#1a365d]"
              />
              <span
                className={`text-sm sm:text-base ${
                  isSelected ? "text-navy font-medium" : "text-gray-700"
                }`}
              >
                {option.label}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

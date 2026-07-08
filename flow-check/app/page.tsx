import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex-1 flex items-center justify-center px-4 py-12">
      <div className="max-w-xl w-full text-center">
        <h1 className="text-4xl sm:text-5xl font-bold text-navy tracking-wide mb-6">
          Flow Check
        </h1>
        <p className="text-lg text-gray-800 leading-relaxed mb-10">
          決めたのに進まない、任せたのに戻ってくる——
          <br className="hidden sm:block" />
          その理由を、面談前に整理します。
        </p>
        <ul className="text-left inline-block space-y-3 text-gray-700 mb-10">
          <li className="flex items-start gap-2">
            <span className="text-gold mt-1">●</span>
            <span>所要時間: 約5分</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-gold mt-1">●</span>
            <span>25の質問に回答していただきます</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-gold mt-1">●</span>
            <span>回答内容は黒川本人のみが確認します</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-gold mt-1">●</span>
            <span>回答後、面談のご案内をお送りします</span>
          </li>
        </ul>
        <div>
          <Link
            href="/check/profile"
            className="inline-block bg-navy hover:bg-navy-dark text-white font-bold text-lg px-12 py-4 rounded-lg transition-colors"
          >
            はじめる
          </Link>
        </div>
      </div>
    </main>
  );
}

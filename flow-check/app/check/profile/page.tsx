"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  EMPLOYEE_COUNT_OPTIONS,
  INDUSTRY_OPTIONS,
  LEAD_SOURCE_OPTIONS,
} from "@/lib/questions";
import { PROFILE_STORAGE_KEY, type Profile } from "@/lib/profile";

const EMPTY_PROFILE: Profile = {
  name: "",
  company_name: "",
  position: "",
  industry: "",
  employee_count: "",
  email: "",
  phone: "",
  lead_source: "",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile>(EMPTY_PROFILE);
  const [errors, setErrors] = useState<Partial<Record<keyof Profile, string>>>(
    {}
  );

  const update = (field: keyof Profile, value: string) => {
    setProfile((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const nextErrors: Partial<Record<keyof Profile, string>> = {};
    if (!profile.name.trim()) nextErrors.name = "お名前を入力してください";
    if (!profile.company_name.trim())
      nextErrors.company_name = "会社名・法人名を入力してください";
    if (!profile.position.trim())
      nextErrors.position = "役職を入力してください";
    if (!profile.industry) nextErrors.industry = "業種を選択してください";
    if (!profile.employee_count)
      nextErrors.employee_count = "従業員数を選択してください";
    if (!profile.email.trim()) {
      nextErrors.email = "メールアドレスを入力してください";
    } else if (!EMAIL_PATTERN.test(profile.email.trim())) {
      nextErrors.email = "メールアドレスの形式が正しくありません";
    }
    if (!profile.lead_source)
      nextErrors.lead_source = "きっかけを選択してください";

    if (Object.values(nextErrors).some(Boolean)) {
      setErrors(nextErrors);
      return;
    }

    sessionStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
    router.push("/check/questions");
  };

  const inputClass = (hasError: boolean) =>
    `w-full border rounded-lg px-4 py-3 text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-navy ${
      hasError ? "border-red-400" : "border-gray-300"
    }`;

  return (
    <main className="flex-1 px-4 py-10">
      <div className="max-w-xl mx-auto">
        <h1 className="text-2xl font-bold text-navy mb-2">Flow Check</h1>
        <p className="text-gray-700 mb-8">
          はじめに、あなたについて教えてください。
        </p>
        <form onSubmit={handleSubmit} noValidate className="space-y-6">
          <div>
            <label htmlFor="name" className="block font-medium mb-1">
              お名前 <span className="text-red-500">*</span>
            </label>
            <input
              id="name"
              type="text"
              value={profile.name}
              onChange={(e) => update("name", e.target.value)}
              className={inputClass(!!errors.name)}
            />
            {errors.name && (
              <p className="text-sm text-red-500 mt-1">{errors.name}</p>
            )}
          </div>

          <div>
            <label htmlFor="company_name" className="block font-medium mb-1">
              会社名・法人名 <span className="text-red-500">*</span>
            </label>
            <input
              id="company_name"
              type="text"
              value={profile.company_name}
              onChange={(e) => update("company_name", e.target.value)}
              className={inputClass(!!errors.company_name)}
            />
            {errors.company_name && (
              <p className="text-sm text-red-500 mt-1">
                {errors.company_name}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="position" className="block font-medium mb-1">
              役職 <span className="text-red-500">*</span>
            </label>
            <input
              id="position"
              type="text"
              value={profile.position}
              onChange={(e) => update("position", e.target.value)}
              className={inputClass(!!errors.position)}
            />
            {errors.position && (
              <p className="text-sm text-red-500 mt-1">{errors.position}</p>
            )}
          </div>

          <div>
            <label htmlFor="industry" className="block font-medium mb-1">
              業種 <span className="text-red-500">*</span>
            </label>
            <select
              id="industry"
              value={profile.industry}
              onChange={(e) => update("industry", e.target.value)}
              className={inputClass(!!errors.industry)}
            >
              <option value="">選択してください</option>
              {INDUSTRY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            {errors.industry && (
              <p className="text-sm text-red-500 mt-1">{errors.industry}</p>
            )}
          </div>

          <div>
            <label htmlFor="employee_count" className="block font-medium mb-1">
              従業員数 <span className="text-red-500">*</span>
            </label>
            <select
              id="employee_count"
              value={profile.employee_count}
              onChange={(e) => update("employee_count", e.target.value)}
              className={inputClass(!!errors.employee_count)}
            >
              <option value="">選択してください</option>
              {EMPLOYEE_COUNT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            {errors.employee_count && (
              <p className="text-sm text-red-500 mt-1">
                {errors.employee_count}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="email" className="block font-medium mb-1">
              メールアドレス <span className="text-red-500">*</span>
            </label>
            <input
              id="email"
              type="email"
              value={profile.email}
              onChange={(e) => update("email", e.target.value)}
              className={inputClass(!!errors.email)}
            />
            {errors.email && (
              <p className="text-sm text-red-500 mt-1">{errors.email}</p>
            )}
          </div>

          <div>
            <label htmlFor="phone" className="block font-medium mb-1">
              電話番号 <span className="text-gray-400 text-sm">（任意）</span>
            </label>
            <input
              id="phone"
              type="tel"
              value={profile.phone}
              onChange={(e) => update("phone", e.target.value)}
              className={inputClass(false)}
            />
          </div>

          <div>
            <label htmlFor="lead_source" className="block font-medium mb-1">
              この診断を知ったきっかけ{" "}
              <span className="text-red-500">*</span>
            </label>
            <select
              id="lead_source"
              value={profile.lead_source}
              onChange={(e) => update("lead_source", e.target.value)}
              className={inputClass(!!errors.lead_source)}
            >
              <option value="">選択してください</option>
              {LEAD_SOURCE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            {errors.lead_source && (
              <p className="text-sm text-red-500 mt-1">{errors.lead_source}</p>
            )}
          </div>

          <button
            type="submit"
            className="w-full bg-navy hover:bg-navy-dark text-white font-bold text-lg py-4 rounded-lg transition-colors"
          >
            次へ
          </button>
        </form>
      </div>
    </main>
  );
}

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // PDF生成(@react-pdf/renderer)はNode専用のためバンドルせず外部依存として扱う
  serverExternalPackages: ["@react-pdf/renderer"],
  // PDFで使う日本語フォントをサーバーレス関数のバンドルに含める(Vercel対応)
  outputFileTracingIncludes: {
    "/api/admin/report/[session_id]": ["./assets/fonts/*"],
  },
};

export default nextConfig;

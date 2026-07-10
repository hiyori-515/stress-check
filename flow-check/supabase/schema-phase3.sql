-- Flow Check フェーズ3 スキーマ変更（schema-phase2.sql 実行後に実行してください）

-- 経営者向けコメント（PDFレポートに掲載する文章）
ALTER TABLE final_assessment ADD COLUMN client_facing_comment TEXT;

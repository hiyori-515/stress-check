-- Flow Check フェーズ1 スキーマ
-- SupabaseダッシュボードのSQLエディタで実行してください。

-- 回答者
CREATE TABLE respondents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  company_name TEXT NOT NULL,
  position TEXT NOT NULL,
  industry TEXT NOT NULL,
  employee_count TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  lead_source TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 診断セッション
CREATE TABLE diagnostic_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  respondent_id UUID REFERENCES respondents(id) NOT NULL,
  status TEXT DEFAULT '未面談',
  question_version INTEGER DEFAULT 1,
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

-- 個別回答
CREATE TABLE answers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES diagnostic_sessions(id) NOT NULL,
  question_no INTEGER NOT NULL CHECK (question_no BETWEEN 1 AND 25),
  category TEXT NOT NULL CHECK (category IN ('judgment', 'execution', 'honesty', 'roles', 'delegation')),
  score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 4)
);

-- カテゴリ別集計
CREATE TABLE category_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES diagnostic_sessions(id) NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('judgment', 'execution', 'honesty', 'roles', 'delegation')),
  total_score INTEGER NOT NULL,
  level TEXT NOT NULL CHECK (level IN ('低', '中', '高'))
);

-- RLS (Row Level Security)
ALTER TABLE respondents ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnostic_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_scores ENABLE ROW LEVEL SECURITY;

-- 診断フォームからの送信を許可（認証なし）
CREATE POLICY "Allow anonymous insert" ON respondents FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous insert" ON diagnostic_sessions FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous insert" ON answers FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous insert" ON category_scores FOR INSERT WITH CHECK (true);

-- 管理画面からの読み取りを許可（認証済みのみ）
CREATE POLICY "Allow authenticated select" ON respondents FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated select" ON diagnostic_sessions FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated select" ON answers FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated select" ON category_scores FOR SELECT USING (auth.role() = 'authenticated');

-- 管理画面からの更新を許可（認証済みのみ）
CREATE POLICY "Allow authenticated update" ON diagnostic_sessions FOR UPDATE USING (auth.role() = 'authenticated');

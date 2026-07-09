-- Flow Check フェーズ2 スキーマ（フェーズ1の schema.sql 実行後に実行してください）

-- AI仮説レポート
CREATE TABLE ai_hypothesis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES diagnostic_sessions(id) NOT NULL UNIQUE,
  summary TEXT,
  category_trends TEXT,
  hypotheses JSONB,
  interview_questions JSONB,
  first_steps JSONB,
  raw_response TEXT,
  generated_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE ai_hypothesis ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow authenticated select" ON ai_hypothesis FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Allow service insert" ON ai_hypothesis FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow service update" ON ai_hypothesis FOR UPDATE USING (true);

-- 面談メモ
CREATE TABLE interview_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES diagnostic_sessions(id) NOT NULL,
  note_text TEXT NOT NULL,
  interview_date DATE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE interview_notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow authenticated all" ON interview_notes FOR ALL USING (auth.role() = 'authenticated');

-- 最終見立て
CREATE TABLE final_assessment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES diagnostic_sessions(id) NOT NULL UNIQUE,
  internal_structure_notes TEXT,
  confirmed_flow_areas JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE final_assessment ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow authenticated all" ON final_assessment FOR ALL USING (auth.role() = 'authenticated');

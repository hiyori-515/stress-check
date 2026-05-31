"""
個人結果の素点換算（1〜5点評価）
厚労省「数値基準に基づいて高ストレス者を選定する方法」準拠

サンプルレポートの表示形式：
  評価点 1点（ストレス状況が良くない）〜 5点（ストレス状況が良い）
"""

# ============================================================
# 素点換算テーブル
# formula: 回答辞書 → 素点（合計）
# table: [(min, max, 評価点), ...] 高得点=良い方向に統一
# ============================================================

def _lookup(raw_score, table):
    for lo, hi, pt in table:
        if lo <= raw_score <= hi:
            return pt
    # 範囲外は端点を返す
    return table[0][2] if raw_score < table[0][0] else table[-1][2]


# A領域：仕事のストレス要因（q1〜q17）
SCALE_CONV = {
    # 負荷系：高得点=高ストレス → 評価点を反転
    "仕事の量的負担": {
        "items": [1,2,3],
        "formula": lambda r: 15 - (r.get(1,2)+r.get(2,2)+r.get(3,2)),
        "table": [(3,5,5),(6,7,4),(8,9,3),(10,11,2),(12,12,1)],
        "domain": "A",
    },
    "仕事の質的負担": {
        "items": [4,5,6],
        "formula": lambda r: 15 - (r.get(4,2)+r.get(5,2)+r.get(6,2)),
        "table": [(3,5,5),(6,7,4),(8,9,3),(10,11,2),(12,12,1)],
        "domain": "A",
    },
    "身体的負担度": {
        "items": [7],
        "formula": lambda r: 5 - r.get(7,2),
        "table": [(1,1,4),(2,2,3),(3,3,2),(4,4,1)],
        "domain": "A",
    },
    "職場での対人関係": {
        "items": [12,13,14],
        "formula": lambda r: 10 - r.get(12,2) - r.get(13,2) + r.get(14,2),
        "table": [(3,3,5),(4,5,4),(6,7,3),(8,9,2),(10,12,1)],
        "domain": "A",
    },
    "職場環境": {
        "items": [15],
        "formula": lambda r: 5 - r.get(15,2),
        "table": [(1,1,4),(2,2,3),(3,3,2),(4,4,1)],
        "domain": "A",
    },
    # 資源系：高得点=良い
    "仕事のコントロール": {
        "items": [8,9,10],
        "formula": lambda r: r.get(8,2)+r.get(9,2)+r.get(10,2) - 3,
        "table": [(0,1,1),(2,3,2),(4,5,3),(6,7,4),(8,9,5)],
        "domain": "A",
    },
    "技能の活用": {
        "items": [11],
        "formula": lambda r: r.get(11,2),
        "table": [(1,1,1),(2,2,2),(3,3,3),(4,4,4)],
        "domain": "A",
    },
    "仕事の適性": {
        "items": [16],
        "formula": lambda r: r.get(16,2),
        "table": [(1,1,1),(2,2,2),(3,3,3),(4,4,4)],
        "domain": "A",
    },
    "働きがい": {
        "items": [17],
        "formula": lambda r: r.get(17,2),
        "table": [(1,1,1),(2,2,2),(3,3,3),(4,4,4)],
        "domain": "A",
    },
    # B領域：ストレス反応（q18〜q46）
    "活気": {
        "items": [18,19,20],
        "formula": lambda r: r.get(18,2)+r.get(19,2)+r.get(20,2),
        "table": [(3,3,1),(4,5,2),(6,7,3),(8,9,4),(10,12,5)],
        "domain": "B",
    },
    "イライラ感": {
        "items": [21,22,23],
        "formula": lambda r: 15 - (r.get(21,2)+r.get(22,2)+r.get(23,2)),
        "table": [(3,5,5),(6,7,4),(8,9,3),(10,11,2),(12,12,1)],
        "domain": "B",
    },
    "疲労感": {
        "items": [24,25,26],
        "formula": lambda r: 15 - (r.get(24,2)+r.get(25,2)+r.get(26,2)),
        "table": [(3,4,5),(5,7,4),(8,10,3),(11,11,2),(12,12,1)],
        "domain": "B",
    },
    "不安感": {
        "items": [27,28,29],
        "formula": lambda r: 15 - (r.get(27,2)+r.get(28,2)+r.get(29,2)),
        "table": [(3,4,5),(5,7,4),(8,9,3),(10,11,2),(12,12,1)],
        "domain": "B",
    },
    "抑うつ感": {
        "items": [30,31,32,33,34,35],
        "formula": lambda r: 30 - sum(r.get(i,2) for i in range(30,36)),
        "table": [(6,9,5),(10,13,4),(14,19,3),(20,23,2),(24,24,1)],
        "domain": "B",
    },
    "身体愁訴": {
        "items": list(range(36,47)),
        "formula": lambda r: 55 - sum(r.get(i,2) for i in range(36,47)),
        "table": [(11,18,5),(19,25,4),(26,33,3),(34,38,2),(39,44,1)],
        "domain": "B",
    },
    # C領域：周囲のサポート（q47〜q55）
    "上司の支援": {
        "items": [47,50,53],
        "formula": lambda r: r.get(47,2)+r.get(50,2)+r.get(53,2),
        "table": [(3,4,1),(5,6,2),(7,8,3),(9,10,4),(11,12,5)],
        "domain": "C",
    },
    "同僚の支援": {
        "items": [48,51,54],
        "formula": lambda r: r.get(48,2)+r.get(51,2)+r.get(54,2),
        "table": [(3,5,1),(6,7,2),(8,9,3),(10,11,4),(12,12,5)],
        "domain": "C",
    },
    "家族・友人の支援": {
        "items": [49,52,55],
        "formula": lambda r: r.get(49,2)+r.get(52,2)+r.get(55,2),
        "table": [(3,6,1),(7,8,2),(9,9,3),(10,11,4),(12,12,5)],
        "domain": "C",
    },
    # D：満足度
    "満足度": {
        "items": [56,57],
        "formula": lambda r: r.get(56,2)+r.get(57,2),
        "table": [(2,3,1),(4,5,2),(6,6,3),(7,7,4),(8,8,5)],
        "domain": "D",
    },
}

# 表示順序
DISPLAY_ORDER_A = [
    "仕事の量的負担", "仕事の質的負担", "身体的負担度",
    "職場での対人関係", "職場環境", "仕事のコントロール",
    "技能の活用", "仕事の適性", "働きがい",
]
DISPLAY_ORDER_B = [
    "活気", "イライラ感", "疲労感",
    "不安感", "抑うつ感", "身体愁訴",
]
DISPLAY_ORDER_CD = [
    "上司の支援", "同僚の支援", "家族・友人の支援", "満足度",
]

# レーダーチャートラベル（短縮）
RADAR_LABELS = {
    "A": {
        "仕事の量的負担": "仕事量（量）",
        "仕事の質的負担": "仕事量（質）",
        "身体的負担度":   "身体負担",
        "職場での対人関係": "対人関係",
        "職場環境":       "職場環境",
        "仕事のコントロール": "コントロール",
        "技能の活用":     "技能活用",
        "仕事の適性":     "適性度",
        "働きがい":       "働き甲斐",
    },
    "B": {
        "活気":     "活気",
        "イライラ感": "イライラ感",
        "疲労感":   "疲労感",
        "不安感":   "不安感",
        "抑うつ感": "抑うつ感",
        "身体愁訴": "身体愁訴",
    },
    "CD": {
        "上司の支援":       "上司から\nのサポート",
        "同僚の支援":       "同僚から\nのサポート",
        "家族・友人の支援": "家族友人\nのサポート",
        "満足度":           "満足度",
    },
}

RADAR_LABELS_EN = {
    "A": {
        "仕事の量的負担": "W.load\n(qty)",
        "仕事の質的負担": "W.load\n(qual)",
        "身体的負担度":   "Physical",
        "職場での対人関係": "Interpers.",
        "職場環境":       "Environ.",
        "仕事のコントロール": "Control",
        "技能の活用":     "Skills",
        "仕事の適性":     "Suitab.",
        "働きがい":       "Meaning",
    },
    "B": {
        "活気":     "Vigor",
        "イライラ感": "Irritab.",
        "疲労感":   "Fatigue",
        "不安感":   "Anxiety",
        "抑うつ感": "Depress.",
        "身体愁訴": "Somatic",
    },
    "CD": {
        "上司の支援":       "Superv.\nsupport",
        "同僚の支援":       "Cowork.\nsupport",
        "家族・友人の支援": "Family/\nfriend",
        "満足度":           "Satisf.",
    },
}

def get_radar_labels(lang: str = "ja") -> dict:
    """言語に応じたレーダーチャートラベルを返す"""
    if lang == "en":
        return RADAR_LABELS_EN
    return RADAR_LABELS

# 逆転尺度（低得点=高ストレス）の表示注記
REVERSED_SCALES = {
    "仕事の量的負担", "仕事の質的負担", "身体的負担度",
    "職場での対人関係", "職場環境",
    "イライラ感", "疲労感", "不安感", "抑うつ感", "身体愁訴",
}


def calc_individual_5pt(responses: dict, lang: str = "ja") -> dict:
    """
    個人の回答から素点換算5段階評価を計算する

    Returns
    -------
    dict
        {
          "scale_points": {尺度名: 評価点(1〜5)},
          "domain_totals": {"A": int, "B": int, "C": int},
          "grand_total": int,
          "high_stress": bool,
          "overall_grade": "A" or "B" or "C",  # 全国基準
          "auto_comment": str,
        }
    """
    scale_points = {}
    for name, cfg in SCALE_CONV.items():
        raw = cfg["formula"](responses)
        pt  = _lookup(raw, cfg["table"])
        scale_points[name] = pt

    # 領域合計（A:9尺度, B:6尺度, C:3尺度）
    A_total = sum(scale_points[s] for s in DISPLAY_ORDER_A)
    B_total = sum(scale_points[s] for s in DISPLAY_ORDER_B)
    C_total = sum(scale_points[s] for s in DISPLAY_ORDER_CD[:3])  # 満足度除く
    grand   = A_total + B_total + C_total

    # 総合評価（全国基準）
    # 高ストレス判定は既実装のraw_B/raw_AC基準を使う
    # ここでは簡易版：B合計（6尺度×5点=30点満点）で判定
    if B_total <= 12:         # 6項目×2点以下 = 高ストレス
        overall_grade = "A"
    elif B_total <= 17:
        overall_grade = "B"
    else:
        overall_grade = "C"

    high_stress = (overall_grade == "A")

    # 自動コメント生成
    comment = _gen_comment(scale_points, overall_grade, lang=lang)

    return {
        "scale_points":  scale_points,
        "domain_totals": {"A": A_total, "B": B_total, "C": C_total},
        "grand_total":   grand,
        "high_stress":   high_stress,
        "overall_grade": overall_grade,
        "auto_comment":  comment,
    }


def _gen_comment(pts: dict, grade: str, lang: str = "ja") -> str:
    """尺度得点から自動コメント文を生成"""
    lines = []

    if lang == "en":
        if grade == "A":
            lines.append("Your overall stress level appears to be high. There are particularly high scores in both stress responses and stressors.")
        elif grade == "B":
            lines.append("Your stress level tends to be somewhat elevated.")
        else:
            lines.append("No particular issues were found in this stress check.")
        bad = [n for n, p in pts.items() if p <= 2 and n != "満足度"]
        if bad:
            SCALE_EN_MAP = {
                "仕事の量的負担":"Quantitative overload","仕事の質的負担":"Qualitative overload",
                "身体的負担度":"Physical demands","職場での対人関係":"Interpersonal conflict",
                "職場環境":"Job environment","仕事のコントロール":"Job control",
                "技能の活用":"Skill utilization","仕事の適性":"Job suitability",
                "働きがい":"Meaningfulness","活気":"Vigor","イライラ感":"Irritability",
                "疲労感":"Fatigue","不安感":"Anxiety","抑うつ感":"Depressed mood",
                "身体愁訴":"Somatic complaints","上司の支援":"Supervisor support",
                "同僚の支援":"Coworker support","家族・友人の支援":"Family/friend support",
                "情緒的負担":"Emotional demands","役割葛藤":"Role conflict",
                "役割明確さ":"Role clarity","成長の機会":"Growth opportunities",
                "経営層との信頼関係":"Trust in management",
                "上司のリーダーシップ":"Supervisor leadership",
                "ワーク・エンゲイジメント":"Work engagement",
                "職場の一体感":"Social capital","職場のハラスメント":"Harassment",
            }
            bad_en = [SCALE_EN_MAP.get(n, n) for n in bad[:4]]
            lines.append(f"Particular attention is needed for: {', '.join(bad_en)}.")
        good = [n for n, p in pts.items() if p >= 4]
        if good:
            good_en = [SCALE_EN_MAP.get(n, n) for n in good[:3]] if bad else [n for n in good[:3]]
            lines.append(f"The following are in good condition: {', '.join(good_en)}.")
    else:
        if grade == "A":
            lines.append("あなたのストレスの状況は全体に高めであるようです。"
                         "ストレス反応とストレスの原因となる因子の両方に特に高い項目がありました。")
        elif grade == "B":
            lines.append("あなたのストレスの状況はやや高めの傾向があります。")
        else:
            lines.append("今回のストレスチェックでは、特に問題は見つかりませんでした。")
        bad = [n for n, p in pts.items() if p <= 2 and n != "満足度"]
        if bad:
            lines.append(f"特に「{'・'.join(bad[:4])}」の状況が良くない傾向があります。")
        good = [n for n, p in pts.items() if p >= 4]
        if good:
            lines.append(f"「{'・'.join(good[:3])}」については良好な状態です。")

    return "\n".join(lines)


if __name__ == "__main__":
    import random, sys
    random.seed(99)
    sys.path.insert(0, "/home/claude/stress_check_system")
    from config.scoring_rules import ALL_ITEMS

    # ダミー回答で動作確認
    responses = {q: random.randint(1,4) for q in ALL_ITEMS}
    result = calc_individual_5pt(responses)

    print("=== 個人素点換算テスト ===")
    print(f"総合評価: {result['overall_grade']}")
    print(f"高ストレス: {result['high_stress']}")
    print(f"領域合計: A={result['domain_totals']['A']} B={result['domain_totals']['B']} C={result['domain_totals']['C']}")
    print(f"合計: {result['grand_total']}")
    print("\n尺度別評価点:")
    for name, pt in result["scale_points"].items():
        bar = "■" * pt + "□" * (5-pt)
        print(f"  {name:15s}: {pt}点 [{bar}]")
    print(f"\nコメント: {result['auto_comment']}")

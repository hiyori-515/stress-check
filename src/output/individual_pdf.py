"""
ストレスチェック 個人結果PDF生成モジュール（サンプル形式準拠版）
Phase 2 revised

ページ構成：
  1ページ目：総合評価・ストレス度合い・ストレスプロフィール（文章）
  2ページ目：3領域レーダーチャート＋項目別評価点一覧
"""

import io, json, math, os, sys
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, PageBreak, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm

BASE_DIR = Path(__file__).resolve().parent.parent.parent
I18N_DIR = BASE_DIR / "src" / "i18n"
sys.path.insert(0, str(BASE_DIR))

from src.scoring.individual_score import (
    calc_individual_5pt, DISPLAY_ORDER_A, DISPLAY_ORDER_B,
    DISPLAY_ORDER_CD, RADAR_LABELS, REVERSED_SCALES, SCALE_CONV,
    get_radar_labels
)

# ============================================================
# フォント
# ============================================================
FONT_JA   = "IPAGothic"
FONT_BOLD = "IPAGothic"
FONT_VIET = "DejaVu"
LANG_FONT = {"ja": FONT_JA, "en": FONT_JA, "zh_cn": "WQY", "vi": FONT_VIET}

_fonts_initialized = False
def _init_fonts():
    global _fonts_initialized
    if _fonts_initialized:
        return
    pdfmetrics.registerFont(TTFont(FONT_JA,   "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"))
    pdfmetrics.registerFont(TTFont(FONT_VIET, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("WQY",     "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", subfontIndex=0))
    _fonts_initialized = True

# ============================================================
# i18n
# ============================================================
_i18n_cache = {}
def _load_i18n(lang):
    if lang not in _i18n_cache:
        path = I18N_DIR / f"{lang}.json"
        if not path.exists(): path = I18N_DIR / "ja.json"
        with open(path, encoding="utf-8") as f:
            _i18n_cache[lang] = json.load(f)
    return _i18n_cache[lang]

# ============================================================
# カラー
# ============================================================
C_PRIMARY    = colors.HexColor("#1a3a5c")
C_ACCENT     = colors.HexColor("#2e86ab")
C_HIGH       = colors.HexColor("#c0392b")
C_SAFE       = colors.HexColor("#27ae60")
C_WARN       = colors.HexColor("#e67e22")
C_LIGHT_GRAY = colors.HexColor("#f5f5f5")
C_MID_GRAY   = colors.HexColor("#bdc3c7")
C_TEXT       = colors.HexColor("#2c3e50")
C_YELLOW     = colors.HexColor("#fffde7")
C_HEADER     = colors.HexColor("#d5e8f0")

def _S(font):
    return {
        "title":   ParagraphStyle("t",  fontName=font, fontSize=14, textColor=C_PRIMARY, leading=20, spaceAfter=2),
        "h2":      ParagraphStyle("h2", fontName=font, fontSize=10, textColor=colors.white, leading=14),
        "h2b":     ParagraphStyle("h2b",fontName=font, fontSize=10, textColor=C_PRIMARY, leading=14, spaceBefore=10, spaceAfter=3),
        "body":    ParagraphStyle("b",  fontName=font, fontSize=8.5,textColor=C_TEXT,    leading=13, spaceAfter=2),
        "small":   ParagraphStyle("s",  fontName=font, fontSize=7.5,textColor=colors.grey,leading=11),
        "grade":   ParagraphStyle("g",  fontName=font, fontSize=28, textColor=C_PRIMARY, leading=36),
        "big":     ParagraphStyle("bg", fontName=font, fontSize=22, textColor=C_HIGH,    leading=28),
        "meta":    ParagraphStyle("m",  fontName=font, fontSize=8,  textColor=C_TEXT,    leading=12),
        "comment": ParagraphStyle("c",  fontName=font, fontSize=8.5,textColor=C_TEXT,    leading=14, spaceAfter=4),
    }

# ============================================================
# matplotlib → Image
# ============================================================
def _fig2img(fig, w_mm=80):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    from PIL import Image as PILImg
    pil = PILImg.open(buf); ratio = pil.height / pil.width
    buf.seek(0)
    w = w_mm * mm
    return Image(buf, width=w, height=w * ratio)

# ============================================================
# スケールバー（横のバー）
# ============================================================
def _scale_bar(score, min_s, max_s, font, width=60*mm, height=5*mm):
    """得点のスケールバーをTableで描画"""
    pct = (score - min_s) / (max_s - min_s)
    bar_w = int(pct * 20)  # 20段階
    empty_w = 20 - bar_w
    bar_txt = "■" * bar_w + "□" * empty_w
    return bar_txt

# ============================================================
# レーダーチャート（5段階）
# ============================================================
def _radar(scale_pts_dict, labels_dict, title, font, w=3.5, h=3.5):
    """reportlab描画によるレーダーチャート（切れ防止）"""
    from reportlab.graphics.shapes import Drawing, Polygon, Line, String, Circle, Rect
    from reportlab.graphics.shapes import Group

    names  = list(labels_dict.keys())
    labels = list(labels_dict.values())
    values = [max(1.0, min(5.0, float(scale_pts_dict.get(n, 1)))) for n in names]
    n      = len(names)

    W, H   = w * 72, h * 72  # inch→pt
    cx, cy = W / 2, H / 2
    r_max  = min(W, H) / 2 - 32  # ラベル用マージン32pt

    drawing = Drawing(W, H)

    # タイトルは外部セクションヘッダーで表示するので省略
    # （チャート内に入れるとラベルと重なる）

    # グリッド（1〜5）
    for lv in range(1, 6):
        r = r_max * (lv - 1) / 4
        pts = []
        for i in range(n):
            a = math.pi/2 + 2*math.pi*i/n
            pts += [cx + r*math.cos(a), cy + r*math.sin(a)]
        pts += [pts[0], pts[1]]
        if lv < 5:
            drawing.add(Polygon(pts, strokeColor=colors.HexColor("#dddddd"),
                                strokeWidth=0.5, fillColor=None))
        else:
            drawing.add(Polygon(pts, strokeColor=colors.HexColor("#cccccc"),
                                strokeWidth=0.8, fillColor=None))

    # 軸線
    for i in range(n):
        a = math.pi/2 + 2*math.pi*i/n
        drawing.add(Line(cx, cy,
            cx + r_max*math.cos(a), cy + r_max*math.sin(a),
            strokeColor=colors.HexColor("#cccccc"), strokeWidth=0.5))

    # データポリゴン
    data_pts = []
    for i, v in enumerate(values):
        r = r_max * (v - 1) / 4
        a = math.pi/2 + 2*math.pi*i/n
        data_pts += [cx + r*math.cos(a), cy + r*math.sin(a)]
    data_pts += [data_pts[0], data_pts[1]]
    drawing.add(Polygon(data_pts,
        strokeColor=colors.HexColor("#2e86ab"), strokeWidth=1.5,
        fillColor=colors.HexColor("#2e86ab"), fillOpacity=0.25))

    # 頂点マーカー
    for i, v in enumerate(values):
        r = r_max * (v - 1) / 4
        a = math.pi/2 + 2*math.pi*i/n
        px = cx + r*math.cos(a)
        py = cy + r*math.sin(a)
        drawing.add(Circle(px, py, 2.5,
            fillColor=colors.HexColor("#2e86ab"),
            strokeColor=colors.white, strokeWidth=0.5))

    # ラベル（外周）
    for i, lbl in enumerate(labels):
        a  = math.pi/2 + 2*math.pi*i/n
        cos_a = math.cos(a)
        sin_a = math.sin(a)
        # 右側ラベルのオフセットを小さくして表への食い込みを防ぐ
        label_offset = 10 if cos_a > 0.3 else 14
        lx = cx + (r_max + label_offset) * cos_a
        ly = cy + (r_max + label_offset) * sin_a
        anchor = "middle"
        if cos_a > 0.3:  anchor = "start"
        elif cos_a < -0.3: anchor = "end"
        # split by newline
        parts = lbl.split("\n")
        line_h = 8
        start_y = ly + (len(parts)-1)*line_h/2
        for j, part in enumerate(parts):
            drawing.add(String(lx, start_y - j*line_h, part,
                fontName=font, fontSize=6.5,
                textAnchor=anchor,
                fillColor=colors.HexColor("#2c3e50")))

    # スコール数値（1/5）
    r0 = r_max * 0 / 4
    r4 = r_max * 4 / 4
    drawing.add(String(cx - 4, cy - r0 - 2, "1",
        fontName=font, fontSize=5.5, textAnchor="end",
        fillColor=colors.grey))
    drawing.add(String(cx - 4, cy - r4 - 2, "5",
        fontName=font, fontSize=5.5, textAnchor="end",
        fillColor=colors.grey))

    return drawing

# ============================================================
# 総合評価ボックス
# ============================================================
def _grade_table(grade, stars, comment_short, font, W, t=None):
    """サンプルの「A★★」ボックス - Drawing使用でA★★を1行に"""
    from reportlab.graphics.shapes import Drawing, String, Rect as GRect
    if t is None: t = {}

    box_w = 45 * mm
    box_h = 18 * mm

    d = Drawing(box_w, box_h)
    d.add(GRect(0, 0, box_w, box_h,
        fillColor=colors.HexColor("#f0f4f8"),
        strokeColor=C_MID_GRAY, strokeWidth=0.5))
    # ラベル（y=0が下なのでbox_hから引く）
    grade_label = t.get("grade_label","ストレスチェック\n総合評価")
    label_lines = grade_label.split("\n")
    for i, line in enumerate(label_lines):
        d.add(String(5, box_h - 12 - i*10, line,
            fontName=font, fontSize=7, fillColor=C_TEXT))
    # A と ★★ を同じベースライン（y=8）で横並び
    d.add(String(22, 8, grade,
        fontName=font, fontSize=22, fillColor=C_PRIMARY))
    d.add(String(35, 8, stars,
        fontName=font, fontSize=13, fillColor=C_PRIMARY))

    comment_cell = Paragraph(comment_short, ParagraphStyle(
        "c", fontName=font, fontSize=8, textColor=C_TEXT, leading=13))
    tbl = Table(
        [[d, comment_cell]],
        colWidths=[box_w + 2*mm, W - box_w - 4*mm]
    )
    tbl.setStyle(TableStyle([
        ("FONTNAME",     (0,0),(-1,-1), font),
        ("BACKGROUND",   (1,0),(1,0),   C_YELLOW),
        ("BOX",          (1,0),(1,0),   0.5, C_MID_GRAY),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
    ]))
    return tbl

# ============================================================
# ストレス度合いテーブル（サンプルp1中段）
# ============================================================
def _stress_score_table(domain_totals, font, W, t=None, lang="ja"):
    if t is None: t = {}
    pt_suffix = "pts" if lang == "en" else "点"
    min_label  = "min" if lang == "en" else "最小"
    max_label  = "max" if lang == "en" else "最大"
    DOMAIN_INFO = {
        "A": (t.get("domain_A_label","ストレスの原因と考えられる因子"), 9, 43),
        "B": (t.get("domain_B_label","ストレスによっておこる心身の反応"), 6, 30),
        "C": (t.get("domain_CD_label","周囲のサポート"), 3, 15),
    }
    grand = sum(domain_totals.values())
    rows = []
    rows.append([
        Paragraph(t.get("table_col_scale","項目"),
                  ParagraphStyle("h",fontName=font,fontSize=8,textColor=colors.white,leading=12)),
        Paragraph(t.get("table_col_score","評価点\n(合計)"),
                  ParagraphStyle("h",fontName=font,fontSize=8,textColor=colors.white,leading=12)),
        Paragraph(t.get("high_low_bar","高いストレス　←─────────→　低いストレス"),
                  ParagraphStyle("h",fontName=font,fontSize=7,textColor=colors.white,leading=12)),
    ])
    for dom, (label, mn, mx) in DOMAIN_INFO.items():
        score = domain_totals.get(dom, mn)
        pct = (score - mn) / (mx - mn)
        bar_filled = int(pct * 30)
        rows.append([
            Paragraph(label, ParagraphStyle("b",fontName=font,fontSize=8,leading=12)),
            Paragraph(f"{score}{pt_suffix}", ParagraphStyle("sc",fontName=font,fontSize=14,
                       textColor=C_HIGH,leading=18)),
            Paragraph(f"{min_label}\n{mn}{pt_suffix}" + " " * bar_filled + f" {max_label}\n{mx}{pt_suffix}",
                      ParagraphStyle("bar",fontName=font,fontSize=7,leading=11)),
        ])
    rows.append([
        Paragraph(t.get("total_label","合計"),
                  ParagraphStyle("b",fontName=font,fontSize=8,leading=12)),
        Paragraph(f"{grand}{pt_suffix}", ParagraphStyle("sc",fontName=font,fontSize=16,
                   textColor=C_HIGH,leading=20)),
        Paragraph(f"{min_label}\n18{pt_suffix}                                                     {max_label}\n88{pt_suffix}",
                  ParagraphStyle("bar",fontName=font,fontSize=7,leading=11)),
    ])
    tbl = Table(rows, colWidths=[65*mm, 22*mm, W-87*mm])
    tbl.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(-1,-1), font),
        ("BACKGROUND",    (0,0),(-1,0),  C_PRIMARY),
        ("BACKGROUND",    (0,1),(-1,-2), colors.white),
        ("BACKGROUND",    (0,-1),(-1,-1),C_LIGHT_GRAY),
        ("ROWBACKGROUNDS",(0,1),(-1,-2), [colors.white, C_LIGHT_GRAY]),
        ("GRID",          (0,0),(-1,-1), 0.3, C_MID_GRAY),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
    ]))
    return tbl

# ============================================================
# 項目別評価点テーブル（2ページ目）
# ============================================================
def _item_table(scale_pts, order, domain_label, font, W, t=None, scale_name_map=None):
    if t is None: t = {}
    if scale_name_map is None: scale_name_map = {}
    pt_suffix = "pts" if t.get("font") == "IPAGothic" and t.get("confidential","").startswith("[") else "点"
    # 言語判定
    is_en = t.get("title","").startswith("Stress")
    pt_suffix = "pts" if is_en else "点"

    header = [
        Paragraph("　", ParagraphStyle("h",fontName=font,fontSize=8,textColor=colors.white)),
        Paragraph(t.get("table_col_scale","項目"),
                  ParagraphStyle("h",fontName=font,fontSize=8,textColor=colors.white,leading=12)),
        Paragraph(t.get("table_col_score","評価点"),
                  ParagraphStyle("h",fontName=font,fontSize=8,textColor=colors.white,leading=12)),
    ]
    rows = [header]

    for i, name in enumerate(order, 1):
        pt   = scale_pts.get(name, 3)
        star = "＊" if name in REVERSED_SCALES else ""
        # 英語尺度名があれば使用
        display_name = scale_name_map.get(name, name)
        if pt <= 2:
            pt_color = C_HIGH
        elif pt <= 3:
            pt_color = C_WARN
        else:
            pt_color = C_SAFE

        rows.append([
            Paragraph(f"{i}", ParagraphStyle("n",fontName=font,fontSize=7.5,
                       textColor=C_TEXT,leading=12)),
            Paragraph(f"{display_name}{star}", ParagraphStyle("n",fontName=font,fontSize=8,
                       textColor=C_TEXT,leading=12)),
            Paragraph(f"{pt}{pt_suffix}", ParagraphStyle("pt",fontName=font,fontSize=11,
                       textColor=pt_color,leading=14)),
        ])

    cw = [8*mm, W*0.62, 18*mm]
    tbl = Table(rows, colWidths=cw)
    tbl.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(-1,-1), font),
        ("BACKGROUND",    (0,0),(-1,0),  C_ACCENT),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, C_LIGHT_GRAY]),
        ("GRID",          (0,0),(-1,-1), 0.3, C_MID_GRAY),
        ("ALIGN",         (2,0),(2,-1),  "CENTER"),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    return tbl

# ============================================================
# メイン生成関数
# ============================================================
def generate_individual_pdf(
    employee_hash, score_result, comparison,
    meta, output_path,
    lang="ja", company_name="", impl_date="",
    # 素点換算結果（渡される場合）
    score_5pt=None,
):
    _init_fonts()
    t    = _load_i18n(lang)
    font = LANG_FONT.get(lang, FONT_JA)
    S    = _S(font)
    matplotlib.rcParams["font.family"] = "IPAGothic"

    # 素点換算
    if score_5pt is None:
        responses = score_result.get("_raw_responses", {})
        score_5pt = calc_individual_5pt(responses, lang=lang) if responses else None
    elif lang != "ja" and score_5pt is not None:
        # 渡されたscore_5ptのauto_commentを現在のlangで再生成
        from src.scoring.individual_score import _gen_comment
        score_5pt = dict(score_5pt)
        score_5pt["auto_comment"] = _gen_comment(
            score_5pt["scale_points"], score_5pt["overall_grade"], lang=lang
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        topMargin=12*mm, bottomMargin=12*mm,
        leftMargin=16*mm, rightMargin=16*mm)
    story = []
    W = A4[0] - 32*mm

    # ── ページ1 ─────────────────────────────────────────
    # ヘッダー
    story.append(Paragraph(t.get("confidential","【個人情報・厳秘】"), S["small"]))
    story.append(Paragraph(t.get("title","ストレスチェック結果通知"), S["title"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_PRIMARY))
    story.append(Spacer(1, 5))

    # メタ情報
    meta_rows = [[
        t.get("company_label","事業場名"), company_name or "-",
        t.get("date_label","実施年月日"), impl_date or "-"
    ],[
        t.get("department_label","所属"), meta.get("department","-"), "", ""
    ]]
    mt = Table(meta_rows, colWidths=[25*mm, 65*mm, 28*mm, 45*mm])
    mt.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),font),("FONTSIZE",(0,0),(-1,-1),8),
        ("TEXTCOLOR",(0,0),(0,-1),C_PRIMARY),("TEXTCOLOR",(2,0),(2,-1),C_PRIMARY),
        ("BACKGROUND",(0,0),(-1,-1),C_LIGHT_GRAY),
        ("GRID",(0,0),(-1,-1),0.3,C_MID_GRAY),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),5),
    ]))
    story += [mt, Spacer(1, 8)]

    # 総合評価ボックス
    if score_5pt:
        grade = score_5pt["overall_grade"]
        hs    = score_5pt["high_stress"]
        stars = "★★" if hs else ""
        short = score_5pt["auto_comment"].split("\n")[0]
        story.append(Paragraph(t.get("section_overall","■ ストレスチェック 総合評価"), S["h2b"]))
        story.append(_grade_table(grade, stars, short, font, W, t=t))
        story.append(Spacer(1, 8))

        # ストレス度合い
        story.append(Paragraph(t.get("stress_score_title","■ あなたのストレス度合い"), S["h2b"]))
        story.append(_stress_score_table(score_5pt["domain_totals"], font, W, t=t, lang=lang))
        story.append(Spacer(1, 8))

        # ストレスプロフィール（文章）
        story.append(Paragraph(t.get("stress_profile_title","■ あなたのストレスプロフィール"), S["h2b"]))
        profile_box = Table(
            [[Paragraph(score_5pt["auto_comment"], S["comment"])]],
            colWidths=[W]
        )
        profile_box.setStyle(TableStyle([
            ("BOX",(0,0),(-1,-1),0.5,C_MID_GRAY),
            ("BACKGROUND",(0,0),(-1,-1),C_YELLOW),
            ("TOPPADDING",(0,0),(-1,-1),8),
            ("BOTTOMPADDING",(0,0),(-1,-1),8),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story.append(profile_box)
    else:
        high = score_result.get("high_stress", False)
        msg  = t.get("high_stress_positive" if high else "high_stress_negative","")
        story.append(Paragraph(msg, S["body"]))

    # メタ（実施情報）フッター
    story.append(Spacer(1, 8))
    footer_rows = [
        [t.get("impl_workplace_label","ストレスチェック実施事業場"), company_name or "-"],
        [t.get("impl_implementer_label","ストレスチェック実施者"),   ""],
        [t.get("impl_period_label","ストレスチェック実施期間"),       impl_date or "-"],
    ]
    ft = Table(footer_rows, colWidths=[55*mm, W-55*mm])
    ft.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),font),("FONTSIZE",(0,0),(-1,-1),8),
        ("TEXTCOLOR",(0,0),(0,-1),C_PRIMARY),
        ("BOX",(0,0),(-1,-1),0.5,C_MID_GRAY),
        ("INNERGRID",(0,0),(-1,-1),0.3,C_MID_GRAY),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(ft)
    story.append(Spacer(1, 4))
    story.append(Paragraph(t.get("footer_note","※ この結果は本人に直接通知されるものです。"), S["small"]))

    # ── ページ2 ─────────────────────────────────────────
    story.append(PageBreak())

    if score_5pt:
        sp = score_5pt["scale_points"]

        # 3つのレーダーチャートを横並び
        story.append(Paragraph(t.get("stress_radar_title","■ ストレスレーダー"), S["h2b"]))
        story.append(Paragraph(t.get("radar_note","評価点：1点（ストレス状況が良くない）〜5点（ストレス状況が良い）"), S["small"]))
        story.append(Spacer(1, 4))

        # レーダー＋表を縦に3段（サンプル形式）
        story.append(Paragraph(t.get("radar_star_note","＊が付いた項目の状況が良くない場合コメントに記載されます。"), S["small"]))
        story.append(Spacer(1, 4))

        # 言語に応じてセクションタイトルを切り替え
        radar_labels = get_radar_labels(lang)
        sections = [
            (DISPLAY_ORDER_A,  radar_labels["A"],
             t.get("section_A","ストレスの原因と考えられる因子"),
             t.get("domain_A_label","ストレスの原因と考えられる因子")),
            (DISPLAY_ORDER_B,  radar_labels["B"],
             t.get("section_B","ストレスによっておこる心身の反応"),
             t.get("domain_B_label","ストレスによっておこる心身の反応")),
            (DISPLAY_ORDER_CD, radar_labels["CD"],
             t.get("section_CD","ストレス反応に影響を与える他の因子"),
             t.get("domain_CD_label","ストレス反応に影響を与える他の因子")),
        ]
        for order, rlabels, section_header, section_title in sections:
            radar_w = 62 * mm
            radar_h = 62 * mm
            fig = _radar({k: sp.get(k,1) for k in order}, rlabels, section_title, font,
                         w=radar_w/72, h=radar_h/72)
            # 英語の場合は尺度名マップを渡す
            scale_name_map = {}
            if lang == "en":
                from src.scoring.individual_score import RADAR_LABELS_EN
                for domain_labels in RADAR_LABELS_EN.values():
                    for ja_name, en_label in domain_labels.items():
                        scale_name_map[ja_name] = en_label.replace("\n", " ")
            tbl = _item_table(sp, order, section_title[0], font, W*0.52, t=t, scale_name_map=scale_name_map)
            sec_tbl = Table(
                [[fig, tbl]],
                colWidths=[radar_w + 2*mm, W - radar_w - 4*mm]
            )
            sec_tbl.setStyle(TableStyle([
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("GRID",(0,0),(-1,-1),0,colors.white),
                ("LEFTPADDING",(0,0),(-1,-1),2),
                ("TOPPADDING",(0,0),(-1,-1),0),
            ]))
            story.append(Paragraph(section_header,
                ParagraphStyle("sh", fontName=font, fontSize=9,
                               textColor=C_ACCENT, leading=13, spaceBefore=8, spaceAfter=3)))
            story.append(sec_tbl)
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_MID_GRAY))
    story.append(Spacer(1, 3))
    story.append(Paragraph(t.get("footer_note","※ この結果は本人に直接通知されるものです。"), S["small"]))

    doc.build(story)
    buf.seek(0)
    with open(output_path, "wb") as f:
        f.write(buf.read())
    return output_path


def generate_all_individual_pdfs(individual_results, output_base,
                                  languages=None, company_name="", impl_date=""):
    if languages is None:
        languages = ["ja", "en", "zh_cn", "vi"]
    generated = {}
    for record in individual_results:
        emp  = record["employee_hash"]
        lang = record.get("meta",{}).get("response_language","ja")
        if lang not in languages: lang = "ja"
        targets = list(set(["ja", lang]))
        generated[emp] = {}
        for lg in targets:
            out_dir = Path(output_base) / emp
            out_dir.mkdir(parents=True, exist_ok=True)
            out = str(out_dir / f"result_{lg}.pdf")
            generate_individual_pdf(
                employee_hash=emp,
                score_result=record["score_result"],
                comparison=record.get("comparison",{}),
                meta=record.get("meta",{}),
                output_path=out, lang=lg,
                company_name=company_name, impl_date=impl_date,
                score_5pt=record.get("score_5pt"),
            )
            generated[emp][lg] = out
    return generated


# ============================================================
# 動作確認
# ============================================================
if __name__ == "__main__":
    import random, sys
    random.seed(42)
    sys.path.insert(0, str(BASE_DIR))
    from config.scoring_rules import ALL_ITEMS
    from src.scoring.calculator import StressCheckScorer

    responses = {q: random.randint(1,4) for q in ALL_ITEMS}
    # 高ストレスになるよう調整
    for q in [18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35]:
        responses[q] = 1  # B領域を最悪値に

    scorer = StressCheckScorer(version="120")
    result = scorer.calculate(responses)
    result["_raw_responses"] = responses
    comp   = scorer.compare_to_national(
        {k:v for k,v in result["scale_scores"].items() if v is not None})
    s5pt   = calc_individual_5pt(responses)
    meta   = {"department": "開発部", "response_language": "ja"}

    print("PDF生成テスト（サンプル形式）...")
    for lang in ["ja", "en", "zh_cn", "vi"]:
        out = f"/tmp/new_result_{lang}.pdf"
        generate_individual_pdf(
            employee_hash="test001", score_result=result,
            comparison=comp, meta=meta, output_path=out,
            lang=lang,
            company_name="株式会社テスト" if lang in ["ja","zh_cn"] else "Test Corp.",
            impl_date="2025-10-15", score_5pt=s5pt,
        )
        print(f"  [{lang}] {out} ({os.path.getsize(out):,} bytes) ✅")
    print("完了")

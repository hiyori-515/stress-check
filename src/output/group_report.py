"""
ストレスチェック 集団分析レポートPDF
Phase 3 revised – ページ別ビルダー構成

ページ構成:
  P1: 集団名・人数(男女別) + 3指標総評 + 職場改善アドバイス
  P2: 総合健康リスク詳細 + 判定図2種          [stub → 後工程]
  P3: 80項目版追加指標(WE/一体感/ハラスメント) [stub → 後工程]
  P4-5: 尺度偏差値比較表 + 横棒グラフ          [stub → 後工程]
  P6-7: 5段階積み上げ横棒グラフ               [stub → 後工程]
  P8: ポートフォリオ4象限マトリクス            [stub → 後工程]
"""

import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, PageBreak,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from config.scoring_rules import NATIONAL_AVERAGES
from src.scoring.health_risk import calc_health_risk, calc_group_health_risk

# ============================================================
# フォント設定
# ============================================================
FONT_JA = "JapaneseFont"

_FONT_CANDIDATES = [
    "/Library/Fonts/Arial Unicode.ttf",                    # macOS
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",   # Linux (IPA)
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf", # Linux (alt)
]

_fonts_initialized = False

def _init_fonts():
    global _fonts_initialized
    if _fonts_initialized:
        return
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            kw = {"subfontIndex": 0} if path.endswith(".ttc") else {}
            pdfmetrics.registerFont(TTFont(FONT_JA, path, **kw))
            _fonts_initialized = True
            return
    raise FileNotFoundError(f"日本語フォントが見つかりません。候補: {_FONT_CANDIDATES}")


def _mpl():
    """matplotlib の日本語フォントを設定"""
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in ["Hiragino Sans", "Hiragino Kaku Gothic ProN",
                 "Arial Unicode MS", "IPAGothic"]:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            break
    else:
        matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["axes.unicode_minus"] = False


# ============================================================
# カラーパレット
# ============================================================
C_PRIMARY    = colors.HexColor("#1a3a5c")
C_ACCENT     = colors.HexColor("#2e86ab")
C_HIGH       = colors.HexColor("#c0392b")
C_SAFE       = colors.HexColor("#27ae60")
C_WARN       = colors.HexColor("#e67e22")
C_LIGHT_GRAY = colors.HexColor("#f5f5f5")
C_MID_GRAY   = colors.HexColor("#bdc3c7")
C_TEXT       = colors.HexColor("#2c3e50")
C_YELLOW     = colors.HexColor("#fff9c4")
C_HEADER     = colors.HexColor("#d0e8f5")

# matplotlib 用
MC_GOOD    = "#27ae60"
MC_WARN    = "#e67e22"
MC_BAD     = "#c0392b"
MC_NA      = "#95a5a6"
MC_PRIMARY = "#1a3a5c"
MC_GRAY    = "#7f8c8d"
MC_LGRAY   = "#bdc3c7"


# ============================================================
# スタイル
# ============================================================
def _S(font):
    return {
        "title":   ParagraphStyle("t",   fontName=font, fontSize=14, textColor=C_PRIMARY,
                                  leading=20, spaceAfter=2),
        "h2":      ParagraphStyle("h2",  fontName=font, fontSize=9,  textColor=C_PRIMARY,
                                  leading=13, spaceBefore=6, spaceAfter=3),
        "body":    ParagraphStyle("b",   fontName=font, fontSize=8,  textColor=C_TEXT,
                                  leading=12, spaceAfter=2),
        "small":   ParagraphStyle("s",   fontName=font, fontSize=7,  textColor=colors.grey,
                                  leading=10),
        "warn":    ParagraphStyle("w",   fontName=font, fontSize=8,  textColor=C_HIGH,
                                  leading=12),
        "advice":  ParagraphStyle("a",   fontName=font, fontSize=8.5, textColor=C_TEXT,
                                  leading=14, spaceAfter=4),
        "section": ParagraphStyle("sec", fontName=font, fontSize=9,  textColor=colors.white,
                                  leading=14, backColor=C_PRIMARY,
                                  leftIndent=6, rightIndent=6),
        "section2": ParagraphStyle("sc2", fontName=font, fontSize=9, textColor=colors.white,
                                   leading=13, backColor=C_ACCENT, leftIndent=4),
    }


def _section_bar(text, font, style="primary"):
    """セクション見出しバー（青帯）"""
    back = C_PRIMARY if style == "primary" else C_ACCENT
    return Paragraph(
        text,
        ParagraphStyle("sb", fontName=font, fontSize=9, textColor=colors.white,
                       leading=14, backColor=back, leftIndent=6, rightIndent=6,
                       spaceBefore=0, spaceAfter=0),
    )


# ============================================================
# 共通ユーティリティ
# ============================================================
def _fig2img(fig, w_mm=80):
    """matplotlib Figure → reportlab Image"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    from PIL import Image as PILImg
    pil = PILImg.open(buf)
    ratio = pil.height / pil.width
    buf.seek(0)
    return Image(buf, width=w_mm * mm, height=w_mm * mm * ratio)


def _to_deviation(score, mean, sd):
    """偏差値(T-score)に変換: 全国平均=50、SD=10"""
    return 50.0 + 10.0 * (score - mean) / max(sd, 0.01)


def _eval_level(val, t_good, t_bad, lower_better=True):
    """
    評価レベルを返す: 'good' / 'warn' / 'bad' / 'na'
    lower_better=True  → val<t_good: good, val<t_bad: warn, それ以上: bad
    lower_better=False → val>t_good: good, val>t_bad: warn, それ以下: bad
    """
    if val is None:
        return "na"
    if lower_better:
        if val < t_good:
            return "good"
        elif val < t_bad:
            return "warn"
        else:
            return "bad"
    else:
        if val >= t_good:
            return "good"
        elif val >= t_bad:
            return "warn"
        else:
            return "bad"


_LEVEL_COLOR = {"good": MC_GOOD, "warn": MC_WARN, "bad": MC_BAD, "na": MC_NA}
_LEVEL_ICON  = {"good": "◎ 良好", "warn": "△ 注意", "bad": "▼ 警戒", "na": "— 不明"}


def _eval_deviation(dev):
    """
    偏差値から4段階評価を返す（高スコア=良い前提）
      ◎ 良好  : dev >= 55
      — 普通  : 45 <= dev < 55
      △ 注意  : 40 <= dev < 45
      ▼ 警戒  : dev < 40
    """
    if dev is None:
        return "na"
    if dev >= 55:
        return "good"
    if dev >= 45:
        return "neutral"
    if dev >= 40:
        return "warn"
    return "bad"


_DEV_COLOR = {
    "good":    MC_GOOD,
    "neutral": "#7f8c8d",
    "warn":    MC_WARN,
    "bad":     MC_BAD,
    "na":      MC_NA,
}
_DEV_ICON = {
    "good":    "◎ 良好",
    "neutral": "— 普通",
    "warn":    "△ 注意",
    "bad":     "▼ 警戒",
    "na":      "— データなし",
}


# ============================================================
# P1 チャート: KPI 3指標カード
# ============================================================
def _kpi_cards_chart(ctx):
    """
    3指標（高ストレス者割合 / 総合健康リスク / 回収率）の
    評価アイコン + 大きな数値 + 3者比較バーを横並びで描画
    """
    _mpl()

    hs_rate        = ctx["hs_rate"]
    total_risk     = ctx["total_risk"]
    collection_rate = ctx.get("collection_rate")       # None = 不明
    company_hs     = ctx.get("company_hs_rate", 21.1)
    company_risk   = ctx.get("company_risk",    100.0)
    company_col    = ctx.get("company_collection", 70.0)

    # 業界・全国デフォルト
    IND_HS   = 21.1   # 厚労省調査: 全国平均高ストレス者割合
    IND_RISK = 100    # 定義上の全国平均
    IND_COL  = 70.0   # 業界平均回収率(仮)

    kpis = [
        {
            "title":        "高ストレス者割合",
            "group_val":    hs_rate,
            "company_val":  company_hs,
            "industry_val": IND_HS,
            "unit":         "%",
            "lower_better": True,
            "t_good":       10.0,   # <10% → 良好
            "t_bad":        25.0,   # >25% → 警戒
            "bar_max":      max(40.0, (hs_rate or 0) * 1.6 + 5),
            "note":         "全国平均 21.1%",
        },
        {
            "title":        "総合健康リスク",
            "group_val":    total_risk,
            "company_val":  company_risk,
            "industry_val": IND_RISK,
            "unit":         "",
            "lower_better": True,
            "t_good":       100,    # <100 → 良好
            "t_bad":        120,    # >120 → 警戒
            "bar_max":      max(160, int((total_risk or 100) * 1.4)),
            "note":         "全国平均 100（基準値）",
        },
        {
            "title":        "回収率",
            "group_val":    collection_rate,
            "company_val":  company_col,
            "industry_val": IND_COL,
            "unit":         "%",
            "lower_better": False,
            "t_good":       80.0,   # >80% → 良好
            "t_bad":        60.0,   # <60% → 警戒
            "bar_max":      100.0,
            "note":         "業界平均 70%",
        },
    ]

    bar_labels  = ["本集団", "全体",  "業界平均"]
    bar_mcolors = [MC_PRIMARY, MC_GRAY, MC_LGRAY]

    fig, axes = plt.subplots(1, 3, figsize=(11, 4.0))
    fig.patch.set_facecolor("white")

    for ax, kpi in zip(axes, kpis):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        gv = kpi["group_val"]
        level = _eval_level(gv, kpi["t_good"], kpi["t_bad"], kpi["lower_better"])
        c     = _LEVEL_COLOR[level]
        icon  = _LEVEL_ICON[level]

        # ── カード背景・枠 ─────────────────────────────
        bg = mpatches.FancyBboxPatch(
            (0.03, 0.03), 0.94, 0.94,
            boxstyle="round,pad=0.02",
            facecolor="#f8f9fa", edgecolor="#dee2e6", linewidth=1.2,
        )
        ax.add_patch(bg)

        # タイトル
        ax.text(0.5, 0.93, kpi["title"],
                ha="center", va="top", fontsize=9,
                color=MC_PRIMARY, fontweight="bold")

        # アイコン（評価レベル）
        ax.text(0.5, 0.80, icon,
                ha="center", va="center", fontsize=9.5, color=c, fontweight="bold")

        # 大きな数値
        val_str = f"{gv:.1f}{kpi['unit']}" if gv is not None else "—"
        ax.text(0.5, 0.64, val_str,
                ha="center", va="center", fontsize=22, color=c, fontweight="bold")

        # 区切り線
        ax.plot([0.07, 0.93], [0.54, 0.54], color="#dee2e6", linewidth=0.8)

        # ── 3者比較バー ────────────────────────────────
        vals   = [kpi["group_val"], kpi["company_val"], kpi["industry_val"]]
        bar_max = kpi["bar_max"]
        ys     = [0.44, 0.32, 0.20]

        for label, v, y, bc in zip(bar_labels, vals, ys, bar_mcolors):
            # ラベル
            ax.text(0.06, y, label,
                    ha="left", va="center", fontsize=6.5, color="#555")
            if v is None:
                ax.text(0.45, y, "—",
                        ha="center", va="center", fontsize=7, color=MC_NA)
                continue
            bar_w = min(v / bar_max, 1.0) * 0.52
            # バー（x: 0.06〜0.58 の範囲で描画）
            ax.barh(y, bar_w, height=0.08, left=0.43,
                    color=bc, alpha=0.85, clip_on=False)
            ax.text(0.43 + bar_w + 0.02, y,
                    f"{v:.1f}{kpi['unit']}",
                    ha="left", va="center", fontsize=7,
                    color=bc, fontweight="bold")

        # 注記
        ax.text(0.5, 0.07, kpi["note"],
                ha="center", va="bottom", fontsize=6.5, color="#888", style="italic")

        # カラー枠（上書き）
        border = mpatches.FancyBboxPatch(
            (0.03, 0.03), 0.94, 0.94,
            boxstyle="round,pad=0.02",
            facecolor="none", edgecolor=c, linewidth=2.0,
        )
        ax.add_patch(border)

    plt.tight_layout(pad=0.4)
    return fig


# ============================================================
# P3 チャート: WE / 一体感 / ハラスメント ゲージカード
# ============================================================
_P3_METRICS = [
    {
        "title":       "ワーク・エンゲイジメント",
        "key":         "ワーク・エンゲイジメント",
        "description": "活力・熱意・没頭度",
        "note":        "高いほど仕事への前向きな姿勢",
    },
    {
        "title":       "職場の一体感",
        "key":         "職場の一体感",
        "description": "ソーシャルキャピタル",
        "note":        "相互理解・協力・情報共有の程度",
    },
    {
        "title":       "職場のハラスメント",
        "key":         "職場のハラスメント",
        "description": "ハラスメントの少なさ",
        "note":        "高いほどハラスメントが少ない良好な状態",
    },
]

# 偏差値バーの表示範囲
_DEV_BAR_MIN, _DEV_BAR_MAX = 35.0, 65.0


def _engagement_gauge_chart(ctx):
    """
    P3: ワークエンゲイジメント/職場の一体感/ハラスメントの
    偏差値ゲージカード（本集団/全体/業界平均の比較バー付き）
    """
    _mpl()

    group_scores   = ctx["group_scores"]
    company_scores = ctx["company_scores"]
    industry_scores = ctx.get("industry_scores", {})

    bar_labels  = ["本集団", "全体",  "業界平均"]
    bar_mcolors = [MC_PRIMARY, MC_GRAY, MC_LGRAY]

    fig, axes = plt.subplots(1, 3, figsize=(11, 4.8))
    fig.patch.set_facecolor("white")

    for ax, metric in zip(axes, _P3_METRICS):
        key = metric["key"]
        nat = NATIONAL_AVERAGES.get(key)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # ── カード背景 ──────────────────────────────────
        bg = mpatches.FancyBboxPatch(
            (0.03, 0.03), 0.94, 0.94,
            boxstyle="round,pad=0.02",
            facecolor="#f8f9fa", edgecolor="#dee2e6", linewidth=1.2,
        )
        ax.add_patch(bg)

        if nat is None:
            ax.text(0.5, 0.5, "データなし", ha="center", va="center",
                    fontsize=10, color=MC_NA)
            continue

        g_score = group_scores.get(key)
        c_score = company_scores.get(key)
        i_score = industry_scores.get(key)

        g_dev = _to_deviation(g_score, nat["mean"], nat["sd"]) if g_score else None
        c_dev = _to_deviation(c_score, nat["mean"], nat["sd"]) if c_score else None
        i_dev = _to_deviation(i_score, nat["mean"], nat["sd"]) if i_score else None

        level = _eval_deviation(g_dev)
        c     = _DEV_COLOR[level]
        icon  = _DEV_ICON[level]

        # ── タイトル・説明 ───────────────────────────────
        ax.text(0.5, 0.93, metric["title"],
                ha="center", va="top", fontsize=9,
                color=MC_PRIMARY, fontweight="bold")
        ax.text(0.5, 0.84, f"（{metric['description']}）",
                ha="center", va="top", fontsize=6.5, color="#777")

        # ── 評価アイコン ─────────────────────────────────
        ax.text(0.5, 0.74, icon,
                ha="center", va="center", fontsize=9.5,
                color=c, fontweight="bold")

        # ── 大きな偏差値 ─────────────────────────────────
        val_str = f"{g_dev:.1f}" if g_dev is not None else "—"
        ax.text(0.5, 0.60, val_str,
                ha="center", va="center", fontsize=24, color=c, fontweight="bold")
        ax.text(0.5, 0.50, "偏差値（全国平均=50）",
                ha="center", va="center", fontsize=6.5, color="#888")

        # ── セパレータ ───────────────────────────────────
        ax.plot([0.07, 0.93], [0.46, 0.46], color="#dee2e6", linewidth=0.8)

        # ── 比較バー ─────────────────────────────────────
        devs = [g_dev, c_dev, i_dev]
        ys   = [0.38, 0.27, 0.16]
        BAR_L = 0.42   # バー左端のx座標
        BAR_W = 0.50   # バー最大幅

        for label, dev, y, bc in zip(bar_labels, devs, ys, bar_mcolors):
            ax.text(0.06, y, label,
                    ha="left", va="center", fontsize=6.5, color="#555")
            if dev is None:
                ax.text(BAR_L + BAR_W * 0.5, y, "—",
                        ha="center", va="center", fontsize=7, color=MC_NA)
                continue
            # バー幅: DEV_BAR_MIN〜DEV_BAR_MAX を BAR_W にマッピング
            frac = max(0.0, min(1.0,
                       (dev - _DEV_BAR_MIN) / (_DEV_BAR_MAX - _DEV_BAR_MIN)))
            bw = frac * BAR_W
            ax.barh(y, bw, height=0.08, left=BAR_L,
                    color=bc, alpha=0.85, clip_on=False)
            ax.text(BAR_L + bw + 0.02, y, f"{dev:.1f}",
                    ha="left", va="center", fontsize=7,
                    color=bc, fontweight="bold")

        # 全国平均基準線（偏差値50）
        ref_x = BAR_L + (50.0 - _DEV_BAR_MIN) / (_DEV_BAR_MAX - _DEV_BAR_MIN) * BAR_W
        ax.plot([ref_x, ref_x], [0.11, 0.44],
                color="#95a5a6", linewidth=1.0, linestyle="--", alpha=0.8)
        ax.text(ref_x, 0.09, "50", ha="center", va="top",
                fontsize=6, color="#95a5a6")

        # 注記
        ax.text(0.5, 0.04, metric["note"],
                ha="center", va="bottom", fontsize=6, color="#999", style="italic")

        # ── カラー枠（上書き）───────────────────────────
        border = mpatches.FancyBboxPatch(
            (0.03, 0.03), 0.94, 0.94,
            boxstyle="round,pad=0.02",
            facecolor="none", edgecolor=c, linewidth=2.0,
        )
        ax.add_patch(border)

    plt.tight_layout(pad=0.4)
    return fig


# ============================================================
# P3 ページビルダー
# ============================================================
_P3_EXPLANATIONS = [
    ("ワーク・エンゲイジメント",
     "仕事に対して「活力」「熱意」「没頭」を感じている状態の総合指標です。"
     "高いほど仕事への前向きな姿勢が強く、組織の生産性・定着率との正の相関が知られています。"),
    ("職場の一体感",
     "職場内でともに働こうという姿勢・相互理解・情報共有が行われている程度を示します"
     "（ソーシャルキャピタル）。職場のメンタルヘルスの保護要因として機能します。"),
    ("職場のハラスメント",
     "セクシャルハラスメント・パワーハラスメントを含むいじめの少なさを示します。"
     "スコアが高いほどハラスメントが少なく良好な状態です。"),
]


def _build_page3(ctx):
    """
    P3: 80/120項目版追加指標ページ
      - 80/120項目版: WE / 職場の一体感 / ハラスメントを偏差値で表示
      - 57項目版   : 「このバージョンでは測定対象外」を表示
    """
    font    = ctx["font"]
    S       = ctx["S"]
    W       = ctx["W"]
    version = ctx.get("version", "57")
    story   = []

    story += [
        _section_bar("追加指標（ワークエンゲイジメント・職場環境）", font),
        Spacer(1, 6),
    ]

    if version == "57":
        # ── 57項目版: 測定対象外メッセージ ──────────────
        msg = Table(
            [[Paragraph(
                "このバージョン（57項目版）では測定対象外です。\n\n"
                "80項目版または120項目版を使用すると、以下の指標が追加測定されます：\n"
                "　・ワーク・エンゲイジメント（仕事への活力・熱意・没頭度）\n"
                "　・職場の一体感（ソーシャルキャピタル：協力・相互理解・情報共有）\n"
                "　・職場のハラスメント（セクハラ・パワハラを含むいじめの少なさ）",
                S["body"],
            )]],
            colWidths=[W],
        )
        msg.setStyle(TableStyle([
            ("BOX",           (0, 0), (-1, -1), 0.8, C_MID_GRAY),
            ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT_GRAY),
            ("TOPPADDING",    (0, 0), (-1, -1), 18),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
            ("LEFTPADDING",   (0, 0), (-1, -1), 16),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ]))
        story.append(msg)

    else:
        # ── 80/120項目版: ゲージカード ──────────────────
        story += [
            Paragraph(
                "以下は80項目版・120項目版で測定される追加指標です。"
                "全国平均=50の偏差値で表示しています（◎≥55 / —45〜55 / △40〜45 / ▼<40）。",
                S["body"],
            ),
            Spacer(1, 6),
        ]

        fig = _engagement_gauge_chart(ctx)
        story.append(_fig2img(fig, 165))
        story.append(Spacer(1, 10))

        # ── 指標の説明テーブル ────────────────────────────
        story.append(_section_bar("各指標の説明", font, style="accent"))
        story.append(Spacer(1, 4))

        for name, desc in _P3_EXPLANATIONS:
            row_tbl = Table(
                [[
                    Paragraph(
                        name,
                        ParagraphStyle("en", fontName=font, fontSize=8,
                                       textColor=C_PRIMARY, leading=13),
                    ),
                    Paragraph(
                        desc,
                        ParagraphStyle("ed", fontName=font, fontSize=7.5,
                                       textColor=C_TEXT, leading=12),
                    ),
                ]],
                colWidths=[44*mm, W - 44*mm],
            )
            row_tbl.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 4),
                ("LINEBELOW",     (0, 0), (-1, -1), 0.3, C_MID_GRAY),
            ]))
            story.append(row_tbl)

    story += [
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.5, color=C_MID_GRAY),
        Spacer(1, 3),
        Paragraph("※ 本レポートは集団分析結果であり、個人は特定されていません。", S["small"]),
        PageBreak(),
    ]
    return story


# ============================================================
# P1 ページビルダー
# ============================================================
def _build_page1(ctx):
    """
    P1: 集団名・人数（男女別）+ 今回の総評（3指標）+ 職場改善アドバイス
    ctx キー:
      font, S, W, company_name, group_name, year,
      n_total, n_male, n_female, n_distributed,
      hs_rate, total_risk, collection_rate,
      company_hs_rate, company_risk, company_collection,
      group_scores
    """
    font = ctx["font"]
    S    = ctx["S"]
    W    = ctx["W"]
    story = []

    # ── ヘッダー ─────────────────────────────────────────
    story += [
        Paragraph("【事業者用・厳秘】個人を特定できない形で作成しています", S["small"]),
        Spacer(1, 2),
        Paragraph("ストレスチェック 集団分析レポート", S["title"]),
        HRFlowable(width="100%", thickness=2, color=C_PRIMARY),
        Spacer(1, 5),
    ]

    # ── メタ情報テーブル ──────────────────────────────────
    n_total    = ctx["n_total"]
    n_male     = ctx.get("n_male", 0)
    n_female   = ctx.get("n_female", 0)
    n_other    = max(0, n_total - n_male - n_female)
    n_dist     = ctx.get("n_distributed")
    year       = ctx.get("year")

    parts = [f"男性 {n_male}名", f"女性 {n_female}名"]
    if n_other > 0:
        parts.append(f"その他 {n_other}名")
    gender_str = " / ".join(parts)

    if n_dist:
        col_str = f"{n_total}名 / 配布 {n_dist}名"
    else:
        col_str = f"{n_total}名（配布数不明）"

    today = datetime.now().strftime("%Y年%m月%d日")

    def _cell(txt, bold=False):
        return Paragraph(
            txt,
            ParagraphStyle("mc", fontName=font, fontSize=8,
                           textColor=C_TEXT, leading=12),
        )

    def _label(txt):
        return Paragraph(
            txt,
            ParagraphStyle("ml", fontName=font, fontSize=8,
                           textColor=C_PRIMARY, leading=12),
        )

    meta_rows = [
        [_label("事業場名"), _cell(ctx.get("company_name") or "—"),
         _label("実施年度"), _cell(f"{year}年度" if year else "—")],
        [_label("集団名"),   _cell(ctx.get("group_name", "全体")),
         _label("人数"),     _cell(f"{n_total}名（{gender_str}）")],
        [_label("回答者数"), _cell(col_str),
         _label("作成日"),   _cell(today)],
    ]
    col_w = [22*mm, 62*mm, 22*mm, 59*mm]
    mt = Table(meta_rows, colWidths=col_w)
    mt.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), font),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT_GRAY),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_MID_GRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    if n_total < 10:
        story += [
            mt, Spacer(1, 3),
            Paragraph(
                "※ 集団の人数が10人未満ですので、個人が特定されることがないよう"
                "事業者に渡す際は注意してください。",
                S["warn"],
            ),
        ]
    else:
        story.append(mt)

    story.append(Spacer(1, 8))

    # ── 今回の総評セクション ──────────────────────────────
    story += [
        _section_bar("今回の総評", font, style="primary"),
        Spacer(1, 5),
    ]

    # 3指標の評価基準を凡例として表示
    legend_rows = [[
        Paragraph("◎ 良好", ParagraphStyle("lg", fontName=font, fontSize=7.5,
                                           textColor=colors.HexColor(MC_GOOD))),
        Paragraph("△ 注意", ParagraphStyle("lw", fontName=font, fontSize=7.5,
                                           textColor=colors.HexColor(MC_WARN))),
        Paragraph("▼ 警戒", ParagraphStyle("lb", fontName=font, fontSize=7.5,
                                           textColor=colors.HexColor(MC_BAD))),
        Paragraph("比較基準: 本集団 / 全体 / 業界平均",
                  ParagraphStyle("ln", fontName=font, fontSize=7,
                                 textColor=colors.grey)),
    ]]
    legend_tbl = Table(legend_rows, colWidths=[22*mm, 22*mm, 22*mm, W - 66*mm])
    legend_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(legend_tbl)
    story.append(Spacer(1, 3))

    # KPI カード（matplotlib）
    fig_kpi = _kpi_cards_chart(ctx)
    story.append(_fig2img(fig_kpi, 165))
    story.append(Spacer(1, 8))

    # ── 職場改善アドバイス ────────────────────────────────
    story += [
        _section_bar("職場改善のためのアドバイス", font, style="accent"),
        Spacer(1, 4),
    ]

    advice = _gen_advice(
        ctx["group_scores"], NATIONAL_AVERAGES,
        ctx["total_risk"], ctx["hs_rate"], n_total, font,
    )
    advice_box = Table(
        [[Paragraph(advice, S["advice"])]],
        colWidths=[W],
    )
    advice_box.setStyle(TableStyle([
        ("BOX",            (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("BACKGROUND",     (0, 0), (-1, -1), C_YELLOW),
        ("TOPPADDING",     (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(advice_box)

    story.append(PageBreak())
    return story


# ============================================================
# 既存チャート（P2 で引き続き使用）
# ============================================================
def _judgment_chart(
    group_val_x, group_val_y,
    company_val_x, company_val_y,
    nat_x, nat_y,
    x_label, y_label, title,
    font, w=3.8, h=3.8,
    x_range=(3, 12), y_range=(3, 12),
    zone_type="demand_control",
):
    """
    判定図（散布図）。
    zone_type:
      "demand_control"  : X=量的負担(高=悪), Y=コントロール(高=良)
                          高ストレス域=右下、低ストレス域=左上
      "support_support" : X=上司支援(高=良), Y=同僚支援(高=良)
                          高ストレス域=左下、低ストレス域=右上
    """
    _mpl()
    fig, ax = plt.subplots(figsize=(w, h))

    xmin, xmax = x_range[0] - 0.5, x_range[1] + 0.5
    ymin, ymax = y_range[0] - 0.5, y_range[1] + 0.5

    # ── ストレスゾーン（最背面に描画）──────────────────
    if zone_type == "demand_control":
        # 高ストレス域: 量的負担 高 × コントロール 低 → 右下
        hs_rect = mpatches.Rectangle(
            (nat_x, ymin), xmax - nat_x, nat_y - ymin,
            facecolor="#ffebee", edgecolor="#e57373",
            hatch="////", linewidth=0, alpha=0.45, zorder=0,
        )
        # 低ストレス域: 量的負担 低 × コントロール 高 → 左上
        ls_rect = mpatches.Rectangle(
            (xmin, nat_y), nat_x - xmin, ymax - nat_y,
            facecolor="#e8f5e9", edgecolor="#81c784",
            hatch="\\\\\\\\", linewidth=0, alpha=0.45, zorder=0,
        )
        ax.add_patch(hs_rect)
        ax.add_patch(ls_rect)
        ax.text(xmax - 0.15, ymin + 0.2, "高ストレス域",
                ha="right", va="bottom", fontsize=6.5,
                color="#c0392b", alpha=0.85, zorder=1)
        ax.text(xmin + 0.15, ymax - 0.15, "低ストレス域",
                ha="left", va="top", fontsize=6.5,
                color="#27ae60", alpha=0.85, zorder=1)

    elif zone_type == "support_support":
        # 高ストレス域: 上司支援 低 × 同僚支援 低 → 左下
        hs_rect = mpatches.Rectangle(
            (xmin, ymin), nat_x - xmin, nat_y - ymin,
            facecolor="#ffebee", edgecolor="#e57373",
            hatch="////", linewidth=0, alpha=0.45, zorder=0,
        )
        # 低ストレス域: 上司支援 高 × 同僚支援 高 → 右上
        ls_rect = mpatches.Rectangle(
            (nat_x, nat_y), xmax - nat_x, ymax - nat_y,
            facecolor="#e8f5e9", edgecolor="#81c784",
            hatch="\\\\\\\\", linewidth=0, alpha=0.45, zorder=0,
        )
        ax.add_patch(hs_rect)
        ax.add_patch(ls_rect)
        ax.text(xmin + 0.15, ymin + 0.2, "高ストレス域",
                ha="left", va="bottom", fontsize=6.5,
                color="#c0392b", alpha=0.85, zorder=1)
        ax.text(xmax - 0.15, ymax - 0.15, "低ストレス域",
                ha="right", va="top", fontsize=6.5,
                color="#27ae60", alpha=0.85, zorder=1)

    # ── 全国平均の基準線 ───────────────────────────────
    ax.axvline(nat_x, color="#95a5a6", linewidth=0.8, linestyle="--", alpha=0.7, zorder=2)
    ax.axhline(nat_y, color="#95a5a6", linewidth=0.8, linestyle="--", alpha=0.7, zorder=2)

    # ── プロット ───────────────────────────────────────
    ax.scatter([nat_x], [nat_y], marker="D", s=40, color="#95a5a6",
               zorder=4, label="全国平均")
    if company_val_x and company_val_y:
        ax.scatter([company_val_x], [company_val_y],
                   marker="s", s=55, color="#2c3e50", zorder=5, label="事業者全体")
    ax.scatter([group_val_x], [group_val_y], s=90, color="#c0392b",
               zorder=6, label="本集団")

    ax.set_xlabel(x_label, fontsize=7.5)
    ax.set_ylabel(y_label, fontsize=7.5)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_title(title, fontsize=8.5, color="#1a3a5c", pad=6)
    ax.legend(fontsize=6.5, loc="upper right", framealpha=0.85)
    ax.tick_params(labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    return fig



# ============================================================
# アドバイス文生成
# ============================================================
def _gen_advice(group_scores, nat_avgs, total_risk, hs_rate, n, font):
    lines = []
    if n < 10:
        lines.append(
            "集団の人数が少ないので少数の人の結果に影響され、"
            "実態とは異なる数値が出ている危険があります。結果の取り扱いには十分に注意してください。"
        )
    lines.append(
        f"総合的な健康リスクは {total_risk} となりました。"
        + (
            f"これは全国の平均的な職場に比べてメンタルヘルス疾患の発生確率が"
            f" {total_risk - 100}% 高いことを示します。"
            if total_risk > 100
            else "これは全国の平均的な職場と同程度のリスク水準です。"
        )
    )
    if total_risk > 120:
        lines.append(
            "健康リスクが120を超えている場合は一般に職場に問題があることが多いので、"
            "職場改善に取り組んでください。"
        )
    good, slight_bad, bad = [], [], []
    for s, nat in nat_avgs.items():
        g = group_scores.get(s)
        if g is None:
            continue
        z = (g - nat["mean"]) / (nat["sd"] if nat["sd"] > 0 else 0.5)
        if z > 0.5:
            good.append(s)
        elif z < -1:
            bad.append(s)
        elif z < -0.3:
            slight_bad.append(s)
    if good:
        lines.append(f"「{'」「'.join(good[:3])}」の項目で良好な傾向が表れていましたので続けていきましょう。")
    if slight_bad:
        lines.append(f"「{'」「'.join(slight_bad[:3])}」の項目で不良の傾向が表れていましたので注意が必要です。")
    if bad:
        lines.append(f"「{'」「'.join(bad[:3])}」の項目では特に不良の傾向が表れていたので改善が必要です。")
    lines.append("これを機に職場の環境改善に取り組みましょう。")
    return "\n".join(lines)


# ============================================================
# 尺度リスト（P2 偏差値表で使用）
# ============================================================
SCALES_57_ORDER = [
    "仕事の量的負担", "仕事の質的負担", "身体的負担度", "職場での対人関係",
    "職場環境", "仕事のコントロール", "技能の活用", "仕事の適性", "働きがい",
    "活気", "イライラ感", "疲労感", "不安感", "抑うつ感", "身体愁訴",
    "上司の支援", "同僚の支援", "家族・友人の支援", "仕事の満足度",
]

# 高得点=良い尺度（スコアが低い=ストレス高）
_RESOURCE_SCALES = {
    "仕事のコントロール", "技能の活用", "仕事の適性", "働きがい",
    "活気", "上司の支援", "同僚の支援", "家族・友人の支援", "仕事の満足度",
}


def _deviation_table(group_scores, company_scores, industry_scores, nat_avgs, font, W):
    """
    偏差値比較表（本集団 / 全体 / 業界平均 + 評価アイコン）
    全国平均=50、SD=10 に換算して表示。
    本集団が全国平均を下回る尺度は赤字。
    """

    def _dev(score, nat):
        if score is None or nat is None:
            return None
        return _to_deviation(score, nat["mean"], nat["sd"])

    def _dev_str(d):
        return f"{d:.1f}" if d is not None else "—"

    def _icon(d):
        """偏差値から評価アイコンと色を返す"""
        if d is None:
            return "—", colors.grey
        if d >= 55:
            return "◎", C_SAFE
        if d >= 45:
            return "—", C_TEXT
        if d >= 40:
            return "△", C_WARN
        return "▼", C_HIGH

    # ── ヘッダー行 ──────────────────────────────────────
    def _hdr(txt):
        return Paragraph(txt, ParagraphStyle(
            "dh", fontName=font, fontSize=7, textColor=colors.white, leading=11,
        ))

    header = [_hdr("尺度"), _hdr("本集団"), _hdr("全体"), _hdr("業界平均"), _hdr("評価")]
    rows = [header]

    # ── データ行 ────────────────────────────────────────
    for s in SCALES_57_ORDER:
        nat = nat_avgs.get(s)
        if nat is None:
            continue

        g_dev = _dev(group_scores.get(s), nat)
        c_dev = _dev(company_scores.get(s), nat)
        i_dev = _dev((industry_scores or {}).get(s), nat)

        icon_txt, icon_color = _icon(g_dev)

        # 本集団が全国平均(偏差値50)を下回れば赤字
        g_color = C_HIGH if g_dev is not None and g_dev < 48 else C_TEXT

        def _p(txt, c=C_TEXT, size=8):
            return Paragraph(txt, ParagraphStyle(
                "dv", fontName=font, fontSize=size, textColor=c, leading=11,
            ))

        rows.append([
            _p(s, size=7.5),
            _p(_dev_str(g_dev), c=g_color),
            _p(_dev_str(c_dev)),
            _p(_dev_str(i_dev)),
            _p(icon_txt, c=icon_color),
        ])

    # ── テーブル組み立て ─────────────────────────────────
    col_w = [W * 0.38, W * 0.15, W * 0.15, W * 0.15, W * 0.17]
    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME",       (0, 0), (-1, -1), font),
        ("FONTSIZE",       (0, 0), (-1, -1), 7),
        ("BACKGROUND",     (0, 0), (-1, 0),  C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_LIGHT_GRAY]),
        ("GRID",           (0, 0), (-1, -1), 0.3, C_MID_GRAY),
        ("ALIGN",          (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",     (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 2),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
    ]))
    return tbl


# ============================================================
# P4-P5 定数・ヘルパー・チャート・ページビルダー
# ============================================================

# カテゴリ別尺度リスト（P4）
_P4_CATEGORIES = [
    ("仕事の負担", [
        "仕事の量的負担", "仕事の質的負担", "身体的負担度",
        "情緒的負担", "役割葛藤",
    ]),
    ("作業資源", [
        "仕事のコントロール", "技能の活用", "役割明確さ",
        "仕事の意義", "成長の機会", "仕事の適性",
    ]),
    ("職場環境・対人サポート", [
        "職場での対人関係", "職場環境",
        "上司の支援", "同僚の支援", "家族・友人の支援",
        "上司のリーダーシップ", "上司の公正な態度",
        "ほめてもらえる職場", "失敗を認める職場",
    ]),
]

# カテゴリ別尺度リスト（P5）
_P5_CATEGORIES = [
    ("組織・キャリア・報酬", [
        "経営層との信頼関係", "変化への対応",
        "個人の尊重", "公正な人事評価", "多様な労働者への対応",
        "キャリア形成",
        "経済・地位報酬", "尊重報酬", "安定報酬",
    ]),
    ("ストレス反応", [
        "活気", "イライラ感", "疲労感", "不安感", "抑うつ感", "身体愁訴",
    ]),
    ("満足度・ワーク・ライフ", [
        "仕事の満足度", "家庭の満足度",
        "ワーク・セルフ・バランス(ポジティブ)",
        "ワーク・セルフ・バランス(ネガティブ)",
    ]),
    ("ハラスメント・社会資本・エンゲイジメント", [
        "職場のハラスメント", "職場の一体感", "ワーク・エンゲイジメント",
    ]),
]

# 5段階カラー・ラベル（低い→高い）
_L5_COLORS = ["#c0392b", "#e67e22", "#95a5a6", "#82e0aa", "#27ae60"]
_L5_LABELS = ["低い", "やや低い", "平均的", "やや高い", "高い"]


def _compute_scale_distributions(raw_responses_list, version="120"):
    """
    個人回答データから各尺度の偏差値ベース5段階分布(%)を計算する。
    Returns: {scale_name: [pct_lv1, pct_lv2, pct_lv3, pct_lv4, pct_lv5]}
      lv1=低い(dev<40), lv2=やや低い(40-45), lv3=平均的(45-50),
      lv4=やや高い(50-55), lv5=高い(dev>=55)
    """
    from config.scoring_rules import SCALES, ALL_ITEMS

    if not raw_responses_list:
        return {}

    items_key = "items_standard" if version == "120" else "items_short"
    dists = {}

    for scale_name, scale_def in SCALES.items():
        nat = NATIONAL_AVERAGES.get(scale_name)
        if nat is None:
            continue
        items = scale_def.get(items_key, [])
        if not items:
            continue

        # 回答率が50%未満の個人はスキップ
        min_valid = max(1, (len(items) + 1) // 2)
        counts = [0, 0, 0, 0, 0]
        n_valid = 0

        for responses in raw_responses_list:
            scores = []
            for q in items:
                item_def = ALL_ITEMS.get(q)
                if item_def is None:
                    continue
                val = responses.get(q)
                if val is None:
                    continue
                mapped = item_def["score_map"].get(val)
                if mapped is not None:
                    scores.append(mapped)

            if len(scores) < min_valid:
                continue

            avg = sum(scores) / len(items)
            dev = _to_deviation(avg, nat["mean"], nat["sd"])

            if dev >= 55:
                counts[4] += 1
            elif dev >= 50:
                counts[3] += 1
            elif dev >= 45:
                counts[2] += 1
            elif dev >= 40:
                counts[1] += 1
            else:
                counts[0] += 1
            n_valid += 1

        if n_valid > 0:
            dists[scale_name] = [c / n_valid * 100 for c in counts]
        else:
            dists[scale_name] = [20.0] * 5  # データなし: 均等分布

    return dists


def _shorten_name(name, max_len=13):
    """尺度名を短縮（matplotlib 軸ラベル用）"""
    return name if len(name) <= max_len else name[: max_len - 1] + "…"


def _scale_stacked_chart(scales_data, font):
    """
    5段階積み上げ横棒グラフ（偏差値アノテーション付き）

    scales_data: [(name, g_dev, c_dev, icon_str, [pct1..pct5]), ...]
      - name      : 尺度名
      - g_dev     : 本集団偏差値 (float | None)
      - c_dev     : 全体偏差値   (float | None)
      - icon_str  : 評価アイコン文字列（例 "◎ 良好"）
      - [pct1..5] : 5段階の割合 (合計≒100)
    """
    _mpl()
    n = len(scales_data)
    if n == 0:
        return None

    fig_h = max(1.6, n * 0.52 + 1.1)
    fig, ax = plt.subplots(figsize=(9.5, fig_h))
    fig.patch.set_facecolor("white")

    for i, (name, g_dev, c_dev, icon_str, pcts) in enumerate(scales_data):
        y = n - 1 - i  # 上が先頭

        # ── 積み上げバー ─────────────────────────────────
        left = 0.0
        for pct, color in zip(pcts, _L5_COLORS):
            if pct > 0.3:
                ax.barh(y, pct, height=0.58, left=left,
                        color=color, alpha=0.88,
                        edgecolor="white", linewidth=0.4)
            left += pct

        # ── 右側アノテーション（偏差値・評価） ───────────
        g_str = f"{g_dev:.1f}" if g_dev is not None else "—"
        c_str = f"{c_dev:.1f}" if c_dev is not None else "—"
        g_color = "#c0392b" if g_dev is not None and g_dev < 45 else "#2c3e50"

        icon_ch = icon_str[0] if icon_str else "—"
        icon_clr = {
            "◎": "#27ae60", "△": "#e67e22", "▼": "#c0392b", "—": "#7f8c8d",
        }.get(icon_ch, "#7f8c8d")

        ax.text(102.5, y, g_str, va="center", ha="left",
                fontsize=8, color=g_color, fontweight="bold")
        ax.text(113.5, y, c_str, va="center", ha="left",
                fontsize=7.5, color="#7f8c8d")
        ax.text(124.5, y, icon_ch, va="center", ha="center",
                fontsize=9.5, color=icon_clr, fontweight="bold")

    # ── Y軸: 尺度名 ──────────────────────────────────────
    ax.set_yticks(range(n))
    ax.set_yticklabels(
        [_shorten_name(row[0]) for row in reversed(scales_data)],
        fontsize=7.5,
    )
    ax.tick_params(axis="y", length=0)

    # ── X軸 ─────────────────────────────────────────────
    ax.set_xlim(-2, 130)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=7)

    # 50% 基準線
    ax.axvline(50, color="#95a5a6", linewidth=0.8, linestyle=":", alpha=0.7)

    # アノテーション列ヘッダー
    header_y = n - 0.55
    ax.text(102.5, header_y, "本集団", ha="left", va="center",
            fontsize=7, color="#555")
    ax.text(113.5, header_y, "全体", ha="left", va="center",
            fontsize=7, color="#555")
    ax.text(124.5, header_y, "評価", ha="center", va="center",
            fontsize=7, color="#555")

    # 凡例
    patches = [mpatches.Patch(color=c, label=l, alpha=0.88)
               for c, l in zip(_L5_COLORS, _L5_LABELS)]
    ax.legend(handles=patches, loc="upper center",
              bbox_to_anchor=(0.42, 1.13), ncol=5,
              fontsize=6.5, frameon=False)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.subplots_adjust(left=0.21, right=0.98, top=0.86, bottom=0.12)
    return fig


def _build_page4_5(ctx):
    """
    P4-P5: カテゴリ別 尺度詳細比較ページ
    各カテゴリ: セクションヘッダー + 偏差値付き5段階積み上げ横棒グラフ
    下位30%（偏差値<45）の本集団偏差値は赤字表示。
    """
    font  = ctx["font"]
    S     = ctx["S"]
    group_scores    = ctx["group_scores"]
    company_scores  = ctx["company_scores"]
    dists           = ctx.get("scale_distributions", {})

    def _cat_section(cat_name, cat_scales):
        """1カテゴリ分のストーリー要素を返す"""
        scales_data = []
        for scale_name in cat_scales:
            g_score = group_scores.get(scale_name)
            nat     = NATIONAL_AVERAGES.get(scale_name)
            if nat is None or g_score is None:
                continue
            g_dev  = _to_deviation(g_score, nat["mean"], nat["sd"])
            c_score = company_scores.get(scale_name)
            c_dev  = _to_deviation(c_score, nat["mean"], nat["sd"]) if c_score else None
            level  = _eval_deviation(g_dev)
            icon   = _DEV_ICON.get(level, "—")
            pcts   = dists.get(scale_name, [20.0] * 5)
            scales_data.append((scale_name, g_dev, c_dev, icon, pcts))

        if not scales_data:
            return []

        fig = _scale_stacked_chart(scales_data, font)
        elems = [
            _section_bar(cat_name, font, style="accent"),
            Spacer(1, 3),
        ]
        if fig:
            elems.append(_fig2img(fig, 165))
        elems.append(Spacer(1, 5))
        return elems

    _note_small = Paragraph(
        "　偏差値: 全国平均=50・SD=10。"
        "赤字=偏差値45未満（下位約30%）。"
        "　棒グラフ: 低い/やや低い/平均的/やや高い/高い の回答者割合。",
        S["small"],
    )
    _footer = [
        HRFlowable(width="100%", thickness=0.5, color=C_MID_GRAY),
        Spacer(1, 3),
        Paragraph("※ 本レポートは集団分析結果であり、個人は特定されていません。", S["small"]),
    ]

    story = []

    # ── P4 ───────────────────────────────────────────────
    story += [
        _section_bar("各尺度の詳細比較 P4 ― 仕事の負担・資源・職場環境", font),
        _note_small,
        Spacer(1, 5),
    ]
    for cat_name, cat_scales in _P4_CATEGORIES:
        story += _cat_section(cat_name, cat_scales)
    story += _footer + [PageBreak()]

    # ── P5 ───────────────────────────────────────────────
    story += [
        _section_bar("各尺度の詳細比較 P5 ― 組織・ストレス反応・満足度・社会資本", font),
        _note_small,
        Spacer(1, 5),
    ]
    for cat_name, cat_scales in _P5_CATEGORIES:
        story += _cat_section(cat_name, cat_scales)
    story += _footer + [PageBreak()]

    return story


# ============================================================
# P6 定数・チャート・ページビルダー
# ============================================================

# WEとの相関係数（文献値: 新職業性ストレス簡易調査票研究より）
# 出典: Shimazu et al. 2008, 川上ら 2012 他
_WE_CORRELATIONS = {
    # 仕事の負担（要因系: 負の相関）
    "仕事の量的負担":    -0.22,
    "仕事の質的負担":    -0.16,
    "身体的負担度":      -0.12,
    "情緒的負担":        -0.31,
    "役割葛藤":          -0.37,
    # 作業資源（正の相関）
    "仕事のコントロール": 0.44,
    "技能の活用":         0.42,
    "役割明確さ":         0.39,
    "仕事の意義":         0.63,
    "成長の機会":         0.55,
    "仕事の適性":         0.49,
    # 職場環境・サポート
    "職場での対人関係":   0.34,
    "職場環境":           0.28,
    "上司の支援":         0.38,
    "同僚の支援":         0.31,
    "家族・友人の支援":   0.22,
    "上司のリーダーシップ": 0.50,
    "上司の公正な態度":   0.44,
    "ほめてもらえる職場": 0.48,
    "失敗を認める職場":   0.41,
    # 組織・キャリア・報酬
    "経営層との信頼関係": 0.44,
    "変化への対応":       0.37,
    "個人の尊重":         0.46,
    "公正な人事評価":     0.40,
    "多様な労働者への対応": 0.33,
    "キャリア形成":       0.45,
    "経済・地位報酬":     0.31,
    "尊重報酬":           0.41,
    "安定報酬":           0.27,
    # ストレス反応
    "活気":              0.62,
    "イライラ感":        -0.37,
    "疲労感":            -0.47,
    "不安感":            -0.44,
    "抑うつ感":          -0.52,
    "身体愁訴":          -0.35,
    # 満足度・ワーク・ライフ
    "仕事の満足度":       0.57,
    "家庭の満足度":       0.23,
    "ワーク・セルフ・バランス(ポジティブ)": 0.46,
    "ワーク・セルフ・バランス(ネガティブ)": -0.33,
    # ハラスメント・社会資本（WE自身は除く）
    "職場のハラスメント":  0.43,
    "職場の一体感":        0.55,
}

# カテゴリ別 色と対象尺度
_PORTFOLIO_CATEGORIES = {
    "仕事の負担":      ("#e74c3c", [
        "仕事の量的負担", "仕事の質的負担", "身体的負担度", "情緒的負担", "役割葛藤",
    ]),
    "作業資源":        ("#2980b9", [
        "仕事のコントロール", "技能の活用", "役割明確さ", "仕事の意義", "成長の機会", "仕事の適性",
    ]),
    "職場環境・サポート": ("#27ae60", [
        "職場での対人関係", "職場環境",
        "上司の支援", "同僚の支援", "家族・友人の支援",
        "上司のリーダーシップ", "上司の公正な態度",
        "ほめてもらえる職場", "失敗を認める職場",
    ]),
    "組織・キャリア":  ("#8e44ad", [
        "経営層との信頼関係", "変化への対応", "個人の尊重",
        "公正な人事評価", "多様な労働者への対応", "キャリア形成",
        "経済・地位報酬", "尊重報酬", "安定報酬",
    ]),
    "ストレス反応":    ("#e67e22", [
        "活気", "イライラ感", "疲労感", "不安感", "抑うつ感", "身体愁訴",
    ]),
    "満足度・社会資本": ("#16a085", [
        "仕事の満足度", "家庭の満足度",
        "ワーク・セルフ・バランス(ポジティブ)", "ワーク・セルフ・バランス(ネガティブ)",
        "職場のハラスメント", "職場の一体感",
    ]),
}

# 尺度の短縮名（プロット上のラベル用）
_SCALE_ABBR = {
    "仕事の量的負担": "量的負担", "仕事の質的負担": "質的負担",
    "身体的負担度": "身体負担", "情緒的負担": "情緒負担", "役割葛藤": "役割葛藤",
    "仕事のコントロール": "コントロール", "技能の活用": "技能活用",
    "役割明確さ": "役割明確", "仕事の意義": "仕事意義", "成長の機会": "成長機会",
    "仕事の適性": "適性",
    "職場での対人関係": "対人関係", "職場環境": "職場環境",
    "上司の支援": "上司支援", "同僚の支援": "同僚支援", "家族・友人の支援": "家族支援",
    "上司のリーダーシップ": "上司LS", "上司の公正な態度": "上司公正",
    "ほめてもらえる職場": "ほめ職場", "失敗を認める職場": "失敗容認",
    "経営層との信頼関係": "経営信頼", "変化への対応": "変化対応",
    "個人の尊重": "個人尊重", "公正な人事評価": "人事評価",
    "多様な労働者への対応": "多様対応", "キャリア形成": "キャリア",
    "経済・地位報酬": "経済報酬", "尊重報酬": "尊重報酬", "安定報酬": "安定報酬",
    "活気": "活気", "イライラ感": "イライラ", "疲労感": "疲労",
    "不安感": "不安", "抑うつ感": "抑うつ", "身体愁訴": "身体愁訴",
    "仕事の満足度": "仕事満足", "家庭の満足度": "家庭満足",
    "ワーク・セルフ・バランス(ポジティブ)": "WSB+",
    "ワーク・セルフ・バランス(ネガティブ)": "WSB−",
    "職場のハラスメント": "ハラスメント", "職場の一体感": "一体感",
}


def _portfolio_matrix_chart(ctx):
    """
    P6: WE KPI ポートフォリオ4象限マトリクス
    X軸: 本集団の偏差値（現在の水準）
    Y軸: WEとの相関係数（重要度）
    """
    _mpl()
    group_scores = ctx["group_scores"]

    # 各尺度のX(偏差値)とY(相関)を収集
    points = []
    for scale_name, corr in _WE_CORRELATIONS.items():
        g_score = group_scores.get(scale_name)
        nat = NATIONAL_AVERAGES.get(scale_name)
        if g_score is None or nat is None:
            continue
        g_dev = _to_deviation(g_score, nat["mean"], nat["sd"])
        points.append((scale_name, g_dev, corr))

    if not points:
        return None

    corrs = [p[2] for p in points]
    devs  = [p[1] for p in points]
    corr_median = sorted(corrs)[len(corrs) // 2]
    x_ref = 50.0  # 全国平均

    xmin = min(35.0, min(devs) - 2)
    xmax = max(65.0, max(devs) + 2)
    ymin = min(corrs) - 0.07
    ymax = max(corrs) + 0.07

    fig, ax = plt.subplots(figsize=(10, 7.2))
    fig.patch.set_facecolor("white")

    # ── 象限背景 ─────────────────────────────────────────
    kw = dict(alpha=0.07)
    ax.fill_betweenx([corr_median, ymax], xmin, x_ref,  color="#e74c3c", **kw)  # 左上: 重点改善
    ax.fill_betweenx([corr_median, ymax], x_ref, xmax,  color="#27ae60", **kw)  # 右上: 重点維持
    ax.fill_betweenx([ymin, corr_median], xmin, x_ref,  color="#e67e22", **kw)  # 左下: 改善
    ax.fill_betweenx([ymin, corr_median], x_ref, xmax,  color="#bdc3c7", **kw)  # 右下: 維持

    # ── 基準線 ───────────────────────────────────────────
    lkw = dict(linewidth=1.1, linestyle="--", alpha=0.55, color="#2c3e50")
    ax.axvline(x_ref,       **lkw)
    ax.axhline(corr_median, **lkw)

    # 基準線ラベル
    ax.text(x_ref + 0.3, ymin + 0.01, "偏差値 50\n(全国平均)",
            fontsize=7, color="#555", va="bottom")
    ax.text(xmin + 0.3, corr_median + 0.01, f"相関中央値 {corr_median:.2f}",
            fontsize=7, color="#555", va="bottom")

    # ── 象限タイトル ─────────────────────────────────────
    q_labels = [
        (xmin + 0.4, ymax - 0.01, "重点改善項目 ★", "#c0392b", "left",  "top"),
        (xmax - 0.4, ymax - 0.01, "重点維持項目",    "#27ae60", "right", "top"),
        (xmin + 0.4, ymin + 0.01, "改善項目",        "#e67e22", "left",  "bottom"),
        (xmax - 0.4, ymin + 0.01, "維持項目",        "#7f8c8d", "right", "bottom"),
    ]
    for qx, qy, qlabel, qc, qha, qva in q_labels:
        ax.text(qx, qy, qlabel, fontsize=9.5, color=qc, fontweight="bold",
                ha=qha, va=qva, alpha=0.6)

    # ── カテゴリ別プロット ────────────────────────────────
    for cat_name, (cat_color, cat_scales) in _PORTFOLIO_CATEGORIES.items():
        cat_pts = [(n, x, y) for n, x, y in points if n in cat_scales]
        if not cat_pts:
            continue
        xs = [p[1] for p in cat_pts]
        ys = [p[2] for p in cat_pts]

        ax.scatter(xs, ys, s=70, color=cat_color, alpha=0.88, zorder=5,
                   label=cat_name, edgecolors="white", linewidths=0.6)

        for name, px, py in cat_pts:
            abbr = _SCALE_ABBR.get(name, name[:6])
            # 重点改善象限(左上)は太字・大きめで強調
            is_priority = px < x_ref and py > corr_median
            ax.annotate(
                abbr, (px, py),
                xytext=(4, 3), textcoords="offset points",
                fontsize=6.8 if is_priority else 6.0,
                color=cat_color,
                fontweight="bold" if is_priority else "normal",
                alpha=0.95 if is_priority else 0.80,
            )

    # ── 軸・グリッド ─────────────────────────────────────
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel("本集団の偏差値　（← 水準低い　　　　水準高い →）",
                  fontsize=9, labelpad=6)
    ax.set_ylabel("WE との相関係数　（← 影響小　　　　影響大 →）",
                  fontsize=9, labelpad=6)
    ax.set_title("ワークエンゲイジメント KPI ポートフォリオ図",
                 fontsize=12, color="#1a3a5c", pad=10)
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.18, linestyle=":")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 凡例
    ax.legend(loc="lower right", fontsize=8, framealpha=0.92,
              markerscale=1.2, ncol=2, borderpad=0.8)

    plt.tight_layout()
    return fig


def _build_page6(ctx):
    """P6: WE KPI ポートフォリオ4象限マトリクス"""
    font = ctx["font"]
    S    = ctx["S"]
    W    = ctx["W"]
    story = []

    story += [
        _section_bar(
            "KPI ポートフォリオ図（ワークエンゲイジメント基準）", font,
        ),
        Spacer(1, 4),
        Paragraph(
            "各尺度の現在の水準（X軸: 本集団の偏差値）とワークエンゲイジメント（WE）への"
            "影響度（Y軸: WEとの相関係数・文献値）を組み合わせ、改善優先度を4象限で可視化します。"
            "相関係数は新職業性ストレス簡易調査票研究（川上ら, 2012 他）の参考値です。",
            S["body"],
        ),
        Spacer(1, 6),
    ]

    fig = _portfolio_matrix_chart(ctx)
    if fig:
        story.append(_fig2img(fig, 165))

    story.append(Spacer(1, 8))

    # 象限説明テーブル
    story.append(_section_bar("各象限の解説", font, style="accent"))
    story.append(Spacer(1, 4))

    quad_data = [
        ("重点改善項目 ★（左上）", "#c0392b",
         "WEへの影響が大きく、現在の水準が全国平均を下回る領域。"
         "最優先で職場改善策を講じることで、WEの向上が期待できます。"),
        ("重点維持項目（右上）", "#27ae60",
         "WEへの影響が大きく、現在の水準も全国平均以上の領域。"
         "現在の取り組みを継続・強化し、良好な状態を維持してください。"),
        ("改善項目（左下）", "#e67e22",
         "現在の水準は全国平均を下回るが、WEへの直接的影響は比較的小さい領域。"
         "中長期的な改善計画の対象として検討してください。"),
        ("維持項目（右下）", "#7f8c8d",
         "現在の水準は全国平均以上で、WEへの直接的影響も比較的小さい領域。"
         "現状維持で問題ありませんが、他象限の改善後に再評価してください。"),
    ]

    def _qlabel(txt, c):
        return Paragraph(txt, ParagraphStyle(
            "ql", fontName=font, fontSize=8,
            textColor=colors.HexColor(c), leading=12,
        ))

    def _qdesc(txt):
        return Paragraph(txt, ParagraphStyle(
            "qd", fontName=font, fontSize=7.5, textColor=C_TEXT, leading=11,
        ))

    q_rows = [[_qlabel(label, c), _qdesc(desc)] for label, c, desc in quad_data]
    q_tbl = Table(q_rows, colWidths=[42*mm, W - 42*mm])
    q_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, C_MID_GRAY),
    ]))
    story.append(q_tbl)

    story += [
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.5, color=C_MID_GRAY),
        Spacer(1, 3),
        Paragraph(
            "※ 相関係数は文献参考値であり、業種・職種により異なる場合があります。"
            "　本レポートは集団分析結果であり、個人は特定されていません。",
            S["small"],
        ),
    ]

    return story


# ============================================================
# メイン生成関数
# ============================================================
def generate_group_report(
    summary_data,
    dept_df,
    group_scores,
    company_scores,
    output_path,
    lang="ja",
    company_name="",
    year=None,
    group_name="全体",
    n_total=0,
    raw_responses_list=None,
    trend_data=None,
    # 追加パラメータ
    n_male: int = 0,
    n_female: int = 0,
    n_distributed: Optional[int] = None,
    company_hs_rate: Optional[float] = None,
    company_risk: Optional[float] = None,
    industry_scores: Optional[Dict] = None,
    version: str = "57",
):
    _init_fonts()
    font = FONT_JA
    S = _S(font)
    _mpl()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=12 * mm, bottomMargin=12 * mm,
        leftMargin=14 * mm, rightMargin=14 * mm,
    )
    W = A4[0] - 28 * mm
    story = []

    hs_rate = summary_data.get("high_stress_rate", 0)
    n_total = summary_data.get("total_respondents", n_total)

    # 健康リスク計算
    if raw_responses_list:
        risk = calc_group_health_risk(raw_responses_list)
    else:
        risk = {"risk_a": 100, "risk_b": 100, "total_risk": 100,
                "quantity_mean": 0, "control_mean": 0,
                "supervisor_mean": 0, "coworker_mean": 0}

    total_risk = risk["total_risk"]

    # 回収率
    collection_rate = (
        round(n_total / n_distributed * 100, 1)
        if n_distributed and n_distributed > 0
        else None
    )

    # ── 共有コンテキスト ─────────────────────────────────
    ctx = {
        "font":               font,
        "S":                  S,
        "W":                  W,
        "company_name":       company_name,
        "group_name":         group_name,
        "year":               year,
        "n_total":            n_total,
        "n_male":             n_male,
        "n_female":           n_female,
        "n_distributed":      n_distributed,
        "hs_rate":            hs_rate,
        "total_risk":         total_risk,
        "collection_rate":    collection_rate,
        "company_hs_rate":    company_hs_rate if company_hs_rate is not None else 21.1,
        "company_risk":       company_risk    if company_risk    is not None else 100.0,
        "company_collection": 70.0,
        "group_scores":       group_scores,
        "company_scores":     company_scores,
        "industry_scores":    industry_scores or {},
        "risk":               risk,
        "dept_df":            dept_df,
        "summary_data":       summary_data,
        "version":            version,
        "scale_distributions": _compute_scale_distributions(
            raw_responses_list or [], version
        ),
    }

    # ── P1 ───────────────────────────────────────────────
    story += _build_page1(ctx)

    # ── P2 ───────────────────────────────────────────────
    nat_q  = NATIONAL_AVERAGES.get("仕事の量的負担",   {}).get("mean", 2.14) * 3
    nat_c  = NATIONAL_AVERAGES.get("仕事のコントロール",{}).get("mean", 2.71) * 3
    nat_s  = NATIONAL_AVERAGES.get("上司の支援",        {}).get("mean", 2.95) * 3
    nat_co = NATIONAL_AVERAGES.get("同僚の支援",        {}).get("mean", 3.12) * 3

    q_mean  = risk["quantity_mean"]   or nat_q
    c_mean  = risk["control_mean"]    or nat_c
    s_mean  = risk["supervisor_mean"] or nat_s
    co_mean = risk["coworker_mean"]   or nat_co

    fig_a = _judgment_chart(
        q_mean, c_mean, q_mean * 0.95, c_mean * 1.02, nat_q, nat_c,
        "仕事の量的負担（合計）", "仕事のコントロール（合計）",
        "仕事の量的負担とコントロール",
        font, x_range=(3, 12), y_range=(3, 12),
        zone_type="demand_control",
    )
    fig_b = _judgment_chart(
        s_mean, co_mean, s_mean * 1.05, co_mean * 0.98, nat_s, nat_co,
        "上司の支援（合計）", "同僚の支援（合計）",
        "上司の支援と同僚の支援",
        font, x_range=(3, 12), y_range=(3, 12),
        zone_type="support_support",
    )
    charts_tbl = Table(
        [[_fig2img(fig_a, 78), _fig2img(fig_b, 78)]],
        colWidths=[W * 0.50, W * 0.50],
    )
    charts_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID",  (0, 0), (-1, -1), 0, colors.white),
    ]))

    risk_a = risk["risk_a"]
    risk_b = risk["risk_b"]
    risk_color = C_HIGH if total_risk > 120 else C_TEXT

    # ── 健康リスク数値バー ────────────────────────────────
    risk_summary = Table(
        [[
            Paragraph("総合健康リスク",
                      ParagraphStyle("rl", fontName=font, fontSize=8,
                                     textColor=C_PRIMARY, leading=11)),
            Paragraph(f"<b>{total_risk}</b>",
                      ParagraphStyle("rv", fontName=font, fontSize=22,
                                     textColor=risk_color, leading=26)),
            Paragraph("量的負荷判定図(A)",
                      ParagraphStyle("rl", fontName=font, fontSize=8,
                                     textColor=C_PRIMARY, leading=11)),
            Paragraph(str(risk_a),
                      ParagraphStyle("rv", fontName=font, fontSize=16,
                                     textColor=C_TEXT, leading=20)),
            Paragraph("職場支援判定図(B)",
                      ParagraphStyle("rl", fontName=font, fontSize=8,
                                     textColor=C_PRIMARY, leading=11)),
            Paragraph(str(risk_b),
                      ParagraphStyle("rv", fontName=font, fontSize=16,
                                     textColor=C_TEXT, leading=20)),
        ]],
        colWidths=[30*mm, 22*mm, 34*mm, 18*mm, 34*mm, 18*mm],
    )
    risk_summary.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), font),
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT_GRAY),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_MID_GRAY),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
    ]))

    story += [
        _section_bar("総合健康リスク詳細・判定図", font),
        Spacer(1, 5),
        charts_tbl,
        Spacer(1, 5),
        risk_summary,
        Spacer(1, 8),
        _section_bar("各尺度の偏差値比較（全国平均=50）", font, style="accent"),
        Paragraph(
            "　偏差値55以上=◎良好　45〜55=—普通　40〜45=△注意　40未満=▼警戒"
            "　（赤字=全国平均を下回る尺度）",
            S["small"],
        ),
        Spacer(1, 2),
        _deviation_table(
            group_scores, company_scores, ctx["industry_scores"],
            NATIONAL_AVERAGES, font, W,
        ),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.5, color=C_MID_GRAY),
        Spacer(1, 3),
        Paragraph("※ 本レポートは集団分析結果であり、個人は特定されていません。", S["small"]),
        PageBreak(),
    ]

    # ── P3 ───────────────────────────────────────────────
    story += _build_page3(ctx)

    # ── P4-P5 ────────────────────────────────────────────
    story += _build_page4_5(ctx)

    # ── P6 ───────────────────────────────────────────────
    story += _build_page6(ctx)

    doc.build(story)
    buf.seek(0)
    with open(output_path, "wb") as f:
        f.write(buf.read())
    return output_path


# ============================================================
# バッチ生成
# ============================================================
def generate_both_lang_reports(
    summary_data,
    dept_df,
    group_scores,
    company_scores,
    output_base,
    company_name="",
    year=None,
    group_name="全体",
    raw_responses_list=None,
    n_male: int = 0,
    n_female: int = 0,
    n_distributed: Optional[int] = None,
    company_hs_rate: Optional[float] = None,
    company_risk: Optional[float] = None,
    industry_scores: Optional[Dict] = None,
    version: str = "57",
):
    Path(output_base).mkdir(parents=True, exist_ok=True)
    results = {}
    for lang in ["ja"]:
        out = str(Path(output_base) / f"group_report_{lang}.pdf")
        generate_group_report(
            summary_data=summary_data,
            dept_df=dept_df,
            group_scores=group_scores,
            company_scores=company_scores,
            output_path=out,
            lang=lang,
            company_name=company_name,
            year=year,
            group_name=group_name,
            n_total=summary_data.get("total_respondents", 0),
            raw_responses_list=raw_responses_list,
            n_male=n_male,
            n_female=n_female,
            n_distributed=n_distributed,
            company_hs_rate=company_hs_rate,
            company_risk=company_risk,
            industry_scores=industry_scores,
            version=version,
        )
        results[lang] = out
    return results


# ============================================================
# デモ実行
# ============================================================
if __name__ == "__main__":
    import random

    random.seed(42)
    sys.path.insert(0, str(BASE_DIR))
    from config.scoring_rules import ALL_ITEMS
    from src.scoring.calculator import StressCheckScorer

    departments = ["営業部", "開発部", "管理部", "製造部"]
    n_each = [15, 18, 12, 14]
    scorer = StressCheckScorer(version="120")
    all_resp, all_results = [], []

    for dept, n in zip(departments, n_each):
        for _ in range(n):
            r = {q: random.randint(1, 4) for q in ALL_ITEMS}
            all_resp.append(r)
            res = scorer.calculate(r)
            all_results.append({
                "department":  dept,
                "high_stress": res["high_stress"],
                "scale_scores": res["scale_scores"],
            })

    company_scores = {}
    group_scores   = {}
    for s in NATIONAL_AVERAGES:
        vals = [r["scale_scores"].get(s) for r in all_results
                if r["scale_scores"].get(s) is not None]
        if vals:
            company_scores[s] = group_scores[s] = sum(vals) / len(vals)

    rows = []
    for dept in departments:
        grp = [r for r in all_results if r["department"] == dept]
        row = {"department": dept, "n": len(grp), "suppressed": len(grp) < 10}
        if len(grp) >= 10:
            row["high_stress_count"] = sum(r["high_stress"] for r in grp)
            row["high_stress_rate"]  = row["high_stress_count"] / len(grp) * 100
        rows.append(row)
    dept_df = pd.DataFrame(rows)

    n_respondents = len(all_results)
    hs_count = sum(r["high_stress"] for r in all_results)
    summary_data = {
        "total_respondents": n_respondents,
        "high_stress_count": hs_count,
        "high_stress_rate":  round(hs_count / n_respondents * 100, 1),
    }

    print("集団分析レポート生成（P1-P3実装版）...")
    results = generate_both_lang_reports(
        summary_data=summary_data,
        dept_df=dept_df,
        group_scores=group_scores,
        company_scores=company_scores,
        output_base="/tmp/group_reports_p3",
        company_name="株式会社テスト",
        year=2025,
        group_name="全体",
        raw_responses_list=all_resp,
        n_male=32,
        n_female=27,
        n_distributed=70,
        company_hs_rate=18.5,
        company_risk=105,
        version="120",
    )
    for lang, path in results.items():
        size = os.path.getsize(path)
        print(f"  [{lang}] {path} ({size:,} bytes) ✅")
    print("完了")

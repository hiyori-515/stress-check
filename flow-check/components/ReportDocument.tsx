import {
  Document,
  Font,
  Line,
  Page,
  Polygon,
  StyleSheet,
  Svg,
  Text,
  View,
} from "@react-pdf/renderer";
import path from "node:path";
import React from "react";
import { CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/questions";
import type { Level } from "@/lib/scoring";

// サーバー専用（Route Handlerからのみimportすること）

const NAVY = "#1a365d";
const GOLD = "#b7935a";
const GOLD_LIGHT = "#f6f0e6";
const GRAY_TRACK = "#e8ecf1";

const fontDir = path.join(process.cwd(), "assets", "fonts");
Font.register({
  family: "Noto Sans JP",
  fonts: [
    { src: path.join(fontDir, "NotoSansJP-Regular.ttf"), fontWeight: 400 },
    { src: path.join(fontDir, "NotoSansJP-Bold.ttf"), fontWeight: 700 },
  ],
});
// 単語内改行を無効化（既定のハイフン付き分割を防ぐ）
Font.registerHyphenationCallback((word) => [word]);

/**
 * 日本語は単語区切りがなく1文が1単語として扱われるため、
 * 文字間に極細スペース(U+200A)を挿入してハイフンなしで折り返せるようにする。
 */
function breakable(text: string): string {
  return Array.from(text).join("\u200A");
}

/** 高スコア領域の経営者向け定型説明文 */
const HIGH_SCORE_DESCRIPTIONS: Record<Category, string> = {
  judgment:
    "最終的な判断やOKが、一か所に集まりやすくなっている傾向が見られます。",
  execution:
    "決定したことが、現場の行動に移るまでの間で止まりやすくなっている傾向が見られます。",
  honesty:
    "率直な意見や違和感が、表の場に出にくくなっている傾向が見られます。",
  roles:
    "誰が何を担当するかが、仕組みではなくその場の状況で決まりやすくなっている傾向が見られます。",
  delegation:
    "任せたことと、実際に相手が判断できる範囲との間にギャップが生まれやすくなっている傾向が見られます。",
};

export interface ReportScore {
  category: Category;
  total_score: number;
  level: Level;
}

export interface ReportData {
  name: string;
  companyName: string;
  /** 実施日（表示用にフォーマット済み） */
  conductedOn: string;
  scores: ReportScore[];
  clientComment: string;
}

const styles = StyleSheet.create({
  page: {
    fontFamily: "Noto Sans JP",
    fontSize: 10.5,
    color: "#1f2937",
    paddingTop: 64,
    paddingBottom: 72,
    paddingHorizontal: 64,
    lineHeight: 1.7,
  },
  footer: {
    position: "absolute",
    bottom: 32,
    left: 64,
    right: 64,
    flexDirection: "row",
    justifyContent: "space-between",
    fontSize: 9,
    color: "#9ca3af",
  },
  heading: {
    fontSize: 16,
    fontWeight: 700,
    color: NAVY,
    marginBottom: 20,
  },
  headingAccent: {
    width: 32,
    height: 3,
    backgroundColor: GOLD,
    marginTop: -14,
    marginBottom: 20,
  },
  // 表紙
  coverPage: {
    fontFamily: "Noto Sans JP",
    fontSize: 11,
    color: "#1f2937",
    paddingTop: 64,
    paddingBottom: 72,
    paddingHorizontal: 64,
    justifyContent: "center",
  },
  coverInner: {
    alignItems: "center",
    textAlign: "center",
  },
  coverLogo: {
    fontSize: 34,
    fontWeight: 700,
    color: NAVY,
    letterSpacing: 2,
  },
  coverRule: {
    width: 48,
    height: 3,
    backgroundColor: GOLD,
    marginTop: 16,
    marginBottom: 40,
  },
  coverDate: {
    fontSize: 11,
    color: "#6b7280",
    marginBottom: 28,
  },
  coverCompany: {
    fontSize: 15,
    fontWeight: 700,
    color: NAVY,
    marginBottom: 6,
  },
  coverName: {
    fontSize: 13,
    marginBottom: 56,
  },
  coverNote: {
    fontSize: 9.5,
    color: "#6b7280",
  },
  // レーダーチャート
  radarWrap: {
    alignItems: "center",
    marginTop: 4,
  },
  scoreNote: {
    fontSize: 9,
    color: "#6b7280",
    marginTop: 8,
  },
  highBox: {
    backgroundColor: GOLD_LIGHT,
    borderRadius: 6,
    padding: 14,
    marginBottom: 10,
  },
  highBoxTitle: {
    fontSize: 11,
    fontWeight: 700,
    color: NAVY,
    marginBottom: 4,
  },
  bodyText: {
    fontSize: 10.5,
  },
  sectionGap: {
    marginTop: 28,
  },
  stepItem: {
    marginBottom: 12,
  },
  contactBox: {
    marginTop: 40,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: GRAY_TRACK,
    fontSize: 10.5,
  },
});

// ===== レーダーチャート(SVG直接描画) =====
const RADAR = {
  width: 380,
  height: 300,
  cx: 190,
  cy: 150,
  radius: 96,
  maxValue: 20,
  gridSteps: [5, 10, 15, 20],
  labelOffset: 18,
};

/** 頂点i(0=上から時計回り)・値vの座標 */
function radarPoint(value: number, index: number): { x: number; y: number } {
  const angle = ((-90 + index * 72) * Math.PI) / 180;
  const r = (RADAR.radius * value) / RADAR.maxValue;
  return {
    x: RADAR.cx + r * Math.cos(angle),
    y: RADAR.cy + r * Math.sin(angle),
  };
}

function radarPolygonPoints(values: number[]): string {
  return values
    .map((value, i) => {
      const p = radarPoint(value, i);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    })
    .join(" ");
}

// 各頂点の外側ラベル配置（anchor/2行分のオフセット）
const RADAR_LABEL_CONFIG = [
  { anchor: "middle", dy1: -16, dy2: -4 }, // 上
  { anchor: "start", dy1: 0, dy2: 12 }, // 右上
  { anchor: "start", dy1: 10, dy2: 22 }, // 右下
  { anchor: "end", dy1: 10, dy2: 22 }, // 左下
  { anchor: "end", dy1: 0, dy2: 12 }, // 左上
] as const;

function RadarChartSvg({ scores }: { scores: Map<Category, ReportScore> }) {
  const values = CATEGORIES.map(
    (category) => scores.get(category)?.total_score ?? 0
  );
  return (
    <Svg
      width={RADAR.width}
      height={RADAR.height}
      viewBox={`0 0 ${RADAR.width} ${RADAR.height}`}
    >
      {/* 五角形グリッド(5,10,15,20) */}
      {RADAR.gridSteps.map((step) => (
        <Polygon
          key={step}
          points={radarPolygonPoints([step, step, step, step, step])}
          fill="none"
          stroke={GRAY_TRACK}
          strokeWidth={1}
        />
      ))}
      {/* 軸線 */}
      {CATEGORIES.map((category, i) => {
        const outer = radarPoint(RADAR.maxValue, i);
        return (
          <Line
            key={category}
            x1={RADAR.cx}
            y1={RADAR.cy}
            x2={outer.x}
            y2={outer.y}
            stroke={GRAY_TRACK}
            strokeWidth={1}
          />
        );
      })}
      {/* データ(半透明の紺) */}
      <Polygon
        points={radarPolygonPoints(values)}
        fill={NAVY}
        fillOpacity={0.35}
        stroke={NAVY}
        strokeWidth={1.5}
      />
      {/* 軸ラベル(日本語+英語)とスコア。高スコアは赤系で強調 */}
      {CATEGORIES.map((category, i) => {
        const score = scores.get(category);
        const isHigh = score?.level === "高";
        const color = isHigh ? "#dc2626" : "#374151";
        const outer = radarPoint(RADAR.maxValue, i);
        const angle = ((-90 + i * 72) * Math.PI) / 180;
        const lx = outer.x + RADAR.labelOffset * Math.cos(angle);
        const ly = outer.y + RADAR.labelOffset * Math.sin(angle);
        const config = RADAR_LABEL_CONFIG[i];
        return (
          <React.Fragment key={category}>
            <Text
              x={lx}
              y={ly + config.dy1}
              textAnchor={config.anchor}
              style={{
                fontFamily: "Noto Sans JP",
                fontSize: 10,
                fontWeight: isHigh ? 700 : 400,
              }}
              fill={color}
            >
              {CATEGORY_LABELS[category]}
            </Text>
            <Text
              x={lx}
              y={ly + config.dy2}
              textAnchor={config.anchor}
              style={{ fontFamily: "Noto Sans JP", fontSize: 9 }}
              fill={color}
            >
              {`${score?.total_score ?? 0}/20`}
            </Text>
          </React.Fragment>
        );
      })}
    </Svg>
  );
}

function Footer() {
  return (
    <View style={styles.footer} fixed>
      <Text>Flow Check</Text>
      <Text render={({ pageNumber }) => `${pageNumber}`} />
    </View>
  );
}

function SectionHeading({ title }: { title: string }) {
  return (
    <View>
      <Text style={styles.heading}>{title}</Text>
      <View style={styles.headingAccent} />
    </View>
  );
}

export function buildReportDocument(data: ReportData) {
  const scoreByCategory = new Map(
    data.scores.map((score) => [score.category, score])
  );
  const highCategories = CATEGORIES.filter(
    (category) => scoreByCategory.get(category)?.level === "高"
  );

  return (
    <Document
      title={`Flow Check レポート - ${data.companyName} ${data.name}様`}
      author="株式会社エピファニー"
    >
      {/* 1ページ目: 表紙 */}
      <Page size="A4" style={styles.coverPage}>
        <View style={styles.coverInner}>
          <Text style={styles.coverLogo}>Flow Check</Text>
          <View style={styles.coverRule} />
          <Text style={styles.coverDate}>実施日: {data.conductedOn}</Text>
          <Text style={styles.coverCompany}>{data.companyName}</Text>
          <Text style={styles.coverName}>{data.name} 様</Text>
          <Text style={styles.coverNote}>
            {breakable(
              "本レポートは、Flow Checkの回答内容と面談をもとに作成しています。"
            )}
          </Text>
        </View>
        <Footer />
      </Page>

      {/* 2ページ目: 今回の整理結果 */}
      <Page size="A4" style={styles.page}>
        <SectionHeading title="今回の整理結果" />
        <View style={styles.radarWrap}>
          <RadarChartSvg scores={scoreByCategory} />
          <Text style={styles.scoreNote}>
            ※外側に広がっている領域ほど、詰まりが集中しています
          </Text>
        </View>

        {highCategories.length > 0 && (
          <View style={styles.sectionGap}>
            <Text
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: NAVY,
                marginBottom: 12,
              }}
            >
              スコアが高かった領域について
            </Text>
            {highCategories.map((category) => (
              <View key={category} style={styles.highBox}>
                <Text style={styles.highBoxTitle}>
                  {CATEGORY_LABELS[category]}
                </Text>
                <Text style={styles.bodyText}>
                  {breakable(HIGH_SCORE_DESCRIPTIONS[category])}
                </Text>
              </View>
            ))}
          </View>
        )}
        <Footer />
      </Page>

      {/* 3ページ目: 面談で見えてきたこと */}
      <Page size="A4" style={styles.page}>
        <SectionHeading title="面談で見えてきたこと" />
        <Text style={styles.bodyText}>{breakable(data.clientComment)}</Text>
        <Footer />
      </Page>

      {/* 4ページ目: 次のステップ */}
      <Page size="A4" style={styles.page}>
        <SectionHeading title="次のステップ" />
        <Text style={[styles.bodyText, { marginBottom: 20 }]}>
          {breakable(
            "今回のFlow Checkと面談で整理した内容をもとに、以下のステップをご提案します。"
          )}
        </Text>
        <View style={styles.stepItem}>
          <Text style={styles.bodyText}>
            {breakable(
              "1. まずは、最も詰まりが集中していた領域から、小さな変化を一つ始めてみてください。"
            )}
          </Text>
        </View>
        <View style={styles.stepItem}>
          <Text style={styles.bodyText}>
            {breakable(
              "2. 3ヶ月の伴走支援で、変化の定着をサポートすることも可能です。"
            )}
          </Text>
        </View>
        <Text style={[styles.bodyText, { marginTop: 12 }]}>
          ご関心がありましたら、黒川までご連絡ください。
        </Text>
        <View style={styles.contactBox}>
          <Text style={{ fontWeight: 700, color: NAVY }}>
            株式会社エピファニー 黒川ゆう子
          </Text>
          <Text>epiphanypsycho@gmail.com</Text>
        </View>
        <Footer />
      </Page>
    </Document>
  );
}

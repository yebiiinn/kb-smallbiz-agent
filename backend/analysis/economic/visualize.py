"""경기지표 상관관계 시각화 (18개 지표 버전)"""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120

CSV = Path(__file__).resolve().parent / "data" / "merged_indicators.csv"
df = pd.read_csv(CSV, index_col="기간", encoding="utf-8-sig").dropna()
OUT = Path(__file__).resolve().parent / "charts"
OUT.mkdir(exist_ok=True)

ECOS_COLS = [
    "기준금리", "소비자물가지수", "생산자물가지수", "원달러환율",
    "현재경기판단CSI", "향후경기전망CSI", "외식비지출전망CSI", "여행비지출전망CSI",
    "BSI_서비스업전망", "BSI_중소기업전망",
]
KOSIS_COLS = [
    "소매판매_편의점", "소매판매_전문소매점", "소매판매_무점포소매",
    "서비스업생산_음식점주점", "서비스업생산_교육서비스",
    "서비스업생산_개인서비스", "서비스업생산_총지수", "실업률",
]
ALL_COLS = ECOS_COLS + KOSIS_COLS
corr = df[ALL_COLS].corr(method="pearson")

# ── 그림 1: 전체 상관계수 히트맵 ────────────────────────────────────────────
fig1, ax = plt.subplots(figsize=(16, 13))
sns.heatmap(corr, annot=True, fmt=".2f", annot_kws={"size": 7.5},
            cmap="RdYlGn", center=0, vmin=-1, vmax=1,
            linewidths=0.5, square=True, ax=ax,
            cbar_kws={"shrink": 0.75, "label": "Pearson r"})
ax.set_title("경기지표 × 업종 지표 상관계수 매트릭스\n(2023.07~2026.06, 18개 지표)",
             fontsize=14, fontweight="bold", pad=16)
ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right", fontsize=8)
ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8)
ax.axhline(len(ECOS_COLS), color="navy", lw=2.5, ls="--")
ax.axvline(len(ECOS_COLS), color="navy", lw=2.5, ls="--")
ax.text(1, len(ECOS_COLS) + 0.3, "◀ ECOS(한국은행)", color="navy", fontsize=8)
ax.text(len(ECOS_COLS) + 0.1, 0.5, "KOSIS ▶", color="navy", fontsize=8, rotation=90)
plt.tight_layout()
fig1.savefig(OUT / "01_correlation_heatmap.png", bbox_inches="tight")
print(f"저장: {OUT / '01_correlation_heatmap.png'}")
plt.close()

# ── 그림 2: ECOS 경기지표 + KOSIS 실업률 시계열 (10개) ──────────────────────
styles = [
    ("기준금리",         "steelblue",      "금리 (%)"),
    ("소비자물가지수",   "tomato",         "지수(2020=100)"),
    ("생산자물가지수",   "saddlebrown",    "지수(2020=100)"),
    ("원달러환율",       "slategray",      "원/달러"),
    ("현재경기판단CSI",  "darkorange",     "CSI"),
    ("향후경기전망CSI",  "mediumseagreen", "CSI"),
    ("외식비지출전망CSI","coral",          "CSI"),
    ("BSI_서비스업전망", "mediumpurple",   "BSI"),
    ("BSI_중소기업전망", "royalblue",      "BSI"),
    ("실업률",          "dimgray",        "%"),
]
fig2, axes = plt.subplots(len(styles), 1, figsize=(14, len(styles) * 2.1), sharex=True)
fig2.suptitle("경기지표 시계열 (2023.07~2026.06)", fontsize=14, fontweight="bold", y=1.01)

RATE_CUTS = [("202410", "↓3.25%"), ("202502", "↓2.75%"), ("202505", "↓2.5%")]

for ax, (col, color, ylabel) in zip(axes, styles):
    s = df[col].dropna()
    s_dates = pd.to_datetime(s.index.astype(str), format="%Y%m")
    ax.plot(s_dates, s, color=color, lw=2, marker="o", markersize=2.5)
    ax.fill_between(s_dates, float(s.min()) * 0.98, s, alpha=0.12, color=color)
    ax.set_ylabel(ylabel, fontsize=7.5)
    ax.set_title(col, fontsize=8.5, fontweight="bold", loc="left")
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=30, labelsize=6.5)
    for dt_str, lbl in RATE_CUTS:
        if dt_str in df.index:
            ax.axvline(pd.to_datetime(dt_str, format="%Y%m"),
                       color="gray", lw=1, ls="--", alpha=0.55)
            if col == "기준금리":
                ax.text(pd.to_datetime(dt_str, format="%Y%m"),
                        float(s.max()) * 0.99, lbl,
                        fontsize=6, color="gray", ha="center", va="top")

axes[-1].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y.%m"))
plt.tight_layout()
fig2.savefig(OUT / "02_ecos_timeseries.png", bbox_inches="tight")
print(f"저장: {OUT / '02_ecos_timeseries.png'}")
plt.close()

# ── 그림 3: KOSIS 업종 시계열 ────────────────────────────────────────────────
fig3, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
fig3.suptitle("KOSIS 업종별 지수 시계열 (2020=100 불변지수, 2023.07~2026.06)",
              fontsize=13, fontweight="bold")

ax = axes[0]
retail_colors = {"소매판매_편의점": "#e07b39", "소매판매_전문소매점": "#3a7dc9", "소매판매_무점포소매": "#50a86a"}
for col, color in retail_colors.items():
    ax.plot(pd.to_datetime(df[col].dropna().index.astype(str), format="%Y%m"),
            df[col].dropna(), label=col.replace("소매판매_",""), color=color, lw=1.8, marker="o", markersize=3)
ax.set_title("소매판매액지수 (업태별)", fontsize=10, fontweight="bold", loc="left")
ax.set_ylabel("지수 (2020=100)", fontsize=9)
ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.4)

ax = axes[1]
svc_colors = {
    "서비스업생산_음식점주점": "#c0392b", "서비스업생산_교육서비스": "#8e44ad",
    "서비스업생산_개인서비스": "#16a085", "서비스업생산_총지수": "#2c3e50",
}
for col, color in svc_colors.items():
    lw, ls = (2.5, "--") if "총지수" in col else (1.5, "-")
    ax.plot(pd.to_datetime(df[col].dropna().index.astype(str), format="%Y%m"),
            df[col].dropna(), label=col.replace("서비스업생산_",""),
            color=color, lw=lw, ls=ls, marker="o", markersize=3)
ax.set_title("서비스업생산지수 (산업별)", fontsize=10, fontweight="bold", loc="left")
ax.set_ylabel("지수 (2020=100)", fontsize=9)
ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.4)
ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y.%m"))
ax.tick_params(axis="x", rotation=30, labelsize=8)
plt.tight_layout()
fig3.savefig(OUT / "03_kosis_timeseries.png", bbox_inches="tight")
print(f"저장: {OUT / '03_kosis_timeseries.png'}")
plt.close()

# ── 그림 4: ECOS → KOSIS 크로스 히트맵 (에이전트 참조 매핑표) ─────────────
cross_corr = corr.loc[ECOS_COLS, KOSIS_COLS]
fig4, ax = plt.subplots(figsize=(13, 5.5))
sns.heatmap(cross_corr, annot=True, fmt=".2f", annot_kws={"size": 9},
            cmap="RdYlGn", center=0, vmin=-1, vmax=1,
            linewidths=0.8, square=False, ax=ax,
            cbar_kws={"label": "Pearson r"})
ax.set_title("경기지표(ECOS) → 업종 지표(KOSIS) 상관계수\n(소상공인 에이전트 참조 매핑표)",
             fontsize=13, fontweight="bold", pad=14)
ax.set_xticklabels(
    [c.replace("소매판매_","소매\n").replace("서비스업생산_","서비스\n") for c in KOSIS_COLS],
    rotation=0, ha="center", fontsize=8.5)
ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=9)
plt.tight_layout()
fig4.savefig(OUT / "04_ecos_kosis_crosscorr.png", bbox_inches="tight")
print(f"저장: {OUT / '04_ecos_kosis_crosscorr.png'}")
plt.close()

# ── 그림 5: 신규 발견 고상관 쌍 산점도 ─────────────────────────────────────
NEW_PAIRS = [
    ("소비자물가지수", "원달러환율",       "royalblue"),
    ("생산자물가지수", "원달러환율",       "saddlebrown"),
    ("기준금리",      "원달러환율",       "steelblue"),
    ("소매판매_편의점","실업률",          "tomato"),
    ("외식비지출전망CSI","여행비지출전망CSI","coral"),
    ("BSI_서비스업전망","소매판매_편의점",  "mediumpurple"),
]
fig5, axes = plt.subplots(2, 3, figsize=(14, 8))
fig5.suptitle("신규 추가 지표 포함 고상관 쌍 산점도", fontsize=13, fontweight="bold")
for ax, (x_col, y_col, color) in zip(axes.flat, NEW_PAIRS):
    x, y = df[x_col].dropna(), df[y_col].dropna()
    common = x.index.intersection(y.index)
    x, y = x[common], y[common]
    r = x.corr(y)
    ax.scatter(x, y, color=color, alpha=0.7, s=40, edgecolors="white", lw=0.5)
    z = np.polyfit(x, y, 1); p = np.poly1d(z)
    x_line = np.linspace(float(x.min()), float(x.max()), 100)
    ax.plot(x_line, p(x_line), "--", color=color, lw=1.5, alpha=0.8)
    ax.set_xlabel(x_col, fontsize=9); ax.set_ylabel(y_col, fontsize=9)
    ax.set_title(f"r = {r:+.3f}", fontsize=10, fontweight="bold",
                 color="darkgreen" if r > 0 else "crimson")
    ax.grid(alpha=0.3)
plt.tight_layout()
fig5.savefig(OUT / "05_scatter_new_pairs.png", bbox_inches="tight")
print(f"저장: {OUT / '05_scatter_new_pairs.png'}")
plt.close()

# ── 그림 6: 업종별 경기지표 민감도 (가로 막대) ──────────────────────────────
fig6, axes = plt.subplots(2, 4, figsize=(18, 7))
fig6.suptitle("업종별 경기지표 민감도 (|상관계수|, 빨강=음/파랑=양)",
              fontsize=13, fontweight="bold")
for ax, k_col in zip(axes.flat, KOSIS_COLS):
    vals = cross_corr[k_col]
    bar_colors = ["tomato" if v < 0 else "steelblue" for v in vals]
    bars = ax.barh(ECOS_COLS, vals, color=bar_colors, edgecolor="white", height=0.6)
    ax.axvline(0, color="black", lw=0.8)
    for thr in [0.4, -0.4, 0.7, -0.7]:
        ax.axvline(thr, color="gray", lw=0.8, ls=":", alpha=0.5)
    short = k_col.replace("소매판매_","소매\n").replace("서비스업생산_","서비스\n")
    ax.set_title(short, fontsize=8.5, fontweight="bold")
    ax.set_xlim(-1.05, 1.05); ax.tick_params(axis="y", labelsize=7); ax.tick_params(axis="x", labelsize=6.5)
    for bar, val in zip(bars, vals):
        ax.text(val + (0.03 if val >= 0 else -0.03),
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}", va="center",
                ha="left" if val >= 0 else "right", fontsize=6.5)
plt.tight_layout()
fig6.savefig(OUT / "06_sensitivity_by_industry.png", bbox_inches="tight")
print(f"저장: {OUT / '06_sensitivity_by_industry.png'}")
plt.close()

# ── 그림 7: 거시지표 그룹 내 상관관계 ────────────────────────────────────────
macro_groups = {
    "금리·물가·환율": ["기준금리","소비자물가지수","생산자물가지수","원달러환율"],
    "소비심리(CSI·BSI)": ["현재경기판단CSI","향후경기전망CSI","외식비지출전망CSI","여행비지출전망CSI","BSI_서비스업전망","BSI_중소기업전망"],
}
fig7, axes = plt.subplots(1, 2, figsize=(14, 5))
fig7.suptitle("거시지표 그룹 내 상관계수", fontsize=13, fontweight="bold")
for ax, (group_name, cols) in zip(axes, macro_groups.items()):
    sub = corr.loc[cols, cols]
    sns.heatmap(sub, annot=True, fmt=".2f", annot_kws={"size": 10},
                cmap="RdYlGn", center=0, vmin=-1, vmax=1,
                linewidths=1, square=True, ax=ax,
                cbar_kws={"shrink": 0.8})
    ax.set_title(group_name, fontsize=11, fontweight="bold")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right", fontsize=8.5)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8.5)
plt.tight_layout()
fig7.savefig(OUT / "07_macro_group_corr.png", bbox_inches="tight")
print(f"저장: {OUT / '07_macro_group_corr.png'}")
plt.close()

print("\n✅ 시각화 완료 (7개 차트). charts/ 폴더를 확인하세요.")

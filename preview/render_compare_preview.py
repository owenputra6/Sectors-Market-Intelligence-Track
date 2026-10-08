"""Deterministic preview of the updated search and continuous duel UI."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("compare_continuous_preview.png")
BG, PAGE, SURFACE, SOFT, BORDER = "#090809", "#121110", "#1C1A1D", "#171619", "#343137"
TEXT, MUTED, ACCENT, GREEN, AMBER = "#F7F3FB", "#ABA5B2", "#C3A2FF", "#8EE2BD", "#F2C35F"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REG, size)


im = Image.new("RGB", (1800, 1180), BG)
d = ImageDraw.Draw(im)


def rr(box, fill=SURFACE, outline=BORDER, radius=14, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def txt(x, y, value, size=18, color=TEXT, bold=False, anchor=None):
    d.text((x, y), value, font=font(size, bold), fill=color, anchor=anchor)


def pill(x, y, value, color=ACCENT):
    w = d.textlength(value, font=font(12, True)) + 26
    rr((x, y, x + w, y + 32), fill=SOFT, outline=color, radius=16)
    txt(x + 13, y + 8, value, 12, color, True)
    return w


def bar(x, y, w, share, left=ACCENT, right=GREEN, h=9):
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=right)
    d.rounded_rectangle((x, y, x + w * share, y + h), radius=h // 2, fill=left)


rr((36, 28, 1764, 1152), fill=PAGE, outline="#29262B", radius=24, width=2)
txt(70, 56, "IDX / FINGERPRINT", 18, TEXT, True)
txt(1510, 58, "Search   Compare   AI", 15, MUTED)

# Search recommendation card.
txt(70, 125, "Ranked search recommendations", 27, TEXT, True)
rr((70, 180, 650, 240), fill=SURFACE, radius=12)
txt(94, 198, "⌕   BB", 18, TEXT, True)
rr((70, 252, 650, 574), fill=SOFT, outline="#6D588E", radius=12)
txt(92, 272, "SEARCH RECOMMENDATIONS", 11, ACCENT, True)
recommendations = [
    ("BBCA", "Bank Central Asia", "78.6%"),
    ("BBRI", "Bank Rakyat Indonesia", "71.2%"),
    ("BBNI", "Bank Negara Indonesia", "66.8%"),
    ("BBTN", "Bank Tabungan Negara", "61.4%"),
]
for i, (ticker, name, score) in enumerate(recommendations):
    y = 312 + i * 61
    d.ellipse((93, y + 8, 101, y + 16), fill=GREEN)
    txt(115, y, ticker, 16, TEXT, True)
    txt(190, y + 2, name, 13, MUTED)
    txt(620, y + 2, score, 15, GREEN, True, anchor="ra")
txt(91, 542, "Top result opens the company page; ranking uses this CSV snapshot.", 11, MUTED)

# Compare summary.
txt(705, 125, "Compare fingerprints", 29, TEXT, True)
rr((705, 180, 1728, 440), fill=SURFACE, radius=14)
pill(730, 204, "HRTA  VS  ARCI")
pill(875, 204, "CONFIDENCE HIGH", GREEN)
txt(730, 255, "ARCI leads · 61.5%", 34, GREEN, True)
txt(730, 304, "Continuous evidence share, while the five-segment verdict stays auditable.", 15, MUTED)
txt(750, 354, "HRTA", 13, TEXT, True)
txt(750, 376, "38.5%", 27, ACCENT, True)
txt(1665, 354, "ARCI", 13, TEXT, True, anchor="ra")
txt(1665, 376, "61.5%", 27, GREEN, True, anchor="ra")
bar(900, 377, 600, .385)

# Segment shares.
segments = [
    ("Valuation", 16.7, ACCENT),
    ("Growth", 33.3, AMBER),
    ("Financial", 33.3, GREEN),
    ("Performance", 100.0, ACCENT),
    ("Dividend", 33.3, GREEN),
]
for i, (name, share, color) in enumerate(segments):
    x = 705 + i * 205
    rr((x, 460, x + 188, 584), fill=SURFACE, radius=12)
    txt(x + 14, 477, name, 12, MUTED)
    txt(x + 14, 506, f"HRTA  {share:.1f}%", 14, color, True)
    txt(x + 174, 506, f"{100-share:.1f}%", 14, TEXT, True, anchor="ra")
    bar(x + 14, 541, 160, share / 100, color, BORDER, 7)
    txt(x + 14, 557, "feature-point share", 10, MUTED)

# Feature evidence.
txt(70, 635, "15-FEATURE EVIDENCE", 13, ACCENT, True)
txt(70, 661, "Each row exposes both values; the winning card receives the segment highlight.", 14, MUTED)
evidence = [
    ("1. P/E", "raw / peer median", "HRTA", "2.47x", "raw 24.10x · peer 9.77x", "ARCI", "0.84x", "raw 8.19x · peer 9.77x", "B"),
    ("4. Revenue growth FY", "raw", "HRTA", "7.32%", "raw 7.32%", "ARCI", "12.18%", "raw 12.18%", "B"),
    ("10. Total return 12M proxy", "market-cap change + yield", "HRTA", "41.20%", "raw 41.20%", "ARCI", "18.70%", "raw 18.70%", "A"),
]
for i, row in enumerate(evidence):
    title, basis, ta, va, ca, tb, vb, cb, winner = row
    y = 704 + i * 142
    rr((70, y, 1728, y + 124), fill=SURFACE, radius=12)
    txt(92, y + 18, title, 17, TEXT, True)
    txt(92, y + 47, basis, 12, MUTED)
    pill(490, y + 17, f"{tb if winner == 'B' else ta} WINS", GREEN if winner == "B" else ACCENT)
    for x, ticker, value, context, won, color in [
        (740, ta, va, ca, winner == "A", ACCENT),
        (1235, tb, vb, cb, winner == "B", GREEN),
    ]:
        rr((x, y + 14, x + 445, y + 108), fill="#201D22" if won else SOFT, outline=color if won else BORDER, radius=10, width=2 if won else 1)
        txt(x + 16, y + 27, ticker, 13, color if won else MUTED, True)
        txt(x + 16, y + 50, value, 25, TEXT, True)
        txt(x + 16, y + 82, context, 11, MUTED)

txt(70, 1120, "Code-derived UI preview · sample values only · responsive Flutter implementation included", 12, MUTED)
OUT.parent.mkdir(parents=True, exist_ok=True)
im.save(OUT, quality=96)
print(OUT)

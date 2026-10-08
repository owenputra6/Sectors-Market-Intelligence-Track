"""Render a deterministic design preview from the Flutter screen's tokens."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("idx_fingerprint_preview.png")
BG, SURFACE, BORDER = "#121110", "#1C1A1D", "#343137"
TEXT, MUTED, ACCENT, GREEN = "#F7F3FB", "#ABA5B2", "#C3A2FF", "#8EE2BD"
AMBER, RED = "#F0C777", "#EF8F9A"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def font(size, bold=False): return ImageFont.truetype(BOLD if bold else REG, size)

im = Image.new("RGB", (1900, 1240), "#0A090A")
d = ImageDraw.Draw(im)

def rr(box, fill=SURFACE, outline=BORDER, radius=18, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def txt(x, y, value, size=20, color=TEXT, bold=False, anchor=None):
    d.text((x, y), value, font=font(size, bold), fill=color, anchor=anchor)

def chip(x, y, value, color=ACCENT):
    w = d.textlength(value, font=font(13, True)) + 28
    rr((x, y, x+w, y+34), fill="#242027", outline=color, radius=17)
    txt(x+14, y+9, value, 13, color, True)
    return w

def progress(x, y, w, pct, color):
    d.rounded_rectangle((x, y, x+w, y+8), radius=4, fill="#2B282E")
    d.rounded_rectangle((x, y, x+w*pct, y+8), radius=4, fill=color)

# Desktop surface
dx, dy, dw, dh = 40, 40, 1220, 1160
rr((dx, dy, dx+dw, dy+dh), fill=BG, outline="#29262B", radius=24, width=2)
txt(dx+34, dy+30, "IDX / FINGERPRINT", 18, TEXT, True)
txt(dx+1090, dy+31, "▦   ⎇   ↻", 23, MUTED)
chip(dx+34, dy+92, "WEEKLY SNAPSHOT")
chip(dx+208, dy+92, "CSV CONNECTED", GREEN)
txt(dx+380, dy+100, "KOMPAS100  •  100 constituents", 15, MUTED)
txt(dx+34, dy+158, "Every stock has a fingerprint.", 42, TEXT, True)
txt(dx+34, dy+215, "15 fitur, 5 segmen, dan benchmark subsektor yang bisa ditelusuri.", 18, MUTED)
rr((dx+34, dy+265, dx+1185, dy+325), fill=SURFACE, radius=12)
txt(dx+57, dy+283, "⌕", 26, MUTED)
txt(dx+94, dy+285, "Cari ticker atau nama perusahaan", 17, MUTED)

# Ranking table
txt(dx+34, dy+374, "BROWSE FINGERPRINTS", 14, ACCENT, True)
txt(dx+34, dy+410, "Ticker", 14, MUTED, True)
txt(dx+430, dy+410, "Duel win rate", 14, MUTED, True)
txt(dx+650, dy+410, "Dominant segment", 14, MUTED, True)
txt(dx+1015, dy+410, "Coverage", 14, MUTED, True)
rows = [
    ("BBCA", "Bank Central Asia", 78.6, "Financial", 96, GREEN),
    ("PANI", "Pantai Indah Kapuk Dua", 64.1, "Performance", 92, ACCENT),
    ("PTRO", "Petrosea", 61.8, "Growth", 89, AMBER),
    ("BBRI", "Bank Rakyat Indonesia", 58.3, "Dividend", 97, GREEN),
]
for i,(ticker,name,score,axis,cov,color) in enumerate(rows):
    y=dy+450+i*108
    rr((dx+25,y-10,dx+1195,y+82), fill="#181619" if i%2==0 else BG, outline="#29262B", radius=12)
    txt(dx+44,y+3,ticker,20,TEXT,True); txt(dx+44,y+34,name,13,MUTED)
    txt(dx+430,y+7,f"{score:.1f}%",26,color,True); progress(dx+430,y+51,160,score/100,color)
    chip(dx+650,y+4,axis,color)
    txt(dx+1060,y+17,f"{cov}%",20,TEXT,True,anchor="mm")

# Sector evidence
txt(dx+34, dy+910, "INDONESIA ECONOMIC SECTORS", 14, ACCENT, True)
cards = [
    ("Financials", "Banks", "median P/E  9.38", "48 companies"),
    ("Properties & Real Estate", "Properties & Real Estate", "median P/E  6.57", "90 companies"),
    ("Energy", "Oil, Gas & Coal", "median P/E  7.92", "73 companies"),
]
for i,(sector,sub,pe,n) in enumerate(cards):
    x=dx+34+i*382
    rr((x,dy+950,x+360,dy+1108),fill=SURFACE,radius=14)
    txt(x+18,dy+970,sector,17,TEXT,True)
    txt(x+18,dy+1004,sub,14,MUTED)
    txt(x+18,dy+1044,pe,17,ACCENT,True)
    txt(x+18,dy+1076,n,13,MUTED)

# Mobile detail surface
mx, my, mw, mh = 1300, 40, 560, 1160
rr((mx,my,mx+mw,my+mh), fill=BG, outline="#29262B", radius=34, width=2)
txt(mx+30,my+32,"‹",34,MUTED); txt(mx+78,my+39,"IDX / FINGERPRINT",16,TEXT,True)
chip(mx+30,my+94,"DEMO VALUES",AMBER)
chip(mx+175,my+94,"CSV CONNECTED",GREEN)
txt(mx+30,my+156,"BBCA",42,TEXT,True)
txt(mx+30,my+208,"Bank Central Asia · Financials / Banks",15,MUTED)
rr((mx+30,my+254,mx+530,my+410),fill=SURFACE,radius=16)
txt(mx+52,my+275,"DUEL WIN RATE",13,MUTED,True)
txt(mx+52,my+312,"78.6%",42,GREEN,True)
txt(mx+275,my+279,"DOMINANT",13,MUTED,True)
chip(mx+275,my+315,"FINANCIAL",GREEN)
txt(mx+52,my+370,"78 menang · 21 kalah · 4 seri",14,MUTED)

txt(mx+30,my+452,"WHERE THE WINS CAME FROM",13,ACCENT,True)
axes=[("Valuation",.62,ACCENT),("Growth",.47,AMBER),("Financial",.84,GREEN),("Performance",.55,ACCENT),("Dividend",.73,GREEN)]
for i,(name,pct,color) in enumerate(axes):
    y=my+494+i*67
    txt(mx+30,y,name,15,TEXT,True); txt(mx+490,y,f"{int(pct*100)}",14,MUTED,True,anchor="ra")
    progress(mx+30,y+30,470,pct,color)

rr((mx+30,my+840,mx+530,my+1090),fill=SURFACE,radius=16)
txt(mx+50,my+862,"P/E SUBSECTOR EVIDENCE",13,ACCENT,True)
txt(mx+50,my+903,"BBCA P/E",14,MUTED); txt(mx+480,my+903,"13.36×",18,TEXT,True,anchor="ra")
txt(mx+50,my+942,"Median Banks",14,MUTED); txt(mx+480,my+942,"9.38×",18,TEXT,True,anchor="ra")
d.line((mx+50,my+982,mx+480,my+982),fill=BORDER,width=1)
txt(mx+50,my+1001,"Relative valuation",14,MUTED); txt(mx+480,my+1001,"1.42×",24,ACCENT,True,anchor="ra")
txt(mx+50,my+1045,"Source: exact subsector statistics · weekly CSV",12,MUTED)

txt(50,1211,"Code-derived visual preview · responsive desktop + mobile · sample values only",13,MUTED)
OUT.parent.mkdir(parents=True, exist_ok=True)
im.save(OUT, quality=96)
print(OUT)

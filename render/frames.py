"""酒の博物誌 雰囲気試作: 静止画3枚 (1920x1080)"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
from scipy import ndimage as ndi

W, H = 1920, 1080
rng = np.random.default_rng(7)
from paths import ROOT, POSES, OUT, find_font
SERIF_B = find_font('Bold')
SERIF_M = find_font('Medium')
SERIF_R = find_font('Regular')
INK = (38, 34, 30)
PAPER = np.array([236, 227, 207], float)
SHU = (178, 68, 48)        # 朱
AI = (44, 72, 112)         # 藍
OCHRE = (196, 150, 62)


def font(p, s):
    return ImageFont.truetype(p, s, index=0)


# ---------- 和紙 ----------
def washi(tint=(0, 0, 0)):
    base = np.ones((H, W, 3)) * (PAPER + np.array(tint))
    # 低周波のムラ
    n = ndi.gaussian_filter(rng.normal(0, 1, (H // 8, W // 8)), 6)
    n = np.kron(n, np.ones((8, 8)))[:H, :W]
    base += (n / n.std() * 5)[..., None]
    # 細かい粒
    base += rng.normal(0, 2.2, (H, W))[..., None]
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    # 繊維
    fib = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(fib)
    for _ in range(1600):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        a = rng.uniform(0, np.pi)
        L = rng.uniform(8, 40)
        pts = [(x + np.cos(a) * t + rng.normal(0, 1.2), y + np.sin(a) * t + rng.normal(0, 1.2)) for t in np.linspace(0, L, 6)]
        d.line(pts, fill=int(rng.uniform(25, 70)), width=1)
    fib = fib.filter(ImageFilter.GaussianBlur(0.6))
    dark = Image.new('RGB', (W, H), (150, 135, 110))
    img = Image.composite(dark, img, fib.point(lambda v: v * 0.35))
    # 周辺減光
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    v = np.clip(1 - 0.18 * np.clip(r - 0.55, 0, None) ** 1.4 * 2.2, 0.8, 1)
    arr = np.asarray(img).astype(float) * v[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def ink_layer(img, mask, color=INK, opacity=1.0):
    """mask(L) の形で墨を置く。紙の質感を残すため乗算気味に"""
    col = Image.new('RGB', img.size, color)
    m = mask.point(lambda v: int(v * opacity))
    return Image.composite(col, img, m)


def brush_line(d, pts, w0, w1, fill=255):
    """太さが変わる筆線"""
    n = len(pts)
    for i in range(n - 1):
        t = i / max(1, n - 2)
        w = w0 + (w1 - w0) * t
        w = max(1, int(round(w)))
        d.line([pts[i], pts[i + 1]], fill=fill, width=w)
        r = w / 2
        d.ellipse([pts[i][0] - r, pts[i][1] - r, pts[i][0] + r, pts[i][1] + r], fill=fill)


# ---------- キャラ ----------
def host(pose, height):
    c = Image.open(POSES / f'{pose}.png')
    s = height / c.height
    c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
    rgb, a = c.convert('RGB'), c.getchannel('A')
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.6, percent=60, threshold=2))
    # 紙色に寄せる (少し温かく、少し彩度を落とす)
    arr = np.asarray(rgb).astype(float)
    g = arr.mean(2, keepdims=True)
    arr = arr * 0.9 + g * 0.1
    arr = arr * np.array([1.0, 0.985, 0.95])
    rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    rgb.putalpha(a)
    return rgb


MARGIN = 0.06   # キャラは画面端から6%以上離す (CLAUDE.md)


def place_host(img, pose, height, cx, foot_y, shadow=True):
    h = host(pose, height)
    # ポーズによって腕の広がりが違うので、絵の実際の範囲で左右の余白を守る
    bx0, _, bx1, _ = h.getchannel('A').getbbox()
    lo, hi = W * MARGIN, W * (1 - MARGIN)
    left, right = cx - h.width / 2 + bx0, cx - h.width / 2 + bx1
    if right > hi:
        cx -= right - hi
    elif left < lo:
        cx += lo - left
    x, y = int(cx - h.width / 2), int(foot_y - h.height)
    if shadow:
        sh = Image.new('L', img.size, 0)
        ImageDraw.Draw(sh).ellipse([cx - h.width * 0.38, foot_y - 16, cx + h.width * 0.38, foot_y + 14], fill=90)
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        img = ink_layer(img, sh, (90, 75, 55), 0.7)
    img = img.copy()
    img.paste(h, (x, y), h)
    return img, (x, y, x + h.width, y + h.height)


# ---------- 字幕 ----------
SUB_FONT = font(SERIF_B, 54)
BAND_TOP = 908


def paper_unify(img):
    g = rng.normal(0, 1, (H, W))
    g = ndi.gaussian_filter(g, .8) * 3.0
    arr = np.asarray(img).astype(float) + g[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def subtitle(img, lines):
    img = paper_unify(img)
    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    # 下部帯: 墨色の半透明 + 上端だけ細い朱線
    d.rectangle([0, BAND_TOP, W, H], fill=(28, 24, 20, 205))
    d.rectangle([0, BAND_TOP, W, BAND_TOP + 3], fill=SHU + (230,))
    lh = 70
    total = lh * len(lines)
    y0 = BAND_TOP + (H - BAND_TOP - total) / 2 - 4
    for i, t in enumerate(lines):
        tw = d.textlength(t, font=SUB_FONT)
        d.text(((W - tw) / 2, y0 + i * lh), t, font=SUB_FONT, fill=(246, 238, 220, 255))
    return Image.alpha_composite(img.convert('RGBA'), over).convert('RGB')


def vertical_text(d, x, y, text, f, fill, spacing=1.08):
    s = f.size
    for i, ch in enumerate(text):
        if ch in '、。':
            d.text((x + s * 0.55, y + i * s * spacing - s * 0.55), ch, font=f, fill=fill)
        elif ch in '？':
            tw = d.textlength(ch, font=f)
            d.text((x + (s - tw) / 2, y + i * s * spacing), ch, font=f, fill=fill)
        else:
            tw = d.textlength(ch, font=f)
            d.text((x + (s - tw) / 2, y + i * s * spacing), ch, font=f, fill=fill)


def seal(img, x, y, text, size=64):
    """朱の落款風ラベル"""
    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.rounded_rectangle([x, y, x + size, y + size * len(text) * 0.92 + 18], radius=6, fill=SHU + (225,))
    f = font(SERIF_B, int(size * 0.62))
    for i, ch in enumerate(text):
        tw = d.textlength(ch, font=f)
        d.text((x + (size - tw) / 2, y + 10 + i * size * 0.92 - 4), ch, font=f, fill=(246, 236, 220, 255))
    # かすれ
    m = Image.fromarray((rng.random((H, W)) > 0.93).astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(0.7))
    a = ImageChops.subtract(over.getchannel('A'), m.point(lambda v: v // 2))
    over.putalpha(a)
    return Image.alpha_composite(img.convert('RGBA'), over).convert('RGB')


# ================= 場面1: 問い =================
def scene_question():
    img = washi()
    # 大きな利き猪口 (蛇の目) を墨と藍で
    cx, cy = 760, 560
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    # 器の外形 (側面)
    rx, ry = 250, 78
    body = [(cx - rx, cy)]
    for t in np.linspace(0, 1, 40):
        x = cx - rx + 2 * rx * t
        y = cy + 230 * np.sin(np.pi * t) ** 0.8 * 0.95
        body.append((x, y))
    d.polygon(body, fill=255)
    m_body = m.filter(ImageFilter.GaussianBlur(1))
    img = ink_layer(img, m_body, (244, 240, 230), 1.0)        # 白磁
    # 側面の陰
    sh = Image.new('L', (W, H), 0)
    ImageDraw.Draw(sh).ellipse([cx + 40, cy - 40, cx + 330, cy + 260], fill=110)
    sh = ImageChops.multiply(sh.filter(ImageFilter.GaussianBlur(50)), m_body)
    img = ink_layer(img, sh, (160, 150, 135), 0.8)
    # 口 (楕円) と酒
    lip = Image.new('L', (W, H), 0)
    ImageDraw.Draw(lip).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    img = ink_layer(img, lip, (250, 248, 242), 1.0)
    inner = Image.new('L', (W, H), 0)
    ImageDraw.Draw(inner).ellipse([cx - rx + 22, cy - ry + 10, cx + rx - 22, cy + ry - 10], fill=255)
    img = ink_layer(img, inner.filter(ImageFilter.GaussianBlur(1.2)), (238, 236, 226), 1.0)
    # 蛇の目
    ring = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(ring)
    for k, (a, b) in enumerate([(150, 46), (92, 28)]):
        dr.ellipse([cx - a, cy - b + 6, cx + a, cy + b + 6], outline=255, width=16)
    img = ink_layer(img, ring.filter(ImageFilter.GaussianBlur(1.6)), AI, 0.85)
    # 酒面のゆらぎ (光)
    gl = Image.new('L', (W, H), 0)
    ImageDraw.Draw(gl).arc([cx - 190, cy - 52, cx + 120, cy + 40], 200, 280, fill=255, width=5)
    img = ink_layer(img, gl.filter(ImageFilter.GaussianBlur(2)), (255, 255, 255), 0.8)
    # 墨の輪郭 (筆)
    ol = Image.new('L', (W, H), 0)
    do = ImageDraw.Draw(ol)
    ell = [(cx + rx * np.cos(t), cy + ry * np.sin(t)) for t in np.linspace(0, 2 * np.pi, 400)]
    brush_line(do, ell, 3, 6)
    side = [(cx - rx + 2 * rx * t, cy + 230 * np.sin(np.pi * t) ** 0.8 * 0.95) for t in np.linspace(0, 1, 60)]
    brush_line(do, side, 6, 3)
    img = ink_layer(img, ol.filter(ImageFilter.GaussianBlur(0.8)), INK, 0.9)

    # 香りの筆線 (猪口から立ちのぼる)
    sm = Image.new('L', (W, H), 0)
    ds = ImageDraw.Draw(sm)
    for k, ox in enumerate([-60, 30, 110]):
        pts = [(cx + ox + 34 * np.sin(t * 2.6 + k), cy - 110 - t * 75) for t in np.linspace(0, 3.2, 50)]
        brush_line(ds, pts, 7, 1)
    img = ink_layer(img, sm.filter(ImageFilter.GaussianBlur(2.2)), (120, 105, 85), 0.55)

    # 薄墨のリンゴ (香りの「気配」として、にじませる)
    ap = Image.new('L', (W, H), 0)
    da = ImageDraw.Draw(ap)
    ax, ay = 900, 210
    da.ellipse([ax - 95, ay - 80, ax + 95, ay + 95], fill=255)
    ap = ap.filter(ImageFilter.GaussianBlur(10))
    img = ink_layer(img, ap, SHU, 0.32)
    ao = Image.new('L', (W, H), 0)
    dao = ImageDraw.Draw(ao)
    brush_line(dao, [(ax - 90 * np.cos(t), ay + 8 + 88 * np.sin(t) * (1 if np.sin(t) > 0 else 0.92)) for t in np.linspace(-1.35, 4.6, 70)], 5, 2)
    brush_line(dao, [(ax + 2, ay - 74), (ax + 8, ay - 100), (ax + 14, ay - 118)], 5, 3)
    leaf=[(ax+12+70*t, ay-104-22*np.sin(np.pi*t)) for t in np.linspace(0,1,20)]+[(ax+12+70*t, ay-104+10*np.sin(np.pi*t)) for t in np.linspace(1,0,20)]
    brush_line(dao, leaf, 3, 2)
    img = ink_layer(img, ao.filter(ImageFilter.GaussianBlur(1)), INK, 0.55)

    # 縦書き見出し
    d = ImageDraw.Draw(img)
    f = font(SERIF_B, 80)
    vertical_text(d, 290, 130, '果物ゼロの酒に、', f, INK)
    vertical_text(d, 180, 130, 'リンゴの香り？', f, SHU)
    img = seal(img, 56, 56, '酒の博物誌', 52)

    img, box = place_host(img, 'think', 760, 1420, 900)
    img = subtitle(img, ['原料は、米と米麹と水。', 'なのに、果物みたいな香りがすることがある。'])
    return img, box


# ================= 場面2: 酒蔵 =================
def ridge(n, base, amp, seed):
    r = np.random.default_rng(seed)
    y = np.zeros(n)
    for k, a in [(3, 1), (7, .5), (17, .25), (41, .12)]:
        ph = r.uniform(0, 2 * np.pi)
        y += a * np.sin(np.linspace(0, k * np.pi, n) + ph)
    return base - amp * y


def stain(mask, strength, scale, seed):
    """淡彩のムラ: mask 内に低周波ノイズの濃淡"""
    r = np.random.default_rng(seed)
    n = ndi.gaussian_filter(r.normal(0, 1, (H // 4, W // 4)), scale)
    n = np.kron(n, np.ones((4, 4)))[:H, :W]
    n = (n - n.min()) / (n.max() - n.min())
    m = np.asarray(mask).astype(float) / 255 * n * 255 * strength
    return Image.fromarray(np.clip(m, 0, 255).astype(np.uint8))


def wobble(pts, amp=1.6, seed=0):
    r = np.random.default_rng(abs(int(seed)))
    out = []
    for x, y in pts:
        out.append((x + r.normal(0, amp * .5), y + r.normal(0, amp * .5)))
    return out


def seg(p0, p1, n=24):
    return [(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t) for t in np.linspace(0, 1, n)]


def kura(img, x0, y0, w, h, roof_h, sc=1.0, op=1.0, seed=0):
    # 白壁 (少し黄ばんだ漆喰 + しみ)
    wall = Image.new('L', (W, H), 0)
    ImageDraw.Draw(wall).rectangle([x0, y0, x0 + w, y0 + h], fill=255)
    img = ink_layer(img, wall, (238, 232, 218), op)
    img = ink_layer(img, stain(wall, .9, 10, seed), (190, 178, 150), .35 * op)
    # 軒下の影
    sh = Image.new('L', (W, H), 0)
    ImageDraw.Draw(sh).rectangle([x0, y0, x0 + w, y0 + 40 * sc], fill=255)
    img = ink_layer(img, ImageChops.multiply(sh.filter(ImageFilter.GaussianBlur(18 * sc)), wall), (120, 110, 96), .45 * op)
    # なまこ壁: 平瓦は青灰、目地は漆喰。目地は細め・にじみ
    nh = int(h * .36)
    ny = y0 + h - nh
    nm = Image.new('L', (W, H), 0)
    ImageDraw.Draw(nm).rectangle([x0, ny, x0 + w, y0 + h], fill=255)
    img = ink_layer(img, nm, (84, 90, 98), op)
    img = ink_layer(img, stain(nm, 1, 6, seed + 1), (50, 54, 60), .5 * op)
    ln = Image.new('L', (W, H), 0)
    dl = ImageDraw.Draw(ln)
    step = 46 * sc
    k = -nh
    while k < w + nh:
        for p0, p1 in [((x0 + k, ny), (x0 + k + nh, y0 + h)), ((x0 + k + nh, ny), (x0 + k, y0 + h))]:
            brush_line(dl, wobble(seg(p0, p1, 18), 1.2, int(k)), 6 * sc, 5 * sc)
        k += step
    ln = ImageChops.multiply(ln, nm).filter(ImageFilter.GaussianBlur(1.2))
    img = ink_layer(img, ln, (222, 216, 202), .92 * op)
    # 窓 (格子付き)
    for fx in [.22, .62]:
        wx, wy = x0 + w * fx, y0 + h * .2
        ww, wh = 70 * sc, 56 * sc
        m = Image.new('L', (W, H), 0)
        ImageDraw.Draw(m).rectangle([wx, wy, wx + ww, wy + wh], fill=255)
        img = ink_layer(img, m, (52, 46, 40), op)
        g = Image.new('L', (W, H), 0)
        dg = ImageDraw.Draw(g)
        for i in range(1, 4):
            dg.line([(wx + ww * i / 4, wy + 3), (wx + ww * i / 4, wy + wh - 3)], fill=255, width=max(2, int(4 * sc)))
        img = ink_layer(img, g, (150, 120, 84), op)
    # 屋根: 本瓦の段を横の筆線で
    ov = w * .06
    rm = Image.new('L', (W, H), 0)
    top_y = y0 - roof_h
    poly = [(x0 - ov * .6, top_y), (x0 + w + ov * .6, top_y)]
    poly += [(x0 + w + ov - (w + 2 * ov) * t, y0 + 6 * sc - 14 * sc * (abs(t - .5) * 2) ** 2) for t in np.linspace(0, 1, 40)]
    ImageDraw.Draw(rm).polygon(poly, fill=255)
    img = ink_layer(img, rm, (58, 58, 64), op)
    img = ink_layer(img, stain(rm, 1, 5, seed + 2), (30, 30, 34), .55 * op)
    rows = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(rows)
    nrow = 6
    for i in range(1, nrow + 1):
        t = i / (nrow + .4)
        yy = top_y + roof_h * t
        pts = [(x0 - ov + (w + 2 * ov) * u, yy + 10 * sc * t * (abs(u - .5) * 2) ** 2 * -1) for u in np.linspace(0, 1, 60)]
        brush_line(dr, wobble(pts, 1, i + seed), 3 * sc, 3 * sc)
    img = ink_layer(img, ImageChops.multiply(rows, rm).filter(ImageFilter.GaussianBlur(.8)), (150, 150, 156), .55 * op)
    # 棟 (上端の太い墨)
    rid = Image.new('L', (W, H), 0)
    brush_line(ImageDraw.Draw(rid), wobble(seg((x0 - ov * .7, top_y), (x0 + w + ov * .7, top_y), 60), 1, seed), 14 * sc, 14 * sc)
    img = ink_layer(img, rid.filter(ImageFilter.GaussianBlur(.8)), (36, 36, 40), op)
    # 墨の輪郭 (壁)
    ol = Image.new('L', (W, H), 0)
    do = ImageDraw.Draw(ol)
    for p0, p1 in [((x0, y0 + 8 * sc), (x0, y0 + h)), ((x0 + w, y0 + 8 * sc), (x0 + w, y0 + h)), ((x0, ny), (x0 + w, ny)), ((x0 - 6, y0 + h), (x0 + w + 6, y0 + h))]:
        brush_line(do, wobble(seg(p0, p1, 40), 1.5, int(p0[0])), 4 * sc, 2.5 * sc)
    img = ink_layer(img, ol.filter(ImageFilter.GaussianBlur(.9)), INK, .8 * op)
    return img


def scene_kura():
    img = washi(tint=(-5, -2, 5))      # わずかに冬の寒色
    for i, (base, amp, op, blur) in enumerate([(420, 70, .16, 9), (510, 55, .26, 5), (590, 38, .36, 3)]):
        ys = ridge(W, base, amp, 10 + i)
        m = Image.new('L', (W, H), 0)
        ImageDraw.Draw(m).polygon([(0, H)] + [(x, ys[x]) for x in range(0, W, 4)] + [(W, H)], fill=255)
        grad = Image.fromarray(np.tile(np.clip(1 - (np.arange(H) - base + 60) / 300, 0, 1)[:, None] * 255, (1, W)).astype(np.uint8))
        m = ImageChops.multiply(m, grad).filter(ImageFilter.GaussianBlur(blur))
        img = ink_layer(img, m, (70, 78, 88), op)

    img = kura(img, 1030, 540, 250, 170, 50, .55, .5, seed=3)   # 奥の蔵 (霞む)
    # 奥と手前の間に霞
    mist = Image.fromarray(np.tile(np.clip(1 - np.abs(np.arange(H) - 700) / 90, 0, 1)[:, None] * 255, (1, W)).astype(np.uint8))
    img = ink_layer(img, mist.filter(ImageFilter.GaussianBlur(10)), (236, 232, 222), .55)
    img = kura(img, 230, 410, 760, 410, 120, 1.0, seed=7)       # 手前の蔵

    # 杉玉 (軒先から)
    sx, sy = 880, 500
    sg = Image.new('L', (W, H), 0)
    ImageDraw.Draw(sg).line([(sx, 412), (sx, sy - 52)], fill=255, width=4)
    img = ink_layer(img, sg, INK, .9)
    ball = Image.new('L', (W, H), 0)
    ImageDraw.Draw(ball).ellipse([sx - 54, sy - 54, sx + 54, sy + 54], fill=255)
    img = ink_layer(img, ball.filter(ImageFilter.GaussianBlur(2.5)), (112, 102, 58), 1)
    tex = Image.new('L', (W, H), 0)
    dtx = ImageDraw.Draw(tex)
    for _ in range(1100):
        a, r = rng.uniform(0, 2 * np.pi), 54 * np.sqrt(rng.uniform(0, 1))
        px, py = sx + r * np.cos(a), sy + r * np.sin(a)
        dtx.line([(px, py), (px + rng.normal(0, 5), py + rng.normal(0, 5))], fill=255, width=2)
    img = ink_layer(img, ImageChops.multiply(tex, ball.filter(ImageFilter.GaussianBlur(2))), (62, 56, 30), .5)
    hl = Image.new('L', (W, H), 0)
    ImageDraw.Draw(hl).ellipse([sx - 36, sy - 40, sx + 2, sy - 6], fill=255)
    img = ink_layer(img, hl.filter(ImageFilter.GaussianBlur(14)), (186, 172, 116), .55)

    # 地面
    gm = Image.new('L', (W, H), 0)
    dgm = ImageDraw.Draw(gm)
    for k in range(16):
        y = 828 + k * 5 + rng.normal(0, 2)
        dgm.line([(rng.uniform(0, 250), y), (rng.uniform(1400, W), y + rng.normal(0, 4))], fill=int(rng.uniform(60, 160)), width=3)
    img = ink_layer(img, gm.filter(ImageFilter.GaussianBlur(3)), (110, 100, 86), .45)

    # 雪 (大小・ぼけ違いで奥行き)
    for cnt, rr, bl, op in [(220, (1.2, 2.6), 1.2, .6), (60, (3, 6), 2.5, .8)]:
        sn = Image.new('L', (W, H), 0)
        dsn = ImageDraw.Draw(sn)
        for _ in range(cnt):
            x, y, r = rng.uniform(0, W), rng.uniform(0, 900), rng.uniform(*rr)
            dsn.ellipse([x - r, y - r, x + r, y + r], fill=255)
        img = ink_layer(img, sn.filter(ImageFilter.GaussianBlur(bl)), (252, 252, 250), op)

    img = seal(img, 56, 56, '酒の博物誌', 52)
    img, box = place_host(img, 'point', 700, 1555, 900)
    img = subtitle(img, ['答えを探しに、酒蔵の中へ。'])
    return img, box


# ================= 場面3: 科学図解 =================
SCIENCE_SUB = ['発酵の途中で、酵母が香りの成分をつくる。', 'それが「果物の香り」の正体。']
# 図解の札と矢印の範囲 (強調しないほうを薄くするとき用)
SCIENCE_ITEMS = {'cap': {'card': 360, 'arrow': (520, 360, 716, 548)},
                 'iso': {'card': 760, 'arrow': (520, 606, 716, 762)}}


def _fade_item(img, plain, item, amount=.62):
    """札と矢印を、描く前の紙 (plain) に寄せて薄くする"""
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    y = SCIENCE_ITEMS[item]['card']
    d.rounded_rectangle([720, y - 100, 1380, y + 100], radius=16, fill=255)
    d.rectangle(SCIENCE_ITEMS[item]['arrow'], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * amount))
    return Image.composite(plain, img, m)


def scene_science(pose='book', highlight=None, sub=SCIENCE_SUB):
    """pose=None でキャラなし、sub=None で字幕なし。
    highlight='cap' / 'iso' で、その札に朱の帯を付け、もう一方の札と矢印を薄くする"""
    img = washi()
    d = ImageDraw.Draw(img)
    # 見出し
    hf = font(SERIF_B, 60)
    d.text((140, 92), '香りをつくるのは「酵母」', font=hf, fill=INK)
    d.line([(140, 180), (820, 180)], fill=SHU, width=4)

    # 酵母 (出芽している楕円細胞, 薄墨の淡彩)
    def cell(img, cx, cy, rx, ry, ang=0):
        m = Image.new('L', (W, H), 0)
        ImageDraw.Draw(m).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
        m = m.rotate(ang, center=(cx, cy))
        img = ink_layer(img, m.filter(ImageFilter.GaussianBlur(3)), (214, 196, 150), 0.75)
        inner = Image.new('L', (W, H), 0)
        ImageDraw.Draw(inner).ellipse([cx - rx * .35, cy - ry * .3, cx + rx * .25, cy + ry * .3], fill=255)
        inner = inner.rotate(ang, center=(cx, cy))
        img = ink_layer(img, inner.filter(ImageFilter.GaussianBlur(6)), (176, 150, 96), 0.45)
        o = Image.new('L', (W, H), 0)
        ImageDraw.Draw(o).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=255, width=5)
        o = o.rotate(ang, center=(cx, cy))
        return ink_layer(img, o.filter(ImageFilter.GaussianBlur(0.9)), INK, 0.85)

    plain = img.copy()
    ycx, ycy = 330, 560
    img = cell(img, ycx, ycy, 150, 125, 10)
    img = cell(img, ycx + 150, ycy - 104, 62, 52, 30)       # 芽
    d = ImageDraw.Draw(img)
    lf = font(SERIF_B, 50)
    sf = font(SERIF_R, 34)
    t = '酵母'
    d.text((ycx - d.textlength(t, font=lf) / 2, ycy + 160), t, font=lf, fill=INK)
    t = '（発酵をになう微生物）'
    d.text((ycx - d.textlength(t, font=sf) / 2, ycy + 226), t, font=sf, fill=(90, 80, 68))

    # 矢印 (筆)
    def arrow(img, p0, p1):
        m = Image.new('L', (W, H), 0)
        dm = ImageDraw.Draw(m)
        pts = [(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t + 18 * np.sin(np.pi * t)) for t in np.linspace(0, 1, 30)]
        brush_line(dm, pts, 7, 4)
        ang = np.arctan2(p1[1] - pts[-3][1], p1[0] - pts[-3][0])
        for s in (2.55, -2.55):
            dm.line([p1, (p1[0] + 34 * np.cos(ang + s), p1[1] + 34 * np.sin(ang + s))], fill=255, width=6)
        return ink_layer(img, m.filter(ImageFilter.GaussianBlur(0.8)), SHU, 0.9)

    img = arrow(img, (530, 520), (700, 380))
    img = arrow(img, (530, 620), (700, 740))

    # 成分カード (左: 名前、右: 果物の淡彩)
    def card(img, y, name, note, fruit):
        x0, x1 = 730, 1370
        ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
        do = ImageDraw.Draw(ov)
        do.rounded_rectangle([x0, y - 90, x1, y + 90], radius=10, fill=(250, 245, 232, 150), outline=INK + (200,), width=3)
        img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
        d = ImageDraw.Draw(img)
        d.text((x0 + 36, y - 66), name, font=font(SERIF_B, 52), fill=INK)
        d.text((x0 + 38, y + 14), note, font=font(SERIF_M, 36), fill=(96, 84, 70))
        # 果物
        fx, fy = x1 - 125, y
        if fruit == 'apple':
            m = Image.new('L', (W, H), 0)
            ImageDraw.Draw(m).ellipse([fx - 52, fy - 44, fx + 52, fy + 54], fill=255)
            img = ink_layer(img, m.filter(ImageFilter.GaussianBlur(4)), SHU, 0.55)
            o = Image.new('L', (W, H), 0)
            do = ImageDraw.Draw(o)
            do.ellipse([fx - 52, fy - 44, fx + 52, fy + 54], outline=255, width=3)
            brush_line(do, [(fx, fy - 40), (fx + 6, fy - 62)], 4, 3)
            brush_line(do, [(fx+6+40*t, fy-58-14*np.sin(np.pi*t)) for t in np.linspace(0,1,14)]+[(fx+6+40*t, fy-58+7*np.sin(np.pi*t)) for t in np.linspace(1,0,14)], 3, 2)
            img = ink_layer(img, o.filter(ImageFilter.GaussianBlur(0.8)), INK, 0.7)
        else:
            oc, ic = (fx, fy - 70), (fx + 3, fy - 96)
            outer = [(oc[0] + 100 * np.cos(t), oc[1] + 100 * np.sin(t)) for t in np.radians(np.linspace(32, 148, 40))]
            inner = [(ic[0] + 106 * np.cos(t), ic[1] + 106 * np.sin(t)) for t in np.radians(np.linspace(144, 36, 40))]
            m = Image.new('L', (W, H), 0)
            ImageDraw.Draw(m).polygon(outer + inner, fill=255)
            img = ink_layer(img, m.filter(ImageFilter.GaussianBlur(3)), OCHRE, .75)
            o = Image.new('L', (W, H), 0)
            do = ImageDraw.Draw(o)
            brush_line(do, outer, 3, 3)
            brush_line(do, inner, 3, 3)
            brush_line(do, [inner[-1], (inner[-1][0] + 10, inner[-1][1] - 14), (inner[-1][0] + 16, inner[-1][1] - 22)], 6, 5)
            img = ink_layer(img, o.filter(ImageFilter.GaussianBlur(.8)), INK, .7)
        return img

    img = card(img, 360, 'カプロン酸エチル', 'リンゴのような香り', 'apple')
    img = card(img, 760, '酢酸イソアミル', 'バナナのような香り', 'banana')
    if highlight:
        other = 'iso' if highlight == 'cap' else 'cap'
        img = _fade_item(img, plain, other)
        y = SCIENCE_ITEMS[highlight]['card']
        ImageDraw.Draw(img).rectangle([730, y - 89, 741, y + 89], fill=SHU)

    img = seal(img, 56, 56, '酒の博物誌', 52)
    box = None
    if pose:
        img, box = place_host(img, pose, 700, 1610, 900)
    if sub:
        img = subtitle(img, sub)
    return img, box


if __name__ == '__main__':
    import json
    boxes = {}
    for name, fn in [('01_question', scene_question), ('02_kura', scene_kura), ('03_science', scene_science)]:
        im, box = fn()
        im.save(OUT / f'{name}.png')
        boxes[name] = box
        print(name, box)
    json.dump(boxes, open(OUT / 'host_boxes.json', 'w'))

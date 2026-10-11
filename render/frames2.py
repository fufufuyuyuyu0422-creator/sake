"""第2弾: 猪口描き直し / 地図ピン→ズーム / ミクロ世界"""
import json, os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from scipy import ndimage as ndi
from paths import ROOT, OUT, MAPDATA
from frames import (W, H, INK, SHU, AI, OCHRE, SERIF_B, SERIF_M, SERIF_R, font, washi, ink_layer,
                    brush_line, place_host, host, subtitle, vertical_text, seal, paper_unify)

rng = np.random.default_rng(11)

# 場面ごとの乱数の開始位置。和紙・落款のかすれ (frames.rng) と猪口・ミクロ (rng) は
# 共有の乱数なので、前に描いた場面で結果が変わってしまう。合格見本 (docs/approved_look/) を
# 「q → map → micro」の順で書き出したときの位置に合わせ、単独で書き出しても見本と同じ画にする。
#   場面: (frames.rng(7) を進める数, rng(11) を進める数)
#   science は frames.py の「問い(旧) → 酒蔵 → 図解」の順で書き出した見本 (03_science.png) に合わせた位置。
SCENE_RNG = {'q': (0, 0), 'map': (6372942, 2119048), 'micro': (21132059, 2119048),
             'science': (12751515, 0)}


def reset_rng(scene):
    import frames
    a, b = SCENE_RNG[scene]
    frames.rng.bit_generator.state = np.random.PCG64(7).advance(a).state
    rng.bit_generator.state = np.random.PCG64(11).advance(b).state


def L():
    return Image.new('L', (W, H), 0)


def ell(cx, cy, rx, ry):
    return [cx - rx, cy - ry, cx + rx, cy + ry]


# ================= 場面1 改: 蛇の目の利き猪口 (キャラなし) =================
def kikichoko(img, cx, cy, R):
    sin_t, cos_t = 0.80, 0.60           # 見下ろし角 約53°
    ry = R * sin_t
    Ho, Rb = R * 1.05, R * 0.86          # 外側の高さ・底径
    drop_o = Ho * cos_t
    Rf, Hf = R * 0.66, R * 0.07          # 高台
    # --- 外形シルエット ---
    sil = L()
    d = ImageDraw.Draw(sil)
    d.ellipse(ell(cx, cy, R, ry), fill=255)
    side = [(cx - R, cy)]
    for t in np.linspace(0, 1, 30):     # 左側面 (わずかにふくらむ)
        side.append((cx - R + (R - Rb) * t - 8 * np.sin(np.pi * t), cy + drop_o * t))
    for a in np.linspace(np.pi, 0, 60):  # 底の手前半分
        side.append((cx + Rb * np.cos(a), cy + drop_o + Rb * sin_t * np.sin(a)))
    for t in np.linspace(1, 0, 30):
        side.append((cx + R - (R - Rb) * t + 8 * np.sin(np.pi * t), cy + drop_o * t))
    d.polygon(side, fill=255)
    # 高台
    d.ellipse(ell(cx, cy + drop_o + Hf * cos_t, Rf, Rf * sin_t), fill=255)
    sil = sil.filter(ImageFilter.GaussianBlur(1))
    # 接地影
    sh = L()
    ImageDraw.Draw(sh).ellipse(ell(cx + 30, cy + drop_o + Hf * cos_t + 18, Rb * 1.15, Rb * sin_t * 0.55), fill=200)
    img = ink_layer(img, sh.filter(ImageFilter.GaussianBlur(26)), (110, 96, 76), .45)
    img = ink_layer(img, sil, (247, 245, 238), 1)
    # 側面の陰 (右側を暗く、釉の淡い青み)
    grad = np.clip((np.arange(W) - (cx - R * .2)) / (R * 1.3), 0, 1) ** 1.4
    gimg = Image.fromarray((np.tile(grad, (H, 1)) * 255).astype(np.uint8))
    body_only = ImageChops.subtract(sil, _ellmask(cx, cy, R, ry))
    img = ink_layer(img, ImageChops.multiply(gimg, body_only).filter(ImageFilter.GaussianBlur(6)), (176, 178, 176), .75)
    hl = L()
    ImageDraw.Draw(hl).rectangle([cx - R * .72, cy + 20, cx - R * .58, cy + drop_o * .8], fill=255)
    img = ink_layer(img, ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(14)), body_only), (255, 255, 255), .8)

    # --- 口の中 ---
    Ri = R - 10
    ryi = Ri * sin_t
    inner = _ellmask(cx, cy, Ri, ryi)
    img = ink_layer(img, inner, (232, 230, 222), 1)            # 内壁
    # 内壁の陰 (奥側の上部が明るく、手前の内側は口縁の陰)
    iw = L()
    ImageDraw.Draw(iw).ellipse(ell(cx, cy - ryi * .55, Ri * .95, ryi * .55), fill=255)
    img = ink_layer(img, ImageChops.multiply(iw.filter(ImageFilter.GaussianBlur(30)), inner), (205, 202, 192), .55)
    # 見込み (内底) と蛇の目
    hi = R * .95
    drop_i = hi * cos_t
    Rbot = R * .80
    bot = ImageChops.multiply(_ellmask(cx, cy + drop_i, Rbot, Rbot * sin_t, blur=6), inner)
    img = ink_layer(img, bot, (250, 249, 244), 1)
    rings = L()
    dr = ImageDraw.Draw(rings)
    for r0, r1 in [(.62, .84), (.22, .42)]:
        dr.ellipse(ell(cx, cy + drop_i, Rbot * r1, Rbot * r1 * sin_t), fill=255)
        dr.ellipse(ell(cx, cy + drop_i, Rbot * r0, Rbot * r0 * sin_t), fill=0)
    rings = rings.filter(ImageFilter.GaussianBlur(1.8))
    # 藍のにじみ (濃淡)
    rings_s = ImageChops.multiply(rings, inner)
    img = ink_layer(img, rings_s, AI, .9)
    n = ndi.gaussian_filter(rng.normal(0, 1, (H, W)), 3)
    n = Image.fromarray(np.clip((n / n.std() * 40 + 60), 0, 255).astype(np.uint8))
    img = ink_layer(img, ImageChops.multiply(rings_s, n), (26, 44, 76), .6)
    # 酒 (液面): ほんのり黄みと光の反射
    fill = 0.30
    drop_s = hi * fill * cos_t
    Rs = Ri - (Ri - Rbot) * fill
    surf = ImageChops.multiply(_ellmask(cx, cy + drop_s, Rs, Rs * sin_t, blur=3), inner)
    img = ink_layer(img, surf, (238, 226, 170), .16)
    gl = L()
    ImageDraw.Draw(gl).arc(ell(cx - 20, cy + drop_s - 10, Rs * .82, Rs * sin_t * .78), 200, 255, fill=255, width=7)
    img = ink_layer(img, ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(3)), inner), (255, 255, 255), .9)
    gl2 = L()
    ImageDraw.Draw(gl2).arc(ell(cx + 10, cy + drop_s, Rs * .9, Rs * sin_t * .86), 20, 70, fill=255, width=4)
    img = ink_layer(img, ImageChops.multiply(gl2.filter(ImageFilter.GaussianBlur(2)), inner), (255, 255, 255), .6)
    # 液面の縁 (内壁との境の細い線)
    sl = L()
    ImageDraw.Draw(sl).ellipse(ell(cx, cy + drop_s, Rs, Rs * sin_t), outline=255, width=3)
    img = ink_layer(img, ImageChops.multiply(sl.filter(ImageFilter.GaussianBlur(1.2)), inner), (190, 180, 150), .7)

    # --- 墨の輪郭 ---
    ol = L()
    do = ImageDraw.Draw(ol)
    rim = [(cx + R * np.cos(a), cy + ry * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 400)]
    brush_line(do, rim, 4, 5)
    rimi = [(cx + Ri * np.cos(a), cy + ryi * np.sin(a)) for a in np.linspace(np.pi * 1.02, np.pi * 1.98, 200)]
    brush_line(do, rimi, 2, 2)
    lft = [(cx - R + (R - Rb) * t - 8 * np.sin(np.pi * t), cy + drop_o * t) for t in np.linspace(0, 1, 60)]
    rgt = [(cx + R - (R - Rb) * t + 8 * np.sin(np.pi * t), cy + drop_o * t) for t in np.linspace(0, 1, 60)]
    brush_line(do, lft, 5, 3)
    brush_line(do, rgt, 5, 4)
    btm = [(cx + Rb * np.cos(a), cy + drop_o + Rb * sin_t * np.sin(a)) for a in np.linspace(np.pi, 0, 160)]
    brush_line(do, btm, 3, 4)
    foot = [(cx + Rf * np.cos(a), cy + drop_o + Hf * cos_t + Rf * sin_t * np.sin(a)) for a in np.linspace(np.pi * .92, np.pi * .08, 100)]
    img = ink_layer(img, ol.filter(ImageFilter.GaussianBlur(.9)), INK, .88)
    return img


def _ellmask(cx, cy, rx, ry, blur=0):
    m = L()
    ImageDraw.Draw(m).ellipse(ell(cx, cy, rx, ry), fill=255)
    return m.filter(ImageFilter.GaussianBlur(blur)) if blur else m


Q_HEADING = ('果物ゼロの酒に、', 'リンゴの香り？')
Q_SUB = ['原料は、米と米麹と水。', 'なのに、果物みたいな香りがすることがある。']


def scene_question2(heading=Q_HEADING, sub=Q_SUB, cx=1080):
    """heading=None で縦書き見出しなし、sub=None で字幕なし。cx で猪口(とリンゴ)の横位置"""
    img = washi()
    cy, R = 470, 270
    # 立ちのぼる香り
    sm = L()
    ds = ImageDraw.Draw(sm)
    for k, ox in enumerate([-90, 10, 100]):
        pts = [(cx + ox + 36 * np.sin(t * 2.4 + k * 1.3), cy - 120 - t * 70) for t in np.linspace(0, 3.4, 60)]
        brush_line(ds, pts, 8, 1)
    img = ink_layer(img, sm.filter(ImageFilter.GaussianBlur(2.5)), (130, 112, 88), .45)
    # 香りの先に、にじんだリンゴ
    ax, ay = cx + 250, 150
    ap = L()
    ImageDraw.Draw(ap).ellipse(ell(ax, ay + 8, 78, 72), fill=255)
    img = ink_layer(img, ap.filter(ImageFilter.GaussianBlur(12)), SHU, .30)
    ao = L()
    dao = ImageDraw.Draw(ao)
    brush_line(dao, [(ax + 74 * np.cos(t), ay + 10 + 70 * np.sin(t)) for t in np.linspace(-1.3, 4.5, 80)], 4, 2)
    brush_line(dao, [(ax + 2, ay - 56), (ax + 7, ay - 80), (ax + 12, ay - 96)], 4, 3)
    brush_line(dao, [(ax + 10 + 56 * t, ay - 84 - 18 * np.sin(np.pi * t)) for t in np.linspace(0, 1, 16)] +
               [(ax + 10 + 56 * t, ay - 84 + 8 * np.sin(np.pi * t)) for t in np.linspace(1, 0, 16)], 3, 2)
    img = ink_layer(img, ao.filter(ImageFilter.GaussianBlur(1.2)), INK, .45)

    img = kikichoko(img, cx, cy, R)

    if heading:
        d = ImageDraw.Draw(img)
        f = font(SERIF_B, 84)
        vertical_text(d, 420, 130, heading[0], f, INK)
        vertical_text(d, 300, 130, heading[1], f, SHU)
    img = seal(img, 56, 56, '酒の博物誌', 52)
    if sub:
        img = subtitle(img, sub)
    return img


# ================= 場面4: 地図 (全体→九州→熊本) =================
POLYS = [np.array(p) for p in json.load(open(MAPDATA)) if min(q[1] for q in p) > 29.5]
KUMAMOTO = (130.71, 32.80)          # 熊本市 (熊本県酒造研究所のある市)
COSLAT = np.cos(np.radians(35))


def project(lon, lat, c, s):
    return (W / 2 + (lon - c[0]) * COSLAT * s, 470 - (lat - c[1]) * s)


_PAPER = None


def map_paper():
    global _PAPER
    if _PAPER is None:
        img = washi(tint=(-2, 0, 3))
        # 海: 薄い藍の横はけ
        sea = L()
        dsea = ImageDraw.Draw(sea)
        r = np.random.default_rng(5)
        for y in range(40, 900, 22):
            x0 = r.uniform(-200, 200)
            pts = [(x0 + x, y + 4 * np.sin(x / 90 + y)) for x in range(0, W + 400, 30)]
            dsea.line(pts, fill=int(r.uniform(40, 110)), width=2)
        img = ink_layer(img, sea.filter(ImageFilter.GaussianBlur(1.5)), (90, 110, 130), .22)
        _PAPER = img
    return _PAPER.copy()


_LAND_STAIN = None


def render_map(c, s, pin_alpha=0.0, label_alpha=0.0):
    global _LAND_STAIN
    img = map_paper()
    land = L()
    coast = L()
    dl, dc = ImageDraw.Draw(land), ImageDraw.Draw(coast)
    for p in POLYS:
        pts = [project(lon, lat, c, s) for lon, lat in p]
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        if max(xs) < -50 or min(xs) > W + 50 or max(ys) < -50 or min(ys) > H + 50:
            continue
        dl.polygon(pts, fill=255)
        dc.line(pts + [pts[0]], fill=255, width=4, joint='curve')
    # 陸: 淡い黄土の淡彩 + ムラ
    img = ink_layer(img, land.filter(ImageFilter.GaussianBlur(1.5)), (222, 206, 166), 1.0)
    if _LAND_STAIN is None:
        n = ndi.gaussian_filter(np.random.default_rng(3).normal(0, 1, (H // 4, W // 4)), 8)
        n = np.kron(n, np.ones((4, 4)))[:H, :W]
        _LAND_STAIN = Image.fromarray(np.clip((n - n.min()) / (n.max() - n.min()) * 255, 0, 255).astype(np.uint8))
    img = ink_layer(img, ImageChops.multiply(land, _LAND_STAIN), (176, 150, 98), .35)
    # 海岸線の内側ぼかし (淡彩の溜まり)
    edge = ImageChops.multiply(coast.filter(ImageFilter.GaussianBlur(9)), land)
    img = ink_layer(img, edge, (170, 140, 90), .45)
    # 墨の海岸線
    img = ink_layer(img, coast.filter(ImageFilter.GaussianBlur(.8)), (52, 46, 40), .85)

    if pin_alpha > 0:
        px, py = project(*KUMAMOTO, c, s)
        # 波紋
        rp = L()
        drp = ImageDraw.Draw(rp)
        for k, rr in enumerate([30, 54]):
            drp.ellipse(ell(px, py, rr, rr * .45), outline=255, width=3)
        img = ink_layer(img, rp.filter(ImageFilter.GaussianBlur(1)), SHU, .55 * pin_alpha)
        # ピン (しずく形)
        pm = L()
        dp = ImageDraw.Draw(pm)
        top = py - 86
        dp.ellipse(ell(px, top, 26, 26), fill=255)
        dp.polygon([(px - 22, top + 13), (px + 22, top + 13), (px, py - 4)], fill=255)
        sh = L()
        ImageDraw.Draw(sh).ellipse(ell(px + 4, py + 2, 16, 6), fill=255)
        img = ink_layer(img, sh.filter(ImageFilter.GaussianBlur(4)), (60, 40, 30), .5 * pin_alpha)
        img = ink_layer(img, pm.filter(ImageFilter.GaussianBlur(.8)), SHU, pin_alpha)
        dot = L()
        ImageDraw.Draw(dot).ellipse(ell(px, top, 9, 9), fill=255)
        img = ink_layer(img, dot, (246, 236, 220), pin_alpha)
    if label_alpha > 0:
        px, py = project(*KUMAMOTO, c, s)
        bx, by = px + 70, py - 210
        ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
        do = ImageDraw.Draw(ov)
        a = int(255 * label_alpha)
        do.line([(px + 20, py - 100), (bx, by + 70)], fill=INK + (int(a * .7),), width=3)
        do.rounded_rectangle([bx, by, bx + 560, by + 150], radius=8, fill=(250, 245, 232, int(a * .92)), outline=INK + (int(a * .8),), width=3)
        do.rectangle([bx, by, bx + 10, by + 150], fill=SHU + (a,))
        do.text((bx + 36, by + 18), '熊本県酒造研究所', font=font(SERIF_B, 50), fill=INK + (a,))
        do.text((bx + 38, by + 86), '吟醸用「熊本酵母」が生まれた場所', font=font(SERIF_M, 32), fill=(96, 84, 70, a))
        img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    img = seal(img, 56, 56, '酒の博物誌', 52)
    return img


MAP_KEYS = [((137.2, 37.6), 50), ((130.8, 32.7), 230), (KUMAMOTO[0] + .55, KUMAMOTO[1] - .05), ]


def map_state(t):
    """t: 0..1 の中で 全体→九州→熊本 へ。ease in-out, 縮尺は対数で補間"""
    c0, s0 = (137.2, 37.6), 50
    c1, s1 = (KUMAMOTO[0] + .5, KUMAMOTO[1] - .25), 400
    e = t * t * (3 - 2 * t)
    ls = np.log(s0) + (np.log(s1) - np.log(s0)) * e
    s = np.exp(ls)
    # 中心は「画面上の移動量」が自然になるよう縮尺に連動させる
    k = (1 / s0 - 1 / s) / (1 / s0 - 1 / s1)
    c = (c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k)
    return c, s


def map_video(path, fps=30):
    tmp = str(OUT / 'map_frames')
    os.makedirs(tmp, exist_ok=True)
    seq = []
    hold0, zoom, hold1 = int(.8 * fps), int(2.6 * fps), int(2.6 * fps)
    for i in range(hold0):
        seq.append((0, 0, 0))
    for i in range(zoom):
        seq.append((i / (zoom - 1), 0, 0))
    for i in range(hold1):
        pa = min(1, i / (.35 * fps))
        la = min(1, max(0, (i - .5 * fps) / (.4 * fps)))
        seq.append((1, pa, la))
    sub = ['日本酒の「華やかな香り」を全国に広めた酵母。', 'そのふるさとは、熊本。']
    for n, (t, pa, la) in enumerate(seq):
        c, s = map_state(t)
        im = render_map(c, s, pa, la)
        im = subtitle(im, sub)
        im.save(f'{tmp}/{n:04d}.png')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', f'{tmp}/%04d.png',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', path], check=True)


# ================= 場面5: ミクロ世界 (醪の中) =================
MICRO_SUB = ['醪（もろみ）の中では、酵母が糖をアルコールに変えながら、', '香りの成分もつくっている。']


def scene_micro(pose='surprise', sub=MICRO_SUB):
    """pose=None でキャラなし、sub=None で字幕なし"""
    # 醪の中: 温かい乳白〜琥珀のにじみ
    base = np.ones((H, W, 3)) * np.array([226, 210, 168], float)
    yy, xx = np.mgrid[0:H, 0:W]
    glow = np.exp(-(((xx - 1300) / 900) ** 2 + ((yy - 250) / 600) ** 2))
    base += glow[..., None] * np.array([22, 20, 14])
    n = ndi.gaussian_filter(rng.normal(0, 1, (H // 6, W // 6)), 7)
    n = np.kron(n, np.ones((6, 6)))[:H, :W]
    base += (n / n.std() * 7)[..., None]
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    paper = washi()
    img = Image.blend(img, ImageChops.multiply(img, paper.point(lambda v: min(255, v + 40))), .5)

    def yeast(img, cx, cy, rx, ry, ang, blur=0, op=1.0, bud=None, scale=1.0):
        m = L()
        ImageDraw.Draw(m).ellipse(ell(cx, cy, rx, ry), fill=255)
        if bud:
            bx, by, br = bud
            ImageDraw.Draw(m).ellipse(ell(cx + bx, cy + by, br, br * .9), fill=255)
        m = m.rotate(ang, center=(cx, cy))
        img = ink_layer(img, m.filter(ImageFilter.GaussianBlur(3 + blur)), (238, 226, 190), .85 * op)
        # 細胞内の淡い陰 (液胞)
        v = L()
        ImageDraw.Draw(v).ellipse(ell(cx - rx * .15, cy + ry * .05, rx * .42, ry * .38), fill=255)
        v = v.rotate(ang, center=(cx, cy))
        img = ink_layer(img, v.filter(ImageFilter.GaussianBlur(10 + blur)), (190, 168, 120), .45 * op)
        # 縁の陰影
        rim = ImageChops.subtract(m, m.filter(ImageFilter.GaussianBlur(12 * scale)).point(lambda q: min(255, q * 1.4)))
        img = ink_layer(img, rim.filter(ImageFilter.GaussianBlur(2 + blur)), (150, 128, 84), .5 * op)
        if blur < 4:
            mm = m.point(lambda q: 255 if q > 127 else 0)
            er = mm.filter(ImageFilter.MinFilter(int(5 * scale) | 1))
            edge = ImageChops.subtract(mm, er).filter(ImageFilter.GaussianBlur(.9 + blur))
            img = ink_layer(img, edge, (78, 64, 44), .8 * op)
            # 細胞内の顆粒
            g = L()
            dg = ImageDraw.Draw(g)
            for _ in range(int(40 * scale)):
                a_, r_ = rng.uniform(0, 2 * np.pi), np.sqrt(rng.uniform(0, .8))
                gx, gy = cx + rx * r_ * np.cos(a_), cy + ry * r_ * np.sin(a_)
                gr = rng.uniform(2, 6) * scale
                dg.ellipse(ell(gx, gy, gr, gr), fill=255)
            g = g.rotate(ang, center=(cx, cy))
            img = ink_layer(img, ImageChops.multiply(g.filter(ImageFilter.GaussianBlur(1.5)), er), (160, 136, 92), .5 * op)
        return img

    # 奥 (ぼけ)
    for cx, cy, r in [(260, 180, 120), (1560, 120, 140), (760, 90, 90), (1840, 520, 110), (120, 640, 100)]:
        img = yeast(img, cx, cy, r, r * .82, rng.uniform(0, 180), blur=14, op=.55)
    # 泡 (炭酸ガス)
    for _ in range(26):
        bx, by, br = rng.uniform(100, W - 100), rng.uniform(60, 860), rng.uniform(8, 34)
        b = L()
        ImageDraw.Draw(b).ellipse(ell(bx, by, br, br), outline=255, width=max(2, int(br / 8)))
        img = ink_layer(img, b.filter(ImageFilter.GaussianBlur(1.2)), (255, 252, 240), .8)
        hl = L()
        ImageDraw.Draw(hl).ellipse(ell(bx - br * .35, by - br * .35, br * .22, br * .22), fill=255)
        img = ink_layer(img, hl.filter(ImageFilter.GaussianBlur(1)), (255, 255, 255), .9)
    # 米のかけら (でんぷん質の白い塊)
    for cx, cy, r in [(330, 860, 230), (1100, 940, 160)]:
        pts = [(cx + r * (1 + .25 * rng.normal()) * np.cos(a), cy + r * .45 * (1 + .25 * rng.normal()) * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 14, endpoint=False)]
        m = L()
        ImageDraw.Draw(m).polygon(pts, fill=255)
        img = ink_layer(img, m.filter(ImageFilter.GaussianBlur(6)), (246, 240, 222), .95)
        o = L()
        brush_line(ImageDraw.Draw(o), pts + [pts[0]], 3, 3)
        img = ink_layer(img, o.filter(ImageFilter.GaussianBlur(2.5)), (150, 136, 104), .5)
    # 主役の酵母 (出芽)
    img = yeast(img, 980, 450, 230, 190, 12, bud=(215, -140, 95), scale=1.3)
    img = yeast(img, 1500, 640, 140, 116, -25, scale=1.0)
    img = yeast(img, 620, 420, 110, 92, 40, bud=(-95, 70, 45), scale=.9)

    # 香り成分 (象徴的な表現: 小さな光の粒)
    def aroma(img, x, y, color, n, spread):
        for _ in range(n):
            ax, ay = x + rng.normal(0, spread), y + rng.normal(0, spread * .7)
            r = rng.uniform(5, 11)
            m = L()
            ImageDraw.Draw(m).ellipse(ell(ax, ay, r * 2.6, r * 2.6), fill=255)
            img = ink_layer(img, m.filter(ImageFilter.GaussianBlur(r * 1.2)), color, .35)
            m2 = L()
            ImageDraw.Draw(m2).ellipse(ell(ax, ay, r, r), fill=255)
            img = ink_layer(img, m2.filter(ImageFilter.GaussianBlur(1.5)), color, .9)
        return img

    img = aroma(img, 1240, 250, SHU, 9, 70)
    img = aroma(img, 720, 230, (214, 160, 40), 8, 60)

    d = ImageDraw.Draw(img)

    def tag(x, y, text, color):
        f = font(SERIF_B, 36)
        tw = d.textlength(text, font=f)
        d.rounded_rectangle([x, y, x + tw + 40, y + 60], radius=30, fill=(250, 245, 232), outline=color, width=3)
        d.text((x + 20, y + 8), text, font=f, fill=INK)

    tag(1300, 140, 'カプロン酸エチル', SHU)
    tag(470, 120, '酢酸イソアミル', (196, 140, 30))
    # 注記
    d.text((1650, 860), '再現イメージ', font=font(SERIF_R, 28), fill=(110, 96, 74))

    # 縮んだ案内人
    box = None
    if pose:
        img, box = place_host(img, pose, 300, 330, 790, shadow=True)
    img = seal(img, 56, 56, '酒の博物誌', 52)
    if sub:
        img = subtitle(img, sub)
    return img, box


if __name__ == '__main__':
    import sys
    which = sys.argv[1:] or ['q', 'map', 'micro', 'video']
    if 'q' in which:
        reset_rng('q')
        scene_question2().save(str(OUT / '01_question_v2.png'))
    if 'map' in which:
        reset_rng('map')
        for name, t, pa, la in [('04a_map_japan', 0, 0, 0), ('04b_map_kyushu', .55, 0, 0), ('04c_map_kumamoto', 1, 1, 1)]:
            c, s = map_state(t)
            im = render_map(c, s, pa, la)
            im = subtitle(im, ['日本酒の「華やかな香り」を全国に広めた酵母。', 'そのふるさとは、熊本。'])
            im.save(str(OUT / f'{name}.png'))
    if 'micro' in which:
        reset_rng('micro')
        im, box = scene_micro()
        im.save(str(OUT / '05_micro.png'))
        print('micro host', box)
    if 'video' in which:
        map_video(str(OUT / '04_map_zoom.mp4'))
    print('done')

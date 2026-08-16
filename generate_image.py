from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageDraw as D, ImageChops
import math, random, os

W, H = 1280, 800
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)

random.seed(42)

# --- Sunset sky gradient ---
def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

# Horizon ~ 60% of image height
horizon = int(H * 0.62)

sky_top = (18, 32, 80)       # deep navy
sky_mid = (120, 60, 120)     # purple
sky_sun = (255, 120, 60)     # orange
sky_bot = (255, 190, 110)    # warm near horizon

for y in range(horizon):
    t = y / horizon
    if t < 0.4:
        c = lerp(sky_top, sky_mid, t / 0.4)
    elif t < 0.75:
        c = lerp(sky_mid, sky_sun, (t - 0.4) / 0.35)
    else:
        c = lerp(sky_sun, sky_bot, (t - 0.75) / 0.25)
    d.line([(0, y), (W, y)], fill=c)

def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

# Sun
sun_cx, sun_cy, sun_r = int(W*0.55), horizon - 10, int(H*0.16)
for r in range(sun_r, 0, -1):
    t = 1 - r / sun_r
    d.ellipse([sun_cx-r, sun_cy-r, sun_cx+r, sun_cy+r],
              fill=lerp((255,255,180), (255,200,120), t))

# Glow around sun
glow = Image.new("RGB", (W, H))
gd = ImageDraw.Draw(glow)
for i in range(30, 0, -1):
    r = sun_r + i*8
    alpha = max(0, 20 - i)
    gd.ellipse([sun_cx-r, sun_cy-r, sun_cx+r, sun_cy+r],
               fill=(255,180,80, alpha))
glow = glow.filter(ImageFilter.GaussianBlur(30))
img = ImageChops.add(img, glow)

# Ground (grasslands)
d = ImageDraw.Draw(img)
for y in range(horizon, H):
    t = (y - horizon) / (H - horizon)
    c = lerp((70, 45, 30), (25, 40, 20), t)
    d.line([(0, y), (W, y)], fill=c)

# Rolling hills silhouettes
def hill(y_base, amp, seed, color):
    d = ImageDraw.Draw(img)
    pts = []
    for x in range(0, W, 4):
        phase = (x / W) * math.pi * 2 * 2.2 + seed * 1.7
        y = y_base - amp * abs(math.sin(phase)) * 0.5 - amp*0.4
        pts.append((x, y))
    pts.append((W, H))
    pts.append((0, H))
    d.polygon(pts, fill=color)

hill(horizon + 10, 60, 1.3, (30, 30, 40))
hill(horizon + 40, 80, 4.2, (20, 25, 30))
hill(horizon + 70, 70, 7.9, (10, 15, 20))

# Trees in foreground
for i in range(12):
    tx = random.randint(0, W)
    tw = random.randint(18, 30)
    th = random.randint(70, 140)
    base = H
    d.polygon([(tx-tw, base), (tx+tw, base), (tx, base-th)], fill=(8,14,10))
    # branches / foliage
    d.ellipse([tx-tw-6, base-th-30, tx+tw+6, base-th+10], fill=(8,14,10))

# Stars in upper sky
for i in range(120):
    sx = random.randint(0, W)
    sy = random.randint(0, int(horizon*0.6))
    b = random.randint(120, 255)
    d.ellipse([sx,sy,sx+2,sy+2], fill=(b,b,b))

# Add tiny lake/reflection bottom
lake_top = H - int(H*0.10)
for y in range(lake_top, H):
    t = (y - lake_top) / (H - lake_top)
    d.line([(0,y),(W,y)], fill=lerp((40,30,70),(20,20,40), t))

img = img.filter(ImageFilter.SMOOTH_MORE)

img.save(r"E:\comyui\phone_bridge\sunset.png")
print("saved sunset.png", img.size)
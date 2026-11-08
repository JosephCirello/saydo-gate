"""Cut the POTESTAS AI wordmark out of the company logo and set it on a wide cover banner.
Usage: python make_cover.py <logo.jpg> <out.png> [width height]
"""
import sys
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
H = int(sys.argv[4]) if len(sys.argv) > 4 else 500

im = Image.open(src).convert("RGB")
w, h = im.size

# background: the circuit-board field from the image's own edges, stretched and softened
bg = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(6))
# darken a touch so the wordmark reads
bg = Image.eval(bg, lambda v: int(v * 0.72))

# the wordmark region: "POTESTAS" and "AI" sit in the lower band of the 587x600 logo
# measured by eye from the supplied image: POTESTAS spans roughly y 395-470, AI roughly y 478-512
word = im.crop((85, 385, 505, 520))
# fit the wordmark to about 55% of the banner width
target_w = int(W * 0.55)
scale = target_w / word.width
word = word.resize((target_w, int(word.height * scale)), Image.LANCZOS)

# feather the crop edges into the background so the rectangle does not show
mask = Image.new("L", word.size, 255)
feather = int(min(word.size) * 0.18)
from PIL import ImageDraw
md = ImageDraw.Draw(mask)
for i in range(feather):
    a = int(255 * (i / feather))
    md.rectangle([i, i, word.width - 1 - i, word.height - 1 - i], outline=a)
mask = mask.filter(ImageFilter.GaussianBlur(feather / 3))

x = (W - word.width) // 2
y = (H - word.height) // 2
bg.paste(word, (x, y), mask)
bg.save(out, "PNG")
print("saved", out, bg.size)

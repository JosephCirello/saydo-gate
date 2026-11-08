"""Turn slides_deck/s01..s09.png (no caption band) into one PDF deck. Run after: NOCAP=1 python build.py"""
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
pngs = sorted((HERE / "slides_deck").glob("s*.png"))
pages = [Image.open(p).convert("RGB").resize((1600, 900), Image.LANCZOS) for p in pngs]
out = HERE / "Potestas_AI_Say_vs_Do_Gate_deck_8NOV26.pdf"
pages[0].save(out, "PDF", resolution=150, save_all=True, append_images=pages[1:], quality=85)
print("deck:", out.name, len(pages), "pages", f"{out.stat().st_size/1e6:.1f} MB")

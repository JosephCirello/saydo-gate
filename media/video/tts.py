"""Speak script.json with Microsoft Edge's neural voice (edge-tts), one file per line, with word timings.
Run with the voice_check venv:  C:\\Users\\joeci\\Desktop\\voice_check\\venv\\Scripts\\python.exe tts.py
Writes tts/line_NN.mp3 and tts/line_NN.json. The spellings below are the ones his ear chose on 2026-11-01."""
import sys, json, asyncio, re
from pathlib import Path
import edge_tts
HERE = Path(__file__).parent
S = json.load(open(HERE / "script.json", encoding="utf-8"))
OUT = HERE / "tts"; OUT.mkdir(exist_ok=True)
SPEAK = {
 "github.com/JosephCirello/swarm-monitor": "github dot com, slash Joseph Cirello, slash swarm monitor",
 "Potestas AI": "po TEST us AI",
 "104 of the 113": "one hundred and four of the one hundred and thirteen",
 "921": "nine hundred and twenty-one",
 "1 percent": "one percent",
}
def speak_text(line):
    s = line
    for k in sorted(SPEAK, key=len, reverse=True):
        s = re.sub(r"(?<![\w$/])" + re.escape(k) + r"(?![\w/])", SPEAK[k], s)
    return s
async def one(n, text):
    for attempt in range(4):
        try:
            com = edge_tts.Communicate(text, S["voice"], rate=S["rate"], boundary="WordBoundary")
            words = []; audio = bytearray()
            async for chunk in com.stream():
                if chunk["type"] == "audio": audio += chunk["data"]
                elif chunk["type"] == "WordBoundary": words.append({"word": chunk["text"], "start": chunk["offset"] / 1e7, "end": (chunk["offset"] + chunk["duration"]) / 1e7})
            if audio: break
        except Exception as e:
            print("retry", n, e); await asyncio.sleep(4 * (attempt + 1))
    else:
        raise SystemExit(f"no audio for line {n}")
    await asyncio.sleep(1.0)
    (OUT / f"line_{n:02d}.mp3").write_bytes(bytes(audio))
    json.dump({"line": n, "spoken": text, "caption": S["lines"][n - 1], "words": words}, open(OUT / f"line_{n:02d}.json", "w", encoding="utf-8"), indent=1)
    print(f"line {n:02d}: {len(words)} words, {len(audio):,} bytes")
async def main():
    only = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else range(1, len(S["lines"]) + 1)
    for n in only:
        await one(n, speak_text(S["lines"][n - 1]))
asyncio.run(main())

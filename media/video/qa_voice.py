"""Transcribe each spoken line back (faster-whisper) and compare with the script, word by word."""
import json, re, difflib, subprocess
import numpy as np
FF = pathlib_ff = open(r"C:/Users/joeci/Desktop/voice_check/ffmpeg_path.txt").read().strip()
from pathlib import Path
from faster_whisper import WhisperModel
HERE = Path(__file__).parent
S = json.load(open(HERE / "script.json", encoding="utf-8"))
m = WhisperModel("medium.en", device="cpu", compute_type="int8")
def norm(t): return re.sub(r"[^a-z0-9 ]", " ", t.lower().replace("-", " ")).split()
bad = 0
for n, line in enumerate(S["lines"], 1):
    raw = subprocess.run([FF, "-v", "error", "-i", str(HERE / "tts" / f"line_{n:02d}.mp3"), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    segs, _ = m.transcribe(audio, beam_size=5, initial_prompt="Potestas AI. Apart Research. Swarm Alignment Hackathon. GitHub.")
    heard = " ".join(s.text for s in segs)
    a, b = norm(line), norm(heard)
    sm = difflib.SequenceMatcher(None, a, b); r = sm.ratio()
    diffs = [(op, " ".join(a[i1:i2]), " ".join(b[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    print(f"line {n:02d} match {r:.2f}" + ("" if r > 0.9 else "  <-- LOOK"))
    for d in diffs[:6]: print("    ", d)
    if r <= 0.9: bad += 1
print("lines needing a look:", bad)

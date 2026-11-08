"""Assemble the video: each slide holds for its line's voice plus a lead and a tail; the voice files trimmed of silence;
one segment per scene, concatenated; 1920x1080, 30 fps, H.264 crf 18, AAC 192k. Also a 540p preview and a plan file.
Run with miniconda: python assemble.py"""
import json, subprocess
from pathlib import Path
HERE = Path(__file__).parent
FF = Path(r"C:\Users\joeci\Desktop\voice_check\ffmpeg_path.txt").read_text().strip(); FP = FF.replace("ffmpeg.exe", "ffprobe.exe")
S = json.load(open(HERE / "script.json", encoding="utf-8"))
N = len(S["lines"]); LEAD, TAIL, LAST_TAIL = 0.6, 1.1, 3.0
SEG = HERE / "segments"; SEG.mkdir(exist_ok=True)
plan = []; t = 0.0
for n in range(1, N + 1):
    mp3 = HERE / "tts" / f"line_{n:02d}.mp3"; wav = SEG / f"v{n:02d}.wav"
    subprocess.run([FF, "-y", "-v", "error", "-i", str(mp3), "-af", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse", "-ar", "48000", "-ac", "1", str(wav)], check=True)
    vo = float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)], capture_output=True, text=True, check=True).stdout.strip())
    dur = round(LEAD + vo + (LAST_TAIL if n == N else TAIL), 2)
    seg = SEG / f"seg{n:02d}.mp4"
    subprocess.run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(HERE / "slides" / f"s{n:02d}.png"), "-i", str(wav),
                    "-filter_complex", f"[1:a]adelay={int(LEAD*1000)}:all=1,apad[a]", "-map", "0:v", "-map", "[a]", "-t", str(dur),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(seg)], check=True)
    plan.append({"scene": n, "start": round(t, 2), "dur": dur, "voice": round(vo, 2)}); t += dur
lst = SEG / "all.txt"; lst.write_text("".join(f"file '{(SEG / f'seg{n:02d}.mp4').as_posix()}'\n" for n in range(1, N + 1)), encoding="utf-8")
master = HERE / "Potestas_AI_Swarm_report_video_8NOV26.mp4"
subprocess.run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(master)], check=True)
subprocess.run([FF, "-y", "-v", "error", "-i", str(master), "-vf", "scale=960:540", "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(HERE / "preview_540p.mp4")], check=True)
total = float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(master)], capture_output=True, text=True, check=True).stdout.strip())
json.dump({"total": round(total, 2), "scenes": plan}, open(HERE / "plan.json", "w", encoding="utf-8"), indent=1)
print(f"TOTAL {total:.1f} s ({int(total//60)} min {int(total%60)} s); master {master.stat().st_size/1e6:.1f} MB")
for p in plan: print(f"  scene {p['scene']} start {p['start']:6.1f} dur {p['dur']:5.1f} voice {p['voice']:5.1f}")

from flask import Flask, render_template, request, send_file
from pathlib import Path
import os, re, subprocess, shutil, requests
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

def make_script(topic, lang, style):
    prompt = f"Write an original YouTube {style} script in {lang} about {topic}. Start with a strong hook, use five short paragraphs, and end with a takeaway. Return only the script."
    try:
        r = requests.post(OLLAMA_URL.rstrip("/") + "/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=90)
        r.raise_for_status()
        script = r.json().get("response", "").strip()
        if script:
            return script, "Ollama local model: " + OLLAMA_MODEL
    except Exception:
        pass
    if lang == "Hindi":
        return f"शीर्षक: {topic}\n\nक्या आपने कभी सोचा है कि {topic} क्यों महत्वपूर्ण है? आज इसे आसान भाषा में समझेंगे। पहले मूल बातें जानें, फिर उदाहरण देखें और निष्कर्ष से पहले जानकारी जाँचें। जिज्ञासु बने रहें और लगातार सीखते रहें। वीडियो पसंद आए तो लाइक और सब्सक्राइब करें।", "Offline starter script"
    if lang == "Marathi":
        return f"विषय: {topic}\n\nतुम्ही कधी विचार केला आहे का की {topic} महत्त्वाचा का आहे? आज आपण हा विषय सोप्या भाषेत समजून घेऊ. आधी मूलभूत गोष्टी जाणून घ्या, उदाहरणे पाहा आणि निष्कर्षापूर्वी माहिती तपासा. सतत शिकत राहा. व्हिडिओ आवडला तर लाईक आणि सबस्क्राइब करा.", "Offline starter script"
    return f"Title: {topic}\n\nHave you ever wondered why {topic} matters? In this video, we break it down in simple steps. Start with the basics, look at examples, and verify information before drawing conclusions. Stay curious and keep learning. If this helped, like and subscribe.", "Offline starter script (Ollama unavailable)"

def render_video(topic, script, ratio, language="English"):
    if not shutil.which("ffmpeg"):
        return None, "FFmpeg is unavailable."
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", topic)[:35] or "video"
    folder = OUT / (slug + "_" + str(os.getpid()))
    folder.mkdir(parents=True, exist_ok=True)
    scenes = [part.strip().replace("\n", " ") for part in re.split(r"\n\s*\n|\[SCENE\]", script) if part.strip()][:10] or [script]
    size = (720, 1280) if ratio == "9:16" else (1280, 720)
    images = []
    for i, text in enumerate(scenes, 1):
        image = Image.new("RGB", size, (13, 18, 32))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
            small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        except Exception:
            font = ImageFont.load_default()
            small = font
        draw.rounded_rectangle((28, 28, size[0]-28, size[1]-28), radius=24, outline=(76, 155, 220), width=3)
        draw.text((52, 55), "YOUTUBE AI STUDIO", fill=(115, 207, 255), font=small)
        words, lines, line = text.split(), [], ""
        max_chars = 32 if ratio == "9:16" else 58
        for word in words:
            test = (line + " " + word).strip()
            if len(test) <= max_chars:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        y = max(150, (size[1] - len(lines) * 44) // 2)
        for line in lines[:20]:
            draw.text((52, y), line, font=font, fill=(245, 247, 252))
            y += 44
        image_path = folder / f"scene_{i:02d}.jpg"
        image.save(image_path, quality=92)
        images.append(image_path)
    concat = folder / "scenes.txt"
    with concat.open("w", encoding="utf-8") as handle:
        for image_path in images:
            handle.write("file '" + image_path.as_posix() + "'\n")
            handle.write("duration 5\n")
        handle.write("file '" + images[-1].as_posix() + "'\n")
    silent_video = folder / "silent.mp4"
    command = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
               "-vf", f"scale={size[0]}:{size[1]},format=yuv420p", "-r", "24",
               "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", str(silent_video)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
        if result.returncode != 0 or not silent_video.exists() or silent_video.stat().st_size < 1000:
            return None, "Video rendering failed: " + result.stderr[-500:]
        voice = folder / "narration.wav"
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            voice_lang = {"English": "en", "Hindi": "hi", "Marathi": "mr"}.get(language, "en")
            speech = subprocess.run([espeak, "-v", voice_lang, "-s", "145", "-w", str(voice), re.sub(r"\s+", " ", script)], capture_output=True, text=True, timeout=120)
            if speech.returncode == 0 and voice.exists() and voice.stat().st_size > 1000:
                output = folder / "final_video.mp4"
                mux = subprocess.run(["ffmpeg", "-y", "-i", str(silent_video), "-i", str(voice),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(output)],
                    capture_output=True, text=True, timeout=300)
                if mux.returncode == 0 and output.exists() and output.stat().st_size > 1000:
                    return output, "MP4 created with generated voice narration and scene cards. This is not realistic AI motion."
        output = folder / "final_video.mp4"
        shutil.copy2(silent_video, output)
        return output, "MP4 created with scene cards, but voice narration was unavailable."
    except Exception as exc:
        return None, "Render error: " + str(exc)

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/create")
def create():
    topic = request.form.get("topic", "").strip()
    language = request.form.get("language", "English")
    style = request.form.get("style", "storytelling")
    ratio = request.form.get("ratio", "9:16")
    if not topic:
        return render_template("index.html", error="Enter a topic.")
    script, source = make_script(topic, language, style)
    output, status = render_video(topic, script, ratio, language)
    video = output.relative_to(OUT).as_posix() if output else None
    return render_template("result.html", topic=topic, script=script, source=source, status=status, video=video)

@app.get("/download/<path:name>")
def download(name):
    target = (OUT / name).resolve()
    if not target.is_relative_to(OUT.resolve()) or not target.is_file():
        return "Not found", 404
    return send_file(target, as_attachment=True)

@app.get("/analyze")
def analyze():
    return render_template("analyze.html", analysis="", title="", transcript="")

@app.post("/analyze")
def analyze_post():
    title = request.form.get("title", "")
    transcript = request.form.get("transcript", "")
    prompt = "Analyze only the supplied title/transcript. Explain main idea, hook, structure, lessons, three original ideas, suggested title, and what cannot be verified. Title: " + title + "\nTranscript: " + transcript
    try:
        response = requests.post(OLLAMA_URL.rstrip("/") + "/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=90)
        response.raise_for_status()
        analysis = response.json().get("response", "")
    except Exception:
        analysis = "For reliable analysis, paste a transcript or notes. Suggested structure: hook, context, examples, takeaway. Exact spoken claims cannot be verified from a title alone."
    return render_template("analyze.html", analysis=analysis, title=title, transcript=transcript)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

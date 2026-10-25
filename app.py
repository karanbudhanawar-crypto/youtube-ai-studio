from flask import Flask, render_template, request
from pathlib import Path
import os, re, subprocess, shutil, requests
from PIL import Image, ImageDraw, ImageFont
app=Flask(__name__)
BASE=Path(__file__).resolve().parent
OUT=BASE/'output'; OUT.mkdir(exist_ok=True)
OLLAMA_URL=os.getenv('OLLAMA_URL','http://127.0.0.1:11434'); OLLAMA_MODEL=os.getenv('OLLAMA_MODEL','llama3.2')
def make_script(topic,lang,style):
 p=f'Write an original YouTube {style} script in {lang} about {topic}. Start with a strong hook, use 5 short paragraphs, end with a takeaway. Return only the script.'
 try:
  r=requests.post(OLLAMA_URL+'/api/generate',json={'model':OLLAMA_MODEL,'prompt':p,'stream':False},timeout=90); r.raise_for_status(); s=r.json().get('response','').strip()
  if s:return s,'Ollama local model: '+OLLAMA_MODEL
 except Exception:pass
 if lang=='Hindi':return f'शीर्षक: {topic}\n\nक्या आपने कभी सोचा है कि {topic} क्यों महत्वपूर्ण है? आज इसे आसान भाषा में समझेंगे। पहले मूल बातें जानें, फिर उदाहरण देखें और निष्कर्ष से पहले जानकारी जाँचें। जिज्ञासु बने रहें और लगातार सीखते रहें। वीडियो पसंद आए तो लाइक और सब्सक्राइब करें।','Offline starter script'
 if lang=='Marathi':return f'विषय: {topic}\n\nतुम्ही कधी विचार केला आहे का की {topic} महत्त्वाचा का आहे? आज आपण हा विषय सोप्या भाषेत समजून घेऊ. आधी मूलभूत गोष्टी जाणून घ्या, उदाहरणे पाहा आणि निष्कर्षापूर्वी माहिती तपासा. सतत शिकत राहा. व्हिडिओ आवडला तर लाईक आणि सबस्क्राइब करा.','Offline starter script'
 return f'Title: {topic}\n\nHave you ever wondered why {topic} matters? In this video, we break it down in simple steps. Start with the basics, look at examples, and verify information before drawing conclusions. Stay curious and keep learning. If this helped, like and subscribe.','Offline starter script (Ollama unavailable)'
def render(topic,script,ratio):
 if not shutil.which('ffmpeg'):return None,'FFmpeg is unavailable.'
 slug=re.sub('[^a-zA-Z0-9_-]+','_',topic)[:35] or 'video'; folder=OUT/slug; folder.mkdir(exist_ok=True)
 scenes=[x.strip().replace('\n',' ') for x in re.split(r'\n\s*\n|\[SCENE\]',script) if x.strip()][:10] or [script]
 size=(720,1280) if ratio=='9:16' else (1280,720); imgs=[]
 for i,txt in enumerate(scenes,1):
  im=Image.new('RGB',size,(13,18,32)); d=ImageDraw.Draw(im)
  try:f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',32)
  except Exception:f=ImageFont.load_default()
  d.rounded_rectangle((28,28,size[0]-28,size[1]-28),radius=24,outline=(76,155,220),width=3); d.text((52,55),'YOUTUBE AI STUDIO',fill=(115,207,255),font=f)
  words=txt.split(); lines=[]; line=''
  for w in words:
   if len(line+w)<38:line=(line+' '+w).strip()
   else:lines.append(line);line=w
  if line:lines.append(line)
  y=max(150,(size[1]-len(lines)*44)//2)
  for line in lines[:20]:d.text((52,y),line,font=f,fill=(245,247,252));y+=44
  p=folder/f'scene_{i:02d}.jpg';im.save(p,quality=90);imgs.append(p)
 concat=folder/'scenes.txt'
 with concat.open('w',encoding='utf8') as f:
  for p in imgs:f.write(f\"file '{p.as_posix()}'\\nduration 4\\n\")
  f.write(f\"file '{imgs[-1].as_posix()}'\\n\")
 out=folder/'final_video.mp4'; cmd=['ffmpeg','-y','-f','concat','-safe','0','-i',str(concat),'-vf',f'scale={size[0]}:{size[1]},format=yuv420p','-r','24','-c:v','libx264','-preset','ultrafast','-an','-movflags','+faststart',str(out)]
 try:
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=900)
  return (out,'MP4 ready. Current video uses still scene cards, not AI motion.') if r.returncode==0 and out.exists() else (None,r.stderr[-600:])
 except Exception as e:return None,str(e)
@app.get('/')
def index():return render_template('index.html')
@app.post('/create')
def create():
 topic=request.form.get('topic','').strip();lang=request.form.get('language','English');style=request.form.get('style','storytelling');ratio=request.form.get('ratio','9:16')
 if not topic:return render_template('index.html',error='Enter a topic.')
 script,source=make_script(topic,lang,style);out,status=render(topic,script,ratio)
 return render_template('result.html',topic=topic,script=script,source=source,status=status,video=out.relative_to(OUT).as_posix() if out else None)
@app.get('/download/<path:name>')
def download(name):
 from flask import send_file
 p=(OUT/name).resolve()
 if not p.is_relative_to(OUT.resolve()) or not p.is_file():return 'Not found',404
 return send_file(p,as_attachment=True)
@app.get('/analyze')
def analyze():return render_template('analyze.html',analysis='',title='',transcript='')
@app.post('/analyze')
def analyze_post():
 title=request.form.get('title','');transcript=request.form.get('transcript','');prompt='Analyze only the supplied title/transcript. Explain main idea, hook, structure, lessons, three original ideas, suggested title, and what cannot be verified. Title: '+title+' Transcript: '+transcript
 try:
  r=requests.post(OLLAMA_URL+'/api/generate',json={'model':OLLAMA_MODEL,'prompt':prompt,'stream':False},timeout=90);r.raise_for_status();result=r.json().get('response','')
 except Exception:result='For reliable analysis, paste a transcript or notes. Suggested structure: hook, context, examples, takeaway. Exact spoken claims cannot be verified from a title alone.'
 return render_template('analyze.html',analysis=result,title=title,transcript=transcript)
@app.get('/health')
def health():return {'status':'ok'}
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')))

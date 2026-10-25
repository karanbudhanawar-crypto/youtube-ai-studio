YouTube AI Agent Studio
=======================
A Claude-inspired independent YouTube workflow using Python, Flask, optional local Ollama, Pillow and FFmpeg. No paid API keys are required.

Features: script generation, English/Hindi/Marathi fallback scripts, optional local Ollama, vertical and landscape still-scene MP4 rendering, reference analysis based on supplied information, Render configuration.

Windows: install Python and FFmpeg; optionally install Ollama and pull llama3.2; run python -m pip install -r requirements.txt; run python app.py; open http://127.0.0.1:5000.

Render cannot access Ollama/Piper installed on your computer. This version creates still scene cards, not realistic AI motion, and does not upload videos automatically to YouTube. Free Render storage may be ephemeral and services may sleep.
# PatentExtractor / IDS Automation

A cross-platform PDF extraction pipeline for patent/FSR/FOA documents with OCR.

## Features

- Multilingual OCR (EasyOCR/Tesseract, Argos-Translate)
- Patent/FSR/FOA parsing with regex + table extraction
- CLI + optional Tkinter GUI
- Optional PyInstaller packaging (.exe / .app)

## Quickstart

```bash

# 1) Create environment
conda create -n ids python=3.12 -y
conda activate ids

# 2) Install deps
pip install -r requirements.txt

# 3) (macOS) Install poppler via Homebrew
# brew install poppler

# 4) Run
python app.py
```

## Package on Mac

```bash
pyinstaller PatentExtractor.spec
```

Test from Terminal (shows real errors if any):

```bash
./dist/PatentExtractor.app/Contents/MacOS/PatentExtractor
```
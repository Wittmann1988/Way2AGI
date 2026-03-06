# Way2AGI Training Log — PC Session 06.03.2026

## System
- Windows 11 Pro, Python 3.13
- GPU: NVIDIA GeForce RTX 5090 (32GB VRAM)
- CUDA 13.0, Driver 581.80
- Repository: E:\claude-projects\Way2AGI

---

## Was gemacht wurde

### 1. Repository geklont
```
git clone https://github.com/Wittmann1988/Way2AGI.git E:\claude-projects\Way2AGI
```

### 2. Dependencies installiert
```
pip install trl peft transformers accelerate datasets torch huggingface-hub sentencepiece protobuf gguf
```
Installierte Versionen:
- transformers 5.3.0
- trl 0.29.0
- peft 0.18.1
- torch 2.10.0+cu128
- datasets 4.6.1
- huggingface-hub 1.5.0

### 3. HuggingFace Login
```
python -c "from huggingface_hub import login; login(token='...')"
```
Login erfolgreich als erik1988.

### 4. SFT Training ausgefuehrt
Script: `scripts/train_on_pc.py`

Ergebnisse:
- 129 SFT-Beispiele geladen, 116 Train / 13 Eval
- 3 Epochen, 24 Steps
- Trainingszeit: ~2 Minuten auf RTX 5090
- Train Loss: 1.261
- Eval Loss: 1.159 -> 1.112 -> 1.102 (stetig verbessert)
- Token Accuracy: ~70.3%
- Modell automatisch gepusht zu: https://huggingface.co/erik1988/way2agi-model

### 5. GGUF Konvertierung
Script: `scripts/convert_gguf.py`

- LoRA + Base Model gemerged -> merged_model/ (5.8GB safetensors)
- llama.cpp geklont fuer convert_hf_to_gguf.py
- F16 GGUF erstellt: 6.2 GB
- Q4_K_M quantisiert: 1.8 GB (via llama-cpp-python)
- Beide Dateien hochgeladen zu: https://huggingface.co/erik1988/way2agi-model-GGUF

---

## Fehler und Fixes

### ERROR 1: Dataset-Laden schlaegt fehl
**Fehler:** `DatasetGenerationCastError` — SFT und DPO Dateien haben unterschiedliche Spalten und koennen nicht zusammen geladen werden.
- SFT hat: messages, domain, model_id, provider
- DPO hat: prompt, system, chosen, rejected, chosen_model, rejected_model, domain

**Fix in train_on_pc.py Zeile 16:**
```python
# VORHER (fehlerhaft):
dataset = load_dataset("erik1988/way2agi-traces", split="train")

# NACHHER (gefixt):
dataset = load_dataset("erik1988/way2agi-traces", data_files="data/train/sft-combined.jsonl", split="train")
```
Dadurch wird nur die SFT-Datei geladen, nicht die DPO-Datei.

### ERROR 2: bf16 nicht unterstuetzt
**Fehler:** `ValueError: Your setup doesn't support bf16/gpu`
**Ursache:** pip install torch installiert standardmaessig die CPU-Version ohne CUDA.

**Fix:**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128 --force-reinstall
```
Danach wurde die RTX 5090 korrekt erkannt. CUDA 12.8 Wheel ist 2.9 GB gross.

### ERROR 3: GGUF Konvertierung — tokenizer_config.json
**Fehler:** `AttributeError: 'list' object has no attribute 'keys'` in transformers 5.3.0
**Ursache:** Das Feld `extra_special_tokens` im tokenizer_config.json des Qwen2.5-Modells ist eine Liste, aber transformers 5.3.0 erwartet ein Dict.

**Fix:**
```python
import json
with open('merged_model/tokenizer_config.json', 'r') as f:
    config = json.load(f)
if isinstance(config.get('extra_special_tokens'), list):
    tokens = config['extra_special_tokens']
    config['extra_special_tokens'] = {t: t for t in tokens}
with open('merged_model/tokenizer_config.json', 'w') as f:
    json.dump(config, f, indent=2)
```

### ERROR 4: cmake nicht installiert
**Fehler:** llama-quantize Binary kann nicht gebaut werden (cmake fehlt).
**Fix:** Statt cmake + llama.cpp Build wurde `llama-cpp-python` verwendet:
```bash
pip install llama-cpp-python
```
Quantisierung dann via Python:
```python
from llama_cpp import llama_model_quantize, llama_model_quantize_default_params
import ctypes
params = llama_model_quantize_default_params()
params.ftype = 15  # Q4_K_M
params.nthread = 8
llama_model_quantize(b'way2agi-f16.gguf', b'way2agi-q4_k_m.gguf', ctypes.byref(params))
```

### WARNING: warmup_ratio deprecated
`warmup_ratio is deprecated and will be removed in v5.2. Use warmup_steps instead.`
Nicht kritisch, funktioniert noch. Fuer zukuenftige Versionen in train_on_pc.py aendern.

### WARNING: torch_dtype deprecated
`torch_dtype is deprecated! Use dtype instead!`
In convert_gguf.py Zeile 25: `torch_dtype=torch.float16` -> `dtype=torch.float16`

---

## Wichtig fuer die naechste Session

1. **train_on_pc.py wurde geaendert** (Zeile 16: data_files Parameter hinzugefuegt)
2. **PyTorch CUDA muss explizit installiert werden** — normales `pip install torch` installiert CPU-only
3. **transformers 5.3.0 hat Breaking Changes** bei extra_special_tokens (List vs Dict)
4. **cmake ist nicht auf dem PC installiert** — llama-cpp-python als Alternative nutzen
5. **Lokale Artefakte** die NICHT im Repo sind (zu gross):
   - merged_model/ (5.8 GB) — gemergtes Modell
   - way2agi-f16.gguf (6.2 GB)
   - way2agi-q4_k_m.gguf (1.8 GB)
   - llama.cpp/ — geklontes Repo
   - way2agi-sft/ — Training Checkpoints
6. **HuggingFace Token** ist lokal gespeichert (huggingface-hub login), muss auf neuem System neu eingeloggt werden

## Links
- Modell (LoRA): https://huggingface.co/erik1988/way2agi-model
- Modell (GGUF): https://huggingface.co/erik1988/way2agi-model-GGUF
- Dataset: https://huggingface.co/datasets/erik1988/way2agi-traces
- Ollama Deploy: `ollama create way2agi -f Modelfile`

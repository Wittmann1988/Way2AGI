#!/usr/bin/env python3
"""
Way2AGI GGUF Conversion — Convert trained model to GGUF for Ollama.

Run AFTER train_on_pc.py has finished.

Usage:
    pip install transformers peft torch accelerate huggingface-hub sentencepiece protobuf gguf
    python convert_gguf.py
"""

import os
import sys
import subprocess
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from huggingface_hub import HfApi

ADAPTER_MODEL = "erik1988/way2agi-model"
BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
OUTPUT_REPO = "erik1988/way2agi-model-GGUF"

print("[Way2AGI] Step 1: Loading and merging model...")
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True
)
model = PeftModel.from_pretrained(base_model, ADAPTER_MODEL)
merged = model.merge_and_unload()
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_MODEL, trust_remote_code=True)

merged_dir = "./merged_model"
merged.save_pretrained(merged_dir, safe_serialization=True)
tokenizer.save_pretrained(merged_dir)
print("[Way2AGI] Merged model saved")

print("[Way2AGI] Step 2: Setting up llama.cpp...")
if not os.path.exists("llama.cpp"):
    subprocess.run(["git", "clone", "--depth", "1",
                    "https://github.com/ggerganov/llama.cpp.git"], check=True)
subprocess.run(["pip", "install", "-r", "llama.cpp/requirements.txt"],
               capture_output=True)

print("[Way2AGI] Step 3: Converting to GGUF...")
gguf_file = "way2agi-f16.gguf"
subprocess.run([
    sys.executable, "llama.cpp/convert_hf_to_gguf.py",
    merged_dir, "--outfile", gguf_file, "--outtype", "f16"
], check=True)

print("[Way2AGI] Step 4: Quantizing to Q4_K_M...")
os.makedirs("llama.cpp/build", exist_ok=True)
subprocess.run(["cmake", "-B", "llama.cpp/build", "-S", "llama.cpp",
                "-DGGML_CUDA=OFF"], check=True, capture_output=True)
subprocess.run(["cmake", "--build", "llama.cpp/build",
                "--target", "llama-quantize", "-j", "4"], check=True)

quantize_bin = "llama.cpp/build/bin/llama-quantize"
q4_file = "way2agi-q4_k_m.gguf"
subprocess.run([quantize_bin, gguf_file, q4_file, "Q4_K_M"], check=True)

size_mb = os.path.getsize(q4_file) / (1024 * 1024)
print(f"[Way2AGI] Q4_K_M: {size_mb:.0f} MB")

print("[Way2AGI] Step 5: Uploading to HuggingFace...")
api = HfApi()
api.create_repo(repo_id=OUTPUT_REPO, repo_type="model", exist_ok=True)
api.upload_file(path_or_fileobj=q4_file, path_in_repo="way2agi-q4_k_m.gguf",
                repo_id=OUTPUT_REPO)
api.upload_file(path_or_fileobj=gguf_file, path_in_repo="way2agi-f16.gguf",
                repo_id=OUTPUT_REPO)

print(f"[Way2AGI] Done! GGUF at: https://huggingface.co/{OUTPUT_REPO}")
print(f"[Way2AGI] Deploy: ollama create way2agi -f Modelfile")

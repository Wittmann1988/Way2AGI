"""
GGUF Pipeline — End-to-end: Training Data -> HF Dataset -> Train -> GGUF -> Ollama

This script orchestrates the full self-improvement pipeline:
1. Upload SFT/DPO JSONL to HuggingFace Hub
2. Launch SFT training as HF Job (cloud GPU)
3. Convert trained model to GGUF
4. Deploy to local Ollama

Designed to run on mobile (Termux) — all heavy work runs on HF cloud.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


HF_USER = "erik1988"
HF_DATASET_REPO = f"{HF_USER}/way2agi-traces"
HF_MODEL_REPO = f"{HF_USER}/way2agi-model"
BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"  # Small enough for fast training


def upload_to_hf(jsonl_path: str | Path, split: str = "train") -> str:
    """Upload JSONL training data to HuggingFace dataset repo."""
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    print(f"[GGUF Pipeline] Uploading {jsonl_path.name} to {HF_DATASET_REPO}...")

    # Use huggingface-cli for upload
    cmd = [
        "huggingface-cli", "upload",
        HF_DATASET_REPO,
        str(jsonl_path),
        f"data/{split}/{jsonl_path.name}",
        "--repo-type", "dataset",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Try creating repo first
        subprocess.run(
            ["huggingface-cli", "repo", "create", HF_DATASET_REPO.split("/")[1],
             "--type", "dataset", "-y"],
            capture_output=True, text=True,
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Upload failed: {result.stderr}")
            return ""

    print(f"[GGUF Pipeline] Uploaded to https://huggingface.co/datasets/{HF_DATASET_REPO}")
    return f"https://huggingface.co/datasets/{HF_DATASET_REPO}"


def generate_training_script(
    dataset_repo: str = HF_DATASET_REPO,
    base_model: str = BASE_MODEL,
    method: str = "sft",
) -> str:
    """Generate a UV training script for HuggingFace Jobs.

    Returns the script content (PEP 723 format for `hf jobs run`).
    """
    script = f'''# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "trl>=0.16",
#   "transformers>=4.50",
#   "datasets>=3.0",
#   "torch>=2.4",
#   "accelerate>=1.0",
#   "peft>=0.15",
#   "bitsandbytes>=0.45",
#   "trackio>=0.2",
# ]
# ///
"""Way2AGI SFT Training on HuggingFace Jobs."""

import os
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer
from peft import LoraConfig
import trackio
import torch

# Config
MODEL = "{base_model}"
DATASET = "{dataset_repo}"
OUTPUT = "/data/output/way2agi-sft"
HF_REPO = "{HF_MODEL_REPO}"

# Init tracking
trackio.init(project="way2agi-training")

# Load dataset
ds = load_dataset(DATASET, split="train")

# Quantization for memory efficiency
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

# Load model
model = AutoModelForCausalLM.from_pretrained(
    MODEL,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)
tokenizer = AutoTokenizer.from_pretrained(MODEL)

# LoRA config
peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    task_type="CAUSAL_LM",
)

# Training config
training_args = SFTConfig(
    output_dir=OUTPUT,
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    bf16=True,
    logging_steps=10,
    save_strategy="epoch",
    push_to_hub=True,
    hub_model_id=HF_REPO,
    report_to="trackio",
)

# Train
trainer = SFTTrainer(
    model=model,
    train_dataset=ds,
    peft_config=peft_config,
    args=training_args,
    tokenizer=tokenizer,
)

trainer.train()
trainer.push_to_hub()
print("[Way2AGI] Training complete! Model pushed to", HF_REPO)
'''
    return script


def generate_gguf_script(model_repo: str = HF_MODEL_REPO) -> str:
    """Generate a UV script for GGUF conversion on HF Jobs."""
    return f'''# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "transformers>=4.50",
#   "torch>=2.4",
#   "gguf>=0.6",
#   "huggingface-hub>=0.25",
#   "peft>=0.15",
#   "sentencepiece",
# ]
# ///
"""Convert Way2AGI model to GGUF for Ollama deployment."""

import subprocess, os
from huggingface_hub import snapshot_download, HfApi
from pathlib import Path

MODEL_REPO = "{model_repo}"
OUTPUT_DIR = "/data/output/gguf"

# Download the trained model
model_path = snapshot_download(MODEL_REPO, local_dir="/data/model")

# Clone llama.cpp for conversion
if not Path("/data/llama.cpp").exists():
    subprocess.run(["git", "clone", "https://github.com/ggerganov/llama.cpp.git", "/data/llama.cpp"], check=True)

# Install conversion deps
subprocess.run(["pip", "install", "-r", "/data/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt"], check=True)

# Convert to GGUF (Q4_K_M quantization for mobile)
os.makedirs(OUTPUT_DIR, exist_ok=True)
gguf_path = f"{{OUTPUT_DIR}}/way2agi-q4_K_M.gguf"

subprocess.run([
    "python", "/data/llama.cpp/convert_hf_to_gguf.py",
    model_path,
    "--outfile", gguf_path,
    "--outtype", "q4_K_M",
], check=True)

# Upload GGUF to HF
api = HfApi()
api.upload_file(
    path_or_fileobj=gguf_path,
    path_in_repo="way2agi-q4_K_M.gguf",
    repo_id=f"{{MODEL_REPO}}-GGUF",
    repo_type="model",
)

print(f"[Way2AGI] GGUF uploaded to {{MODEL_REPO}}-GGUF")
print(f"[Way2AGI] To deploy: ollama create way2agi -f Modelfile")
'''


def generate_modelfile(gguf_url: str = "") -> str:
    """Generate Ollama Modelfile for deploying the GGUF model."""
    return f'''FROM {gguf_url or "way2agi-q4_K_M.gguf"}

TEMPLATE """{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
<|im_start|>assistant
"""

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
PARAMETER stop "<|im_end|>"

SYSTEM """Du bist Way2AGI, ein selbstverbessernder AI-Assistent.
Du hilfst bei Code, Analyse, Reasoning und kreativen Aufgaben.
Antworte praezise und strukturiert. Verwende Deutsch wenn der User Deutsch spricht."""
'''


def save_pipeline_scripts(output_dir: str | Path | None = None) -> dict[str, Path]:
    """Save all pipeline scripts to disk, ready for execution."""
    out = Path(output_dir or Path.home() / ".way2agi" / "pipeline")
    out.mkdir(parents=True, exist_ok=True)

    scripts = {}

    # SFT training script
    sft_script = out / "train_sft.py"
    sft_script.write_text(generate_training_script(), encoding="utf-8")
    scripts["sft_train"] = sft_script

    # GGUF conversion script
    gguf_script = out / "convert_gguf.py"
    gguf_script.write_text(generate_gguf_script(), encoding="utf-8")
    scripts["gguf_convert"] = gguf_script

    # Ollama Modelfile
    modelfile = out / "Modelfile"
    modelfile.write_text(generate_modelfile(), encoding="utf-8")
    scripts["modelfile"] = modelfile

    print(f"[GGUF Pipeline] Scripts saved to {out}/")
    for name, path in scripts.items():
        print(f"  {name}: {path}")

    return scripts


def print_pipeline_instructions() -> None:
    """Print step-by-step instructions for the full pipeline."""
    print("""
=== Way2AGI Self-Improving Pipeline ===

Step 1: Generate training data (already done)
  python -m research.src.training_data

Step 2: Upload to HuggingFace
  python -c "from research.src.gguf_pipeline import upload_to_hf; upload_to_hf('~/.way2agi/training/sft-traces-*.jsonl')"

Step 3: Launch SFT training on HF Jobs
  hf jobs run ~/.way2agi/pipeline/train_sft.py --gpu a10g-small --timeout 3600

Step 4: Convert to GGUF
  hf jobs run ~/.way2agi/pipeline/convert_gguf.py --gpu a10g-small --timeout 1800

Step 5: Deploy to Ollama
  ollama create way2agi -f ~/.way2agi/pipeline/Modelfile

Step 6: Test
  ollama run way2agi "Erklaere den Unterschied zwischen MoA und MoE"
""")


if __name__ == "__main__":
    scripts = save_pipeline_scripts()
    print_pipeline_instructions()

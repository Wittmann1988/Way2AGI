#!/usr/bin/env python3
"""
Way2AGI SFT Training Script — Run on Gaming PC with GPU.

Usage:
    pip install trl peft transformers accelerate datasets torch huggingface-hub
    huggingface-cli login
    python train_on_pc.py
"""

from datasets import load_dataset
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

print("[Way2AGI] Loading dataset from HuggingFace...")
dataset = load_dataset("erik1988/way2agi-traces", split="train")
print(f"[Way2AGI] {len(dataset)} training examples loaded")

ds = dataset.train_test_split(test_size=0.1, seed=42)
print(f"[Way2AGI] Train: {len(ds['train'])}, Eval: {len(ds['test'])}")

config = SFTConfig(
    output_dir="way2agi-sft",
    push_to_hub=True,
    hub_model_id="erik1988/way2agi-model",
    hub_strategy="every_save",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    warmup_ratio=0.1,
    lr_scheduler_type="cosine",
    logging_steps=5,
    save_strategy="epoch",
    save_total_limit=2,
    eval_strategy="epoch",
    bf16=True,
)

peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
)

print("[Way2AGI] Initializing trainer with Qwen2.5-3B-Instruct + LoRA...")
trainer = SFTTrainer(
    model="Qwen/Qwen2.5-3B-Instruct",
    train_dataset=ds["train"],
    eval_dataset=ds["test"],
    args=config,
    peft_config=peft_config,
)

print("[Way2AGI] Starting SFT training...")
trainer.train()

print("[Way2AGI] Pushing to HuggingFace Hub...")
trainer.push_to_hub()

print("[Way2AGI] Done! Model: https://huggingface.co/erik1988/way2agi-model")

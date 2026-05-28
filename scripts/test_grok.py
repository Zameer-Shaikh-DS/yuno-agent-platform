#!/usr/bin/env python3
"""Smoke test for LLM API (xAI Grok or Groq). Run from project root: py -3.11 scripts/test_grok.py"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from app.llm_provider import resolve_llm_config

cfg = resolve_llm_config()
if not cfg.api_key:
    print("ERROR: Set XAI_API_KEY (xai-...) or GROQ_API_KEY / gsk_ key in .env")
    sys.exit(1)

from openai import OpenAI

client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
model = cfg.default_model

print(f"Provider: {cfg.provider}")
print(f"Base URL: {cfg.base_url}")
print(f"Model: {model}")
print("Sending test message...")

try:
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with exactly: llm-ok"}],
        max_tokens=20,
    )
    print("Response:", r.choices[0].message.content)
    print("Usage:", r.usage)
    print(f"{cfg.provider.upper()} API OK")
except Exception as e:
    print(f"ERROR: {e}")
    if cfg.provider == "groq":
        print("\nGroq tip: key starts with gsk_ — get one at https://console.groq.com")
        print("Set GROQ_MODEL=llama-3.3-70b-versatile in .env")
    else:
        print("\nxAI tip: key starts with xai- — get one at https://console.x.ai")
        print("Set XAI_MODEL=grok-3-mini in .env")
    sys.exit(1)

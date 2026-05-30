"""
Quick diagnostic — run this BEFORE the server to see exactly which
embedding models your API key has access to.

Usage:
    python test_embeddings.py
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)

import google.generativeai as genai

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌  GOOGLE_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=api_key)

print("\n📋  Embedding models available for your API key:\n")
found = []
for m in genai.list_models():
    if "embedContent" in m.supported_generation_methods:
        print(f"  ✅  {m.name}")
        found.append(m.name)

if not found:
    print("  ❌  No embedding models found — check your API key permissions")
    exit(1)

# Test the first available model
test_model = found[0]
print(f"\n🧪  Testing embed_content with: {test_model}")
try:
    result = genai.embed_content(
        model=test_model,
        content="RoadAid test sentence",
        task_type="retrieval_document",
    )
    print(f"  ✅  Success! Embedding dimension: {len(result['embedding'])}")
    print(f"\n👉  Set this in your .env:\n     GEMINI_EMBEDDING_MODEL={test_model}")
except Exception as e:
    print(f"  ❌  Failed: {e}")

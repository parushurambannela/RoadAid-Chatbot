"""
ChromaDB Inspector — equivalent of opening MongoDB Compass.

Usage:
    python inspect_chroma.py
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)

import chromadb

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

client = chromadb.PersistentClient(path=CHROMA_DIR)

# ── 1. List all collections (like listing MongoDB collections) ──────────────
collections = client.list_collections()
print(f"\n📦  Collections in ChromaDB  ({CHROMA_DIR})")
print("─" * 50)

if not collections:
    print("  (empty — no documents uploaded yet)")
else:
    for col in collections:
        c = client.get_collection(col.name)
        print(f"  📁  {col.name}   ({c.count()} chunks)")

# ── 2. Inspect the roadaid_docs collection ──────────────────────────────────
COLLECTION = "roadaid_docs"
try:
    col = client.get_collection(COLLECTION)
except Exception:
    print(f"\n❌  Collection '{COLLECTION}' not found. Upload a PDF first.")
    exit(0)

total = col.count()
print(f"\n🔍  Collection: '{COLLECTION}'  —  {total} total chunks")
print("─" * 50)

if total == 0:
    print("  (no chunks yet)")
    exit(0)

# ── 3. Peek at first 5 chunks (like a .find().limit(5) in Mongo) ────────────
peek = col.peek(limit=5)

print(f"\n📄  First 5 chunks (out of {total}):\n")
for i, (doc_id, text, meta) in enumerate(
    zip(peek["ids"], peek["documents"], peek["metadatas"]), start=1
):
    print(f"  [{i}] ID       : {doc_id}")
    print(f"      Source   : {meta.get('source', 'unknown')}")
    print(f"      Page     : {meta.get('page', '?')}")
    print(f"      Text     : {text[:120].strip()}...")
    print()

# ── 4. Get ALL document sources (which PDFs are indexed) ────────────────────
all_meta = col.get(include=["metadatas"])["metadatas"]
sources = sorted({m.get("source", "unknown") for m in all_meta})

print(f"📎  Indexed PDFs ({len(sources)}):")
for s in sources:
    chunks_for_source = sum(1 for m in all_meta if m.get("source") == s)
    print(f"    • {os.path.basename(s)}  ({chunks_for_source} chunks)")

# ── 5. Run a similarity search (like a Mongo $text search) ──────────────────
print("\n🔎  Similarity search test:")
query = input("   Enter a test query (or press Enter to skip): ").strip()

if query:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embeddings = GoogleGenerativeAIEmbeddings(
        model=os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-2"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        task_type="retrieval_query",   # use query type for search
    )
    query_vector = embeddings.embed_query(query)

    results = col.query(
        query_embeddings=[query_vector],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )

    print(f"\n   Top 3 results for: '{query}'\n")
    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ), start=1):
        print(f"   [{i}] Score    : {1 - dist:.3f}  (1.0 = perfect match)")
        print(f"       Source   : {meta.get('source', '?')}  page {meta.get('page', '?')}")
        print(f"       Text     : {doc[:150].strip()}...")
        print()

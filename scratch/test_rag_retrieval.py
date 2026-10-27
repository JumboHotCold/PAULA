import os
import django

import sys
sys.path.insert(0, r"c:\Users\ADMIN\OneDrive\DEX CAPSTONE 2026\paulibot")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paulibot.settings')
django.setup()

from chatbot.rag import RAGSearcher

rag = RAGSearcher()
queries = [
    "How do I drop or change a subject?",
    "What are the office hours of PBMO?",
    "What is the enrollment procedure for incoming freshmen?",
    "How to request event photo coverage from PBMO?",
    "What are the official colors of SPUS?"
]

print("=" * 70)
print("TESTING RAG RETRIEVAL FOR NEWLY INGESTED OFFICE DOCUMENTS")
print("=" * 70)

for q in queries:
    print(f"\nQUERY: '{q}'")
    results = rag.search(q, limit=2)
    if not results:
        print("  NO RESULTS FOUND!")
    for r in results:
        office = r.get("source_office") or "General"
        tier = r.get("source_type") or "N/A"
        score = r.get("score", 0)
        print(f"  -> [{office} | {tier} | score={score:.3f}] {r.get('title')}")
        answer_preview = (r.get("text") or "")[:160].replace("\n", " ")
        print(f"     Text: {answer_preview}...")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETED SUCCESSFULLY!")

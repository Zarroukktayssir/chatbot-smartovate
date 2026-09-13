import sys, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, '.')
from app.services.azure_ai_search_service import AzureAISearchService

s = AzureAISearchService()

questions = [
    "Quel est le prix d'un billet d'avion pour Paris",
    "Comment fonctionne ChatGPT ?",
    "Quel temps fait-il aujourd'hui ?",
    "Comment activer mon compte Smartovate ?",
]

for q in questions:
    docs = s.search(q, top_k=3)
    top = docs[0] if docs else {}
    score = round(top.get("score", 0), 5)
    source = top.get("source", "N/A")
    print(f"Q: {q}")
    print(f"  Top1: {source}  score={score}")
    for d in docs:
        print(f"    {d['source']}  {round(d['score'],5)}")
    print()

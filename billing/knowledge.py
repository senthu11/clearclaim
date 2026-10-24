"""Local lexical vector RAG with source IDs and exact procedure lookups."""

import hashlib
import json
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from sklearn.feature_extraction.text import HashingVectorizer

ROOT = Path(__file__).resolve().parents[1]


class LocalEmbeddings(Embeddings):
    """Hashing vectors: lexical retrieval, no model download or embedding API."""

    def __init__(self):
        self.vectorizer = HashingVectorizer(n_features=1024, alternate_sign=False,
                                           ngram_range=(1, 2), norm="l2")

    def embed_documents(self, texts):
        return self.vectorizer.transform(texts).toarray().tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class KnowledgeBase:
    def __init__(self):
        self.prices = {item["code"]: item for item in json.loads(
            (ROOT / "data/pricing.json").read_text(encoding="utf-8"))}
        self.policies = json.loads((ROOT / "data/policies.json").read_text(encoding="utf-8"))
        self.documents = [Document(page_content=item["text"], metadata={
            "source_id": item["id"], "title": item["title"], "kind": "policy",
        }) for item in self.policies]
        for code, item in self.prices.items():
            self.documents.append(Document(
                page_content=(f"SYNTHETIC FICTIONAL PRICE. Code {code}: {item['description']}. "
                              f"Reference price per unit USD {item['unit_price']}. "
                              f"Visit type: {item['visit_type']}. Not a real Medicare or insurer rate."),
                metadata={"source_id": f"PRICE-{code}", "title": item["description"],
                          "kind": "price", "code": code},
            ))
        for doc in self.documents:
            doc.metadata.update(version="2026.10.24", effective_date="Not applicable: fictional demo", applicability="Educational only; no real payer or jurisdiction", sha256=hashlib.sha256(doc.page_content.encode()).hexdigest())
        self.by_id = {doc.metadata["source_id"]: doc for doc in self.documents}
        self.store = InMemoryVectorStore(LocalEmbeddings())
        self.store.add_documents(self.documents)

    def get(self, source_id):
        return self.by_id.get(source_id)

    def retrieve(self, query, k=5):
        exact = [self.by_id[f"PRICE-{code}"] for code in self.prices
                 if re.search(rf"\b{re.escape(code)}\b", query)]
        # Exact procedure matches supplement lexical vector similarity.
        semantic = self.store.similarity_search(query, k=k)
        merged = {doc.metadata["source_id"]: doc for doc in exact + semantic}
        return list(merged.values())[:max(k, len(exact))]


def context_text(documents):
    return "\n\n".join(f"[{doc.metadata['source_id']}] {doc.page_content}" for doc in documents)

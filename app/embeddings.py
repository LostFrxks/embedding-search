import json
import numpy as np
from sentence_transformers import SentenceTransformer
from . import models

model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

PRICES = {
    "cheap": "очень дешевый телефон по минимальной цене",
    "affordable": "недорогой телефон по доступной цене",
    "medium": "телефон средней цены",
    "expensive": "дорогой качественный телефон",
    "premium": "очень дорогой премиум флагманский телефон"
}

PRICE_EMBEDDINGS = {
    name: model.encode(text).astype(float) 
    for name, text in PRICES.items()
}

def build_ad_text(ad: models.Ad) -> str:
    parts = []

    if ad.title:
        parts.append(ad.title)
        parts.append(ad.title)


     
    if ad.price is not None:
        try:
            price_int = int(ad.price)
            parts.append(f"цена {price_int} сом")
        except Exception:
            parts.append("есть цена")
    if ad.city:
        parts.append(f"Город {ad.city}")

    if ad.description:
        parts.append(ad.description)

    return ". ".join(parts)

def embed_text(text: str) -> list[float]:
    vec = model.encode(text)
    return vec.astype(float).tolist()

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    if denom == 0.0:
        return 0.0

    return float(np.dot(a, b) / denom)


def detect_price_intent(query: str) -> str:
    q_vec = model.encode(query).astype(float)
    best_name = "neutral"
    best_sim = 0.0
    for name, price_vec in PRICE_EMBEDDINGS.items():
        sim = cosine_sim(q_vec, price_vec)
        if sim > best_sim:
            best_sim = sim
            best_name = name

    if best_sim < 0.3:
        return "neutral"
    return best_name
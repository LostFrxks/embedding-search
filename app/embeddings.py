import json
import numpy as np
from sentence_transformers import SentenceTransformer
from . import models

model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')


def build_ad_text(ad: models.Ad) -> str:
    parts = []

    if ad.title:
        parts.append(ad.title)
    if ad.description:
        parts.append(ad.description)

    if ad.city:
        parts.append(ad.city)
    
    return ". ".join(parts)

def embed_text(text: str) -> list[float]:
    vec = model.encode(text)
    return vec.astype(float).tolist()

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    if denom == 0.0:
        return 0.0

    return float(np.dot(a, b) / denom)
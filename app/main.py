from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .db import get_db, init_db
from . import models
from pydantic import BaseModel
from .scraper_lalafo import scrape_lalafo
from sqlalchemy import or_
import json
import numpy as np
from .embeddings import build_ad_text, embed_text, cosine_sim, detect_price_intent
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AdCreate(BaseModel):
    title: str
    description: str | None = None
    price: float
    url: str
    city: str


@app.get("/ping")
def ping():
    return {"status":"ok"}


@app.get("/ads")
def list_ads(db: Session = Depends(get_db)):
    ads = db.query(models.Ad).all()
    return ads


@app.get("/ads/semantic_search")
def semantic_search(q: str, limit: int = 10, db: Session = Depends(get_db)):
    return run_semantic_search(q=q, limit=limit, db=db)





@app.get("/ads/local_search")
def local_search(
    q: str | None = None, 
    city: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Ad)

    if q:
        words = [w.strip() for w in q.split() if w.strip()]
        for w in words:
            pattern = f"%{w}%"
            query = query.filter(
                or_(
                    models.Ad.title.ilike(pattern),
                    models.Ad.description.ilike(pattern) # если искать и по описанию тоже, пока только по заголовку проверка
                )
            )
    if city:
        query = query.filter(models.Ad.city == city)

    if min_price is not None:
        query = query.filter(models.Ad.price >= min_price)
    
    if max_price is not None:
        query = query.filter(models.Ad.price <= max_price)
    
    query = query.order_by(models.Ad.id.desc())

    ads = query.limit(50).all()

    return [
        {
            "id": ad.id,
            "title": ad.title,
            "description": ad.description,
            "price": ad.price,
            "url": ad.url,
            "city": ad.city
        }
        for ad in ads
    ]




@app.post("/ads/refresh_lalafo")
def refresh_lalafo(limit: int = 500, db: Session = Depends(get_db)):
    scraped_ads = scrape_lalafo("", max_items=limit)
    urls = [ad.url for ad in scraped_ads if ad.url]
    existing_ads = []
    if urls:
        existing_ads = (
            db.query(models.Ad).filter(models.Ad.url.in_(urls)).all()
        )
    
    existing_by_url = {ad.url: ad for ad in existing_ads}
    new_urls = set()
    created = 0
    updated_emb = 0
    for s in scraped_ads[:limit]:
        if not s.url:
            continue
        existing = existing_by_url.get(s.url)
        if existing:
            if not existing.embedding:
                text = build_ad_text(existing)
                if text.strip():
                    vec = embed_text(text)
                    existing.embedding = json.dumps(vec)
                    updated_emb += 1
            continue 

        if s.url in new_urls:
            continue 

        ad = models.Ad(
            title=s.title,
            description=s.description,
            price=s.price,
            url=s.url,
            city=s.city
        )
        text = build_ad_text(ad)
        if text.strip():
            vec = embed_text(text)
            ad.embedding = json.dumps(vec)
        db.add(ad)
        created += 1
        new_urls.add(s.url)
    db.commit()
    return {
        "created": created,
        "updated_embeddings": updated_emb
    }


def run_semantic_search(q: str, limit: int, db: Session):
    query_vec = np.array(embed_text(q), dtype=float)

    ads = db.query(models.Ad).filter(models.Ad.embedding != None).all()
    scored = []
    for ad in ads:
        try:
            emb_list = json.loads(ad.embedding)
        except Exception:
            continue
        ad_vec = np.array(emb_list, dtype=float)
        score = cosine_sim(query_vec, ad_vec)
        scored.append((score, ad))
    if not scored:
        return {
            "query": q,
            "results": []
        }

    scored.sort(key=lambda x: x[0], reverse=True)
    
    top_semantic = scored[:limit * 5]

    price_detect = detect_price_intent(q)
    prices = [ad.price for _, ad in top_semantic if ad.price is not None]
    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None

    result = []
    alpha = 0.7
    for semantic_score, ad in top_semantic:
        if price_detect in ["cheap", "affordable", "expensive", "premium", "medium"] and ad.price is None:
            continue
        if ad.price is None or min_price is None or max_price is None or min_price == max_price:
            price_score = 0.5
        else:
            norm_price = (ad.price - min_price) / (max_price - min_price)
            if price_detect in ["cheap", "affordable"]:
                price_score = 1.0 - norm_price
            elif price_detect in ["expensive", "premium"]:
                price_score = norm_price
            elif price_detect == "medium":
                price_score = 1.0 - abs(0.5 - norm_price) * 2.0 
            else:
                price_score = 0.5

        final_score = alpha * semantic_score + (1.0 - alpha) * price_score
        result.append((final_score, semantic_score, price_score, ad))

    result.sort(key=lambda x: x[0], reverse=True)

    the_most = result[0][0]
    threshold = the_most - 0.3

    top = [i for i in result if i[0] >= threshold][:limit]
    return {
        "query": q,
        "price_intent": price_detect,
        "results": [
            {
                "id": ad.id,
                "title": ad.title,
                "description": ad.description,
                "price": ad.price,
                "url": ad.url,
                "city": ad.city,
                "final_score": float(final_score),
                "semantic_score": float(s_score),
                "price_score": float(price_score)
            }
            for final_score, s_score, price_score, ad in top
        ] 
    }

# @app.post("/ads")
# def create_ad(ad_in: AdCreate, db: Session = Depends(get_db)):
#     ad = models.Ad(
#         title=ad_in.title,
#         description=ad_in.description,
#         price=ad_in.price,
#         url=ad_in.url,
#         city=ad_in.city
#     )

#     db.add(ad)
#     db.commit()
#     db.refresh(ad)
#     return ad

# @app.post("/ads/update_embeddings")
# def update_embeddings(db: Session = Depends(get_db)):
#     ads = db.query(models.Ad).filter(models.Ad.embedding == None).all()

#     updated = 0

#     for ad in ads:
#         text = build_ad_text(ad)
#         if not text.strip():
#             continue

#         vec = embed_text(text)
#         ad.embedding = json.dumps(vec)
#         updated += 1
    
#     db.commit()

#     return {"updated": updated}


# @app.get("/ads/semantic_search")
# def semantic_search(
#     q: str,
#     limit: int = 10,
#     db: Session = Depends(get_db)
# ):
#     query_vec = np.array(embed_text(q), dtype=float)

#     ads = db.query(models.Ad).filter(models.Ad.embedding != None).all()

#     scored : list[tuple[float, models.Ad]] = []

#     for ad in ads:
#         try:
#             emb_list = json.loads(ad.embedding)
#         except Exception:
#             continue
#         ad_vec = np.array(emb_list, dtype=float)
#         score = cosine_sim(query_vec, ad_vec)
#         scored.append((score, ad))

#     if not scored:
#         return {
#             "query": q,
#             "results": []
#         }

#     scored.sort(key=lambda x: x[0], reverse=True)
#     threshold = scored[0][0] - 0.1

#     filtered = [(s, ad) for s, ad in scored if s >= threshold][:limit]

#     return {
#         "query": q,
#         "results": [
#             {
#                 "id": ad.id,
#                 "title": ad.title,
#                 "description": ad.description,
#                 "price": ad.price,
#                 "url": ad.url,
#                 "city": ad.city,
#                 "score": score
#             }
#             for score, ad in filtered
#         ]
#     }
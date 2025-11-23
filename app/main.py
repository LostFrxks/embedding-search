from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .db import get_db
from . import models
from pydantic import BaseModel
from .scraper_lalafo import scrape_lalafo
from sqlalchemy import or_
import json
import numpy as np
from .embeddings import build_ad_text, embed_text, cosine_sim
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

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


@app.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    scraped_ads = scrape_lalafo(q)
    stored_ads: list[models.Ad] = []

    urls = [ad.url for ad in scraped_ads if ad.url]
    ex_urls: dict[str, models.Ad] = {}

    if urls:
        existing_ads = (
            db.query(models.Ad)
            .filter(models.Ad.url.in_(urls))
            .all()
        )
        ex_urls = {ad.url: ad for ad in existing_ads}
    new_urls: set[str] = set()

    for s in scraped_ads:
        if not s.url:
            continue
        existing = ex_urls.get(s.url)
        if existing:
            stored_ads.append(existing)
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
        stored_ads.append(ad)
        new_urls.add(s.url)
    db.commit()
    for ad in stored_ads:
        db.refresh(ad)
    
    return {
        "query": q,
        "count": len(stored_ads),
        "results": [
            {
                "id": ad.id,
                "title": ad.title,
                "description": ad.description,
                "price": ad.price,
                "url": ad.url,
                "city": ad.city
            }   
            for ad in stored_ads
        ]
    }


@app.post("/ads")
def create_ad(ad_in: AdCreate, db: Session = Depends(get_db)):
    ad = models.Ad(
        title=ad_in.title,
        description=ad_in.description,
        price=ad_in.price,
        url=ad_in.url,
        city=ad_in.city
    )

    db.add(ad)
    db.commit()
    db.refresh(ad)
    return ad


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


@app.get("/ads/semantic_search")
def semantic_search(
    q: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    query_vec = np.array(embed_text(q), dtype=float)

    ads = db.query(models.Ad).filter(models.Ad.embedding != None).all()

    scored : list[tuple[float, models.Ad]] = []

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

    [0.8, 0,75, 0.7, 0.65, 0.50]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]
    threshold = best_score - 0.1

    filtered = [(s, ad) for s, ad in scored if s >= threshold][:limit]

    return {
        "query": q,
        "results": [
            {
                "id": ad.id,
                "title": ad.title,
                "description": ad.description,
                "price": ad.price,
                "url": ad.url,
                "city": ad.city,
                "score": score
            }
            for score, ad in filtered
        ]
    }

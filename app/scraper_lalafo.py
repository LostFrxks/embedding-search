from typing import List 
import httpx 
from bs4 import BeautifulSoup
import re


BASE_CATEGORY_URL = "https://lalafo.kg/kyrgyzstan/mobilnye-telefony-i-aksessuary/mobilnye-telefony"

class LalafoAd:
    def __init__(self, title: str, price: float | None, url: str, city: str | None = None, description: str | None = None):
        self.title = title
        self.price = price
        self.url = url
        self.city = city
        self.description = description
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "price": self.price,
            "url": self.url,
            "city": self.city,
            "description": self.description
        }


# def make_req(query: str) -> str:
#     q = query.strip().lower()
#     q = re.sub(r"\s+", "-", q)
#     q = re.sub(r"[^a-z0-9\-]+", "", q)
#     q = re.sub(r"-+", "-", q).strip("-")
#     return q


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def scrape_lalafo(query:str) -> List[LalafoAd]:
    q_for_path = query.strip()
    if q_for_path:
        search_url = f"{BASE_CATEGORY_URL}/q-{q_for_path}"
    else:
        search_url = BASE_CATEGORY_URL

    with httpx.Client(timeout=10.0) as client:
        response = client.get(
            search_url,
            params={"q": query},
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; mbank-scraper/1.0)"
            }
        )
    html = response.text
    print(html)
    soup = BeautifulSoup(html, "html.parser")

    ad_cards = soup.select("article[class*='LFAdTileHorizontal']")

    ads = []
    for card in ad_cards:
        title_el = card.select_one("a[class*='Header_adTileHorizontalHeaderLinkTitle']")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)

        discription = None
        for i in range(len(title)):
            if title[i] == ",":
                discription = title[i+1:].strip()
                title = title[:i].strip()
                break
        
        href = title_el.get("href") or ""
        if href.startswith("http"):
            url = href
        else:
            url = "https://lalafo.kg" + href


        price = None 
        for p in card.select("p[class*='LFSubHeading']"):
            text = p.get_text(strip=True)
            if "KGS" in text or "сом" in text.lower():
                price = parse_price(text)
                break


        city_wrap = card.select_one("div[class*='FooterMetaInfoCityWrap']")
        if city_wrap:
            city_el = city_wrap.select_one("span")
            city = city_el.get_text(strip=True) if city_el else None    
        else:
            city = None
        ads.append(
            LalafoAd(
                title=title,
                price=price,
                url=url,
                city=city,
                description=discription
            )
        )

    return ads
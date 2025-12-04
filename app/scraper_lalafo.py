from typing import List 
import httpx 
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

BASE_SITE_URL = "https://lalafo.kg"
BASE_CATEGORY_URL = f"{BASE_SITE_URL}/kyrgyzstan/mobilnye-telefony-i-aksessuary/mobilnye-telefony"

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

def scrape_lalafo(query: str, max_items: int = 100) -> List[LalafoAd]:
    ads: List[LalafoAd] = []
    seen_urls: set[str] = set()

    if query.strip():
        q_param = quote_plus(query.strip())
        url = f"{BASE_CATEGORY_URL}?q={q_param}"
    else:
        url = BASE_CATEGORY_URL

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle")

        prev_cards_count = 0
        stagnant_rounds = 0

        while len(ads) < max_items and stagnant_rounds < 5:
            card_elements = page.query_selector_all("article[class*='LFAdTileHorizontal']")
            current_count = len(card_elements)

            if current_count == prev_cards_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                prev_cards_count = current_count

            for card in card_elements:
                title_el = card.query_selector("a[class*='Header_adTileHorizontalHeaderLinkTitle']")
                if not title_el:
                    continue

                href = title_el.get_attribute("href") or ""
                if href.startswith("http"):
                    full_url = href
                else:
                    full_url = BASE_SITE_URL + href

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                title_text = title_el.inner_text().strip()
                title = title_text
                description = None

                comma_idx = title_text.find(",")
                if comma_idx != -1:
                    title = title_text[:comma_idx].strip()
                    description = title_text[comma_idx + 1 :].strip()

                price = None
                price_nodes = card.query_selector_all("p[class*='LFSubHeading']")
                for p_node in price_nodes:
                    t = p_node.inner_text().strip()
                    if "KGS" in t or "сом" in t.lower():
                        price = parse_price(t)
                        break

                city = None
                city_wrap = card.query_selector("div[class*='FooterMetaInfoCityWrap']")
                if city_wrap:
                    span = city_wrap.query_selector("span")
                    if span:
                        city = span.inner_text().strip()

                ads.append(
                    LalafoAd(
                        title=title,
                        price=price,
                        url=full_url,
                        city=city,
                        description=description,
                    )
                )

                if len(ads) >= max_items:
                    break

            if len(ads) >= max_items:
                break

            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

        browser.close()

    return ads
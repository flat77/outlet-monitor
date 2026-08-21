import os
import json
import requests
from playwright.sync_api import sync_playwright

PUSHBULLET_TOKEN = os.environ.get("PUSHBULLET_TOKEN")
DB_FILE = "seen_products.json"

URLS = {
    "Komplett": "https://www.komplett.se/category/21611/demo-fyndvaror?q=asus+rog+ally",
    "Inet": "https://www.inet.se/kategori/851/fyndhorna?q=asus+rog+ally",
    "Webhallen": "https://www.webhallen.se/se/search?query=asus%20rog%20ally&condition=1",
    "Elgiganten": "https://www.elgiganten.se/outlet?q=asus+rog+ally",
    "Power": "https://www.power.se/outlet/search/?q=asus+rog+ally+outlet",
    "Blocket": "https://www.blocket.se/e/annonser?q=asus+rog+ally",
    "Facebook Marketplace (Uppsala 7 mil)": "https://www.facebook.com/marketplace/uppsala/search?query=asus%20rog%20ally&exact=false"
}

def load_seen_products():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[VARNING] Kunde inte läsa {DB_FILE}: {e}")
    return set()

def save_seen_products(seen_set):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen_set), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[FEL] Kunde inte spara till {DB_FILE}: {e}")

def send_push_notification(title, body):
    if not PUSHBULLET_TOKEN:
        print("[VARNING] Ingen PUSHBULLET_TOKEN hittades! Hoppar över notis.")
        return

    url = "https://api.pushbullet.com/v2/pushes"
    headers = {
        "Access-Token": PUSHBULLET_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {"type": "note", "title": title, "body": body}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print("[INFO] Pushnotis skickades framgångsrikt.")
        else:
            print(f"[FEL] Kunde inte skicka notis. Statuskod: {response.status_code}")
    except Exception as e:
        print(f"[FEL] Undantag vid notisskickning: {e}")

def run():
    print("=== Startar Outlet-skanning ===")
    seen_products = load_seen_products()
    new_found = False

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="sv-SE",
            timezone_id="Europe/Stockholm"
        )
        
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for store, url in URLS.items():
            print(f"\n[INFO] Skannar {store}...")
            safe_store_name = "".join(c for c in store if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")

            try:
                try:
                    page.goto(url, timeout=45000, wait_until="networkidle")
                except Exception:
                    page.goto(url, timeout=45000, wait_until="domcontentloaded")
                
                page.wait_for_timeout(3000)

                # Sparar skärmdump och HTML för artifacts/felsökning
                try:
                    page.screenshot(path=f"debug_{safe_store_name}.png", full_page=True)
                    with open(f"debug_{safe_store_name}.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                except Exception as debug_err:
                    print(f"[VARNING] Kunde inte spara debug-filer för {store}: {debug_err}")

                # SPECIFIK LOGIK FÖR BLOCKET.SE
                if store == "Blocket":
                    try:
                        popup_close = page.locator("button:has-text('Godkänn'), button:has-text('Acceptera'), button:has-text('Påminn mig senare'), [aria-label='Stäng']")
                        if popup_close.first.is_visible(timeout=3000):
                            popup_close.first.click()
                    except Exception:
                        pass

                    product_cards = page.locator("a[href*='/annons/']").all()
                    found_blocket_product = False

                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        if "rog ally" in card_text:
                            found_blocket_product = True
                            clean_name = " ".join(card_text.split())[:80]
                            product_id = f"Blocket:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                message = f"Ny träff på Blocket:\n{clean_name}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] Blocket: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Blocket!", message)
                            else:
                                print("[INFO] Träff finns på Blocket, men har redan notifierats.")
                            break

                    if not found_blocket_product:
                        print("[INFO] Inga annonser hittades på Blocket.")

                # SPECIFIK LOGIK FÖR POWER.SE
                elif store == "Power":
                    no_results = page.locator("text=/0 träffar|inga produkter/i").count()
                    product_cards = page.locator("a[href*='/p-']").all()
                    
                    found_power_product = False
                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        if "rog ally" in card_text:
                            found_power_product = True
                            clean_name = " ".join(card_text.split())[:60]
                            product_id = f"Power:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                message = f"Ny träff hos Power:\n{clean_name}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] Power: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Power!", message)
                            else:
                                print("[INFO] Träff finns på Power, men har redan notifierats.")
                            break
                    
                    if not found_power_product or no_results > 0:
                        print("[INFO] Inga riktiga produkter hittades på Power.")

                # SPECIFIK LOGIK FÖR KOMPLETT.SE
                elif store == "Komplett":
                    product_cards = page.locator(".product-list-item, .product-box, [data-product-id]").all()
                    found_komplett_product = False

                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        if "rog ally" in card_text:
                            found_komplett_product = True
                            clean_name = " ".join(card_text.split())[:60]
                            product_id = f"Komplett:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                message = f"Ny träff hos Komplett Demo:\n{clean_name}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] Komplett: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Komplett Demo!", message)
                            else:
                                print("[INFO] Träff finns på Komplett, men har redan notifierats.")
                            break

                    if not found_komplett_product:
                        print("[INFO] Inga demovaror hittades på Komplett.")

                # SPECIFIK LOGIK FÖR INET.SE
                elif store == "Inet":
                    product_cards = page.locator(".product-card, a[href*='/produkt/']").all()
                    found_inet_product = False

                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        if "rog ally" in card_text:
                            found_inet_product = True
                            clean_name = " ".join(card_text.split())[:60]
                            product_id = f"Inet:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                message = f"Ny träff hos Inet Fyndhörna:\n{clean_name}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] Inet: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Inet Fyndhörna!", message)
                            else:
                                print("[INFO] Träff finns på Inet, men har redan notifierats.")
                            break

                    if not found_inet_product:
                        print("[INFO] Inga fyndvaror hittades på Inet.")

                # SPECIFIK LOGIK FÖR WEBHALLEN.SE
                elif store == "Webhallen":
                    product_cards = page.locator(".product-list-item, a[href*='/product/']").all()
                    found_webhallen_product = False

                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        if "rog ally" in card_text:
                            found_webhallen_product = True
                            clean_name = " ".join(card_text.split())[:60]
                            product_id = f"Webhallen:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                message = f"Ny träff hos Webhallen Fyndvara:\n{clean_name}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] Webhallen: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Webhallen Fyndvara!", message)
                            else:
                                print("[INFO] Träff finns på Webhallen, men har redan notifierats.")
                            break

                    if not found_webhallen_product:
                        print("[INFO] Inga fyndvaror hittades på Webhallen.")

                # ALLMÄN LOGIK FÖR ÖVRIGA BUTIKER (Elgiganten, Facebook)
                else:
                    body_text = page.inner_text("body").lower()
                    search_term = "rog ally"

                    if search_term in body_text:
                        elements = page.locator(f"text=/{search_term}/i").all()
                        
                        for el in elements:
                            text = el.inner_text().strip()
                            if len(text) > 15:
                                clean_text = " ".join(text.split())[:80]
                                product_id = f"{store}:{clean_text}"

                                if product_id not in seen_products:
                                    seen_products.add(product_id)
                                    new_found = True
                                    message = f"Ny träff hos {store}:\n{clean_text}\n\nLänk: {url}"
                                    print(f"[NY TRÄFF] {store}: {clean_text}")
                                    send_push_notification(f"Ny Asus ROG Ally på {store}!", message)
                                else:
                                    print(f"[INFO] Träff finns på {store}, men har redan notifierats.")
                                break
                    else:
                        print(f"[INFO] Inga träffar på {store}.")

            except Exception as e:
                print(f"[FEL] Kunde inte skanna {store}: {e}")

        browser.close()

    if new_found:
        save_seen_products(seen_products)
        print("[INFO] Nya produkter har sparats till minnet.")

    print("\n=== Skanning klar ===")

if __name__ == "__main__":
    run()

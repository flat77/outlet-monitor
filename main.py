import os
import json
import requests
from playwright.sync_api import sync_playwright

PUSHBULLET_TOKEN = os.environ.get("PUSHBULLET_TOKEN")
DB_FILE = "seen_products.json"

URLS = {
    "Elgiganten": "https://www.elgiganten.se/outlet?q=asus+rog+ally",
    "Power": "https://www.power.se/search/?q=asus+rog+ally",
    "Blocket": "https://www.blocket.se/skopa/erbjudanden?q=asus+rog+ally",
    "Facebook Marketplace (Uppsala 7 mil)": "https://www.facebook.com/marketplace/uppsala/search?query=asus%20rog%20ally&exact=false"
}

def load_seen_products():
    """Laddar tidigare sedda produkter från JSON-filen."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[VARNING] Kunde inte läsa {DB_FILE}: {e}")
    return set()

def save_seen_products(seen_set):
    """Sparar sedda produkter till JSON-filen."""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen_set), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[FEL] Kunde inte spara till {DB_FILE}: {e}")

def send_push_notification(title, body):
    """Skickar pushnotis via Pushbullet."""
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
    print("=== Startar Outlet-skanning med historik ===")
    seen_products = load_seen_products()
    new_found = False

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for store, url in URLS.items():
            print(f"\n[INFO] Skannar {store}...")
            try:
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                
                body_text = page.inner_text("body").lower()
                search_term = "rog ally"

                if search_term in body_text:
                    elements = page.locator(f"text=/{search_term}/i").all()
                    
                    for el in elements:
                        text = el.inner_text().strip()
                        if len(text) > 12:
                            # Skapar ett unikt ID för produkten baserat på butik och text
                            product_id = f"{store}:{text[:80]}"

                            # KONTROLL: Skicka ENDAST push om produkten ÄR NY!
                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                
                                message = f"Ny träff hos {store}:\n{text[:120]}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] {store}: {text[:60]}")
                                send_push_notification(f"Ny Asus ROG Ally på {store}!", message)
                            else:
                                print(f"[INFO] Träff hittad på {store}, men produkten har redan skickats tidigare.")
                            break
                else:
                    print(f"[INFO] Inga träffar på {store}.")

            except Exception as e:
                print(f"[FEL] Kunde inte skanna {store}: {e}")

        browser.close()

    if new_found:
        save_seen_products(seen_products)
        print("[INFO] Nya produkter har sparats till databasen.")

    print("\n=== Skanning klar ===")

if __name__ == "__main__":
    run()

import os
import requests
from playwright.sync_api import sync_playwright

# Pushbullet-konfiguration
PUSHBULLET_TOKEN = os.environ.get("PUSHBULLET_TOKEN")

# Butiker och sök-URL:er
STORES = {
    "Blocket": "https://www.blocket.se/e/annonser?q=asus+rog+ally",
    # Lägg till dina övriga butiker här nedanför
}

# Håller koll på redan notifierade produkter under körningen
seen_products = set()

def send_push_notification(title, body):
    if not PUSHBULLET_TOKEN:
        print("[VARNING] Ingen PUSHBULLET_TOKEN hittades i environment variables.")
        return
    url = "https://api.pushbullet.com/v2/pushes"
    headers = {
        "Access-Token": PUSHBULLET_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "type": "note",
        "title": title,
        "body": body
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        print("[INFO] Notis skickad via Pushbullet!")
    else:
        print(f"[FEL] Kunna inte skicka notis: {response.status_code} - {response.text}")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Använd en realistisk User-Agent för att undvika enkla bot-spärrar
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for store, url in STORES.items():
            print(f"\n--- Kontrollerar: {store} ---")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)  # Skapa marginal för dynamiskt innehåll

                # Ta skärmdump och spara HTML för felsökning/artifacts
                page.screenshot(path=f"debug_{store}.png")
                with open(f"debug_{store}.html", "w", encoding="utf-8") as f:
                    f.write(page.content())

                # ==========================================
                # SPECIFIK LOGIK FÖR BLOCKET
                # ==========================================
                if store == "Blocket":
                    # Klicka bort popups, cookie-banners eller "Påminn mig senare"-dialoger
                    try:
                        popup_close = page.locator("button:has-text('Godkänn'), button:has-text('Acceptera'), button:has-text('Påminn mig senare'), [aria-label='Stäng']")
                        if popup_close.first.is_visible(timeout=3000):
                            popup_close.first.click()
                            print("[INFO] Stängde popup på Blocket.")
                    except Exception:
                        pass

                    # Leta efter Blocket-annonser (länkar till enskilda annonser)
                    product_cards = page.locator("a[href*='/annons/']").all()
                    found_product = False

                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        if "rog ally" in card_text:
                            found_product = True
                            clean_name = " ".join(card_text.split())[:80]
                            product_id = f"Blocket:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                message = f"Ny träff på Blocket:\n{clean_name}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] Blocket: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Blocket!", message)
                            else:
                                print("[INFO] Träff finns på Blocket, men har redan notifierats.")
                            break

                    if not found_product:
                        print("[INFO] Inga relevanta annonser hittades på Blocket.")

                # ==========================================
                # ÖVRIGA BUTIKER (T.EX. KOMPLETT / WEBHALLEN)
                # ==========================================
                else:
                    print(f"[INFO] Ingen specifik logik tillagd för {store} än.")

            except Exception as e:
                print(f"[FEL] Ett fel uppstod vid kontroll av {store}: {e}")

        browser.close()

if __name__ == "__main__":
    main()

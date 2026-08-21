import os
import sys
import requests
from playwright.sync_api import sync_playwright

# Hämtar Pushbullet-token säkert från GitHub Secrets (miljövariabler)
PUSHBULLET_TOKEN = os.environ.get("PUSHBULLET_TOKEN")

# Butiker som ska övervakas
URLS = {
    "Elgiganten": "https://www.elgiganten.se/outlet?q=asus+rog+ally",
    "Power": "https://www.power.se/search/?q=asus+rog+ally"
}

def send_push_notification(title, body):
    """Skickar en pushnotis till mobilen via Pushbullet API."""
    if not PUSHBULLET_TOKEN:
        print("[VARNING] Ingen PUSHBULLET_TOKEN hittades i miljövariablerna! Hoppar över notis.")
        return

    url = "https://api.pushbullet.com/v2/pushes"
    headers = {
        "Access-Token": PUSHBULLET_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "type": "note",
        "title": title,
        "body": body
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print("[INFO] Pushnotis skickades framgångsrikt till telefonen.")
        else:
            print(f"[FEL] Kunde inte skicka notis. Statuskod: {response.status_code}, Svar: {response.text}")
    except Exception as e:
        print(f"[FEL] Ett undantag uppstod vid skickande av notis: {e}")

def run():
    print("=== Startar Outlet-skanning ===")
    
    with sync_playwright() as playwright:
        # Startar en headless Chromium-webbläsare
        browser = playwright.chromium.launch(headless=True)
        
        # Sätter en realistisk User-Agent för att undvika Cloudflare/bot-spärrar
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for store, url in URLS.items():
            print(f"\n[INFO] Skannar {store}...")
            try:
                # Laddar sidan och väntar på att nätverkstrafiken ska tystna (dynamiskt innehåll laddats)
                page.goto(url, timeout=45000, wait_until="networkidle")
                
                # Hämtar all text på sidan i gemener
                body_text = page.inner_text("body").lower()

                # Kontrollerar om sökfrasen finns
                if "rog ally" in body_text:
                    # Söker upp specifika textnoder som matchar sökordet
                    elements = page.locator("text=/rog ally/i").all()
                    
                    found_valid_product = False
                    for el in elements:
                        text = el.inner_text().strip()
                        # Filtrera bort för korta träffar (t.ex. sökrutor eller menyer)
                        if len(text) > 10:
                            found_valid_product = True
                            message = f"Möjlig träff hos {store}:\n{text[:120]}\n\nLänk: {url}"
                            print(f"[HIT] Produkthittad på {store}!")
                            print(f"Träfftext: {text[:100]}")
                            
                            # Skickar pushnotis
                            send_push_notification(f"Asus ROG Ally funnen på {store}!", message)
                            break  # Skickar en notis per butik vid träff
                    
                    if not found_valid_product:
                        print(f"[INFO] Texten 'rog ally' fanns på sidan hos {store}, men ingen enskild produkt kunde isoleras.")
                else:
                    print(f"[INFO] Inga produkter hittades på {store}.")

            except Exception as e:
                print(f"[FEL] Kunde inte skanna {store}: {e}")

        browser.close()
    print("\n=== Skanning klar ===")

if __name__ == "__main__":
    run()

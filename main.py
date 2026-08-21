import os
import json
import requests
from playwright.sync_api import sync_playwright

PUSHBULLET_TOKEN = os.environ.get("PUSHBULLET_TOKEN")
DB_FILE = "seen_products.json"

URLS = {
    "Blocket": "https://www.blocket.se/e/annonser?q=asus+rog+ally",
    "Inet": "https://www.inet.se/kategori/851/fyndhorna?q=asus+rog+ally",
    "Komplett": "https://www.komplett.se/search?q=asus+rog+ally&b=DEMO",
    "Webhallen": "https://www.webhallen.se/se/search?query=asus%20rog%20ally&condition=1",
    "Elgiganten": "https://www.elgiganten.se/outlet?q=asus+rog+ally",
    "Power": "https://www.power.se/outlet/search/?q=asus+rog+ally+outlet"
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

            # ==========================================
            # BLOCKET VIA DIREKT API
            # ==========================================
            if store == "Blocket":
                api_url = "https://api.blocket.se/search_bff/v2/content?q=asus%20rog%20ally&status=active"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "application/json"
                }
                
                try:
                    res = requests.get(api_url, headers=headers, timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        docs = data.get("docs", [])
                        found_blocket_product = False

                        for doc in docs:
                            subject = doc.get("subject", "").strip()
                            ad_id = doc.get("ad_id") or doc.get("list_id")
                            
                            if "rog ally" in subject.lower():
                                found_blocket_product = True
                                clean_name = " ".join(subject.split())[:80]
                                product_key = f"Blocket:{ad_id}" if ad_id else f"Blocket:{clean_name}"

                                if product_key not in seen_products:
                                    seen_products.add(product_key)
                                    new_found = True
                                    ad_url = doc.get("canonical_url") or url
                                    message = f"Ny träff på Blocket:\n{clean_name}\n\nLänk: {ad_url}"
                                    print(f"[NY TRÄFF] Blocket: {clean_name}")
                                    send_push_notification("Ny Asus ROG Ally på Blocket!", message)
                                else:
                                    print("[INFO] Träff finns på Blocket, men har redan notifierats.")
                                break

                        if not found_blocket_product:
                            print("[INFO] Inga relevanta annonser hittades på Blocket via API.")
                    else:
                        print(f"[VARNING] Blocket API svarade med statuskod: {res.status_code}")
                except Exception as api_err:
                    print(f"[FEL] Kunde inte hämta Blocket-data via API: {api_err}")

                continue  # Hoppa över Playwright för Blocket

            # ==========================================
            # INET VIA DIREKT API (Går förbi Cloudflare)
            # ==========================================
            if store == "Inet":
                api_url = "https://www.inet.se/api/search?q=asus%20rog%20ally"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "application/json"
                }
                try:
                    res = requests.get(api_url, headers=headers, timeout=10)
                    if res.status_code == 200:
                        products = res.json().get("products", [])
                        found_inet_product = False
                        
                        for prod in products:
                            name = prod.get("name", "").strip()
                            is_outlet = prod.get("isBStock", False) or "fyndvara" in name.lower() or "outlet" in name.lower()
                            
                            if "rog ally" in name.lower() and is_outlet:
                                found_inet_product = True
                                prod_id = prod.get("id")
                                clean_name = " ".join(name.split())[:80]
                                product_key = f"Inet:{prod_id}" if prod_id else f"Inet:{clean_name}"

                                if product_key not in seen_products:
                                    seen_products.add(product_key)
                                    new_found = True
                                    prod_url = f"https://www.inet.se/produkt/{prod_id}" if prod_id else url
                                    message = f"Ny träff på Inet Fyndhörna:\n{clean_name}\n\nLänk: {prod_url}"
                                    print(f"[NY TRÄFF] Inet: {clean_name}")
                                    send_push_notification("Ny Asus ROG Ally på Inet!", message)
                                else:
                                    print("[INFO] Träff finns på Inet, men har redan notifierats.")
                                break

                        if not found_inet_product:
                            print("[INFO] Inga fyndvaror för ROG Ally hittades på Inet via API.")
                    else:
                        print(f"[VARNING] Inet API svarade med statuskod: {res.status_code}")
                except Exception as api_err:
                    print(f"[FEL] Kunde inte hämta Inet-data via API: {api_err}")

                continue  # Hoppa över Playwright för Inet

            # ==========================================
            # ÖVRIGA BUTIKER VIA PLAYWRIGHT
            # ==========================================
            try:
                try:
                    page.goto(url, timeout=45000, wait_until="networkidle")
                except Exception:
                    page.goto(url, timeout=45000, wait_until="domcontentloaded")
                
                page.wait_for_timeout(2000)

                # Försök klicka bort cookie-banner direkt efter sidladdning
                try:
                    cookie_btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Acceptera alla'), button:has-text('Godkänn alla'), button:has-text('Acceptera allt')")
                    if cookie_btn.first.is_visible(timeout=3000):
                        cookie_btn.first.click()
                        print(f"[INFO] Stängde cookie-banner på {store}.")
                        page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Sparar skärmdump och HTML EFTER cookie-hantering
                try:
                    page.screenshot(path=f"debug_{safe_store_name}.png", full_page=True)
                    with open(f"debug_{safe_store_name}.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                except Exception as debug_err:
                    print(f"[VARNING] Kunde inte spara debug-filer för {store}: {debug_err}")

                # SPECIFIK LOGIK FÖR ELGIGANTEN.SE
                if store == "Elgiganten":
                    product_cards = page.locator("a[href*='/product/'], .product-tile, [data-test='product-card']").all()
                    found_elgiganten_product = False

                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        if "rog ally" in card_text:
                            found_elgiganten_product = True
                            clean_name = " ".join(card_text.split())[:60]
                            product_id = f"Elgiganten:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                message = f"Ny träff hos Elgiganten Outlet:\n{clean_name}\n\nLänk: {url}"
                                print(f"[NY TRÄFF] Elgiganten: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Elgiganten!", message)
                            else:
                                print("[INFO] Träff finns på Elgiganten, men har redan notifierats.")
                            break

                    if not found_elgiganten_product:
                        print("[INFO] Inga outlet-produkter hittades på Elgiganten.")

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
                    try:
                        page.wait_for_selector(".product-list-item, .product-box, article, [data-product-id]", timeout=10000)
                    except Exception:
                        print("[INFO] Ingen produktstruktur hittades inom timeout på Komplett.")

                    product_cards = page.locator(".product-list-item, .product-box, article, a[href*='/product/']").all()
                    found_komplett_product = False

                    print(f"[DEBUG] Hittade {len(product_cards)} potentiella element/kort på Komplett.")

                    for card in product_cards:
                        card_text = card.inner_text().strip().lower()
                        
                        if "rog ally" in card_text:
                            href = card.get_attribute("href")
                            if href:
                                product_link = href if href.startswith("http") else f"https://www.komplett.se{href}"
                            else:
                                product_link = url

                            found_komplett_product = True
                            clean_name = " ".join(card_text.split())[:80]
                            product_id = f"Komplett:{clean_name}"

                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                new_found = True
                                message = f"Ny träff hos Komplett Demo:\n{clean_name}\n\nLänk: {product_link}"
                                print(f"[NY TRÄFF] Komplett: {clean_name}")
                                send_push_notification("Ny Asus ROG Ally på Komplett Demo!", message)
                            else:
                                print("[INFO] Träff finns på Komplett, men har redan notifierats.")
                            break

                    if not found_komplett_product:
                        print("[INFO] Inga demovaror för ROG Ally hittades på Komplett.")

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

            except Exception as e:
                print(f"[FEL] Kunde inte skanna {store}: {e}")

        browser.close()

    if new_found:
        save_seen_products(seen_products)
        print("[INFO] Nya produkter har sparats till minnet.")

    print("\n=== Skanning klar ===")

if __name__ == "__main__":
    run()

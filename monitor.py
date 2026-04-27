import os
import sys
import json
import argparse
import requests  # <--- Tambahkan ini
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# --- KONFIGURASI DINAMIS ---
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="URL target dari n8n")
# Tambahkan argument untuk URL Webhook n8n agar lebih fleksibel
parser.add_argument("--webhook", help="URL Webhook n8n", default="https://sync.impacta.id/webhook-test/github-screenshot")
args = parser.parse_args()

TARGET_URL = args.url if args.url else "https://portoqu.onrender.com/"
WEBHOOK_URL = args.webhook
OUTPUT_IMAGE = "screenshot.png"

def run_advanced_checker():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        health_report = {
            "target_url": TARGET_URL,
            "status_code": 0,
            "is_blank": False,
            "css_broken": False,
            "html_leaked": False,
            "error_message": ""
        }

        try:
            failed_resources = []
            page.on("requestfailed", lambda request: failed_resources.append(request.url))

            print(f"Mulai pengecekan: {TARGET_URL}")
            response = page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000) 
            health_report["status_code"] = response.status if response else 0

            # Deteksi kesehatan website (Logika Anda tetap sama)
            body_height = page.evaluate("document.body.getBoundingClientRect().height")
            if body_height < 300: health_report["is_blank"] = True
            
            css_failures = [r for r in failed_resources if ".css" in r]
            if len(css_failures) > 3: health_report["css_broken"] = True

            content = page.content()
            if any(x in content for x in ["<?php", "SQL STATE", "stack trace"]):
                health_report["html_leaked"] = True

            # Ambil Screenshot
            page.screenshot(path=OUTPUT_IMAGE, full_page=True)
            
            # --- BAGIAN KIRIM KE n8n ---
            print(f"Mengirim data ke n8n: {WEBHOOK_URL}")
            
            # Kita kirim sebagai multipart/form-data agar file dan json terkirim sekaligus
            with open(OUTPUT_IMAGE, 'rb') as f:
                files = {'image': (OUTPUT_IMAGE, f, 'image/png')}
                # Data JSON dimasukkan ke dalam payload
                payload = {
                    "data": json.dumps(health_report),
                    "status": "WEBSITE_HEALTHY" if health_report["status_code"] < 400 else "WEBSITE_BROKEN"
                }
                
                # Tambahkan User-Agent browser agar tidak diblokir Cloudflare saat POST
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }

                res = requests.post(WEBHOOK_URL, data=payload, files=files, headers=headers)
                print(f"n8n Response: {res.status_code} - {res.text}")

        except Exception as e:
            health_report["error_message"] = str(e)
            print(f"Error Terjadi: {e}")
            # Tetap kirim laporan error ke n8n tanpa screenshot (atau screenshot lama jika ada)
            requests.post(WEBHOOK_URL, data={"data": json.dumps(health_report), "status": "CRITICAL_ERROR"})
        
        finally:
            browser.close()

if __name__ == "__main__":
    run_advanced_checker()
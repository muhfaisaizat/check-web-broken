import os
import sys
import json
import argparse
from playwright.sync_api import sync_playwright

# --- KONFIGURASI DINAMIS ---
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="URL target dari n8n")
args = parser.parse_args()

# Jika n8n tidak mengirim URL, gunakan Portoqu sebagai default
TARGET_URL = args.url if args.url else "https://portoqu.onrender.com/"
OUTPUT_IMAGE = "screenshot.png"

def run_advanced_checker():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        # Setup layar desktop standar
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Inisialisasi laporan untuk n8n
        health_report = {
            "target_url": TARGET_URL,
            "status_code": 0,
            "is_blank": False,
            "css_broken": False,
            "html_leaked": False,
            "error_message": ""
        }

        try:
            # Monitor request gagal untuk deteksi CSS/JS bocor
            failed_resources = []
            page.on("requestfailed", lambda request: failed_resources.append(request.url))

            print(f"Mulai pengecekan: {TARGET_URL}")
            response = page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            health_report["status_code"] = response.status

            # 1. Deteksi Blank Page (Cek tinggi elemen body)
            body_height = page.evaluate("document.body.getBoundingClientRect().height")
            if body_height < 300:
                health_report["is_blank"] = True

            # 2. Deteksi CSS Bocor
            css_failures = [r for r in failed_resources if ".css" in r]
            if len(css_failures) > 3:
                health_report["css_broken"] = True

            # 3. Deteksi HTML/PHP Bocor
            content = page.content()
            if any(x in content for x in ["<?php", "SQL STATE", "stack trace"]):
                health_report["html_leaked"] = True

            # 4. Ambil Screenshot
            page.evaluate("window.scrollTo(0, 500)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=OUTPUT_IMAGE, full_page=True)
            
            # --- OUTPUT DATA UNTUK n8n ---
            # Menggunakan json.dumps agar n8n mudah melakukan parsing
            print(f"DATA:: {json.dumps(health_report)}")

            # Penentuan status akhir GitHub Action
            if health_report["status_code"] >= 400 or health_report["is_blank"] or health_report["css_broken"] or health_report["html_leaked"]:
                print("RESULT:: WEBSITE_BROKEN")
                sys.exit(1)
            else:
                print("RESULT:: WEBSITE_HEALTHY")
                sys.exit(0)

        except Exception as e:
            health_report["error_message"] = str(e)
            print(f"DATA:: {json.dumps(health_report)}")
            print("RESULT:: CRITICAL_ERROR")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run_advanced_checker()
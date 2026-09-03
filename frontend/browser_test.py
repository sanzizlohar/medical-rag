"""Headless browser test of the medical RAG frontend end-to-end."""

import sys
from playwright.sync_api import sync_playwright

SHOTS = "screenshots"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto("http://localhost:5173/", wait_until="domcontentloaded")

    # 1. App renders
    page.wait_for_selector("text=MedDoc Q&A", timeout=10000)
    page.screenshot(path=f"{SHOTS}/1_home.png")
    print("PASS: app header rendered")

    # 2. Document list shows the uploaded sample
    page.wait_for_selector("text=medical_fact_sheets.pdf", timeout=10000)
    print("PASS: uploaded document visible in sidebar")

    # 3. Ask a question through the chat
    page.fill(".chat-input input", "What is the diagnostic criteria for type 2 diabetes?")
    page.click(".chat-input button")
    print("question sent, waiting for answer...")

    # Wait for the assistant answer bubble after the user message
    page.wait_for_selector(".typing", state="attached", timeout=10000)
    page.wait_for_selector(".typing", state="detached", timeout=120000)
    answer = page.text_content(".message.assistant .bubble >> nth=-1")
    assert "HbA1c" in answer or "126" in answer, f"unexpected answer: {answer[:200]}"
    print(f"PASS: grounded answer received ({len(answer)} chars)")

    # 4. Sources section present and expandable
    page.click("text=Sources (")
    page.wait_for_selector(".sources li", timeout=5000)
    src = page.text_content(".sources li >> nth=0")
    assert "medical_fact_sheets.pdf" in src and "page" in src
    print("PASS: sources section shows document + page")

    page.screenshot(path=f"{SHOTS}/2_answer.png")
    browser.close()

print("ALL BROWSER TESTS PASSED")

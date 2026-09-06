"""Record polished demo GIFs of the running MedDoc Q&A app.

Requires: backend (8000) + frontend (5173) running, playwright, pillow.
Outputs GIFs + a Swagger screenshot into ../docs/demo/.
"""

import os
import shutil
import time

import urllib.request
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "demo")
FRAMES = os.path.join(OUT, "frames")
os.makedirs(FRAMES, exist_ok=True)

API = "http://127.0.0.1:8000"
VIEW = {"width": 1360, "height": 850}
SCALE = 2          # device scale factor for crisp frames
GIF_W = 900        # final GIF width
DEFAULT_MS = 750   # per-frame duration


def shot(page, name):
    page.screenshot(path=os.path.join(FRAMES, f"{name}.png"))
    print("  frame:", name)


def wait_backend():
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{API}/api/health", timeout=3)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("backend not reachable")


def save_gif(frame_names, durations_ms, out_name):
    paths = [os.path.join(FRAMES, n if n.endswith(".png") else f"{n}.png")
             for n in frame_names]
    imgs = [Image.open(p).convert("RGB").resize(
        (GIF_W, int(Image.open(p).height * GIF_W / Image.open(p).width)),
        Image.LANCZOS) for p in paths]
    dura = [durations_ms[i] for i in range(len(imgs))]
    out_path = os.path.join(OUT, out_name)
    imgs[0].save(
        out_path, save_all=True, append_images=imgs[1:],
        duration=dura, loop=0, optimize=True,
    )
    size_mb = os.path.getsize(out_path) / 1e6
    print(f"GIF saved: {out_name} ({len(imgs)} frames, {size_mb:.1f} MB)")


def restore_docs(keep_filename):
    """Delete every document except keep_filename (cleanup after demo upload)."""
    with urllib.request.urlopen(f"{API}/api/documents") as r:
        docs = json_loads(r.read())["documents"]
    for d in docs:
        if d["filename"] != keep_filename:
            req = urllib.request.Request(
                f"{API}/api/documents/{d['document_id']}", method="DELETE")
            urllib.request.urlopen(req)
            print("cleaned up demo doc:", d["filename"])


def json_loads(b):
    import json
    return json.loads(b)


def main():
    wait_backend()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEW, device_scale_factor=SCALE)
        page = ctx.new_page()

        # ================= GIF 1: ask -> answer -> sources =================
        print("Recording chat demo...")
        page.goto("http://localhost:5173/", wait_until="domcontentloaded")
        page.wait_for_selector("text=medical_fact_sheets.pdf", timeout=20000)
        page.evaluate("document.querySelector('.messages').scrollTop = 0")
        time.sleep(0.4)
        shot(page, "c01_start")

        question = "what are the warning signs of severe dengue?"
        inp = page.locator(".chat-input input")
        inp.click()
        chunk = max(1, len(question) // 5)
        for i in range(0, len(question), chunk):
            inp.press_sequentially(question[i:i + chunk], delay=12)
            shot(page, f"c02_typing{i:02d}")

        page.click(".chat-input button")
        page.wait_for_selector(".typing", state="attached", timeout=10000)
        time.sleep(0.3)
        shot(page, "c03_thinking")
        time.sleep(0.7)
        shot(page, "c04_thinking2")

        page.wait_for_selector(".typing", state="detached", timeout=120000)
        page.evaluate(
            "document.querySelector('.messages').scrollTop = "
            "document.querySelector('.messages').scrollHeight")
        time.sleep(0.3)
        shot(page, "c05_answer")

        page.click(".sources > button")
        page.wait_for_selector(".sources li", timeout=5000)
        time.sleep(0.3)
        shot(page, "c06_sources")
        time.sleep(0.5)
        shot(page, "c07_sources_hold")

        save_gif(
            ["c01_start"]
            + [n for n in os.listdir(FRAMES) if n.startswith("c02_") and n.endswith(".png")]
            + ["c03_thinking", "c04_thinking2", "c05_answer", "c06_sources",
               "c07_sources_hold", "c07_sources_hold", "c07_sources_hold"],
            [900] + [260] * len([n for n in os.listdir(FRAMES)
                                 if n.startswith("c02_") and n.endswith(".png")])
            + [800, 800, 900, 700, 1400, 1400, 1400],
            "chat-demo.gif",
        )

        # ================= GIF 2: upload -> index (OCR-ready) =================
        print("Recording upload demo...")
        # reset chat state by reloading; also scroll sidebar into full view
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("text=medical_fact_sheets.pdf", timeout=20000)
        shot(page, "u01_before")

        with open(os.path.join(HERE, "..", "backend",
                               "sample_data", "medical_fact_sheets.pdf"), "rb") as f:
            pdf_bytes = f.read()
        page.set_input_files(
            "input[type=file]",
            [{"name": "who_dengue_guidelines.pdf",
              "mimeType": "application/pdf", "buffer": pdf_bytes}],
        )
        page.wait_for_selector(".status.info", timeout=10000)
        time.sleep(0.4)
        shot(page, "u02_ingesting")
        time.sleep(0.8)
        shot(page, "u03_ingesting2")

        page.wait_for_selector(".status.success", timeout=120000)
        time.sleep(0.3)
        shot(page, "u04_indexed")
        time.sleep(0.5)
        shot(page, "u05_indexed_hold")

        save_gif(
            ["u01_before", "u02_ingesting", "u03_ingesting2",
             "u04_indexed", "u05_indexed_hold", "u05_indexed_hold"],
            [900, 800, 800, 1200, 1600, 1600],
            "upload-demo.gif",
        )

        restore_docs("medical_fact_sheets.pdf")

        # ================= Swagger API docs screenshot =================
        print("Capturing API docs...")
        page.goto(f"{API}/docs", wait_until="domcontentloaded")
        page.wait_for_selector(".opblock-tag-section, .information-container",
                               timeout=20000)
        time.sleep(1.2)
        page.screenshot(path=os.path.join(OUT, "api-docs.png"))
        print("saved api-docs.png")

        browser.close()

    shutil.rmtree(FRAMES, ignore_errors=True)
    print("ALL DEMOS RECORDED")


if __name__ == "__main__":
    main()

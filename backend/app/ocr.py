"""
OCR for JD screenshots. Stubbed to raise a clear error until a real vision
backend (e.g. Gemini vision, or Tesseract for a fully local option) is
wired in. Text-input JDs never call this — see app/ai_pipeline.py.
"""


async def extract_text_from_image(image_url: str) -> str:
    raise NotImplementedError(
        "OCR is not wired up yet. Plug in Tesseract (pytesseract) for a "
        "fully local option, or send the image to a vision-capable model "
        "(Gemini) and return its transcription as plain text."
    )

from __future__ import annotations

import io

from PIL import Image

from config import WATERMARK_PATH

WATERMARK_WIDTH_RATIO = 0.28
WATERMARK_PADDING_RATIO = 0.02


class WatermarkError(Exception):
    pass


def apply_watermark(source_bytes: bytes) -> bytes:
    if not WATERMARK_PATH.exists():
        raise WatermarkError(
            f"Watermark image not found at {WATERMARK_PATH}. Add a watermark.png file to the assets folder."
        )

    with Image.open(io.BytesIO(source_bytes)) as opened_source:
        base_image = opened_source.convert("RGBA")

    with Image.open(WATERMARK_PATH) as opened_watermark:
        watermark_image = opened_watermark.convert("RGBA")

    target_width = max(int(base_image.width * WATERMARK_WIDTH_RATIO), 1)
    scale_ratio = target_width / watermark_image.width
    target_height = max(int(watermark_image.height * scale_ratio), 1)
    watermark_resized = watermark_image.resize((target_width, target_height))

    padding = int(base_image.width * WATERMARK_PADDING_RATIO)
    position = (
        base_image.width - watermark_resized.width - padding,
        base_image.height - watermark_resized.height - padding,
    )

    composed_image = base_image.copy()
    composed_image.alpha_composite(watermark_resized, dest=position)

    output_buffer = io.BytesIO()
    composed_image.convert("RGB").save(output_buffer, format="PNG")
    return output_buffer.getvalue()

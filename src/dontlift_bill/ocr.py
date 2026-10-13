"""Optional local CPU OCR adapter. Never uploads receipt images."""

import hashlib
from importlib.metadata import version
from pathlib import Path
import time

from .domain import ValidationError


def scan_image(path: str, model_dir: str = 'models') -> dict:
    image_path = Path(path)
    if not image_path.is_file() or image_path.stat().st_size > 20 * 1024 * 1024:
        raise ValidationError('image must be a local file <= 20 MiB')
    try:
        from PIL import Image, ImageOps
        import numpy as np
        from rapidocr import RapidOCR, LangRec, ModelType, OCRVersion
    except ImportError as exc:
        raise ValidationError('install the ocr extra: pip install -e ".[ocr]"') from exc
    with Image.open(image_path) as source:
        if source.width * source.height > 25_000_000:
            raise ValidationError('image exceeds 25 megapixels')
        orientation = source.getexif().get(274, 1)
        original_size = list(source.size)
        image = ImageOps.exif_transpose(source).convert('RGB')
    model_root = Path(model_dir)
    model_root.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    engine = RapidOCR(params={'Global.model_root_dir': str(model_root.resolve()),
                              'Det.ocr_version': OCRVersion.PPOCRV6,
                              'Det.model_type': ModelType.SMALL,
                              'Rec.lang_type': LangRec.LATIN,
                              'Rec.model_type': ModelType.MOBILE,
                              'Rec.ocr_version': OCRVersion.PPOCRV5})
    try:
        result = engine(np.array(image)[:, :, ::-1].copy())
    except Exception as exc:
        raise ValidationError('OCR failed; check model availability and runtime (no draft written)') from exc
    elapsed = time.perf_counter() - start
    tokens = []
    if result.txts is not None:
        for index, (text, box, score) in enumerate(zip(result.txts, result.boxes, result.scores)):
            tokens.append({'tokenId': f't{index:04}', 'text': str(text),
                           'polygon': [[float(x), float(y)] for x, y in box],
                           'confidence': float(score)})
    weights = [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(model_root.rglob('*.onnx'))]
    return {'schemaVersion': 1, 'imageId': hashlib.sha256(image_path.read_bytes()).hexdigest(),
            'width': image.width, 'height': image.height,
            'coordinates': 'exif-oriented-image-pixels',
            'sourceTransform': {'exifOrientation': orientation, 'originalSize': original_size},
            'engine': {'name': 'rapidocr', 'version': version('rapidocr'),
                       'runtimeVersion': version('onnxruntime'), 'language': 'latin',
                       'modelHashes': weights}, 'elapsedSeconds': elapsed, 'tokens': tokens}

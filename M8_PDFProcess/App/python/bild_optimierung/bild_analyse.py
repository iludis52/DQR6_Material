"""Deterministische Klassifikation, Kandidatenerzeugung und Qualitätsschranken.

Inhaltlich unverändert aus Notebook 03 (Abschnitte 03 und 04); die
Konstanten kommen jetzt aus `BildKonfig` statt aus Notebook-Globalen.
"""

from __future__ import annotations

import io
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab
from skimage.metrics import structural_similarity as ssim

from .bild_konfig import BildKonfig


# ------------------------------------------------------------ Klassifikation

def analysis_thumbnail(img: Image.Image, max_side: int) -> Image.Image:
    out = img.copy()
    out.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return out


def pil_to_rgb_array(img: Image.Image) -> np.ndarray:
    if "A" in img.getbands():
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.alpha_composite(img.convert("RGBA"))
        return np.asarray(bg.convert("RGB"))
    return np.asarray(img.convert("RGB"))


def normalized_entropy(gray: np.ndarray) -> float:
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    p = hist / max(hist.sum(), 1)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum() / 8.0)


def technical_features(path: Path, cfg: BildKonfig) -> dict[str, Any]:
    with Image.open(path) as src:
        src.load()
        has_alpha = "A" in src.getbands()
        alpha_fraction = (float(np.mean(np.asarray(src.getchannel("A")) < 255))
                          if has_alpha else 0.0)
        small = analysis_thumbnail(src, cfg.feature_max_side)
        rgb = pil_to_rgb_array(small).astype(np.uint8)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        rgbf = rgb.astype(np.float32) / 255.0
        chdiff = np.maximum.reduce([
            np.abs(rgbf[..., 0] - rgbf[..., 1]),
            np.abs(rgbf[..., 0] - rgbf[..., 2]),
            np.abs(rgbf[..., 1] - rgbf[..., 2]),
        ])

        med = float(np.median(gray))
        edges = cv2.Canny(gray, int(max(0, 0.66 * med)), int(min(255, 1.33 * med)))

        g = gray.astype(np.float32)
        mean = cv2.GaussianBlur(g, (0, 0), 2.0)
        mean2 = cv2.GaussianBlur(g * g, (0, 0), 2.0)
        var = np.maximum(mean2 - mean * mean, 0)

        return {
            "actual_width": src.width,
            "actual_height": src.height,
            "actual_mode": src.mode,
            "actual_format": src.format,
            "has_alpha": has_alpha,
            "alpha_fraction_nonopaque": alpha_fraction,
            "grayscale_distance": float(np.mean(chdiff)),
            "luminance_entropy": normalized_entropy(gray),
            "edge_density": float(np.mean(edges > 0)),
            "flat_area_fraction": float(np.mean(var < 9.0)),
            "extreme_fraction": float(np.mean(gray <= 24) + np.mean(gray >= 231)),
            "midtone_fraction": float(np.mean((gray > 48) & (gray < 207))),
        }


def classify_image(f: dict[str, Any], cfg: BildKonfig) -> tuple[str, list[str]]:
    c = cfg.classifier
    if f["has_alpha"] and f["alpha_fraction_nonopaque"] > 0:
        return "ALPHA_GRAPHIC", ["non-opaque alpha"]

    grayscale = f["grayscale_distance"] <= c["grayscale_distance_max"]
    bilevel = (
        grayscale
        and f["extreme_fraction"] >= c["bilevel_extreme_fraction_min"]
        and f["midtone_fraction"] <= c["bilevel_midtone_fraction_max"]
    )
    if bilevel:
        return "LINE_ART_BILEVEL", ["near-bilevel grayscale profile"]

    flat = f["flat_area_fraction"] >= c["graphic_flat_area_min"]
    edgy = f["edge_density"] >= c["graphic_edge_density_min"]
    extreme = f["extreme_fraction"] >= c["graphic_extreme_fraction_min"]
    low_entropy = f["luminance_entropy"] <= c["graphic_low_entropy_max"]
    graphic = (flat and edgy) or (flat and extreme) or (low_entropy and extreme) or (edgy and extreme)
    if graphic:
        return (("LINE_ART_GRAYSCALE" if grayscale else "SCREENSHOT_OR_TEXT_GRAPHIC"),
                ["graphic/text-like profile"])

    if grayscale:
        return "PHOTO_GRAYSCALE", ["grayscale continuous-tone fallback"]

    if not flat and not edgy and not low_entropy:
        return "PHOTO_COLOR", ["continuous-tone photographic profile"]

    return "MIXED_CONTENT", ["ambiguous technical profile"]


# ------------------------------------------------------------ Kandidaten

@dataclass
class Candidate:
    candidate_id: str
    format: str
    params: dict[str, Any]
    data: bytes
    image: Image.Image

    @property
    def nbytes(self) -> int:
        return len(self.data)


def resize_reference(path: Path, tw: int, th: int) -> Image.Image:
    with Image.open(path) as img:
        img.load()
        scale = min(tw / img.width, th / img.height, 1.0)
        size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        return img.copy() if img.size == size else img.resize(size, Image.Resampling.LANCZOS)


def decode(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    im.load()
    return im


def encode_jpeg(img: Image.Image, quality: int, grayscale: bool = False) -> Candidate:
    out = img.convert("L" if grayscale else "RGB")
    bio = io.BytesIO()
    out.save(bio, format="JPEG", quality=quality, optimize=True, progressive=True,
             subsampling=0 if grayscale else 2)
    data = bio.getvalue()
    return Candidate(f"jpeg_q{quality}_{'gray' if grayscale else 'rgb'}", "JPEG",
                     {"quality": quality, "grayscale": grayscale}, data, decode(data))


def encode_png_truecolor(img: Image.Image, grayscale: bool = False) -> Candidate:
    out = img.convert("L" if grayscale else ("RGBA" if "A" in img.getbands() else "RGB"))
    bio = io.BytesIO()
    out.save(bio, format="PNG", optimize=True)
    data = bio.getvalue()
    return Candidate(f"png_{'gray' if grayscale else 'truecolor'}", "PNG",
                     {"grayscale": grayscale, "encoder": "pillow"}, data, decode(data))


def encode_png_palette(img: Image.Image, colors: int, dither: bool = False) -> Candidate:
    q = img.convert("RGB").quantize(
        colors=colors, method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)
    bio = io.BytesIO()
    q.save(bio, format="PNG", optimize=True)
    data = bio.getvalue()
    return Candidate(f"png_palette_{colors}_{'dither' if dither else 'nodither'}", "PNG",
                     {"palette_colors": colors, "dither": dither, "encoder": "pillow"},
                     data, decode(data))


def encode_pngquant(img: Image.Image, colors: int, quality_min: int, quality_max: int,
                    cfg: BildKonfig) -> Candidate | None:
    if not (cfg.enable_pngquant and cfg.pngquant_binary):
        return None
    with tempfile.TemporaryDirectory() as td:
        input_path = Path(td) / "input.png"
        output_path = Path(td) / "output.png"
        img.convert("RGB").save(input_path, format="PNG", optimize=True)
        proc = subprocess.run(
            [cfg.pngquant_binary, str(colors), f"--quality={quality_min}-{quality_max}",
             f"--speed={cfg.pngquant_speed}", "--force", "--output", str(output_path),
             str(input_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0 or not output_path.exists():
            return None
        data = output_path.read_bytes()
    return Candidate(f"pngquant_{colors}_q{quality_min}-{quality_max}", "PNG",
                     {"palette_colors": colors, "quality_min": quality_min,
                      "quality_max": quality_max, "encoder": "pngquant"},
                     data, decode(data))


def encode_png_bilevel(img: Image.Image) -> Candidate:
    gray = np.asarray(img.convert("L"))
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    out = Image.fromarray(bw, mode="L").convert("1")
    bio = io.BytesIO()
    out.save(bio, format="PNG", optimize=True)
    data = bio.getvalue()
    return Candidate("png_bilevel_otsu", "PNG", {"threshold": "otsu"}, data, decode(data))


def palette_candidates(ref: Image.Image, cfg: BildKonfig, *, min_colors: int) -> list[Candidate]:
    sizes = [n for n in cfg.png_palette_sizes if n >= min_colors]
    out = [encode_png_palette(ref, n, dither=False) for n in sizes]
    out += [encode_png_palette(ref, n, dither=True) for n in sizes if n >= 32]
    if cfg.enable_pngquant and cfg.pngquant_binary:
        for n in sizes:
            for qmin, qmax in cfg.pngquant_quality_profiles:
                cand = encode_pngquant(ref, n, qmin, qmax, cfg)
                if cand is not None:
                    out.append(cand)
    return out


def candidate_family(ref: Image.Image, cls: str, cfg: BildKonfig) -> list[Candidate]:
    floor = cfg.color_graphic_min_palette_colors
    if cls == "PHOTO_COLOR":
        return [encode_jpeg(ref, q) for q in cfg.jpeg_qualities] + [encode_png_truecolor(ref)]
    if cls == "PHOTO_GRAYSCALE":
        return ([encode_jpeg(ref, q, True) for q in cfg.jpeg_qualities]
                + [encode_png_truecolor(ref, True)])
    if cls == "LINE_ART_BILEVEL":
        return ([encode_png_bilevel(ref), encode_png_truecolor(ref, True)]
                + palette_candidates(ref, cfg, min_colors=2))
    if cls == "LINE_ART_GRAYSCALE":
        return [encode_png_truecolor(ref, True)] + palette_candidates(ref, cfg, min_colors=2)
    if cls in {"SCREENSHOT_OR_TEXT_GRAPHIC", "ALPHA_GRAPHIC"}:
        return [encode_png_truecolor(ref)] + palette_candidates(ref, cfg, min_colors=floor)
    # Mischinhalt: JPEG konkurriert mit PNG, farbige Paletten mit derselben Untergrenze.
    return ([encode_jpeg(ref, q) for q in cfg.jpeg_qualities] + [encode_png_truecolor(ref)]
            + palette_candidates(ref, cfg, min_colors=floor))


# ------------------------------------------------------------ Metriken

def gray_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.uint8)


def rgb_float(img: Image.Image, size=None) -> np.ndarray:
    im = img.convert("RGB")
    if size and im.size != size:
        im = im.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(im, dtype=np.float32) / 255.0


def edge_map(img: Image.Image) -> np.ndarray:
    g = gray_array(img)
    med = float(np.median(g))
    return cv2.Canny(g, int(max(0, 0.66 * med)), int(min(255, 1.33 * med))) > 0


def edge_f1(ref: Image.Image, cand: Image.Image, tolerance_px: int = 1) -> float:
    r = edge_map(ref)
    c = edge_map(cand.resize(ref.size, Image.Resampling.BILINEAR))
    k = np.ones((2 * tolerance_px + 1, 2 * tolerance_px + 1), np.uint8)
    rd = cv2.dilate(r.astype(np.uint8), k) > 0
    cd = cv2.dilate(c.astype(np.uint8), k) > 0
    p = np.sum(c & rd) / max(np.sum(c), 1)
    rec = np.sum(r & cd) / max(np.sum(r), 1)
    return float(2 * p * rec / (p + rec)) if p + rec else 1.0


def component_count(img: Image.Image) -> int:
    g = gray_array(img)
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, _, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    return 0 if n <= 1 else int(np.sum(stats[1:, cv2.CC_STAT_AREA] >= 2))


def component_retention(ref: Image.Image, cand: Image.Image) -> float:
    a, b = component_count(ref), component_count(cand)
    return (1.0 if b == 0 else 0.0) if a == 0 else float(min(a, b) / max(a, b, 1))


def color_difference_metrics(ref: Image.Image, cand: Image.Image) -> dict[str, float]:
    scale = min(1.0, 640 / max(ref.size))
    size = (max(1, round(ref.width * scale)), max(1, round(ref.height * scale)))
    de = deltaE_ciede2000(rgb2lab(rgb_float(ref, size)), rgb2lab(rgb_float(cand, size)))
    return {"deltae_mean": float(np.mean(de)), "deltae_p95": float(np.percentile(de, 95))}


def evaluate(ref: Image.Image, cand: Candidate) -> dict[str, float]:
    c = cand.image.resize(ref.size, Image.Resampling.BILINEAR)
    # SSIM braucht mindestens 7x7 Pixel (Standardfenster).
    if min(ref.size) >= 7:
        s = float(ssim(gray_array(ref), gray_array(c), data_range=255))
    else:
        s = 1.0 if np.array_equal(gray_array(ref), gray_array(c)) else 0.0
    return {"ssim": s, "edge_f1": edge_f1(ref, c),
            "component_retention": component_retention(ref, c),
            **color_difference_metrics(ref, c)}


def passes_gate(cls: str, m: dict[str, float], cfg: BildKonfig) -> tuple[bool, list[str]]:
    q = cfg.quality
    failures: list[str] = []
    if cls in {"PHOTO_COLOR", "PHOTO_GRAYSCALE"}:
        if m["ssim"] < q["photo_ssim_min"]:
            failures.append("photo_ssim")
    elif cls == "LINE_ART_BILEVEL":
        if m["edge_f1"] < q["bilevel_edge_f1_min"]:
            failures.append("bilevel_edge_f1")
        if m["component_retention"] < q["component_retention_min"]:
            failures.append("component_retention")
    elif cls in {"LINE_ART_GRAYSCALE", "SCREENSHOT_OR_TEXT_GRAPHIC", "ALPHA_GRAPHIC"}:
        if m["ssim"] < q["graphic_ssim_min"]:
            failures.append("graphic_ssim")
        if m["edge_f1"] < q["edge_f1_min"]:
            failures.append("edge_f1")
        if cls in {"LINE_ART_GRAYSCALE", "SCREENSHOT_OR_TEXT_GRAPHIC"}:
            if m["component_retention"] < q["component_retention_min"]:
                failures.append("component_retention")
        if cls in {"SCREENSHOT_OR_TEXT_GRAPHIC", "ALPHA_GRAPHIC"}:
            if m["deltae_mean"] > q["color_deltae_mean_max"]:
                failures.append("deltae_mean")
            if m["deltae_p95"] > q["color_deltae_p95_max"]:
                failures.append("deltae_p95")
    else:
        if m["ssim"] < q["mixed_ssim_min"]:
            failures.append("mixed_ssim")
        if m["edge_f1"] < q["edge_f1_min"]:
            failures.append("edge_f1")
        if m["deltae_mean"] > q["color_deltae_mean_max"]:
            failures.append("deltae_mean")
        if m["deltae_p95"] > q["color_deltae_p95_max"]:
            failures.append("deltae_p95")
    return not failures, failures


def preferred_quality_zone(cls: str, m: dict[str, float], cfg: BildKonfig) -> bool:
    q = cfg.quality
    if cls not in {"SCREENSHOT_OR_TEXT_GRAPHIC", "ALPHA_GRAPHIC", "MIXED_CONTENT",
                   "LINE_ART_GRAYSCALE"}:
        return False
    if m["ssim"] < q["preferred_graphic_ssim_min"] or m["edge_f1"] < q["preferred_edge_f1_min"]:
        return False
    if cls in {"SCREENSHOT_OR_TEXT_GRAPHIC", "LINE_ART_GRAYSCALE"}:
        if m["component_retention"] < q["preferred_component_retention_min"]:
            return False
    if cls in {"SCREENSHOT_OR_TEXT_GRAPHIC", "ALPHA_GRAPHIC", "MIXED_CONTENT"}:
        if m["deltae_mean"] > q["preferred_color_deltae_mean_max"]:
            return False
        if m["deltae_p95"] > q["preferred_color_deltae_p95_max"]:
            return False
    return True


# ------------------------------------------------------------ Auswahl

@dataclass
class Auswahl:
    """Ergebnis der Kandidatenwahl für ein Bild."""
    technical_class: str
    class_reasons: list[str]
    features: dict[str, Any]
    reference: Image.Image
    candidate: Candidate | None
    metrics: dict[str, float] | None
    selection_zone: str | None
    status: str          # "OPTIMIZED" | "NO_CANDIDATE_PASSED" | "KEEP_ORIGINAL_NO_SAVING"


def waehle_kandidat(src: Path, target_w: int, target_h: int, cfg: BildKonfig) -> Auswahl:
    feats = technical_features(src, cfg)
    cls, reasons = classify_image(feats, cfg)
    ref = resize_reference(src, target_w, target_h)

    evaluated = []
    for cand in candidate_family(ref, cls, cfg):
        metrics = evaluate(ref, cand)
        ok, _failures = passes_gate(cls, metrics, cfg)
        if ok:
            evaluated.append((cand, metrics, preferred_quality_zone(cls, metrics, cfg)))

    if not evaluated:
        return Auswahl(cls, reasons, feats, ref, None, None, None, "NO_CANDIDATE_PASSED")

    preferred = [x for x in evaluated if x[2]]
    pool = preferred or evaluated
    cand, metrics, _ = min(pool, key=lambda x: (x[0].nbytes, x[1]["deltae_mean"], -x[1]["ssim"]))
    zone = "preferred" if preferred else "minimum"

    if 1 - cand.nbytes / src.stat().st_size < cfg.min_saving_ratio:
        return Auswahl(cls, reasons, feats, ref, None, metrics, zone, "KEEP_ORIGINAL_NO_SAVING")
    return Auswahl(cls, reasons, feats, ref, cand, metrics, zone, "OPTIMIZED")

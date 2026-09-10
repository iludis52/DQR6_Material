# Image Optimization & Metadata Enrichment Pipeline — Software Design Specification

**Document:** `spec.md`  
**Status:** Draft / SDD v0.1  
**Date:** 2026-09-10  
**Scope:** Optimization and metadata enrichment of images extracted from scanned PDFs by Docling and referenced from Markdown documents.

---

## 1. Purpose

This specification defines a deterministic, auditable pipeline for reducing the storage footprint of raster images produced during scan-PDF-to-Markdown conversion while preserving enough visual information for screen-based document consumption and later RAG processing.

The system SHALL:

- locate image assets referenced by a Docling document and/or Markdown document;
- derive the intended physical image size from Docling provenance bounding boxes;
- enforce a maximum raster density of **144 pixels per inch (ppi)** relative to the source document geometry;
- classify images by technical raster characteristics;
- select **JPEG** or **PNG** as the canonical output format;
- optimize resolution, bit depth, palette and compression according to the image class;
- preserve or generate machine-readable metadata using **XMP**;
- optionally call a local vision LLM through **LM Studio**, initially targeting **Gemma 4 12B**, to generate semantic metadata;
- update Markdown image references and alt text when appropriate;
- validate the written image and metadata by reopening the output;
- generate an audit manifest describing every decision;
- never irreversibly overwrite source assets by default.

The principal optimization objective is:

> **Minimize output byte size subject to recognizability, metadata integrity, document portability and the 144 ppi ceiling.**

High-fidelity preservation is explicitly secondary to portability and compactness.

---

## 2. Design Principles

### 2.1 Portability over maximum fidelity

The canonical output set SHALL be restricted to:

- **JPEG** for suitable lossy photographic or continuous-tone content;
- **PNG** for line art, diagrams, screenshots, transparency, low-color graphics and other cases where JPEG artifacts would be disproportionately harmful.

WebP, AVIF and other modern formats SHALL NOT be canonical outputs in v0.1, even if they yield smaller files.

Rationale: JPEG and PNG have broad, mature decoder support, support embedded metadata workflows, and are suitable for long-lived Markdown assets.

### 2.2 Deterministic optimization before AI

Image resizing, classification, format choice, palette reduction, grayscale conversion, JPEG quality search and objective quality checks SHALL be deterministic.

The vision LLM SHALL be used only for semantic description and keyword generation, not for:

- choosing JPEG versus PNG;
- choosing compression quality;
- deciding whether an image is safe to binarize;
- computing target dimensions;
- validating pixel-level preservation.

### 2.3 No unconditional global compression preset

The system SHALL NOT apply one global rule such as `JPEG quality = 80` or `convert all PNG files to JPEG`.

Each image SHALL be evaluated independently.

### 2.4 “Keep original” is a valid result

If no candidate is sufficiently smaller or passes required validation, the pipeline SHALL retain the original asset.

### 2.5 Metadata is part of output correctness

An image SHALL NOT be considered successfully processed until:

1. the file can be reopened;
2. dimensions and image mode are valid;
3. the expected embedded metadata can be read back;
4. the image reference can be resolved from the Markdown document or manifest.

---

## 3. Inputs

### 3.1 Primary input: Docling JSON

The primary metadata source SHALL be a Docling `DoclingDocument` JSON file.

For each `picture`, the pipeline SHOULD consume:

```text
self_ref
prov[].page_no
prov[].bbox.l
prov[].bbox.t
prov[].bbox.r
prov[].bbox.b
prov[].bbox.coord_origin
image.mimetype
image.dpi
image.size.width
image.size.height
image.uri
captions[]
```

The supplied reference document confirms that the extracted pictures include:

- a source-page bounding box;
- source page number;
- 300 dpi extraction metadata;
- raster dimensions;
- the relative artifact URI.

### 3.2 Secondary input: Markdown

The Markdown document SHALL be scanned for image references.

Typical current syntax:

```markdown
![Image](FachkundeMechatronik_I4-0_artifacts/example.png)
```

The pipeline MAY replace the generic `Image` alt text with a generated semantic alt text.

### 3.3 Asset directory

The pipeline SHALL resolve image URIs relative to a configurable document root.

It SHOULD support both:

- **document-aware mode:** process only images referenced by Docling/Markdown;
- **folder mode:** recursively process eligible raster assets in a configured directory.

Document-aware mode SHALL be the default.

---

## 4. Output Structure

The default workflow SHOULD preserve source files and write processed assets to a separate tree.

Example:

```text
document-root/
├── source/
│   ├── document.json
│   ├── document.md
│   └── artifacts/
├── optimized/
│   ├── document.md
│   ├── assets/
│   ├── manifest.json
│   └── manifest.csv
└── notebook/
    └── image_optimization.ipynb
```

The concrete folder structure SHALL be configurable.

---

## 5. Resolution Policy

### 5.1 Hard density ceiling

The maximum output density SHALL be:

```text
MAX_PPI = 144
```

Docling bounding boxes are expressed in page coordinates compatible with PDF point geometry in the supplied fixture. The implementation SHALL derive target dimensions from the bounding box rather than from the extracted raster DPI alone.

Assuming 72 points per inch:

```python
bbox_width_pt  = abs(r - l)
bbox_height_pt = abs(b - t)

max_width_px  = round(bbox_width_pt  / 72 * MAX_PPI)
max_height_px = round(bbox_height_pt / 72 * MAX_PPI)
```

At 144 ppi:

```python
max_width_px  = round(bbox_width_pt * 2)
max_height_px = round(bbox_height_pt * 2)
```

### 5.2 Never upscale

The system SHALL NOT upscale an image.

```python
scale = min(
    1.0,
    max_width_px / original_width,
    max_height_px / original_height,
)
```

### 5.3 Preserve aspect ratio

The output SHALL preserve source aspect ratio unless a future explicit crop correction stage is introduced.

### 5.4 Resampling

Downsampling SHOULD use a high-quality reconstruction filter such as Lanczos.

A prefilter or staged reduction MAY be evaluated if aliasing is observed in difficult line-art cases.

### 5.5 Density metadata

Output DPI/PPI metadata MAY be written as `144 × 144` when supported, but SHALL NOT be treated as authoritative layout geometry.

The Docling bounding box remains the authoritative source for document placement geometry.

---

## 6. Technical Image Classification

### 6.1 Required classes

The deterministic classifier SHALL support at least:

```text
PHOTO_COLOR
PHOTO_GRAYSCALE
LINE_ART_BILEVEL
LINE_ART_GRAYSCALE
GRAPHIC_LOW_COLOR
SCREENSHOT_OR_TEXT_GRAPHIC
MIXED_CONTENT
ALPHA_GRAPHIC
UNKNOWN
```

### 6.2 Classification is technical, not semantic

The classifier answers questions such as:

- Is the image continuous-tone?
- Is it effectively grayscale?
- Does it contain very few dominant colors?
- Are edges unusually dense?
- Is the image likely to tolerate palette reduction?
- Is true transparency present?
- Is near-bilevel conversion plausible?

It SHALL NOT attempt to determine semantic concepts such as “robot”, “machine”, “flowchart” or “digital twin”.

### 6.3 Feature set

The initial classifier SHOULD calculate the following inexpensive features after optional thumbnailing:

```text
has_alpha
alpha_fraction_nonopaque
grayscale_distance
unique_color_estimate
dominant_color_fraction
luminance_entropy
color_entropy
edge_density
edge_strength_distribution
local_variance
flat_area_fraction
near_black_fraction
near_white_fraction
mid_tone_fraction
connected_component statistics (optional)
```

The full-resolution image SHOULD NOT be required for all features.

### 6.4 Grayscale detection

A color image MAY be classified as effectively grayscale when channel differences are negligible.

Example metric:

```python
gray_distance = mean(
    max(abs(R-G), abs(R-B), abs(G-B))
)
```

The final threshold SHALL be calibrated against a representative corpus.

A threshold SHALL NOT be treated as a universal best-practice constant unless empirical validation supports it.

### 6.5 Bilevel candidate detection

An image MAY be considered a bilevel candidate when:

- it is grayscale or effectively grayscale;
- most pixels cluster near black or white;
- mid-tone occupancy is low;
- edges are structurally strong;
- binarization does not remove excessive connected components or edge content.

The system SHALL NOT binarize solely because an image “looks black and white”.

### 6.6 Low-color graphic detection

The system SHOULD classify likely former vector graphics, icons and diagrams using:

- a low number of perceptually distinct colors;
- large homogeneous regions;
- relatively high edge density;
- low photographic texture;
- low local variance within regions.

Such images SHOULD favor indexed PNG candidates.

### 6.7 Screenshot/text-heavy detection

Text-heavy and screenshot-like images SHOULD favor PNG.

JPEG SHALL only be evaluated for these classes as an explicit fallback or benchmark candidate, not as the primary choice.

### 6.8 Unknown and ambiguous content

Ambiguous images SHALL use candidate competition rather than forced classification.

For example:

```text
MIXED_CONTENT / UNKNOWN
    → evaluate JPEG candidate set
    → evaluate PNG candidate set
    → apply class-neutral safety checks
    → select smallest acceptable result
```

---

## 7. Black-and-White and Former Vector Graphics

### 7.1 Bilevel conversion

Potential bilevel images SHALL be tested using one or more deterministic thresholding methods:

- Otsu global thresholding;
- adaptive thresholding where illumination is non-uniform.

OpenCV documents Otsu and adaptive thresholding as standard approaches, and adaptive thresholding is specifically appropriate when different image regions have different illumination.

The pipeline SHALL compare the binarized candidate against the resized grayscale reference before accepting it.

### 7.2 PNG bit depth

Where supported by the encoder, bilevel output SHOULD use an efficient 1-bit representation.

Low-color grayscale or palette candidates MAY use reduced effective bit depth when this materially reduces size.

### 7.3 Palette quantization

Former vector graphics and low-color diagrams SHOULD be tested as indexed PNG.

Candidate palette sizes SHOULD include a bounded search such as:

```text
2, 4, 8, 16, 32, 64, 128, 256 colors
```

The search MAY terminate early once additional colors no longer materially improve validation quality.

### 7.4 Quantization implementation

Preferred implementations SHOULD include:

- Pillow `Image.quantize()` for baseline support;
- `libimagequant` / `pngquant` where deployment and licensing constraints permit.

`libimagequant` is preferred for high-quality palette generation because it includes perceptual quality handling and can target the smallest palette satisfying a quality goal.

The production implementation SHALL document any third-party licensing implications before distribution.

### 7.5 Dithering

Dithering SHALL NOT be globally enabled.

For diagrams and former vector graphics, no-dither or adaptive-dither candidates SHOULD be compared because dithering can:

- increase entropy and file size;
- introduce visual noise;
- degrade OCR/text edges.

For photographic or gradient-heavy palette candidates, adaptive dithering MAY produce better perceived quality.

---

## 8. JPEG Strategy

### 8.1 JPEG eligibility

JPEG SHOULD be the primary format for:

```text
PHOTO_COLOR
PHOTO_GRAYSCALE
```

JPEG MAY be evaluated for:

```text
MIXED_CONTENT
UNKNOWN
```

JPEG SHOULD NOT be the default for:

```text
LINE_ART_BILEVEL
LINE_ART_GRAYSCALE
GRAPHIC_LOW_COLOR
SCREENSHOT_OR_TEXT_GRAPHIC
ALPHA_GRAPHIC
```

### 8.2 Grayscale JPEG

Effectively grayscale photographs SHALL be converted to a true single-channel grayscale representation before JPEG encoding.

### 8.3 Candidate quality search

The first implementation SHOULD evaluate a discrete quality ladder rather than one fixed value.

Initial search range:

```text
85, 75, 65, 55, 45
```

A lower emergency candidate such as `35` MAY be enabled by configuration for particularly aggressive deployments.

These values are starting points for corpus calibration, not universal quality standards.

Pillow currently recommends avoiding values above 95 because they produce disproportionately large files for little gain.

### 8.4 Chroma subsampling

For color photographs, the default candidate SHOULD allow 4:2:0 chroma subsampling.

For mixed graphics or text-like edges, 4:4:4 MAY be benchmarked if JPEG is otherwise competitive.

The pipeline SHOULD prefer PNG rather than increasing JPEG quality indefinitely for hard-edged content.

### 8.5 JPEG optimization flags

The implementation SHOULD evaluate:

```text
optimize=True
progressive=True
```

Progressive JPEG MAY be used if it is consistently supported by the target stack and does not interfere with metadata handling.

---

## 9. PNG Strategy

### 9.1 PNG eligibility

PNG SHOULD be primary for:

```text
LINE_ART_BILEVEL
LINE_ART_GRAYSCALE
GRAPHIC_LOW_COLOR
SCREENSHOT_OR_TEXT_GRAPHIC
ALPHA_GRAPHIC
```

### 9.2 PNG candidate family

The candidate generator SHOULD evaluate relevant subsets of:

```text
PNG truecolor
PNG grayscale
PNG bilevel
PNG indexed 2 colors
PNG indexed 4 colors
PNG indexed 8 colors
PNG indexed 16 colors
PNG indexed 32 colors
PNG indexed 64 colors
PNG indexed 128 colors
PNG indexed 256 colors
```

### 9.3 Lossy PNG quantization

Palette quantization is permitted because the project explicitly prioritizes portability and compactness over perfect pixel preservation.

A quantized PNG SHALL still pass the class-specific quality gate.

### 9.4 PNG post-optimization

A lossless PNG optimizer MAY be run after raster/palette decisions, provided it:

- does not alter pixels;
- does not strip required XMP metadata;
- passes read-back validation.

The pipeline SHALL verify metadata after any such step.

---

## 10. Candidate Evaluation

### 10.1 Reference image

Quality comparison SHALL use the **resized 144-ppi reference**, not the original 300-ppi extraction.

This separates two decisions:

1. approved resolution loss caused by the 144 ppi policy;
2. additional codec/quantization loss.

### 10.2 Objective metrics

No single metric SHALL determine acceptance for every image class.

The implementation SHOULD support:

```text
SSIM
edge retention
contrast retention
connected-component retention
palette/quantization error
optional OCR consistency
```

SSIM is preferred over raw MSE as a general structural metric because it better reflects structural image changes, but it SHALL NOT be the sole metric for text and line art.

### 10.3 Edge retention

For line art, diagrams and text-heavy assets, the pipeline SHOULD compare edge maps between the reference and candidate.

The exact edge detector MAY be Canny or an equivalent deterministic detector.

The metric SHOULD penalize:

- deleted thin lines;
- newly introduced ringing edges;
- severe boundary displacement.

### 10.4 Connected-component retention

For bilevel or text-like images, the pipeline MAY compare connected components before and after optimization.

This is useful for detecting lost dots, thin strokes, symbols and small labels.

### 10.5 OCR consistency

OCR SHALL be optional in v0.1.

When enabled for text-heavy graphics, OCR SHOULD be treated as a sanity check, not a semantic truth source.

Potential metrics include:

```text
recognized token overlap
character-level similarity
word-count ratio
text-region count
```

OCR SHALL NOT be required for photographic assets with little or no embedded text.

### 10.6 Acceptance philosophy

Because recognizability is more important than high fidelity, default thresholds MAY be relatively permissive.

However, thresholds SHALL be corpus-calibrated.

No hard-coded SSIM, edge-retention or OCR threshold in this specification is considered normative until benchmark data exists.

### 10.7 Selection function

Among all accepted candidates, select:

```text
candidate with minimum byte size
```

subject to:

```text
candidate passes required quality gates
candidate metadata can be embedded
candidate can be reopened
candidate preserves required transparency semantics
candidate respects 144 ppi ceiling
```

### 10.8 Minimum savings requirement

A configurable minimum reduction SHOULD prevent pointless rewrites.

Example configuration:

```text
MIN_SAVING_RATIO = 0.10
```

If no candidate is at least 10% smaller than the relevant baseline, `KEEP_ORIGINAL` MAY be selected.

This value is a project policy parameter and SHALL be benchmarked.

---

## 11. Metadata Architecture

### 11.1 Canonical embedded metadata format

XMP SHALL be the canonical embedded semantic metadata representation.

Standard namespaces SHOULD be preferred whenever semantics already exist.

Initial standards:

```text
Dublin Core
IPTC Core / IPTC Extension
XMP Rights where relevant
```

A custom namespace SHALL be used only for pipeline-specific provenance.

### 11.2 Proposed standard fields

The following fields SHOULD be populated when available:

```text
dc:title
dc:description
dc:subject
dc:language
```

IPTC accessibility fields SHOULD be evaluated for the generated alt-text representation.

### 11.3 Custom namespace

Working prefix:

```text
docrag
```

The production namespace URI SHALL be owned and versioned by the project or customer organization before release.

Suggested fields:

```text
docrag:schemaVersion
docrag:assetId
docrag:sourceDocument
docrag:sourcePage
docrag:sourcePictureRef
docrag:sourceBBox
docrag:sourceCoordOrigin
docrag:sourceImageUri
docrag:sourceWidth
docrag:sourceHeight
docrag:sourceDpi
docrag:optimizedWidth
docrag:optimizedHeight
docrag:technicalClass
docrag:descriptionMethod
docrag:descriptionModel
docrag:descriptionModelVersion
docrag:metadataGeneratedAt
```

### 11.4 Human description versus source caption

The pipeline SHALL distinguish:

```text
source caption
generated title
generated alt text
generated description
generated keywords
```

A source caption SHALL NOT be silently replaced by an LLM-generated description.

### 11.5 Redundant semantic storage

Semantic image information SHOULD exist in three places:

```text
1. embedded XMP
2. Markdown alt text
3. JSON audit / RAG manifest
```

The redundancy is intentional.

### 11.6 Existing metadata

Existing metadata SHALL be inspected before writing.

The pipeline SHOULD retain useful provenance but SHALL NOT blindly copy stale technical metadata whose values are no longer correct after resizing or re-encoding.

---

## 12. Vision LLM Integration

### 12.1 Runtime

The initial implementation SHALL target a local LM Studio server.

LM Studio currently exposes OpenAI-compatible API endpoints and supports image-capable chat requests.

Default base URL SHOULD be configurable, with the common local default:

```text
http://localhost:1234/v1
```

### 12.2 Initial model

Initial target model:

```text
Gemma 4 12B
```

The exact LM Studio model identifier SHALL be resolved from `/v1/models` at runtime or configured explicitly.

No pipeline logic SHALL depend on a hard-coded display name.

### 12.3 Input image

The LLM SHALL describe the **final optimized image**, not the higher-resolution source.

Rationale: metadata should describe information actually available in the delivered asset.

### 12.4 Context

The model SHOULD receive, when available:

```text
document title
section heading
source caption
nearby text
page number
optimized image
```

Context SHALL be labeled as document context and SHALL NOT be presented as guaranteed visual truth.

### 12.5 Required structured output

LM Studio supports JSON-schema-constrained structured outputs through its OpenAI-compatible API.

The pipeline SHOULD request a strict schema similar to:

```json
{
  "title": "string",
  "alt_text": "string",
  "description": "string",
  "keywords": ["string"],
  "semantic_visual_type": "string",
  "contains_visible_text": true,
  "visible_text_summary": "string"
}
```

### 12.6 LLM restrictions

The system prompt SHALL instruct the model to:

- describe only visible or strongly context-supported information;
- avoid identifying uncertain people, brands or locations;
- not invent text that is unreadable;
- distinguish visible content from contextual interpretation;
- produce concise alt text;
- produce a more detailed RAG description separately;
- return a compact keyword list;
- use the document language where known.

### 12.7 Failure handling

If the LLM is unavailable or returns invalid structured output:

```text
image optimization SHALL still succeed
metadata status = SEMANTIC_METADATA_PENDING
```

The vision stage SHALL be retryable independently.

---

## 13. Markdown Update Policy

### 13.1 Path rewriting

If the image extension changes, all matching Markdown references SHALL be rewritten.

Example:

```markdown
![Image](assets/example.png)
```

may become:

```markdown
![semantic alt text](assets/example.jpg)
```

### 13.2 Alt text

Generated alt text SHOULD be concise and useful for both accessibility and RAG preprocessing.

The long description SHALL remain in XMP/manifest rather than being copied wholesale into Markdown alt text.

### 13.3 Source captions

Existing document captions SHALL remain ordinary Markdown content and SHALL NOT be deleted merely because metadata contains a caption field.

---

## 14. Audit Manifest

### 14.1 Manifest record

Every processed asset SHALL produce an audit record.

Minimum fields:

```json
{
  "asset_id": "...",
  "source_path": "...",
  "output_path": "...",
  "source_sha256": "...",
  "source_format": "PNG",
  "source_width": 1282,
  "source_height": 568,
  "source_bytes": 941862,
  "source_page": 3,
  "bbox": [229.75, 99.97, 525.92, 224.83],
  "max_ppi": 144,
  "target_width": 592,
  "target_height": 250,
  "technical_class": "PHOTO_COLOR",
  "selected_format": "JPEG",
  "selected_quality": 55,
  "selected_palette_size": null,
  "output_width": 592,
  "output_height": 262,
  "output_bytes": 0,
  "saving_ratio": 0.0,
  "quality_metrics": {},
  "metadata_status": "VALID",
  "llm_status": "VALID",
  "decision": "REPLACE"
}
```

Numerical values above are illustrative except where derived directly from the known sample metadata.

### 14.2 Decision reasons

The manifest SHOULD include machine-readable reason codes, e.g.:

```text
RESIZED_TO_PPI_LIMIT
CONVERTED_PHOTO_TO_JPEG
CONVERTED_TO_GRAYSCALE
QUANTIZED_PALETTE
BINARIZED
KEPT_ORIGINAL_QUALITY_GATE
KEPT_ORIGINAL_NO_SAVING
METADATA_VALIDATED
LLM_UNAVAILABLE
```

---

## 15. Idempotency and Repeatability

The pipeline SHOULD be idempotent.

A second run over an already optimized tree SHALL NOT repeatedly apply lossy re-encoding.

Recommended mechanisms:

- source SHA-256;
- optimization schema version;
- pipeline version;
- stored candidate parameters;
- generated-file marker in the manifest/XMP.

When the source hash and relevant configuration are unchanged, the pipeline SHOULD reuse the prior result.

---

## 16. Safety and File Integrity

### 16.1 Non-destructive default

Source images SHALL NOT be overwritten by default.

### 16.2 Atomic writes

Output files SHOULD be written to a temporary path and atomically renamed only after validation succeeds.

### 16.3 Read-back validation

Each written candidate SHALL be reopened and checked for:

```text
decodability
expected dimensions
expected format
expected color mode
metadata presence
XMP parseability
```

### 16.4 Broken Markdown prevention

Markdown path updates SHALL occur only after the target image has been successfully written and validated.

---

## 17. Notebook Structure

The Jupyter notebook SHOULD be organized into separable stages:

```text
00_configuration
01_environment_check
02_discover_documents
03_parse_docling
04_parse_markdown
05_build_asset_manifest
06_analyze_images
07_compute_144ppi_targets
08_generate_candidates
09_evaluate_candidates
10_select_candidates
11_write_images
12_generate_semantic_metadata
13_embed_xmp
14_validate_outputs
15_update_markdown
16_write_manifests
17_report
```

Each stage SHOULD be rerunnable independently where practical.

---

## 18. Configuration Model

Initial configuration SHOULD expose at least:

```yaml
input_root: ...
output_root: ...

max_ppi: 144

formats:
  jpeg: true
  png: true

jpeg:
  quality_candidates: [85, 75, 65, 55, 45]
  allow_quality_35: false
  optimize: true
  progressive: true

png:
  palette_candidates: [2, 4, 8, 16, 32, 64, 128, 256]
  allow_bilevel: true
  use_libimagequant_if_available: true

selection:
  minimum_saving_ratio: 0.10

quality:
  ssim_enabled: true
  edge_metric_enabled: true
  connected_components_enabled: true
  ocr_enabled: false

metadata:
  embed_xmp: true
  write_manifest_json: true
  write_manifest_csv: true

llm:
  enabled: true
  provider: lm_studio
  base_url: http://localhost:1234/v1
  model: gemma-4-12b
  structured_output: true
```

Thresholds used by the classifier and quality gates SHALL be centralized in configuration rather than scattered through notebook cells.

---

## 19. Benchmark and Calibration Plan

### 19.1 Why calibration is mandatory

There is no defensible universal threshold for:

```text
grayscale_distance
edge_density
SSIM acceptance
bilevel safety
minimum connected-component retention
```

These SHALL therefore be calibrated against real extracted assets.

### 19.2 Corpus

The benchmark corpus SHOULD deliberately include:

```text
color photographs
grayscale photographs
black-and-white scans
technical diagrams
former vector graphics
screenshots
small text
fine lines
mixed photo/text assets
transparent graphics
noisy scans
```

### 19.3 Benchmark outputs

For each candidate:

```text
source bytes
target bytes
saving %
encoding time
technical class
SSIM
edge metric
component metric
OCR metric if enabled
human pass/fail sample
```

### 19.4 Human review

A representative subset SHOULD be manually reviewed at realistic document-viewer scale.

The review question is intentionally modest:

> Is all materially relevant visual information still recognizable for the intended screen-based document use?

The benchmark SHALL not optimize for pixel-level indistinguishability.

### 19.5 Threshold finalization

Only after benchmark review SHOULD classifier and quality thresholds be promoted from experimental defaults to project defaults.

---

## 20. Initial Decision Matrix

| Technical class | Primary candidate | Secondary candidate | Special handling |
|---|---|---|---|
| `PHOTO_COLOR` | JPEG | PNG benchmark only | resize ≤144 ppi, JPEG quality search |
| `PHOTO_GRAYSCALE` | grayscale JPEG | grayscale PNG | remove unnecessary color channels |
| `LINE_ART_BILEVEL` | 1-bit/indexed PNG | grayscale PNG | Otsu/adaptive candidate + structure gate |
| `LINE_ART_GRAYSCALE` | grayscale PNG | indexed PNG | protect thin edges |
| `GRAPHIC_LOW_COLOR` | indexed PNG | truecolor PNG | palette search, preferably perceptual quantizer |
| `SCREENSHOT_OR_TEXT_GRAPHIC` | PNG | JPEG benchmark only | edge/text preservation |
| `ALPHA_GRAPHIC` | PNG | — | preserve transparency semantics |
| `MIXED_CONTENT` | JPEG + PNG competition | — | class-neutral candidate comparison |
| `UNKNOWN` | JPEG + PNG competition | keep original | conservative fallback |

---

## 21. Non-Goals for v0.1

The first implementation SHALL NOT attempt:

- SVG reconstruction or general raster-to-vector conversion;
- neural super-resolution;
- image restoration;
- generative reconstruction of lost details;
- semantic image editing;
- cloud-based vision APIs;
- AVIF/WebP canonical output;
- full document-layout reconstruction;
- automatic removal of images judged “unimportant”.

These MAY be revisited in later versions.

---

## 22. Open Design Questions

The following remain intentionally unresolved until benchmarking:

1. Exact grayscale classification threshold.
2. Exact near-bilevel threshold.
3. Whether Otsu alone is sufficient for most line-art or whether adaptive thresholding is frequently needed.
4. Whether connected-component retention materially improves safety.
5. Whether OCR validation is worth its runtime cost.
6. Final JPEG quality ladder and minimum permitted quality.
7. Whether `progressive=True` yields a meaningful practical benefit for local Markdown viewing.
8. Whether `pngquant/libimagequant` can be deployed under the project's licensing constraints.
9. Exact XMP custom namespace URI.
10. Whether the RAG manifest becomes a permanent customer-facing artifact or remains pipeline-internal.
11. Exact LM Studio model identifier for the selected Gemma 4 12B quantization.
12. Maximum keyword count and long-description length for RAG metadata.

---

## 23. Acceptance Criteria for v0.1

The implementation is accepted when it can process a representative test document end-to-end and satisfy all of the following:

- every Docling-referenced image is discovered or explicitly reported missing;
- no output exceeds 144 ppi relative to its Docling bounding box;
- no image is upscaled;
- every replacement is JPEG or PNG;
- every replacement is smaller than the configured minimum-savings threshold unless explicitly forced;
- every replacement passes its required quality gate;
- every final image can be reopened;
- XMP can be read back after final encoding;
- Markdown references resolve to existing final files;
- source assets remain untouched;
- the manifest records every decision;
- the pipeline completes even if LM Studio is unavailable;
- LLM output, when enabled, validates against a JSON schema before being embedded.

---

## 24. Current Best-Practice and Standards Basis

The design above intentionally separates standards-backed decisions from project-specific thresholds.

### Standards / primary references

1. **W3C — Portable Network Graphics (PNG) Specification, Third Edition**  
   PNG defines grayscale, indexed-color and metadata mechanisms including XMP carriage.  
   https://www.w3.org/TR/png-3/

2. **IPTC Photo Metadata Standard 2025.1**  
   Current IPTC Photo Metadata specification; XMP is used as a technical representation and the 2025.1 update includes AI-related provenance fields.  
   https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata-2025.1.html

3. **IPTC Photo Metadata Standard overview**  
   Documents the current relationship between IPTC metadata and XMP.  
   https://iptc.org/standards/photo-metadata/iptc-standard/

4. **LM Studio — OpenAI Compatibility Endpoints**  
   LM Studio provides local OpenAI-compatible endpoints including chat with image inputs.  
   https://lmstudio.ai/docs/developer/openai-compat

5. **LM Studio — Structured Output**  
   Documents JSON-Schema-constrained responses through `/v1/chat/completions`.  
   https://lmstudio.ai/docs/developer/openai-compat/structured-output

### Image-processing references

6. **Pillow — Image File Formats**  
   Documents current JPEG quality, optimization, progressive output, DPI and ICC handling.  
   https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html

7. **Pillow — `Image.quantize()`**  
   Documents palette quantization methods including libimagequant where compiled in.  
   https://pillow.readthedocs.io/en/stable/reference/Image.html

8. **pngquant / libimagequant**  
   Perceptual palette quantization, adaptive dithering and quality-constrained palette generation.  
   https://pngquant.org/  
   https://pngquant.org/lib/

9. **OpenCV — Image Thresholding**  
   Documents global, Otsu and adaptive thresholding; adaptive thresholding is intended for spatially varying illumination.  
   https://docs.opencv.org/4.12.0/d7/dd0/tutorial_js_thresholding.html

10. **scikit-image — Structural Similarity (SSIM)**  
    SSIM is preferred over simple MSE for structural/perceptual comparisons, while not being sufficient alone for line art and text.  
    https://scikit-image.org/docs/stable/auto_examples/transform/plot_ssim.html

11. **libjpeg-turbo — Quality vs. Size**  
    Demonstrates the substantial trade-off between JPEG quality and compression and provides empirical reference points for low-quality versus perceptually lossless settings.  
    https://libjpeg-turbo.org/About/SmartScale-Lossy

---

## 25. Decision Log

### D-001 — Canonical raster formats

**Decision:** JPEG + PNG only.  
**Reason:** portability, browser support, mature tooling, metadata capability and long-term readability outweigh additional savings from newer formats.

### D-002 — Maximum density

**Decision:** hard ceiling of 144 ppi relative to Docling/PDF geometry.  
**Reason:** screen use and portability take precedence over high-resolution preservation.

### D-003 — Vision model role

**Decision:** local vision LLM used only for semantic metadata.  
**Initial target:** Gemma 4 12B via LM Studio.  
**Reason:** semantic description benefits from a multimodal model; compression decisions remain reproducible and deterministic.

### D-004 — Metadata

**Decision:** XMP is canonical embedded metadata; Markdown alt text and a JSON manifest duplicate selected semantic information.  
**Reason:** asset portability, RAG accessibility and independent auditability.

### D-005 — Thresholds

**Decision:** classifier and quality thresholds are empirical configuration, not fixed by this specification.  
**Reason:** current developer practice and image-processing literature support the techniques, but no universal thresholds exist across heterogeneous scan corpora.

---

## 26. Next Implementation Step

Before implementing the full optimizer, create an **analysis/calibration notebook** that:

1. parses the supplied Docling JSON;
2. resolves all referenced images;
3. computes the 144-ppi target size for each image;
4. extracts the technical classifier features;
5. generates JPEG/PNG candidate families;
6. records candidate sizes and quality metrics;
7. displays selected representative candidates for human review;
8. does **not** yet overwrite or rewrite production Markdown.

The resulting benchmark data SHALL be used to finalize the classifier thresholds and quality gates for SDD v0.2.

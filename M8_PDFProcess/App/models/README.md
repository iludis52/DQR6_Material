---
license: apache-2.0
base_model: PaddlePaddle/PP-DocLayoutV3_safetensors
tags:
- onnx
- onnxruntime
- document-layout-analysis
- document-ai
- layout-detection
- object-detection
pipeline_tag: object-detection
library_name: onnxruntime
---

# PP-DocLayoutV3 (ONNX)

ONNX export of [`PaddlePaddle/PP-DocLayoutV3_safetensors`](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3_safetensors),
a DETR-style document layout detection model. Given a document page image, it
predicts per-region bounding boxes, layout class, reading order, and
(optionally) segmentation polygons for 25 layout element types
(title, text, table, figure, formula, header/footer, reference, seal, ...).

This repo ships the traced ONNX graph only — inference needs **ONNX Runtime +
NumPy + OpenCV**, no PyTorch or `transformers` required at serve time. The
export script and reference pre/post-processing code (`pp_doclayout_v3_onnx.py`)
are included in this repo for convenience — see below.

## Files

| File | Description |
|---|---|
| `pp_doclayoutv3.onnx` | Full graph, includes the mask head (`out_masks`) for polygon output |
| `pp_doclayoutv3_nomask.onnx` | Same graph without `out_masks` — smaller, no ~48 MB/image mask tensor; polygons degrade to axis-aligned boxes |
| `pp_doclayoutv3_fp16.onnx` | Half-precision copy of the graph above it (normalization/mask ops kept in fp32) |
| `labels.json` | `id2label` mapping used to decode `logits` |

Only the variants actually present in this repo were exported — see the
file list on the repo page for what's available.

## Model I/O

**Input**

| Name | Shape | Notes |
|---|---|---|
| `pixel_values` | `(B, 3, 800, 800)` float32 | RGB, resized to a fixed 800×800 square (bicubic), scaled to `[0, 1]`. No mean/std normalization (`mean=0`, `std=1`). Batch dim is dynamic. |

**Output**

| Name | Shape | Notes |
|---|---|---|
| `logits` | `(B, 300, 25)` | Per-query class scores (sigmoid, not softmax) |
| `pred_boxes` | `(B, 300, 4)` | `cxcywh`, normalized to `[0, 1]` |
| `order_logits` | `(B, 300, 300)` | Reading-order pointer matrix |
| `out_masks` *(optional)* | `(B, 300, 200, 200)` | Mask logits at stride 4 (input_size / 4) |

300 object queries, no NMS — box selection is done by top-`k` over the
flattened `(query, class)` score grid and thresholding, matching the
original PaddlePaddle/HF post-processing.

## Usage

```python
import numpy as np
import onnxruntime as ort

session = ort.InferenceSession("pp_doclayoutv3.onnx", providers=["CPUExecutionProvider"])
pixel_values = np.random.rand(1, 3, 800, 800).astype(np.float32)  # preprocess your image to this
logits, pred_boxes, order_logits, out_masks = session.run(None, {"pixel_values": pixel_values})
```

Decoding raw outputs into boxes/labels/reading-order/polygons requires the
post-processing logic ported from `PPDocLayoutV3ImageProcessor` (sigmoid
scoring, top-k selection, cxcywh→xyxy rescaling, reading-order pointer
resolution, mask→polygon extraction). The reference implementation is
`pp_doclayout_v3_onnx.py` in the source repo — a self-contained
`PPDocLayoutV3ONNX` class with no torch/transformers dependency:

```python
from pp_doclayout_v3_onnx import PPDocLayoutV3ONNX

det = PPDocLayoutV3ONNX("pp_doclayoutv3.onnx", device="cpu")  # or "cuda" / "tensorrt"
for r in det.predict("page.jpg"):
    print(r["order"], r["label"], r["score"], r["box"])
```

## Examples

Served with `serve_pp_doclayout_v3.py` (TensorRT/CUDA EP, `threshold=0.4`, masks on)
against dense scientific-article pages from the CDLA-Permissive-1.0-licensed
[`creative-graphic-design/PubLayNet`](https://huggingface.co/datasets/creative-graphic-design/PubLayNet)
dataset (PubMed Central open-access articles), selected for high layout-element
count out of a scan of the train split — see `fetch_example_images.py`. Boxes
below are colored by predicted label, tagged `{reading_order}:{label} {score}`.
Full detections (all 25 classes, boxes, polygons, reading order) are in the
linked JSON.

| Input → detections | Elements | Labels detected | JSON |
|---|---|---|---|
| ![PMC5883225_00001](examples/outputs/PMC5883225_00001_annotated.jpg) | 38 | chart, figure_title, formula, header, number, paragraph_title, text | [PMC5883225_00001.json](examples/outputs/PMC5883225_00001.json) |
| ![PMC5883194_00003](examples/outputs/PMC5883194_00003_annotated.jpg) | 30 | chart, figure_title, header, number, paragraph_title, table, text, vision_footnote | [PMC5883194_00003.json](examples/outputs/PMC5883194_00003.json) |
| ![PMC4413546_00014](examples/outputs/PMC4413546_00014_annotated.jpg) | 29 | chart, figure_title, header, number, paragraph_title, text | [PMC4413546_00014.json](examples/outputs/PMC4413546_00014.json) |
| ![PMC5942346_00002](examples/outputs/PMC5942346_00002_annotated.jpg) | 25 | figure_title, footer, header, image, number, paragraph_title, table, text, vision_footnote | [PMC5942346_00002.json](examples/outputs/PMC5942346_00002.json) |

Source page images and their provenance are in `examples/inputs/SOURCE.json`.
Reproduce with:

```bash
python fetch_example_images.py --count 4 --out-dir examples/inputs
python visualize_layout.py --images "examples/inputs/*.jpg" --out-dir examples/outputs --threshold 0.4
```

## Export details

- Traced with `torch.onnx.export`, opset 17 (`GridSample` requires ≥16), dynamic batch axis.
- `disable_custom_kernels=True` — the custom CUDA deformable-attention kernel
  has no ONNX symbolic, so export uses the pure-PyTorch (`grid_sample`) path instead.
- The upstream 2D sin/cos position embedding is computed in float64 upstream;
  ONNX Runtime's CPU EP has no double kernel for `Cos`, so it's patched to
  float32 during tracing (diff ~1e-6, otherwise the exported graph fails to load).
- Verified against the PyTorch reference with a parity check
  (`max|diff| < 1e-3` per output tensor) using the real pretrained weights.
- Export script: `export_pp_doclayout_v3.py` (`torch==2.13.0`, `transformers==5.15.0`).

## Intended use & limitations

- Intended for document layout analysis in document-AI / IDP pipelines
  (reading-order extraction, region cropping, downstream OCR routing).
- Inherits the training data, biases, and limitations of the base
  `PaddlePaddle/PP-DocLayoutV3_safetensors` checkpoint — this repo changes
  only the runtime format, not the weights or decision boundary.
- Fixed 800×800 input: very small text regions or extreme aspect-ratio pages
  may lose detail relative to their original resolution.
- Not evaluated here beyond output-tensor parity with the PyTorch model —
  refer to the base model card for accuracy/benchmark numbers.

## License

Apache 2.0, inherited from the base model. Verify current license terms on
the [base model card](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3_safetensors)
before redistribution.

## Citation

Please cite the original PP-DocLayoutV3 / PaddleOCR work if you use this model:

```
https://huggingface.co/PaddlePaddle/PP-DocLayoutV3_safetensors
```

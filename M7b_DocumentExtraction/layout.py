"""Stufe 1: PDF-Seite -> SeitenBefund mit verorteten, typisierten Blöcken.

Inhaltlich unverändert gegenüber Notebook 1. Geändert ist nur die Fassung:
die ONNX-Sitzung liegt in einer Klasse statt in einem Modulglobal, damit ein
Stapellauf sie einmal öffnet und über hunderte Seiten weiterbenutzt.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import pymupdf

from schema import (
    Bbox, Bezugsrahmen, Block, Lesekante, SeitenBefund, Stufe, PP_LABELS,
)

RENDER_DPI = 200            # Standard für die Layout-Analyse
ZIEL = (800, 800)           # (Breite, Höhe) für cv2.resize
INTERP = cv2.INTER_CUBIC    # entspricht interp: 2 aus der PaddleX-config.json
SKALIERE_AUF_EINS = True    # is_scale; norm_type ist none, keine ImageNet-Statistik
MASKEN_STRIDE = 4           # Maskenkopf hat 800/4 = 200 Kantenlänge


# ------------------------------------------------------------ Bild und Tensor

def seite_rendern(pfad: Path, dpi: int = RENDER_DPI, seite: int = 0,
                  dok: "pymupdf.Document | None" = None):
    """PDF-Seite -> (RGB-Bild als uint8-Array, pymupdf-Seitenobjekt).

    `dok` erlaubt es dem Stapellauf, die Datei einmal zu öffnen statt einmal
    je Seite. Das zurückgegebene Seitenobjekt lebt nur, solange das Dokument
    offen ist – deshalb wird ein selbst geöffnetes hier nicht geschlossen.
    """
    dok = dok or pymupdf.open(pfad)
    pg = dok[seite]
    pix = pg.get_pixmap(dpi=dpi)
    bild = np.frombuffer(pix.samples, dtype=np.uint8)
    bild = bild.reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return np.ascontiguousarray(bild), pg


def vorverarbeiten(bild_rgb: np.ndarray,
                   skaliere_auf_eins: bool = SKALIERE_AUF_EINS) -> np.ndarray:
    """Seitenbild (RGB, HxWx3, uint8) -> Modelltensor NCHW float32.

    Der Export hat genau EINEN Eingang, `pixel_values`. Es gibt kein
    `scale_factor` und kein `im_shape`: die Rücktransformation der Boxen
    passiert bei uns, nicht im Graphen.
    """
    if bild_rgb.ndim != 3 or bild_rgb.shape[2] != 3:
        raise ValueError(f"Erwarte HxWx3, bekommen {bild_rgb.shape}")
    klein = cv2.resize(bild_rgb, ZIEL, interpolation=INTERP)
    tensor = klein.astype(np.float32)
    if skaliere_auf_eins:
        tensor /= 255.0
    tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
    return np.ascontiguousarray(tensor)


# --------------------------------------------------------------- Zeigermatrix

def _sigmoid(x: np.ndarray) -> np.ndarray:
    return (1.0 / (1.0 + np.exp(-x.astype(np.float64)))).astype(np.float32)


def lese_raenge(order_logits: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(Q, Q) Zeigerlogits -> (Rang je Query, sigmoidierte Matrix)."""
    s = _sigmoid(order_logits)
    q = s.shape[0]
    stimmen = np.triu(s, 1).sum(axis=0) + np.tril(1.0 - s.T, -1).sum(axis=0)
    zeiger = np.argsort(stimmen, kind="stable")
    rang = np.empty(q, dtype=np.int64)
    rang[zeiger] = np.arange(q)
    return rang, s


def folgt_auf(s: np.ndarray, a: int, b: int) -> float:
    """Wahrscheinlichkeit, dass Query b auf Query a folgt."""
    return float(s[a, b]) if a < b else float(1.0 - s[b, a])


def marge_fuer(order_logits: np.ndarray, a: int, b: int) -> float:
    """Vorzeichenbehaftete Logit-Marge für 'Query b folgt auf Query a'.

    Dieselbe Aussage wie folgt_auf(), aber vor der Sigmoid. Weil float32
    jenseits von etwa ±17 sättigt, ist nur die Marge als Gütemaß brauchbar.
    """
    return float(order_logits[a, b]) if a < b else float(-order_logits[b, a])


# ------------------------------------------------------------------- Polygone

def _ecken_filtern(polygon: np.ndarray, spitzer_winkel: float = 45.0) -> list[tuple]:
    """Portiert aus `_extract_custom_vertices` der Referenz-Implementierung."""
    poly = np.asarray(polygon, dtype=np.float64)
    n = len(poly)
    res = []
    for i in range(n):
        vorher, hier, danach = poly[(i - 1) % n], poly[i], poly[(i + 1) % n]
        v1, v2 = vorher - hier, danach - hier
        if (v1[1] * v2[0]) - (v1[0] * v2[1]) >= 0:
            continue
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            res.append(tuple(hier))
            continue
        winkel = np.degrees(np.arccos(np.clip((v1 @ v2) / (n1 * n2), -1.0, 1.0)))
        if abs(winkel - spitzer_winkel) < 1:
            richtung = v1 / n1 + v2 / n2
            richtung = richtung / np.linalg.norm(richtung)
            res.append(tuple(hier + richtung * ((n1 + n2) / 2)))
        else:
            res.append(tuple(hier))
    return res


def _maske_zu_polygon(maske: np.ndarray, epsilon_anteil: float = 0.004):
    konturen, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not konturen:
        return None
    kontur = max(konturen, key=cv2.contourArea)
    eps = epsilon_anteil * cv2.arcLength(kontur, True)
    punkte = np.atleast_2d(cv2.approxPolyDP(kontur, eps, True).squeeze())
    if punkte.ndim != 2 or len(punkte) < 4:
        return None
    gefiltert = _ecken_filtern(punkte)
    return gefiltert if len(gefiltert) >= 4 else None


def polygone_ziehen(boxen: np.ndarray, masken: np.ndarray,
                    bild_breite: int, bild_hoehe: int) -> list:
    """Instanzmasken -> Polygone in Bildpixeln. Fällt auf das Rechteck zurück."""
    sx = (800 / bild_breite) / MASKEN_STRIDE
    sy = (800 / bild_hoehe) / MASKEN_STRIDE
    mh, mw = masken.shape[1:]
    ergebnis = []

    for i in range(len(boxen)):
        x0, y0, x1, y1 = boxen[i].astype(np.int32)
        bw, bh = int(x1 - x0), int(y1 - y0)
        rechteck = [(float(x0), float(y0)), (float(x1), float(y0)),
                    (float(x1), float(y1)), (float(x0), float(y1))]
        if bw <= 0 or bh <= 0:
            ergebnis.append(rechteck)
            continue

        xa, xe = np.clip([int(round(x0 * sx)), int(round(x1 * sx))], 0, mw)
        ya, ye = np.clip([int(round(y0 * sy)), int(round(y1 * sy))], 0, mh)
        ausschnitt = masken[i, ya:ye, xa:xe]
        if ausschnitt.size == 0 or ausschnitt.sum() == 0:
            ergebnis.append(rechteck)
            continue

        gross = cv2.resize(ausschnitt.astype(np.uint8), (bw, bh),
                           interpolation=cv2.INTER_NEAREST)
        poly = _maske_zu_polygon(gross)
        ergebnis.append(rechteck if poly is None
                        else [(float(px + x0), float(py + y0)) for px, py in poly])
    return ergebnis


# ----------------------------------------------------------------- Dekodieren

def dekodieren(ausgaben: dict[str, np.ndarray], bild_breite: int, bild_hoehe: int,
               schwelle: float = 0.5) -> tuple[list[Block], list[Lesekante]]:
    """Rohtensoren -> Blöcke (nach Lesereihenfolge sortiert) und Lesekanten."""
    logits = ausgaben["logits"][0]                 # (Q, C)
    pred_boxes = ausgaben["pred_boxes"][0]         # (Q, 4) cxcywh normiert
    order_logits = ausgaben["order_logits"][0]     # (Q, Q)
    out_masks = ausgaben.get("out_masks")

    anzahl_queries, anzahl_klassen = logits.shape

    # 1. Auswahl: Top-k über das flache (Query x Klasse)-Gitter, dann Schwelle
    flach = _sigmoid(logits).reshape(-1)
    top = np.argpartition(-flach, anzahl_queries - 1)[:anzahl_queries]
    top = top[np.argsort(-flach[top], kind="stable")]
    scores = flach[top]
    klassen = top % anzahl_klassen
    queries = top // anzahl_klassen

    behalten = scores >= schwelle
    scores, klassen, queries = scores[behalten], klassen[behalten], queries[behalten]

    # 2. Boxen: cxcywh normiert -> xyxy in Bildpixeln
    mitte, groesse = pred_boxes[..., :2], pred_boxes[..., 2:]
    xyxy = np.concatenate([mitte - 0.5 * groesse, mitte + 0.5 * groesse], axis=-1)
    xyxy = xyxy * np.array([bild_breite, bild_hoehe, bild_breite, bild_hoehe],
                           dtype=np.float32)
    boxen = xyxy[queries]

    # 3. Lesereihenfolge
    rang, matrix = lese_raenge(order_logits)
    ordnung = rang[queries]
    sortiert = np.argsort(ordnung, kind="stable")
    scores, klassen, queries = scores[sortiert], klassen[sortiert], queries[sortiert]
    boxen, ordnung = boxen[sortiert], ordnung[sortiert]

    # 4. Polygone
    if out_masks is not None and len(boxen):
        masken = (_sigmoid(out_masks[0][queries]) > schwelle).astype(np.uint8)
        polygone = polygone_ziehen(boxen, masken, bild_breite, bild_hoehe)
    else:
        polygone = [None] * len(boxen)

    bloecke = [
        Block(
            id=i,
            query_id=int(queries[i]),
            pp_label=PP_LABELS[int(klassen[i])],
            score=float(scores[i]),
            lese_index=int(ordnung[i]),
            bbox=Bbox(x0=float(boxen[i][0]), y0=float(boxen[i][1]),
                      x1=float(boxen[i][2]), y1=float(boxen[i][3]),
                      rahmen=Bezugsrahmen.BILD_PIXEL),
            polygon=polygone[i],
        )
        for i in range(len(boxen))
    ]

    # Trägt dieselbe Query zwei Labels, gibt es keinen Übergang zwischen ihnen –
    # diese Paare werden übersprungen, statt eine bedeutungslose Zahl zu erzeugen.
    kanten = [
        Lesekante(von=i, nach=i + 1,
                  konfidenz=folgt_auf(matrix, int(queries[i]), int(queries[i + 1])),
                  marge=marge_fuer(order_logits, int(queries[i]), int(queries[i + 1])))
        for i in range(len(bloecke) - 1)
        if int(queries[i]) != int(queries[i + 1])
    ]
    return bloecke, kanten


# -------------------------------------------------------------------- Sitzung

def provider_kette(nur_cpu: bool = True) -> list[str]:
    """Nur real verfügbare Provider anfordern – sonst wirft ORT auf dem Mac."""
    if nur_cpu:
        return ["CPUExecutionProvider"]
    verfuegbar = set(ort.get_available_providers())
    wunsch = ["CUDAExecutionProvider", "CoreMLExecutionProvider", "CPUExecutionProvider"]
    return [p for p in wunsch if p in verfuegbar] or ["CPUExecutionProvider"]


class Detektor:
    """Gekapselte ONNX-Sitzung. Einmal öffnen, beliebig oft aufrufen.

    Der Selbsttest im Konstruktor ist Absicht: ein Export mit eingebackenem
    Postprocess liefert einen einzelnen (300, 7)-Tensor und scheitert sonst
    erst mitten im Stapellauf, mit einem KeyError auf `order_logits`.
    """

    def __init__(self, onnx_datei: Path, nur_cpu: bool = True,
                 threads: int | None = None):
        self.datei = Path(onnx_datei)
        opt = ort.SessionOptions()
        opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if threads:
            opt.intra_op_num_threads = threads
        self.sitzung = ort.InferenceSession(
            str(self.datei), sess_options=opt, providers=provider_kette(nur_cpu))

        self.eingang = self.sitzung.get_inputs()[0].name
        self.ausgaenge = [a.name for a in self.sitzung.get_outputs()]

        fehlend = [k for k in ("logits", "pred_boxes", "order_logits")
                   if k not in self.ausgaenge]
        if fehlend:
            raise RuntimeError(
                f"Export unvollständig, es fehlen: {fehlend}. Gebraucht werden die "
                "Rohköpfe (phungpx/PP-DocLayoutV3-ONNX). Exporte mit eingebackenem "
                "Postprocess liefern stattdessen einen einzelnen (300, 7)-Tensor.")
        self.hat_masken = "out_masks" in self.ausgaenge

    @property
    def modellname(self) -> str:
        return self.datei.name

    def signatur_zeigen(self) -> None:
        print("Provider:", self.sitzung.get_providers())
        print("\nEingänge:")
        for e in self.sitzung.get_inputs():
            print(f"  {e.name:16s} {e.type:22s} {e.shape}")
        print("Ausgänge:")
        for a in self.sitzung.get_outputs():
            print(f"  {a.name:16s} {a.type:22s} {a.shape}")
        print("\nAlle vier Köpfe vorhanden." if self.hat_masken
              else "\n! 'out_masks' fehlt – Polygone fallen auf die Bounding Box zurück.")

    def erkenne(self, pfad: Path, seite: int = 0, dpi: int = RENDER_DPI,
                schwelle: float = 0.5,
                dok: "pymupdf.Document | None" = None) -> SeitenBefund:
        """Eine Seite. Die Laufspur wird gleich mit eingetragen."""
        t0 = time.perf_counter()
        bild, pg = seite_rendern(pfad, dpi, seite, dok=dok)
        h, b = bild.shape[:2]
        roh = self.sitzung.run(None, {self.eingang: vorverarbeiten(bild)})
        bloecke, kanten = dekodieren(dict(zip(self.ausgaenge, roh)), b, h, schwelle)

        warnungen = []
        if not bloecke:
            warnungen.append(f"Keine Detektion über der Schwelle {schwelle}.")
        if not self.hat_masken:
            warnungen.append("Export ohne Maskenkopf – Polygone sind Rechtecke.")

        befund = SeitenBefund(
            quelle_datei=Path(pfad).name, seite=seite,
            seite_breite_pt=pg.rect.width, seite_hoehe_pt=pg.rect.height,
            render_dpi=dpi, bild_breite_px=b, bild_hoehe_px=h,
            bloecke=bloecke, kanten=kanten, warnungen=warnungen,
            stufe=Stufe.LAYOUT)
        befund.spur_hinzufuegen(Stufe.LAYOUT, self.modellname,
                                time.perf_counter() - t0)
        return befund

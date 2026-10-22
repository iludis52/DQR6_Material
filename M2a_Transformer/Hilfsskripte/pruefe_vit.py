"""Prüft das ViT-Lehrnotebook; optional kompletter verkürzter Lauf mit echten Daten.

    .venv/Scripts/python.exe Hilfsskripte/pruefe_vit.py
    .venv/Scripts/python.exe Hilfsskripte/pruefe_vit.py --mit-daten

Kein Download. --mit-daten benötigt lokal bereitgestelltes Fashion-MNIST.
Der Durchlauf verwendet 100 Trainingsbilder und ein kleineres Modell; er belegt
die Ausführbarkeit, nicht die Genauigkeit des regulären Trainings. Alle erzeugten
Checkpoints und Diagramme liegen in einem vorübergehenden Prüfverzeichnis.
Mit --vorschau bleiben die Diagramme zusätzlich unter vit-pruefvorschau erhalten.
"""

import argparse
import ast
import copy
import json
import os
import sys
from pathlib import Path
import tempfile

os.environ.setdefault("MPLBACKEND", "Agg")

import nbformat
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main(mit_daten=False, vorschau=False):
    os.chdir(ROOT)
    torch.set_num_threads(2)
    nb = nbformat.read(ROOT / "fashion_vit_lehrnotebook.ipynb", as_version=4)
    nbformat.validate(nb)
    codes = {}
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        assert i > 0 and nb.cells[i - 1].cell_type == "markdown", cell.id
        assert not cell.outputs and cell.execution_count is None
        if not cell.source.startswith("%"):
            ast.parse(cell.source)
            codes[cell.id] = cell.source
    print("Notebookformat, Python-Syntax und Erklärung vor jeder Codezelle: OK")
    ns = {}

    def run(ident):
        exec(compile(codes[ident], f"Notebook:{ident}", "exec"), ns)

    for ident in ("umgebung", "konfiguration", "patches", "embedding", "position",
                  "attention", "ffn", "block", "modell"):
        # Die Patchzelle enthält nach der Definition einen Batch zur Beobachtung.
        if ident == "patches":
            ns["x_probe"] = torch.randn(10, 1, 28, 28)
        run(ident)
    Config = ns["ViTConfig"]
    cfg = Config(d_model=32, n_heads=4, n_layers=2, ffn_hidden=64, dropout=0.0)
    model = ns["VisionTransformer"](cfg)
    standard = ns["VisionTransformer"](ns["konfig"]).eval()
    with torch.no_grad():
        assert standard(torch.zeros(2, 1, 28, 28))[0].shape == (2, 10)
    print(f"Standardarchitektur: {sum(p.numel() for p in standard.parameters()):,} Parameter; Vorwärtslauf OK")

    # Rekonstruktion mit unabhängigem Slicing prüft beide räumlichen Achsen.
    pixels = torch.arange(2 * 3 * 28 * 28).reshape(2, 3, 28, 28)
    actual = ns["zerlege_patches"](pixels, 4)
    expected = torch.stack([pixels[:, :, r:r + 4, c:c + 4].reshape(2, -1)
                            for r in range(0, 28, 4) for c in range(0, 28, 4)], dim=1)
    torch.testing.assert_close(actual, expected)
    for kwargs in ({"patch_size": 5}, {"n_heads": 3}, {"dropout": 1.0}, {"d_model": 0}):
        try:
            Config(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Ungültige Konfiguration akzeptiert: {kwargs}")
    try:
        model(torch.zeros(2, 1, 32, 32))
    except ValueError:
        pass
    else:
        raise AssertionError("Falsche Auflösung akzeptiert")
    print("Patchreihenfolge einschließlich Farbkanälen und Eingabeprüfungen: OK")

    # Unabhängige Bibliotheksrechnung gegen explizite Q/K/V-Attention.
    attn = ns["Attention"](cfg).eval()
    x = torch.randn(2, 7, cfg.d_model)
    actual, weights = attn(x, return_attn=True)
    q, k, v = attn.qkv(x).reshape(2, 7, 3, 4, 8).permute(2, 0, 3, 1, 4)
    reference = F.scaled_dot_product_attention(q, k, v, dropout_p=0, is_causal=False)
    reference = attn.out(reference.transpose(1, 2).reshape(2, 7, 32))
    torch.testing.assert_close(actual, reference, atol=2e-7, rtol=2e-5)
    torch.testing.assert_close(weights.sum(-1), torch.ones(2, 4, 7))
    assert torch.all(weights[:, :, 0, -1] > 0)
    modified = x.clone()
    modified[:, -1] += torch.randn(32)
    assert not torch.allclose(attn(x)[:, 0], attn(modified)[:, 0])

    block = ns["Block"](cfg).eval()
    expected = x + block.attn(block.norm1(x))
    expected = expected + block.ffn(block.norm2(expected))
    torch.testing.assert_close(block(x), expected)
    # Bei verschwindenden Teilnetzbeiträgen ist der gesamte Block die Identität.
    with torch.no_grad():
        block.attn.out.weight.zero_()
        block.attn.out.bias.zero_()
        block.ffn.runter.weight.zero_()
        block.ffn.runter.bias.zero_()
    torch.testing.assert_close(block(x), x)
    print("Attention gegen PyTorch-Referenz, globale Sichtbarkeit und Residualpfade: OK")

    bilder = torch.randn(6, 1, 28, 28, requires_grad=True)
    ziele = torch.tensor([0, 1, 2, 3, 4, 5])
    model.eval()
    logits, loss = model(bilder, ziele)
    assert logits.shape == (6, 10)
    assert model(bilder)[1] is None
    loss.backward()
    for name, parameter in model.named_parameters():
        assert parameter.grad is not None and torch.isfinite(parameter.grad).all(), name
    for name in ("eingang.cls_token", "eingang.pos_emb", "eingang.patch_emb.proj.weight",
                 "blocks.0.attn.qkv.weight", "blocks.0.ffn.hoch.weight"):
        assert model.get_parameter(name).grad.abs().sum() > 0, name
    assert torch.all(bilder.grad.abs().sum(dim=1) > 0)
    before = loss.item()
    optim = torch.optim.SGD(model.parameters(), lr=0.005)
    optim.step()
    assert model(bilder, ziele)[1].item() < before
    print("Gradienten bis zu Patchpixeln, CLS und Positionen; verlustsenkendes Update: OK")

    # Kein Positionssignal: CLS-Ausgang invariant gegen Permutation ganzer Patches.
    invariant = copy.deepcopy(model).eval()
    with torch.no_grad():
        invariant.eingang.pos_emb.zero_()
        p = ns["zerlege_patches"](bilder.detach(), 4)
        permutation = torch.randperm(49)
        permuted = p[:, permutation].reshape(6, 7, 7, 1, 4, 4)
        permuted = permuted.permute(0, 3, 1, 4, 2, 5).reshape(6, 1, 28, 28)
        torch.testing.assert_close(invariant(bilder)[0], invariant(permuted)[0],
                                   atol=2e-6, rtol=2e-5)
    print("Permutationsexperiment ohne Positions-Embeddings: OK")

    run("bewerten")
    loader = DataLoader(TensorDataset(bilder.detach(), ziele), batch_size=4)
    model.train()
    state = copy.deepcopy(model.state_dict())
    value, accuracy = ns["bewerte"](model, loader)
    assert model.training
    model.eval()
    with torch.no_grad():
        expected_logits, expected_loss = model(bilder, ziele)
    assert abs(value - expected_loss.item()) < 1e-6
    assert abs(accuracy - (expected_logits.argmax(-1) == ziele).float().mean().item()) < 1e-6
    for key in state:
        torch.testing.assert_close(state[key], model.state_dict()[key])
    print("Bildgewichtete Auswertung, Moduswiederherstellung und unveränderte Gewichte: OK")

    if mit_daten:
        from torchvision.datasets import FashionMNIST
        from torch.utils.data import Subset
        import matplotlib.pyplot as plt

        # Originaldaten bleiben im Projekt; erzeugte Dateien nur im Testordner.
        with tempfile.TemporaryDirectory(prefix=".vit-pruefung-", dir=ROOT) as tmp:
            work = Path(tmp)
            (work / "Checkpoints").mkdir()
            ns.update(WORK=work, HERUNTERLADEN=False, DEVICE="cpu", konfig=cfg)
            data_code = codes["daten"].replace('root=WORK / "Data"', 'root=DATEN_ROOT')
            ns["DATEN_ROOT"] = ROOT / "Data"
            exec(compile(data_code, "Notebook:daten", "exec"), ns)
            run("split")
            train_ids, val_ids = ns["train_ids"], ns["val_ids"]
            assert len(train_ids) == 55000 and len(val_ids) == 5000
            for ids, count in ((train_ids, 5500), (val_ids, 500)):
                assert torch.bincount(ns["datenpool"].targets[ids]).tolist() == [count] * 10
            # Je Klasse zehn echte Trainings- und fünf Validierungsbilder.
            ns["train_ids"] = [train_ids[k * 5500 + j] for k in range(10) for j in range(10)]
            ns["val_ids"] = [val_ids[k * 500 + j] for k in range(10) for j in range(5)]
            ns["train_daten"] = Subset(ns["datenpool"], ns["train_ids"])
            ns["val_daten"] = Subset(ns["datenpool"], ns["val_ids"])
            ns["BATCH_SIZE"] = 32
            ns["train_loader"], ns["val_loader"] = ns["baue_loader"](
                ns["train_daten"], ns["val_daten"], 32)

            def save_plot():
                number = len(list(work.glob("abbildung-*.png")))
                plt.savefig(work / f"abbildung-{number:02d}.png", dpi=100)
                plt.close("all")

            plt.show = save_plot
            for ident in ("bilder", "patches", "patchbild", "vorwaerts", "sichtbarkeit", "trainwerte"):
                run(ident)
            # Gleicher Trainingscode mit genau acht Updates für den Funktionstest.
            ns.update(EPOCHEN=2, MAX_STEPS=8, WARMUP_STEPS=4)
            assert ns["lernrate"](0) < ns["lernrate"](3)
            assert abs(ns["lernrate"](7) - ns["MIN_LR"]) < 1e-12
            run("training")
            run("kurven")
            run("laden")
            check_path = ns["CHECKPOINT_PFAD"]
            expected = ns["bestes_modell"](ns["x_probe"])[0].detach()
            restored, ckpt = ns["lade_checkpoint"](check_path, "cpu")
            torch.testing.assert_close(expected, restored(ns["x_probe"])[0])
            assert ckpt["train_ids"] == ns["train_ids"]
            # Der komplette offizielle Testsatz wird nur für Ausführbarkeit verwendet.
            test_code = codes["test"].replace('root=WORK / "Data"', 'root=DATEN_ROOT')
            exec(compile(test_code, "Notebook:test", "exec"), ns)
            for ident in ("inferenz", "vorhersagen", "konfusion", "attentionbild"):
                run(ident)
            assert ns["matrix"].sum().item() == 10000
            assert abs(ns["matrix"].diag().sum().item() / 10000 - ns["test_quote"]) < 1e-12
            torch.testing.assert_close(ns["verteilungen"].sum(-1), torch.ones(12))
            # Falsche Pixelumrechnung muss vor der Inferenz zurückgewiesen werden.
            ckpt["vorverarbeitung"]["mittel"] = 0.1
            torch.save(ckpt, work / "falsch.pt")
            try:
                ns["lade_checkpoint"](work / "falsch.pt", "cpu")
            except ValueError:
                pass
            else:
                raise AssertionError("Falsche Vorverarbeitung akzeptiert")
            assert len(list(work.glob("abbildung-*.png"))) == 7
            # Optionale Kopie zur visuellen Prüfung bleibt außerhalb der Checkpoints.
            if vorschau:
                preview = ROOT / "Hilfsskripte" / "vit-pruefvorschau"
                preview.mkdir(exist_ok=True)
                import shutil
                for path in work.glob("abbildung-*.png"):
                    shutil.copy2(path, preview / path.name)
        print("Echte Fashion-MNIST-Daten: alle Ausführungszellen, Split, acht Updates,")
        print("Checkpoint-Roundtrip, 10.000 Testbilder und sieben Diagramme: OK")
        print("Der verkürzte Lauf belegt keine Qualität des regulären Modells.")
    print("ViT-Prüfung erfolgreich.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mit-daten", action="store_true")
    parser.add_argument("--vorschau", action="store_true", help="Prüfdiagramme zur Sichtprüfung behalten")
    args = parser.parse_args()
    main(args.mit_daten, args.vorschau)

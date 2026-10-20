"""Lokale Funktionsprüfung ohne Datendownload oder vollständiges Modelltraining.

Aufruf mit den installierten Trainings-/Exportpaketen: python pruefe_notebooks.py
Testdateien entstehen ausschließlich in einem temporären Projektunterordner.
"""

import ast
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import nbformat
import torch

ROOT = Path(__file__).resolve().parent


def notebook(name):
    path = ROOT / name
    data = nbformat.read(path, as_version=4)
    nbformat.validate(data)
    for cell in data.cells:
        if cell.cell_type == "code" and not cell.source.startswith("%"):
            ast.parse(cell.source)
    return {cell.id: cell.source for cell in data.cells}


def run(cells, ident, namespace):
    exec(compile(cells[ident], ident, "exec"), namespace)


def fails(kind, function, message):
    try:
        function()
    except kind as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError(f"Erwarteter Fehler fehlt: {kind.__name__}")


def main():
    os.chdir(ROOT)
    torch.set_num_threads(2)
    train = notebook("guppylm_lehrnotebook.ipynb")
    export = notebook("guppylm_export_lmstudio.ipynb")
    print("Notebookformat und Python-Syntax: OK")

    with tempfile.TemporaryDirectory(prefix=".guppy-pruefung-", dir=ROOT) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(ROOT) and work != ROOT
        (work / "data").mkdir()
        (work / "checkpoints").mkdir()
        ns = {}
        run(train, "code03", ns)
        run(train, "code05", ns)
        assert len(ns["texte"]["train"]) == 57000
        assert len(ns["texte"]["test"]) == 3000
        missing = {"WORK": work}
        fails(FileNotFoundError, lambda: run(train, "code05", missing), "train.jsonl")
        ns["WORK"] = work
        run(train, "code09", ns)
        run(train, "code13", ns)
        print(f"Lokale Daten, vollständiger Tokenizer und UTF-8-Rückübersetzung: OK (V={ns['konfig'].vocab_size})")

        run(train, "code15", ns)
        fails(ValueError, lambda: ns["zu_sequenzen"]([ns["texte"]["train"][0]], 1),
              "nichts still abgeschnitten")
        Config = ns["GuppyConfig"]
        fails(ValueError, lambda: Config(d_model=32, n_heads=3), "teilbar")
        # Kleines Modell für Funktionsprüfungen, identischer Rechengraph.
        ns["konfig"] = Config(vocab_size=ns["tokenizer"].get_vocab_size(),
                              d_model=32, n_heads=4, n_layers=2, ffn_hidden=128)
        run(train, "code21", ns)
        run(train, "code25", ns)
        # Die Blockzelle enthält auch eine Demo mit vorherigen Probevariablen.
        tree = ast.parse(train["code27"])
        block = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        exec(compile(ast.Module(body=[block], type_ignores=[]), "Block", "exec"), ns)
        run(train, "code29", ns)
        model = ns["GuppyLM"](ns["konfig"]).eval()
        x, y = ns["baue_batch"](ns["train_seq"], [0, 1, 2])
        logits, loss = model(x, y)
        assert logits.shape == (*x.shape, ns["konfig"].vocab_size)
        assert torch.isfinite(loss)
        # Änderungen nach p dürfen frühere Logits nicht verändern.
        a = x[:1, :8].clone()
        b = a.clone()
        b[:, 5:] = (b[:, 5:] + 1) % ns["konfig"].vocab_size
        with torch.no_grad():
            torch.testing.assert_close(model(a)[0][:, :5], model(b)[0][:, :5])
            # Rechtes Padding beeinflusst gültige Positionen nicht.
            padded = torch.cat([a, torch.zeros((1, 3), dtype=torch.long)], dim=1)
            torch.testing.assert_close(model(a)[0], model(padded)[0][:, :8])
        print("Forward, Kausalität, rechtes Padding und Konfigurationsgrenzen: OK")

        ns.update(DEVICE="cpu", MAX_STEPS=3)
        import matplotlib.pyplot as plt
        ns["plt"] = plt
        run(train, "code35", ns)
        ns.update(EVAL_ALLE=1, EVAL_BEISPIELE=5, BATCH_SIZE=2, WARMUP=1)
        run(train, "code-eval-preparation", ns)
        run(train, "code-evaluation", ns)
        run(train, "code36", ns)
        assert len(ns["verlaufsverlust"]) == 3
        assert all(torch.isfinite(torch.tensor(ns["verlaufsverlust"])))
        run(train, "code38", ns)
        run(train, "code-best-checkpoint", ns)
        net, tok, checkpoint = ns["lade_checkpoint"](work / "checkpoints" / "bestes_modell.pt", "cpu")
        assert tok.to_str() == ns["tokenizer"].to_str()
        # Eine geänderte separate Datei darf das gespeicherte Paar nicht verändern.
        (work / "data" / "tokenizer.json").write_text("{}", encoding="utf-8")
        assert ns["lade_checkpoint"](work / "checkpoints" / "bestes_modell.pt", "cpu")[1].to_str() == tok.to_str()
        corrupt = dict(checkpoint, tokenizer_sha256="falsch")
        torch.save(corrupt, work / "checkpoints" / "defekt.pt")
        fails(ValueError, lambda: ns["lade_checkpoint"](work / "checkpoints" / "defekt.pt", "cpu"), "Prüfsumme")
        torch.save({"konfig": checkpoint["konfig"]}, work / "checkpoints" / "alt.pt")
        fails(ValueError, lambda: ns["lade_checkpoint"](work / "checkpoints" / "alt.pt", "cpu"), "Alter Checkpoint")
        # Validierung gewichtet nach Tokens und erhält den Modellmodus.
        net.eval()
        ns["bewerte"](net)
        assert not net.training
        total, count = 0.0, 0
        with torch.no_grad():
            for bx, by in ns["eval_batches"]:
                total += torch.nn.functional.cross_entropy(net(bx)[0].reshape(-1, net.konfig.vocab_size),
                                                           by.reshape(-1), ignore_index=net.konfig.pad_id,
                                                           reduction="sum").item()
                count += (by != net.konfig.pad_id).sum().item()
        assert abs(ns["bewerte"](net) - total / count) < 1e-5
        print("Drei Trainingsschritte, Validierung, Checkpointbindung und Fehlerfälle: OK")

        run(train, "code40", ns)
        ids = ns["tokenizer"].encode("hello").ids
        generate = ns["erzeuge"]
        assert generate(net, ids, max_neu=3, temperatur=0) == generate(net, ids, max_neu=3, temperatur=0)
        for temperature in [0.1, 0.7, 1.5]:
            generate(net, ids, max_neu=2, temperatur=temperature, top_k=0)
        fails(ValueError, lambda: generate(net, ids, temperatur=-1), "Temperatur")
        fails(ValueError, lambda: generate(net, ids, temperatur=float("nan")), "Temperatur")
        fails(ValueError, lambda: generate(net, ids * 129), "Prompt")
        context_ids = [3] * net.konfig.max_seq_len
        result, reason = generate(net, context_ids, return_info=True)
        assert result == context_ids and reason == "Kontextgrenze"
        assert generate(net, ids, max_neu=0, return_info=True)[1] == "Tokenlimit"
        # Endtoken unabhängig von zufälligen Modellgewichten prüfen.
        class EndModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(1))
                self.konfig = net.konfig

            def forward(self, idx):
                values = torch.zeros((*idx.shape, self.konfig.vocab_size))
                values[..., self.konfig.eos_id] = 10
                return values, None

        result, reason = generate(EndModel(), ids, temperatur=0, return_info=True)
        assert reason == "Endtoken" and len(result) == len(ids) + 1
        print("Greedy, Sampling, Temperaturprüfung und alle drei Abbruchgründe: OK")

        # Den echten Export bis zum HF-Format ohne llama.cpp ausführen.
        ens = {"torch": torch, "checkpoint_pfad": work / "checkpoints" / "bestes_modell.pt",
               "WORK": work, "EXPORT": work / "hf_export", "Path": Path}
        from dataclasses import dataclass
        ens["dataclass"] = dataclass
        run(export, "code05", ens)
        run(export, "code06", ens)
        run(export, "code08", ens)
        run(export, "code10", ens)
        assert ens["abweichung"] < 1e-4
        import shutil
        ens.update(shutil=shutil, json=json)
        assert ens["EXPORT"].resolve() == work / "hf_export"
        run(export, "code12", ens)
        print("HF-Gewichtsabbildung, gespeicherter Tokenizer und Chatvorlage: OK")

        # Fehlerpfade der GGUF-Konvertierung ohne externen Prozess prüfen.
        import re
        import subprocess
        import sys
        base = dict(ens, os=os, re=re, subprocess=subprocess, sys=sys,
                    LLAMA_CPP=work / "llama.cpp", GGUF_DATEI=work / "probe.gguf")
        with patch.object(subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="anderer Fehler")):
            fails(RuntimeError, lambda: run(export, "code14", base), "anderer Fehler")
        with patch.object(subprocess, "run", return_value=SimpleNamespace(
                returncode=1, stdout="chkhsh: " + "a" * 64, stderr="pre-tokenizer was not recognized")):
            run(export, "code14", base)
            assert base["FINGERABDRUCK"] == "a" * 64
            run(export, "code16", base)
            assert not base["PATCH_ERLAUBT"]
        base["FINGERABDRUCK"] = None
        fails(RuntimeError, lambda: run(export, "code16", base), "nicht anwendbar")
        print("Exportfehler werden mit ursprünglicher Ursache abgefangen; Patch standardmäßig aus: OK")
    print("ALLE PRÜFUNGEN BESTANDEN. Kein vollständiges Training und kein GGUF-Lauf ausgeführt.")


if __name__ == "__main__":
    main()

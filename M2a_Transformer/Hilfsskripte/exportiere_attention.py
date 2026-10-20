"""Exportiert Attention-Werte ausgewählter Köpfe des GuppyLM-Lehrnotebooks.

Aufruf (aus dem Projektordner):
    python Hilfsskripte/exportiere_attention.py Checkpoints/bestes_modell.pt
    python Hilfsskripte/exportiere_attention.py --auswahl 1:4,5,6 6:3,4,5

Die Ausgabe ist eine JavaScript-Datei (window.GuppyAttention = {...}). So lädt die
Lernapp sie auch beim direkten Öffnen als lokale HTML-Datei ohne Webserver.
Endet --output auf .json, wird reines JSON geschrieben.

Blöcke und Köpfe werden ab 1 gezählt, wie in den Lernapps. Ohne --auswahl
werden alle Köpfe der Blöcke 1 und 6 exportiert (zum Sichten der Muster).
Benötigt die bereits fürs Notebook installierten Pakete torch und tokenizers.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


PROMPTS = [
    "<|im_start|>user\nhello guppy<|im_end|>\n<|im_start|>assistant\n",
    "<|im_start|>user\nfish fish fish<|im_end|>\n<|im_start|>assistant\n",
]
EPSILON = 1e-5  # nn.LayerNorm ohne eps-Argument im Lehrnotebook.


def runde(tensor):
    """float32 mit 9 signifikanten Stellen: verlustfrei rückübersetzbar, kompakter als repr(double)."""
    if tensor.dim() == 0:
        return float(f"{tensor.item():.9g}")
    return [runde(t) for t in tensor]


def parse_auswahl(eintraege, n_layers, n_heads):
    auswahl = {}
    for eintrag in eintraege:
        try:
            block, koepfe = eintrag.split(":")
            block = int(block)
            koepfe = [int(k) for k in koepfe.split(",")]
        except ValueError:
            raise ValueError(f"Ungültige Auswahl {eintrag!r}; erwartet z. B. 1:1,3,5") from None
        if not 1 <= block <= n_layers or not koepfe or any(not 1 <= k <= n_heads for k in koepfe):
            raise ValueError(f"Auswahl {eintrag!r} liegt außerhalb von {n_layers} Blöcken × {n_heads} Köpfen.")
        if len(set(koepfe)) != len(koepfe):
            raise ValueError(f"Auswahl {eintrag!r} nennt einen Kopf mehrfach.")
        auswahl[block - 1] = [k - 1 for k in koepfe]
    return dict(sorted(auswahl.items()))


def vorwaerts(state, config, ids):
    """Vorwärtslauf wie GuppyLM.forward im Lehrnotebook, Evaluationsmodus (Dropout aus)."""
    import torch
    import torch.nn.functional as F

    d, n_heads = config["d_model"], config["n_heads"]
    head_dim = d // n_heads
    T = len(ids)
    idx = torch.tensor(ids)
    token = state["tok_emb.weight"][idx]
    position = state["pos_emb.weight"][:T]
    x = token + position
    maske = torch.tril(torch.ones(T, T))
    bloecke = []
    for b in range(config["n_layers"]):
        p = f"blocks.{b}."
        eingang = x
        x_hat = F.layer_norm(x, (d,), state[p + "norm1.weight"], state[p + "norm1.bias"], EPSILON)
        qkv = x_hat @ state[p + "attn.qkv.weight"].T + state[p + "attn.qkv.bias"]
        # Gleiche Aufteilung wie qkv.reshape(B, T, 3, n_heads, head_dim) im Notebook.
        q, k, v = qkv.reshape(T, 3, n_heads, head_dim).permute(1, 2, 0, 3)  # je (Köpfe, T, head_dim)
        roh = (q @ k.transpose(-2, -1)) / math.sqrt(head_dim)
        roh = roh.masked_fill(maske == 0, float("-inf"))
        gewichte = F.softmax(roh, dim=-1)
        h = gewichte @ v  # (Köpfe, T, head_dim)
        concat = h.transpose(0, 1).reshape(T, d)
        attention = concat @ state[p + "attn.out.weight"].T + state[p + "attn.out.bias"]
        x = eingang + attention
        z = F.layer_norm(x, (d,), state[p + "norm2.weight"], state[p + "norm2.bias"], EPSILON)
        ffn = F.gelu(z @ state[p + "ffn.hoch.weight"].T + state[p + "ffn.hoch.bias"], approximate="tanh")
        x = x + ffn @ state[p + "ffn.runter.weight"].T + state[p + "ffn.runter.bias"]
        bloecke.append({"x_hat": x_hat, "q": q, "k": k, "v": v, "roh": roh, "gewichte": gewichte, "h": h})
    logits = F.layer_norm(x, (d,), state["norm.weight"], state["norm.bias"], EPSILON) @ state["tok_emb.weight"].T
    return {"token": token, "position": position, "summe": token + position, "bloecke": bloecke, "logits": logits}


def export(checkpoint_path, output_path, auswahl_args, referenz_pfad=None):
    import torch
    from tokenizers import Tokenizer

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    config = checkpoint["konfig"]
    tokenizer_json = checkpoint["tokenizer_json"]
    if hashlib.sha256(tokenizer_json.encode("utf-8")).hexdigest() != checkpoint["tokenizer_sha256"]:
        raise ValueError("Tokenizer-Prüfsumme im Checkpoint stimmt nicht.")
    tokenizer = Tokenizer.from_str(tokenizer_json)
    if tokenizer.get_vocab_size() != config["vocab_size"]:
        raise ValueError("Vokabulargröße passt nicht zum Checkpoint.")
    state = {k: v.detach().cpu() for k, v in checkpoint["model_state_dict"].items()}
    for key, tensor in state.items():
        if tensor.dtype != torch.float32 or not torch.isfinite(tensor).all():
            raise ValueError(f"Ungültiger Datentyp oder Werte bei {key}; erwartet endliches float32.")

    n_layers, n_heads, d = config["n_layers"], config["n_heads"], config["d_model"]
    head_dim = d // n_heads
    auswahl = (parse_auswahl(auswahl_args, n_layers, n_heads) if auswahl_args
               else {0: list(range(n_heads)), n_layers - 1: list(range(n_heads))})

    if referenz_pfad:
        pruefe_referenz(state, config, tokenizer, referenz_pfad)

    gewichte = []
    for b, koepfe in auswahl.items():
        W, bias = state[f"blocks.{b}.attn.qkv.weight"], state[f"blocks.{b}.attn.qkv.bias"]
        for h in koepfe:
            # Zeilen von qkv.weight: [Q aller Köpfe | K aller Köpfe | V aller Köpfe], je Kopf head_dim Zeilen.
            zeilen = {s: slice(i * d + h * head_dim, i * d + (h + 1) * head_dim) for i, s in enumerate("qkv")}
            gewichte.append({"block": b + 1, "kopf": h + 1,
                             **{f"W_{s.upper()}": runde(W[z]) for s, z in zeilen.items()},
                             **{f"b_{s.upper()}": runde(bias[z]) for s, z in zeilen.items()}})

    prompts = []
    with torch.no_grad():
        for text in PROMPTS:
            encoding = tokenizer.encode(text)
            ids = encoding.ids
            if not ids or len(ids) > config["max_seq_len"]:
                raise ValueError(f"Prompt passt nicht in die Kontextlänge: {text!r}")
            lauf = vorwaerts(state, config, ids)
            bloecke = []
            for b, koepfe in auswahl.items():
                spur = lauf["bloecke"][b]
                bloecke.append({"block": b + 1, "x_hat": runde(spur["x_hat"]), "koepfe": [{
                    "kopf": h + 1,
                    "q": runde(spur["q"][h]), "k": runde(spur["k"][h]), "v": runde(spur["v"][h]),
                    # Maskierte Felder als null: JSON kennt kein −∞.
                    "scores": [[None if j > i else float(f"{spur['roh'][h, i, j].item():.9g}")
                                for j in range(len(ids))] for i in range(len(ids))],
                    "gewichte": runde(spur["gewichte"][h]),
                    "h": runde(spur["h"][h]),
                } for h in koepfe]})
            herkunft = None
            if 0 in auswahl:
                herkunft = {"token_embedding": runde(lauf["token"]), "positions_embedding": runde(lauf["position"]),
                            "summe": runde(lauf["summe"]),
                            "norm_gamma": runde(state["blocks.0.norm1.weight"]),
                            "norm_beta": runde(state["blocks.0.norm1.bias"]), "norm_epsilon": EPSILON}
            prompts.append({"text": text, "ids": ids, "tokens": encoding.tokens,
                            "herkunft_block1": herkunft, "bloecke": bloecke})

    with Path(checkpoint_path).open("rb") as source_file:
        checkpoint_checksum = hashlib.file_digest(source_file, "sha256").hexdigest()
    result = {
        "format": "guppylm-attention-v1",
        "source": {"checkpoint": Path(checkpoint_path).name, "checkpoint_sha256": checkpoint_checksum,
                   "step": checkpoint.get("schritt"), "eval_loss": checkpoint.get("eval_verlust"), "mode": "eval"},
        "config": config, "head_dim": head_dim, "tokenizer_sha256": checkpoint["tokenizer_sha256"],
        "auswahl": [{"block": b + 1, "koepfe": [h + 1 for h in k]} for b, k in auswahl.items()],
        "gewichte": gewichte, "prompts": prompts,
    }
    content = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    output_path = Path(output_path)
    if output_path.suffix == ".js":
        content = ("// Erzeugt von Hilfsskripte/exportiere_attention.py. Nicht von Hand bearbeiten.\n"
                   f"window.GuppyAttention = {content};\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return result


def pruefe_referenz(state, config, tokenizer, referenz_pfad):
    """Greedy-Generierung muss die gespeicherte Notebook-Antwort exakt reproduzieren."""
    import torch

    referenz = json.loads(Path(referenz_pfad).read_text(encoding="utf-8"))
    ids = tokenizer.encode(referenz["prompt"]).ids
    erwartet = referenz["token_ids"]
    with torch.no_grad():
        for _ in range(referenz["max_neu"]):
            logits = vorwaerts(state, config, ids)["logits"][-1].clone()
            logits[referenz["unterdrueckte_token_ids"]] = float("-inf")
            ids.append(int(logits.argmax()))
            if ids[-1] == config["eos_id"]:
                break
    antwort = ids[len(tokenizer.encode(referenz["prompt"]).ids):]
    if antwort != erwartet:
        raise ValueError(f"Nachgebauter Vorwärtslauf weicht ab: {antwort} statt {erwartet}.")
    print(f"Referenz geprüft: Greedy-Antwort reproduziert ({tokenizer.decode(antwort, skip_special_tokens=True)!r}).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("checkpoint", type=Path, nargs="?", default=Path("Checkpoints/bestes_modell.pt"))
    parser.add_argument("--output", type=Path, default=Path("Data/attention-daten.js"))
    parser.add_argument("--auswahl", nargs="+", metavar="BLOCK:KÖPFE",
                        help="z. B. 1:1,3,5 6:2,4,6 (ab 1 gezählt); Standard: alle Köpfe der Blöcke 1 und 6")
    parser.add_argument("--referenz", type=Path, default=Path("Hilfsskripte/vergleich_referenz.json"),
                        help="gespeicherte Greedy-Antwort zur Prüfung des Vorwärtslaufs")
    args = parser.parse_args()
    if not args.checkpoint.is_file():
        parser.error(f"Checkpoint fehlt: {args.checkpoint}. Bitte vom Trainingsrechner synchronisieren.")
    referenz = args.referenz if args.referenz.is_file() else None
    if referenz is None:
        print(f"Hinweis: {args.referenz} fehlt; Vorwärtslauf wird nicht gegen eine Referenz geprüft.")
    result = export(args.checkpoint, args.output, args.auswahl, referenz)
    print(f"Exportiert: {args.output} ({args.output.stat().st_size / 1024**2:.1f} MiB)")
    for eintrag in result["auswahl"]:
        print(f"Block {eintrag['block']}: Köpfe {', '.join(map(str, eintrag['koepfe']))}")
    for prompt in result["prompts"]:
        print(f"{len(prompt['ids'])} Tokens: {prompt['tokens']}")


if __name__ == "__main__":
    main()

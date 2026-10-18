"""Exportiert Originalgewichte und Referenzwerte des GuppyLM-Lehrnotebooks.

Aufruf: python exportiere_embeddings.py Checkpoints/bestes_modell.pt
Benötigt die bereits fürs Notebook installierten Pakete torch und tokenizers.
"""
import argparse
import hashlib
import json
from pathlib import Path


EXAMPLES = [
    "hello guppy", "The fish swims in the water.", "fish fish fish",
    "Das kleine Modell lernt Sprache.", "Hello, café! 🐟",
    "<|im_start|>user\nhello guppy<|im_end|>\n<|im_start|>assistant\n",
]


def export_checkpoint(checkpoint_path, output_path):
    import torch
    from tokenizers import Tokenizer

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    config = checkpoint["konfig"]
    tokenizer_json = checkpoint["tokenizer_json"]
    checksum = hashlib.sha256(tokenizer_json.encode("utf-8")).hexdigest()
    if checksum != checkpoint["tokenizer_sha256"]:
        raise ValueError("Tokenizer-Prüfsumme im Checkpoint stimmt nicht.")
    tokenizer = Tokenizer.from_str(tokenizer_json)
    if tokenizer.get_vocab_size() != config["vocab_size"]:
        raise ValueError("Vokabulargröße passt nicht zum Checkpoint.")
    for name, field in [("<pad>", "pad_id"), ("<|im_start|>", "bos_id"), ("<|im_end|>", "eos_id")]:
        if tokenizer.token_to_id(name) != config[field]:
            raise ValueError(f"Sondertoken {name} passt nicht zum Checkpoint.")
    state = checkpoint["model_state_dict"]
    expected = {
        "tok_emb.weight": (config["vocab_size"], config["d_model"]),
        "pos_emb.weight": (config["max_seq_len"], config["d_model"]),
        "blocks.0.norm1.weight": (config["d_model"],),
        "blocks.0.norm1.bias": (config["d_model"],),
    }
    tensors = {}
    for key, shape in expected.items():
        tensor = state[key].detach().cpu()
        # Das Lehrnotebook trainiert und speichert diese Gewichte als float32.
        if tensor.dtype != torch.float32 or tuple(tensor.shape) != shape or not torch.isfinite(tensor).all():
            raise ValueError(f"Ungültige Form, Werte oder Datentyp bei {key}; erwartet float32 {shape}.")
        tensors[key] = tensor
    token = tensors["tok_emb.weight"]
    position = tensors["pos_emb.weight"]
    gamma = tensors["blocks.0.norm1.weight"]
    beta = tensors["blocks.0.norm1.bias"]
    epsilon = 1e-5  # nn.LayerNorm ohne eps-Argument im Lehrnotebook.
    references = []
    with torch.no_grad():
        for text in EXAMPLES:
            ids = tokenizer.encode(text).ids
            if not ids or len(ids) > config["max_seq_len"]:
                continue
            x = token[ids] + position[:len(ids)]
            y = torch.nn.functional.layer_norm(x, (config["d_model"],), gamma, beta, epsilon)
            references.append({"text": text, "ids": ids, "rows": [
                {"position": p, "output": y[p].tolist()} for p in sorted({0, len(ids) - 1})
            ]})
    if not references:
        raise ValueError("Kein Referenzsatz passt in die Kontextlänge.")
    with Path(checkpoint_path).open("rb") as source_file:
        checkpoint_checksum = hashlib.file_digest(source_file, "sha256").hexdigest()
    result = {
        "format": "guppylm-embeddings-v1",
        "source": {"checkpoint": Path(checkpoint_path).name,
                   "checkpoint_sha256": checkpoint_checksum,
                   "step": checkpoint.get("schritt"), "eval_loss": checkpoint.get("eval_verlust"),
                   "norm": "blocks.0.norm1", "mode": "eval"},
        "config": config, "tokenizer_json": tokenizer_json, "tokenizer_sha256": checksum,
        "weights": {"token_embeddings": token.tolist(), "position_embeddings": position.tolist(),
                    "norm_gamma": gamma.tolist(), "norm_beta": beta.tolist(), "norm_epsilon": epsilon},
        "references": references,
    }
    # Zuerst vollständig serialisieren/prüfen; keine halbe Exportdatei bei Datenfehlern.
    content = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path, nargs="?", default=Path("Checkpoints/bestes_modell.pt"))
    parser.add_argument("--output", type=Path, default=Path("Data/embeddings-checkpoint.json"))
    args = parser.parse_args()
    if not args.checkpoint.is_file():
        parser.error(f"Checkpoint fehlt: {args.checkpoint}. Bitte vom Trainingsrechner synchronisieren.")
    result = export_checkpoint(args.checkpoint, args.output)
    c = result["config"]
    print(f"Exportiert: {args.output} ({args.output.stat().st_size / 1024**2:.1f} MiB)")
    print(f"Originalgewichte: {c['vocab_size']} Tokens × {c['d_model']} Dimensionen, "
          f"{c['max_seq_len']} Positionen; erste LayerNorm aus Block 1.")
    print("Tokenizer aus demselben Checkpoint und PyTorch-Referenzberechnungen enthalten.")


if __name__ == "__main__":
    main()

/* ByteLevel-BPE und Eingangsberechnung für das GuppyLM-Lehrnotebook. */
"use strict";
(function (global) {
  const examples = [
    "hello guppy",
    "The fish swims in the water.",
    "fish fish fish",
    "Das kleine Modell lernt Sprache.",
    "Hello, café! 🐟",
    "<|im_start|>user\nhello guppy<|im_end|>\n<|im_start|>assistant\n",
  ];
  function check(condition, message) { if (!condition) throw new Error(message); }
  const byteChars = (() => {
    const bytes = [];
    for (let b = 33; b <= 126; b++) bytes.push(b);
    for (let b = 161; b <= 172; b++) bytes.push(b);
    for (let b = 174; b <= 255; b++) bytes.push(b);
    const codes = bytes.slice();
    for (let b = 0, extra = 0; b < 256; b++) if (!bytes.includes(b)) { bytes.push(b); codes.push(256 + extra++); }
    const result = [];
    bytes.forEach((b, i) => { result[b] = String.fromCodePoint(codes[i]); });
    return result;
  })();
  const inverseBytes = new Map(byteChars.map((ch, b) => [ch, b]));
  const utf8 = new TextEncoder();
  // Unicode White_Space entspricht hier der Regex-Semantik des Rust-Tokenizers.
  const preRegex = /'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\p{White_Space}\p{L}\p{N}]+|\p{White_Space}+(?!\P{White_Space})|\p{White_Space}+/gu;
  const pairKey = (a, b) => `${a}\0${b}`;
  class Tokenizer {
    constructor(data) {
      const m = data?.model, p = data?.pre_tokenizer;
      check(m?.type === "BPE" && p?.type === "ByteLevel" && p.add_prefix_space === false && p.use_regex === true,
        "Erwartet wird der ByteLevel-BPE-Tokenizer aus dem Lehrnotebook (ohne Präfix-Leerzeichen)." );
      check(!data.normalizer && (!data.post_processor || data.post_processor.type === "ByteLevel") && data.decoder?.type === "ByteLevel",
        "Diese Normalisierung oder Vor-/Nachverarbeitung wird nicht unterstützt.");
      check(!data.padding && !data.truncation && !m.dropout && !m.unk_token && !m.continuing_subword_prefix && !m.end_of_word_suffix && !m.byte_fallback && !m.ignore_merges,
        "Der Tokenizer verwendet Optionen außerhalb des GuppyLM-Lehrnotebooks.");
      check(m.vocab && Array.isArray(m.merges), "Vokabular oder Merge-Liste fehlt.");
      this.vocab = new Map(Object.entries(m.vocab));
      this.tokens = Array(this.vocab.size);
      for (const [token, id] of this.vocab) {
        check(Number.isInteger(id) && id >= 0 && id < this.tokens.length && this.tokens[id] === undefined, "Token-IDs müssen eindeutig und lückenlos sein.");
        this.tokens[id] = token;
      }
      check(byteChars.every(ch => this.vocab.has(ch)), "Im Tokenizer fehlen Zeichen des vollständigen Byte-Alphabets.");
      this.special = (data.added_tokens || []).map(t => {
        check(t.special && !t.single_word && !t.lstrip && !t.rstrip && !t.normalized && this.vocab.get(t.content) === t.id,
          "Nicht unterstützte Added-Token-Regel oder abweichende Sondertoken-ID.");
        return t;
      }).sort((a, b) => b.content.length - a.content.length);
      this.specialRegex = this.special.length ? new RegExp(this.special.map(t => t.content.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "gu") : null;
      this.ranks = new Map();
      m.merges.forEach((merge, rank) => {
        const parts = Array.isArray(merge) ? merge : merge.split(" ");
        check(parts.length === 2 && parts.every(t => this.vocab.has(t)) && this.vocab.has(parts.join("")), "Ungültiger BPE-Merge.");
        this.ranks.set(pairKey(...parts), rank);
      });
      this.cache = new Map();
    }
    word(raw) {
      if (this.cache.has(raw)) return this.cache.get(raw);
      const symbols = Array.from(utf8.encode(raw), byte => byteChars[byte]);
      while (symbols.length > 1) {
        let best = Infinity, at = -1;
        for (let i = 0; i < symbols.length - 1; i++) {
          const rank = this.ranks.get(pairKey(symbols[i], symbols[i + 1]));
          if (rank !== undefined && rank < best) { best = rank; at = i; }
        }
        if (at < 0) break;
        symbols.splice(at, 2, symbols[at] + symbols[at + 1]);
      }
      const ids = symbols.map(s => this.vocab.get(s));
      if (this.cache.size > 4096) this.cache.clear();
      this.cache.set(raw, ids);
      return ids;
    }
    encode(text) {
      check(typeof text === "string" && text.length <= 4000, "Bitte höchstens 4.000 Zeichen eingeben.");
      const ids = [];
      const plain = str => { for (const m of str.matchAll(preRegex)) ids.push(...this.word(m[0])); };
      let last = 0;
      if (this.specialRegex) for (const match of text.matchAll(this.specialRegex)) {
        plain(text.slice(last, match.index));
        ids.push(this.vocab.get(match[0]));
        last = match.index + match[0].length;
      }
      plain(text.slice(last));
      return ids;
    }
    decode(ids) {
      let result = "", bytes = [];
      const special = new Set(this.special.map(t => t.id));
      const flush = () => { result += new TextDecoder().decode(Uint8Array.from(bytes)); bytes = []; };
      for (const id of ids) {
        check(this.tokens[id] !== undefined, "Unbekannte Token-ID.");
        if (special.has(id)) { flush(); result += this.tokens[id]; }
        else for (const ch of this.tokens[id]) bytes.push(inverseBytes.get(ch));
      }
      flush();
      return result;
    }
  }
  function stats(values) {
    const mean = values.reduce((s, v) => s + v, 0) / values.length;
    const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
    return { mean, variance };
  }
  function layerNorm(input, gamma, beta, epsilon) {
    const { mean, variance } = stats(input), denominator = Math.sqrt(variance + epsilon);
    const normalized = input.map(x => (x - mean) / denominator);
    return { mean, variance, normalized, output: normalized.map((x, i) => x * gamma[i] + beta[i]) };
  }
  function validateBundle(data) {
    check(data?.format === "guppylm-embeddings-v1", "Keine GuppyLM-Embedding-Exportdatei (Format v1).");
    const { config: cfg, weights: w } = data;
    check(cfg && w && Number.isInteger(cfg.d_model) && cfg.d_model > 0 && cfg.d_model <= 4096 && Number.isInteger(cfg.vocab_size) && cfg.vocab_size > 0 && Number.isInteger(cfg.max_seq_len) && cfg.max_seq_len > 0,
      "Ungültige Modelldimensionen.");
    check(typeof data.tokenizer_json === "string" && /^[a-f0-9]{64}$/.test(data.tokenizer_sha256), "Tokenizer oder seine Prüfsumme fehlt.");
    const tok = new Tokenizer(JSON.parse(data.tokenizer_json));
    check(tok.tokens.length === cfg.vocab_size, "Tokenizer und Embeddingtabelle haben verschiedene Vokabulargrößen.");
    for (const [name, field] of [["<pad>", "pad_id"], ["<|im_start|>", "bos_id"], ["<|im_end|>", "eos_id"]])
      check(tok.vocab.get(name) === cfg[field], `Sondertoken ${name} passt nicht zur Konfiguration.`);
    const vector = v => Array.isArray(v) && v.length === cfg.d_model && v.every(Number.isFinite);
    check(Array.isArray(w.token_embeddings) && w.token_embeddings.length === cfg.vocab_size && w.token_embeddings.every(vector), "Ungültige Token-Embeddingtabelle.");
    check(Array.isArray(w.position_embeddings) && w.position_embeddings.length === cfg.max_seq_len && w.position_embeddings.every(vector), "Ungültige Positions-Embeddingtabelle.");
    check(vector(w.norm_gamma) && vector(w.norm_beta) && Number.isFinite(w.norm_epsilon) && w.norm_epsilon > 0, "Ungültige Parameter der ersten LayerNorm.");
    check(data.references?.length > 0, "Referenzberechnungen aus PyTorch fehlen.");
    for (const ref of data.references) {
      const ids = tok.encode(ref.text);
      check(JSON.stringify(ids) === JSON.stringify(ref.ids), "Die Browser-Tokenisierung weicht von der Python-Referenz ab.");
      check(Array.isArray(ref.rows) && ref.rows.length > 0, "Referenzvektoren fehlen.");
      for (const row of ref.rows) {
        check(Number.isInteger(row.position) && row.position >= 0 && row.position < ids.length && vector(row.output), "Ungültiger Referenzvektor.");
        const x = w.token_embeddings[ids[row.position]].map((v, i) => v + w.position_embeddings[row.position][i]);
        const actual = layerNorm(x, w.norm_gamma, w.norm_beta, w.norm_epsilon).output;
        check(actual.every((v, i) => Math.abs(v - row.output[i]) <= 2e-5 + 2e-5 * Math.abs(row.output[i])), "Die berechnete LayerNorm weicht von der PyTorch-Referenz ab.");
      }
    }
    return tok;
  }
  async function verifyChecksum(data) {
    check(global.crypto?.subtle, "Für die Prüfsumme bitte die Seite lokal über http://localhost öffnen.");
    const hash = await global.crypto.subtle.digest("SHA-256", utf8.encode(data.tokenizer_json));
    const hex = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, "0")).join("");
    check(hex === data.tokenizer_sha256, "Tokenizer-Prüfsumme stimmt nicht. Bitte den Export erneut erzeugen.");
  }
  function forward(bundle, ids) {
    const { weights: w, config: cfg } = bundle;
    check(ids.length > 0, "Bitte Text eingeben.");
    check(ids.length <= cfg.max_seq_len, `${ids.length} Tokens überschreiten die Kontextlänge ${cfg.max_seq_len}. Bitte den Text kürzen; es wird nichts abgeschnitten.`);
    return ids.map((id, position) => {
      check(Number.isInteger(id) && id >= 0 && id < cfg.vocab_size, "Token-ID außerhalb der Embeddingtabelle.");
      const embedding = w.token_embeddings[id], positional = w.position_embeddings[position];
      const sum = embedding.map((v, i) => v + positional[i]);
      return { id, position, embedding, positional, sum, ...layerNorm(sum, w.norm_gamma, w.norm_beta, w.norm_epsilon) };
    });
  }
  const api = { Tokenizer, examples, stats, layerNorm, validateBundle, verifyChecksum, forward };
  global.EmbeddingModell = api;
  if (typeof module !== "undefined") module.exports = api;
})(globalThis);

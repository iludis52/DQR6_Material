/* Aufruf: node pruefe_embeddings.js; vorher den Originalcheckpoint exportieren. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const M = require("./Lernapp/embeddings-modell.js");
const read = file => JSON.parse(fs.readFileSync(path.join(__dirname, file), "utf8"));

async function main() {
  const tokenizer = new M.Tokenizer(read("Data/tokenizer.json"));
  const fixtures = read("Data/embedding-tokenizer-referenzen.json");
  for (const ref of fixtures) {
    assert.deepEqual(tokenizer.encode(ref.text), ref.ids, `Python-Tokenisierung: ${JSON.stringify(ref.text)}`);
    assert.equal(tokenizer.decode(ref.ids), ref.text, "Bytegenaue Rückübersetzung einschließlich Sondertokens");
  }
  console.log(`${fixtures.length} Referenzen aus Python-tokenizers: IDs und Rückübersetzung stimmen überein.`);

  const bundle = read("Data/embeddings-checkpoint.json");
  const originalTokenizer = M.validateBundle(bundle);
  await M.verifyChecksum(bundle);
  let maximumError = 0;
  for (const ref of bundle.references) {
    const rows = M.forward(bundle, originalTokenizer.encode(ref.text));
    for (const sample of ref.rows) for (let d = 0; d < bundle.config.d_model; d++)
      maximumError = Math.max(maximumError, Math.abs(rows[sample.position].output[d] - sample.output[d]));
  }
  assert.ok(maximumError < 2e-5);
  console.log(`Originalcheckpoint: Tokenizer-Prüfsumme, Tabellenformen und trainierte LayerNorm gegen PyTorch geprüft (max. Fehler ${maximumError.toExponential(2)}).`);

  // Derselbe Token inklusive Leerzeichen muss an unterschiedlichen Positionen
  // dasselbe Token-Embedding, aber die jeweils andere Positionszeile erhalten.
  const repeatedIds = originalTokenizer.encode(" fish fish fish");
  assert.equal(repeatedIds.length, 3);
  assert.equal(new Set(repeatedIds).size, 1);
  const repeated = M.forward(bundle, repeatedIds);
  assert.deepEqual(repeated[0].embedding, repeated[1].embedding);
  assert.notDeepEqual(repeated[0].positional, repeated[1].positional);
  assert.notDeepEqual(repeated[0].sum, repeated[1].sum);
  for (const row of repeated) for (let d = 0; d < bundle.config.d_model; d++)
    assert.equal(row.sum[d], row.embedding[d] + row.positional[d]);
  console.log("Gleiche Token-ID → gleiche Embeddingzeile; unterschiedliche Position → andere Positionszeile; komponentenweise Addition: OK.");

  const id = repeatedIds[0];
  assert.equal(M.forward(bundle, Array(bundle.config.max_seq_len).fill(id)).length, bundle.config.max_seq_len);
  assert.throws(() => M.forward(bundle, Array(bundle.config.max_seq_len + 1).fill(id)), /überschreiten/);
  assert.throws(() => M.forward(bundle, []), /Text eingeben/);
  assert.throws(() => M.forward(bundle, [bundle.config.vocab_size]), /Token-ID/);
  assert.throws(() => M.validateBundle({ ...bundle, config: { ...bundle.config, d_model: 6 } }), /Embeddingtabelle/);
  assert.throws(() => M.validateBundle({ ...bundle, weights: { ...bundle.weights, norm_gamma: [1] } }), /LayerNorm/);
  assert.throws(() => M.validateBundle({ ...bundle, weights: { ...bundle.weights, norm_gamma: bundle.weights.norm_gamma.map(v => v + 1) } }), /PyTorch/);
  await assert.rejects(M.verifyChecksum({ ...bundle, tokenizer_sha256: "0".repeat(64) }), /Prüfsumme/);
  const constant = M.layerNorm([2, 2, 2], [1, 1, 1], [0, 0, 0], 1e-5);
  assert.deepEqual(constant.output, [0, 0, 0]);
  console.log("Kontextgrenze ohne Abschneiden, falsche Dimensionen/Normgewichte, beschädigte Tokenizer-Prüfsumme und konstanter Normeingang: OK.");
}
main().catch(error => { console.error(error); process.exitCode = 1; });

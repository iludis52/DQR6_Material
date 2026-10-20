/* Aufruf aus dem Projektordner: node Hilfsskripte/pruefe_attention.js
   Vorher Data/attention-daten.js mit Hilfsskripte/exportiere_attention.py erzeugen. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const wurzel = path.join(__dirname, "..");
const kontext = { window: {} };
vm.createContext(kontext);
for (const datei of ["Data/attention-daten.js", "Lernapp/attention-modell.js"])
  vm.runInContext(fs.readFileSync(path.join(wurzel, datei), "utf8"), kontext, { filename: datei });
const M = kontext.window.AttentionModell;
const daten = kontext.window.GuppyAttention;
const kopie = () => JSON.parse(JSON.stringify(daten));

// 1. Jeder exportierte Wert lässt sich aus x̂ und den exportierten Gewichten nachrechnen.
const { maxAbw, anzahl } = M.pruefe(daten);
console.log(`${anzahl} Werte nachgerechnet (Projektionen, Bewertungen, Softmax, Kopfausgänge, LayerNorm Block 1); max. Abweichung ${maxAbw.toExponential(2)}.`);

// 2. Kausalität und Normierung: Zukunft genau 0, jede Zeile summiert sich zu 1.
for (const p of daten.prompts) for (const b of p.bloecke) for (const k of b.koepfe) k.gewichte.forEach((zeile, i) => {
  zeile.forEach((a, j) => { if (j > i) assert.equal(a, 0, "Gewicht auf spätere Position"); else assert.ok(a >= 0); });
  assert.ok(Math.abs(zeile.reduce((s, a) => s + a, 0) - 1) < 1e-6, "Zeilensumme 1");
});
console.log("Kausale Maske und Zeilennormierung in allen Köpfen erfüllt.");

// 3. Die Query-Ebene ist exakt: Bewertung aus der x-Lage, Keylänge aus x und y.
let ebeneMax = 0;
for (const p of daten.prompts) for (const b of p.bloecke) for (const k of b.koepfe) k.q.forEach((q, i) => {
  const lq = M.norm(q);
  M.queryEbene(q, k.k).forEach((punkt, j) => {
    ebeneMax = Math.max(ebeneMax, Math.abs(punkt.x * lq / Math.sqrt(daten.head_dim) - M.skalarprodukt(q, k.k[j]) / Math.sqrt(daten.head_dim)));
    ebeneMax = Math.max(ebeneMax, Math.abs(Math.hypot(punkt.x, punkt.y) - M.norm(k.k[j])));
  });
});
assert.ok(ebeneMax < 1e-9);
console.log(`Query-Ebene reproduziert Bewertungen und Keylängen exakt (max. Fehler ${ebeneMax.toExponential(2)}).`);

// 4. Embeddings stammen aus demselben Checkpoint wie die Embedding-Werkbank, falls deren Export vorliegt.
const embeddingDatei = path.join(wurzel, "Data/embeddings-checkpoint.json");
if (fs.existsSync(embeddingDatei)) {
  const emb = JSON.parse(fs.readFileSync(embeddingDatei, "utf8"));
  if (emb.source.checkpoint_sha256 === daten.source.checkpoint_sha256) {
    for (const p of daten.prompts) p.ids.forEach((id, t) => {
      p.herkunft_block1.token_embedding[t].forEach((v, d) => assert.ok(Math.abs(v - emb.weights.token_embeddings[id][d]) < 1e-7));
      p.herkunft_block1.positions_embedding[t].forEach((v, d) => assert.ok(Math.abs(v - emb.weights.position_embeddings[t][d]) < 1e-7));
    });
    console.log("Token- und Positions-Embeddings stimmen mit dem Export der Embedding-Werkbank überein.");
  } else console.log("Hinweis: Embedding-Export stammt aus einem anderen Checkpoint; Abgleich übersprungen.");
}

// 5. Veränderte oder unvollständige Daten werden abgewiesen.
const faelle = [
  ["veränderte Query", d => { d.prompts[0].bloecke[0].koepfe[0].q[3][7] += 0.01; }],
  ["veränderte Gewichtsmatrix", d => { d.gewichte[0].W_K[0][0] += 0.01; }],
  ["unmaskierte Zukunft", d => { d.prompts[0].bloecke[0].koepfe[0].scores[0][1] = 0; }],
  ["fehlende Kopfgewichte", d => { d.gewichte.pop(); }],
  ["falsches Format", d => { d.format = "anders"; }],
];
for (const [name, aendere] of faelle) {
  const d = kopie(); aendere(d);
  assert.throws(() => M.pruefe(d), undefined, `nicht erkannt: ${name}`);
}
console.log(`${faelle.length} manipulierte Datensätze werden abgewiesen.`);

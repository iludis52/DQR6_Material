/* Mathematische Funktionsprüfung des Browser-Lehrmodells. Aufruf: node pruefe_transformer.js */
"use strict";
const assert = require("node:assert/strict");
require("./Lernapp/transformer-modell.js");
const { Lehrmodell, vokabular, beispiele, werte, konfig } = globalThis.TransformerModell;

const model = new Lehrmodell();
const sequence = beispiele[0].map(t => vokabular.indexOf(t));
const ids = sequence.slice(0, -1), targets = sequence.slice(1);
const trace = model.forward(ids, targets);
assert.equal(trace.bloecke.length, 2);
assert.equal(trace.embeddings.length, ids.length);
assert.equal(trace.embeddings[0], model.embedding[ids[0]], "Embedding ist dieselbe Parameterzeile");
assert.equal(trace.bloecke[0].heads.length, 3);
assert.equal(trace.bloecke[0].hoch[0].length, 24);
assert.equal(trace.bloecke[1].ausgang[0].length, 6);
assert.equal(trace.bloecke[1].eingang, trace.bloecke[0].ausgang,
  "Block 2 bekommt den vollständigen Ausgang aus Block 1");
assert.equal(trace.logits[0].length, 8);
for (const block of trace.bloecke) {
  assert.equal(block.heads.length, 3);
  for (let t = 0; t < ids.length; t++) {
    assert.equal(block.concat[t].length, 6);
    for (let d = 0; d < 6; d++) {
      assert.equal(block.residual1[t][d].wert, block.eingang[t][d].wert + block.attention[t][d].wert,
        "Erstes Plus: unveränderter Eingang + Attention-Beitrag");
      assert.equal(block.ausgang[t][d].wert, block.residual1[t][d].wert + block.ffn[t][d].wert,
        "Zweites Plus: bisheriger Residualstrom + FFN-Beitrag");
    }
  }
  for (const head of block.heads) {
    for (const [t, row] of werte(head.gewichte).entries()) {
      assert.ok(Math.abs(row.reduce((a, b) => a + b) - 1) < 1e-12);
      for (let j = t + 1; j < row.length; j++) assert.equal(row[j], 0);
    }
  }
}
console.log("Zwei Blöcke mit je drei Köpfen, sechs Dimensionen und korrekte Residualadditionen: OK");
console.log("Softmax und kausale Masken in beiden Blöcken: OK");

const changed = [...ids];
changed[2] = vokabular.indexOf("water");
const changedTrace = model.forward(changed, targets);
for (let t = 0; t < 2; t++) {
  for (let i = 0; i < vokabular.length; i++) {
    assert.ok(Math.abs(trace.logits[t][i].wert - changedTrace.logits[t][i].wert) < 1e-12);
  }
}
const same = new Lehrmodell().forward(ids, targets);
assert.equal(same.verlust.wert, trace.verlust.wert);
console.log("Zukunft beeinflusst frühere Vorhersagen nicht; Initialisierung reproduzierbar: OK");

const initial = model.parameter.map(p => p.wert);
model.backward(trace);
assert.deepEqual(model.parameter.map(p => p.wert), initial, "Backward darf Gewichte nicht ändern");
assert.ok(model.parameter.every(p => Number.isFinite(p.grad)));
const names = ["E[0][0]", "P[0][0]", "B1.W_QKV[0][0]", "B1.W_QKV[4][1]",
  "B1.W_QKV[8][1]", "B1.W_QKV[16][1]", "B2.W_O[1][2]", "B2.W_hoch[4][2]",
  "B2.W_runter[1][4]", "B2.Norm2.γ[2]", "Norm_final.β[1]"];
const epsilon = 1e-5;
for (const name of names) {
  const p = model.parameter.find(p => p.name === name);
  assert.ok(p, name);
  const original = p.wert, analytical = p.grad;
  p.wert = original + epsilon;
  const plus = model.forward(ids, targets).verlust.wert;
  p.wert = original - epsilon;
  const minus = model.forward(ids, targets).verlust.wert;
  p.wert = original;
  const numeric = (plus - minus) / (2 * epsilon);
  assert.ok(Math.abs(numeric - analytical) < 2e-5 * Math.max(1, Math.abs(numeric)),
    `${name}: numerisch ${numeric}, Backprop ${analytical}`);
}
console.log("Backprop gegen numerische Ableitungen geprüft, einschließlich Weight tying und GELU: OK");

model.update(0.03);
const after = model.forward(ids, targets).verlust.wert;
assert.ok(after < trace.verlust.wert);
assert.ok(model.parameter.some((p, i) => p.wert !== initial[i]));
for (const sample of beispiele) {
  const seq = sample.map(t => vokabular.indexOf(t));
  const f = model.forward(seq.slice(0, -1), seq.slice(1));
  assert.ok(Number.isFinite(f.verlust.wert));
}
const long = model.forward(Array(konfig.kontext).fill(0));
assert.equal(long.logits.length, konfig.kontext);
assert.equal(long.verlust, null);
console.log(`Echtes SGD-Update senkt Beispielverlust: ${trace.verlust.wert.toFixed(6)} → ${after.toFixed(6)}`);
console.log("Alle Lehrbeispiele und Generierung bis zur Kontextgrenze: OK");

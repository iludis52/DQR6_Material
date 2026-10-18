/* Kleines Lehrmodell: echter Vorwärtslauf und automatische Differenzierung.
   Ohne Bibliotheken; die Architektur folgt dem Pre-Norm-Decoder im Notebook. */
"use strict";

(function (global) {
  class Zahl {
    constructor(wert, eltern = [], rueckwaerts = () => {}) {
      this.wert = wert;
      this.grad = 0;
      this.eltern = eltern;
      this.rueckwaerts = rueckwaerts;
    }
    add(b) {
      b = zahl(b);
      const c = new Zahl(this.wert + b.wert, [this, b]);
      c.rueckwaerts = () => { this.grad += c.grad; b.grad += c.grad; };
      return c;
    }
    mul(b) {
      b = zahl(b);
      const c = new Zahl(this.wert * b.wert, [this, b]);
      c.rueckwaerts = () => {
        this.grad += b.wert * c.grad;
        b.grad += this.wert * c.grad;
      };
      return c;
    }
    pow(p) {
      const c = new Zahl(this.wert ** p, [this]);
      c.rueckwaerts = () => { this.grad += p * this.wert ** (p - 1) * c.grad; };
      return c;
    }
    exp() {
      const c = new Zahl(Math.exp(this.wert), [this]);
      c.rueckwaerts = () => { this.grad += c.wert * c.grad; };
      return c;
    }
    log() {
      const c = new Zahl(Math.log(this.wert), [this]);
      c.rueckwaerts = () => { this.grad += c.grad / this.wert; };
      return c;
    }
    tanh() {
      const c = new Zahl(Math.tanh(this.wert), [this]);
      c.rueckwaerts = () => { this.grad += (1 - c.wert ** 2) * c.grad; };
      return c;
    }
    backward() {
      const besucht = new Set();
      const folge = [];
      function besuchen(knoten) {
        if (besucht.has(knoten)) return;
        besucht.add(knoten);
        for (const elternteil of knoten.eltern) besuchen(elternteil);
        folge.push(knoten);
      }
      besuchen(this);
      for (const knoten of folge) knoten.grad = 0;
      this.grad = 1;
      for (let i = folge.length - 1; i >= 0; i--) folge[i].rueckwaerts();
    }
  }

  const zahl = a => a instanceof Zahl ? a : new Zahl(a);
  const summe = xs => xs.reduce((s, x) => s.add(x), zahl(0));
  const skalarprodukt = (a, b) => summe(a.map((x, i) => x.mul(b[i])));
  const addiere = (a, b) => a.map((x, i) => x.add(b[i]));
  const werte = x => Array.isArray(x) ? x.map(werte) : x.wert;

  function softmax(logits) {
    const maximum = Math.max(...logits.map(x => x.wert));
    const exponential = logits.map(x => x.add(-maximum).exp());
    const kehrwert = summe(exponential).pow(-1);
    return exponential.map(x => x.mul(kehrwert));
  }

  // Stabiler Log-Softmax statt log(softmax): auch bei sehr kleinen p endlich.
  function kreuzentropie(logits, ziel) {
    const maximum = Math.max(...logits.map(x => x.wert));
    const logsum = summe(logits.map(x => x.add(-maximum).exp())).log().add(maximum);
    return logsum.add(logits[ziel].mul(-1));
  }

  function gelu(x) {
    const innen = x.add(x.pow(3).mul(0.044715)).mul(Math.sqrt(2 / Math.PI));
    return x.mul(0.5).mul(innen.tanh().add(1));
  }

  function linear(x, matrix, bias) {
    return matrix.map((zeile, i) => skalarprodukt(x, zeile).add(bias ? bias[i] : 0));
  }

  function normiere(x, gamma, beta) {
    const mittel = summe(x).mul(1 / x.length);
    const zentriert = x.map(v => v.add(mittel.mul(-1)));
    const varianz = summe(zentriert.map(v => v.pow(2))).mul(1 / x.length);
    const skala = varianz.add(1e-5).pow(-0.5);
    return zentriert.map((v, i) => v.mul(skala).mul(gamma[i]).add(beta[i]));
  }

  const vokabular = ["guppy", "likes", "bubbles", "food", "fish", "water", "hello", "<end>"];
  const beispiele = [
    ["guppy", "likes", "bubbles", "<end>"],
    ["guppy", "likes", "food", "<end>"],
    ["fish", "likes", "water", "<end>"],
    ["hello", "guppy", "<end>"],
  ];
  const konfig = Object.freeze({ breite: 6, koepfe: 3, kopfbreite: 2, ffn: 24, bloecke: 2, kontext: 8 });

  class Lehrmodell {
    constructor(seed = 42) {
      this.parameter = [];
      let zufallsstand = seed;
      const zufall = () => {
        zufallsstand = (Math.imul(1664525, zufallsstand) + 1013904223) >>> 0;
        return zufallsstand / 4294967296;
      };
      const parameter = (name, gruppe, fest) => {
        const p = new Zahl(fest === undefined ? (zufall() - 0.5) * 0.5 : fest);
        p.name = name;
        p.gruppe = gruppe;
        this.parameter.push(p);
        return p;
      };
      const vektor = (n, name, gruppe, fest) => Array.from({ length: n }, (_, i) => parameter(`${name}[${i}]`, gruppe, fest));
      const matrix = (n, m, name, gruppe) => Array.from({ length: n }, (_, i) => vektor(m, `${name}[${i}]`, gruppe));
      const norm = (name, gruppe) => ({
        gamma: vektor(konfig.breite, `${name}.γ`, gruppe, 1),
        beta: vektor(konfig.breite, `${name}.β`, gruppe, 0),
      });
      this.embedding = matrix(vokabular.length, konfig.breite, "E", "Token-Embedding / Ausgabe");
      this.positionen = matrix(konfig.kontext, konfig.breite, "P", "Positions-Embedding");
      this.bloecke = Array.from({ length: konfig.bloecke }, (_, i) => {
        const g = `Block ${i + 1}`;
        const name = `B${i + 1}`;
        return {
          norm1: norm(`${name}.Norm1`, g),
          qkv: matrix(3 * konfig.breite, konfig.breite, `${name}.W_QKV`, g),
          qkvBias: vektor(3 * konfig.breite, `${name}.b_QKV`, g, 0),
          ausgabe: matrix(konfig.breite, konfig.breite, `${name}.W_O`, g),
          ausgabeBias: vektor(konfig.breite, `${name}.b_O`, g, 0),
          norm2: norm(`${name}.Norm2`, g),
          hoch: matrix(konfig.ffn, konfig.breite, `${name}.W_hoch`, g),
          hochBias: vektor(konfig.ffn, `${name}.b_hoch`, g, 0),
          runter: matrix(konfig.breite, konfig.ffn, `${name}.W_runter`, g),
          runterBias: vektor(konfig.breite, `${name}.b_runter`, g, 0),
        };
      });
      this.norm = norm("Norm_final", "Abschlussnormierung");
    }

    forward(ids, ziele) {
      if (!ids.length || ids.length > konfig.kontext) throw new Error("Ungültige Kontextlänge");
      if (ziele && ziele.length !== ids.length) throw new Error("Ziele und Eingaben müssen gleich lang sein");
      const embeddings = ids.map(id => this.embedding[id]);
      const positionen = ids.map((_, t) => this.positionen[t]);
      let x = embeddings.map((v, t) => addiere(v, positionen[t]));
      const start = x;
      const spuren = [];
      for (const block of this.bloecke) {
        const eingang = x;
        const norm1 = x.map(v => normiere(v, block.norm1.gamma, block.norm1.beta));
        const qkv = norm1.map(v => linear(v, block.qkv, block.qkvBias));
        const q = qkv.map(v => v.slice(0, konfig.breite));
        const k = qkv.map(v => v.slice(konfig.breite, 2 * konfig.breite));
        const v = qkv.map(v => v.slice(2 * konfig.breite, 3 * konfig.breite));
        const heads = [];
        for (let h = 0; h < konfig.koepfe; h++) {
          const bereich = a => a.map(row => row.slice(h * konfig.kopfbreite, (h + 1) * konfig.kopfbreite));
          const qh = bereich(q), kh = bereich(k), vh = bereich(v);
          const scores = qh.map(query => kh.map(key => skalarprodukt(query, key).mul(1 / Math.sqrt(konfig.kopfbreite))));
          const gewichte = scores.map((zeile, t) => {
            const gueltig = softmax(zeile.slice(0, t + 1));
            return zeile.map((_, j) => j <= t ? gueltig[j] : zahl(0));
          });
          const ausgang = gewichte.map(zeile => Array.from({ length: konfig.kopfbreite }, (_, d) => summe(zeile.map((a, j) => a.mul(vh[j][d])))));
          heads.push({ q: qh, k: kh, v: vh, scores, gewichte, ausgang });
        }
        const concat = x.map((_, t) => heads.flatMap(head => head.ausgang[t]));
        const attention = concat.map(v => linear(v, block.ausgabe, block.ausgabeBias));
        const residual1 = eingang.map((v, t) => addiere(v, attention[t]));
        const norm2 = residual1.map(v => normiere(v, block.norm2.gamma, block.norm2.beta));
        const hoch = norm2.map(v => linear(v, block.hoch, block.hochBias));
        const aktiviert = hoch.map(v => v.map(gelu));
        const ffn = aktiviert.map(v => linear(v, block.runter, block.runterBias));
        x = residual1.map((v, t) => addiere(v, ffn[t]));
        spuren.push({ eingang, norm1, q, k, v, heads, concat, attention, residual1, norm2, hoch, aktiviert, ffn, ausgang: x });
      }
      const normFinal = x.map(v => normiere(v, this.norm.gamma, this.norm.beta));
      // Weight tying: dieselbe Embeddingmatrix wird für die Ausgabe verwendet.
      const logits = normFinal.map(v => this.embedding.map(zeile => skalarprodukt(v, zeile)));
      const wahrscheinlichkeiten = logits.map(softmax);
      const einzelverluste = ziele ? logits.map((zeile, t) => kreuzentropie(zeile, ziele[t])) : [];
      const verlust = einzelverluste.length ? summe(einzelverluste).mul(1 / einzelverluste.length) : null;
      return { ids, ziele, embeddings, positionen, start, bloecke: spuren, normFinal, logits, wahrscheinlichkeiten, einzelverluste, verlust };
    }

    backward(spur) {
      for (const p of this.parameter) p.grad = 0;
      spur.verlust.backward();
      return this.parameter.map(p => ({ name: p.name, gruppe: p.gruppe, vorher: p.wert, gradient: p.grad }));
    }

    update(lernrate) {
      // SGD zeigt die Grundidee direkt. Im Notebook übernimmt AdamW das Update.
      for (const p of this.parameter) p.wert -= lernrate * p.grad;
    }
  }

  global.TransformerModell = { Zahl, Lehrmodell, vokabular, beispiele, konfig, werte, softmax, kreuzentropie };
})(typeof window !== "undefined" ? window : globalThis);

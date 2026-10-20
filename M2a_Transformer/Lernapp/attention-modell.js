/* Prüfung und Nachrechnung der exportierten GuppyLM-Attentionwerte.
   Keine Ersatzwerte: Fehlt der Export oder passt er nicht, wird nichts angezeigt. */
"use strict";
(function (global) {
  const TOLERANZ = 2e-4; // absolut plus relativ; Export in float32, Nachrechnung in double.

  function check(bedingung, meldung) { if (!bedingung) throw new Error(meldung); }
  const endlich = x => typeof x === "number" && Number.isFinite(x);
  function matrix(m, zeilen, spalten, name) {
    check(Array.isArray(m) && m.length === zeilen, `${name}: ${zeilen} Zeilen erwartet.`);
    for (const z of m) check(Array.isArray(z) && z.length === spalten && z.every(endlich), `${name}: ${spalten} endliche Werte je Zeile erwartet.`);
  }
  function vektor(v, n, name) { check(Array.isArray(v) && v.length === n && v.every(endlich), `${name}: ${n} endliche Werte erwartet.`); }

  const skalarprodukt = (a, b) => a.reduce((s, x, i) => s + x * b[i], 0);
  const norm = a => Math.sqrt(skalarprodukt(a, a));
  const projektion = (W, b, x) => W.map((zeile, i) => skalarprodukt(zeile, x) + b[i]);

  function softmax(werte) {
    const m = Math.max(...werte);
    const e = werte.map(x => Math.exp(x - m));
    const z = e.reduce((s, x) => s + x, 0);
    return e.map(x => x / z);
  }
  function layerNorm(x, gamma, beta, eps) {
    const mittel = x.reduce((s, v) => s + v, 0) / x.length;
    const varianz = x.reduce((s, v) => s + (v - mittel) ** 2, 0) / x.length;
    const nenner = Math.sqrt(varianz + eps);
    return { mittel, varianz, nenner, y: x.map((v, i) => (v - mittel) / nenner * gamma[i] + beta[i]) };
  }

  // Exakte Ebene aus Sicht einer Query: x = Anteil in Richtung q, y = Länge des Rests senkrecht dazu.
  function queryEbene(q, keys) {
    const laenge = norm(q);
    return keys.map(k => {
      const x = skalarprodukt(k, q) / laenge;
      return { x, y: Math.sqrt(Math.max(0, skalarprodukt(k, k) - x * x)), laenge: norm(k) };
    });
  }

  function validiere(daten) {
    check(daten && daten.format === "guppylm-attention-v1", "Unbekanntes Datenformat; erwartet wird guppylm-attention-v1.");
    const c = daten.config;
    check(c && Number.isInteger(c.d_model) && Number.isInteger(c.n_heads) && c.d_model % c.n_heads === 0, "Konfiguration fehlt oder ist ungültig.");
    const d = c.d_model, hd = daten.head_dim;
    check(hd === d / c.n_heads, "Kopfbreite passt nicht zur Konfiguration.");
    check(Array.isArray(daten.auswahl) && daten.auswahl.length, "Keine Kopfauswahl enthalten.");
    for (const g of daten.gewichte) {
      for (const s of ["Q", "K", "V"]) { matrix(g[`W_${s}`], hd, d, `W_${s} Block ${g.block} Kopf ${g.kopf}`); vektor(g[`b_${s}`], hd, `b_${s}`); }
    }
    for (const a of daten.auswahl) for (const h of a.koepfe) check(daten.gewichte.some(g => g.block === a.block && g.kopf === h), `Gewichte für Block ${a.block}, Kopf ${h} fehlen.`);
    check(Array.isArray(daten.prompts) && daten.prompts.length, "Keine Prompts enthalten.");
    for (const p of daten.prompts) {
      const T = p.ids.length;
      check(T > 0 && T <= c.max_seq_len && p.tokens.length === T, `Prompt ${JSON.stringify(p.text)}: ungültige Tokenzahl.`);
      check(p.bloecke.length === daten.auswahl.length, "Blöcke im Prompt passen nicht zur Auswahl.");
      for (const b of p.bloecke) {
        matrix(b.x_hat, T, d, `x̂ Block ${b.block}`);
        for (const k of b.koepfe) {
          for (const s of ["q", "k", "v", "h"]) matrix(k[s], T, hd, `${s} Block ${b.block} Kopf ${k.kopf}`);
          matrix(k.gewichte, T, T, "Attentiongewichte");
          check(k.scores.length === T && k.scores.every((z, i) => z.length === T && z.every((s, j) => j > i ? s === null : endlich(s))),
            "Bewertungen: Zukunft muss maskiert (null), Vergangenheit endlich sein.");
        }
      }
      if (p.herkunft_block1) {
        const hk = p.herkunft_block1;
        for (const s of ["token_embedding", "positions_embedding", "summe"]) matrix(hk[s], T, d, s);
        vektor(hk.norm_gamma, d, "γ"); vektor(hk.norm_beta, d, "β");
      }
    }
    return true;
  }

  // Rechnet jeden exportierten Wert aus den exportierten Gewichten und x̂ nach.
  function pruefe(daten) {
    validiere(daten);
    let maxAbw = 0, anzahl = 0;
    const vergleiche = (ist, soll, wo) => {
      const abw = Math.abs(ist - soll);
      check(abw <= TOLERANZ * (1 + Math.abs(soll)), `${wo}: nachgerechnet ${ist}, exportiert ${soll}.`);
      maxAbw = Math.max(maxAbw, abw); anzahl++;
    };
    const hd = daten.head_dim;
    for (const p of daten.prompts) {
      const T = p.ids.length;
      for (const b of p.bloecke) {
        if (b.block === 1 && p.herkunft_block1) {
          const hk = p.herkunft_block1;
          hk.summe.forEach((s, t) => {
            s.forEach((v, i) => vergleiche(hk.token_embedding[t][i] + hk.positions_embedding[t][i], v, `E+P Position ${t}`));
            layerNorm(s, hk.norm_gamma, hk.norm_beta, hk.norm_epsilon).y.forEach((v, i) => vergleiche(v, b.x_hat[t][i], `LayerNorm Position ${t}`));
          });
        }
        for (const k of b.koepfe) {
          const g = gewicht(daten, b.block, k.kopf);
          for (const s of ["q", "k", "v"]) b.x_hat.forEach((x, t) => projektion(g[`W_${s.toUpperCase()}`], g[`b_${s.toUpperCase()}`], x)
            .forEach((v, i) => vergleiche(v, k[s][t][i], `${s} Block ${b.block} Kopf ${k.kopf} Position ${t}`)));
          for (let i = 0; i < T; i++) {
            const roh = k.k.slice(0, i + 1).map(key => skalarprodukt(k.q[i], key) / Math.sqrt(hd));
            roh.forEach((v, j) => vergleiche(v, k.scores[i][j], `Bewertung (${i}, ${j})`));
            const a = softmax(roh);
            k.gewichte[i].forEach((v, j) => vergleiche(j <= i ? a[j] : 0, v, `Gewicht (${i}, ${j})`));
            for (let d = 0; d < hd; d++) vergleiche(a.reduce((s, w, j) => s + w * k.v[j][d], 0), k.h[i][d], `Kopfausgang Position ${i}`);
          }
        }
      }
    }
    return { maxAbw, anzahl };
  }

  function gewicht(daten, block, kopf) { return daten.gewichte.find(g => g.block === block && g.kopf === kopf); }

  // Alle Werte eines Kopfes für die Anzeige, einschließlich der später verworfenen Zukunftsbewertungen.
  function kopfansicht(daten, promptIndex, block, kopf) {
    const p = daten.prompts[promptIndex];
    const b = p.bloecke.find(x => x.block === block);
    const k = b.koepfe.find(x => x.kopf === kopf);
    const skala = Math.sqrt(daten.head_dim);
    const rohAlle = k.q.map(q => k.k.map(key => skalarprodukt(q, key) / skala));
    return { prompt: p, block: b, kopf: k, gewichte: gewicht(daten, block, kopf), rohAlle };
  }

  global.AttentionModell = { validiere, pruefe, kopfansicht, gewicht, skalarprodukt, norm, projektion, softmax, layerNorm, queryEbene, TOLERANZ };
})(typeof window !== "undefined" ? window : globalThis);

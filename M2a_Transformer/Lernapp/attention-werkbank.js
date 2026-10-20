"use strict";

(() => {
  const M = window.AttentionModell;
  const $ = id => document.getElementById(id);
  const fmt = (x, n = 3) => Number(x).toLocaleString("de-DE", { minimumFractionDigits: n, maximumFractionDigits: n });
  const escape = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sichtbar = t => t.replace(/Ġ/g, "␠").replace(/Ċ/g, "↵");
  const KURZ = { "<|im_start|>": "⟨start⟩", "<|im_end|>": "⟨end⟩", assistant: "assist." };
  const kurz = t => KURZ[t] ?? sichtbar(t);
  const cos = (a, b) => M.skalarprodukt(a, b) / (M.norm(a) * M.norm(b));

  // Beobachtungen an den beiden Prompts dieser Werkbank, keine nachgewiesenen Funktionen.
  const KOPFMUSTER = {
    "1:4": ["Nachbar", "Viel Gewicht geht an das jeweils vorige Token."],
    "1:5": ["Selbstbezug", "Viele Positionen geben einen großen Teil des Gewichts sich selbst."],
    "1:6": ["Rollenmarke", "⟨end⟩ und assistant schauen stark auf das Token user."],
    "6:3": ["Breit verteilt", "Die Gewichte verteilen sich auf viele Positionen."],
    "6:4": ["Anker", "Viel Gewicht fließt zum ersten Token ⟨start⟩."],
    "6:5": ["Inhalt", "Die letzte Position, an der die Antwort beginnt, schaut auf die Inhaltswörter der Frage."],
  };

  const STEPS = [
    {
      kurz: "Eingang",
      title: "Der Eingang des Kopfes: x̂",
      description: "Jede Tokenposition bringt einen Vektor x̂ mit 384 Komponenten mit. x̂ ist der Residualstrom nach der ersten LayerNorm dieses Blocks. Alle sechs Köpfe des Blocks erhalten exakt denselben Vektor x̂. Links steht er einmal pro Zeile; für Keys und Values oben und unten werden dieselben Vektoren verwendet.",
      formula: "x̂ₜ = LayerNorm₁(xₜ)    384 Komponenten je Position",
      takeaway: "In Block 1 ist x die Summe aus Token- und Positions-Embedding. In Block 6 ist x der Residualstrom nach fünf Blöcken; er enthält bereits Information, die frühere Köpfe zwischen Positionen ausgetauscht haben.",
      code: "# Block.forward im Notebook\nx = x + self.attn(self.norm1(x), maske)\n#              └── x̂ = self.norm1(x): Eingang aller Köpfe",
    },
    {
      kurz: "Projektionen",
      title: "Drei Projektionen: q, k und v",
      description: "Der Kopf multipliziert x̂ mit drei eigenen lernbaren Matrizen. So entstehen pro Position eine Query (links), ein Key (oben) und ein Value (unten), jeweils mit 64 Komponenten. Jede dieser 64 Komponenten ist eine gewichtete Summe aller 384 Komponenten von x̂.",
      formula: "qₜ = W_Q,h · x̂ₜ + b_Q,h    (64 × 384) · 384 + 64 → 64\nkₜ = W_K,h · x̂ₜ + b_K,h\nvₜ = W_V,h · x̂ₜ + b_V,h",
      takeaway: "Ein Kopf erhält keinen Ausschnitt von x̂. Wechsle den Kopf: x̂ bleibt unverändert, aber q, k und v ändern sich vollständig, weil jeder Kopf eigene Matrizen hat.",
      code: "qkv = self.qkv(x)  # (B, T, 3·384): alle Köpfe auf einmal\nqkv = qkv.reshape(B, T, 3, self.n_heads, self.head_dim)\nq, k, v = qkv.permute(2, 0, 3, 1, 4)  # je (B, Köpfe, T, 64)\n# Kopf h nutzt die Zeilen h·64 … h·64+63 jedes Drittels von qkv.weight.\n# Aufgeteilt wird also nach der Projektion, nicht x̂.",
    },
    {
      kurz: "Bewertungen",
      title: "Jede Query bewertet jeden Key",
      description: "Die Zelle in Zeile i und Spalte j liegt im Schnittpunkt von qᵢ (links) und kⱼ (oben). Ihr Wert ist das Skalarprodukt der beiden 64-dimensionalen Vektoren, geteilt durch √64 = 8. Berechnet werden zunächst alle Paare, auch solche mit späteren Positionen.",
      formula: "Bewertung(i, j) = qᵢ · kⱼ / √64\n= (qᵢ[0]·kⱼ[0] + … + qᵢ[63]·kⱼ[63]) / 8",
      takeaway: "Das Skalarprodukt ist groß, wenn Key und Query in eine ähnliche Richtung zeigen, und wächst mit der Länge des Keys. Die Teilung durch 8 hält die Werte in einem Bereich, in dem Softmax nicht fast immer nur einen Gewinner liefert.",
      code: "roh = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)\n# (B, Köpfe, T, T): Zeile = Query-Position, Spalte = Key-Position",
    },
    {
      kurz: "Maske",
      title: "Die kausale Maske",
      description: "Eine Position darf sich selbst und frühere Positionen sehen, aber keine späteren. Deshalb werden alle Bewertungen oberhalb der Diagonale vor Softmax durch −∞ ersetzt. Zeile i behält i + 1 Bewertungen.",
      formula: "Bewertung(i, j) = −∞   für j > i",
      takeaway: "Die Maske multipliziert nicht nachträglich mit 0. Sie setzt −∞ vor Softmax; wegen exp(−∞) = 0 erhalten diese Positionen danach genau Gewicht 0, und die übrigen Gewichte werden trotzdem auf 1 normiert.",
      code: "maske = torch.tril(torch.ones(T, T))  # untere Dreiecksmatrix\nroh = roh.masked_fill(maske == 0, float(\"-inf\"))",
    },
    {
      kurz: "Softmax",
      title: "Softmax macht jede Zeile zu Gewichten",
      description: "Softmax wird für jede Zeile getrennt über ihre sichtbaren Bewertungen gerechnet. Jedes Gewicht liegt zwischen 0 und 1, und jede Zeile summiert sich zu 1. Mit dem Umschalter oben zeigt die Matrix wahlweise Bewertungen oder Gewichte.",
      formula: "aᵢⱼ = exp(Bewertung(i, j)) / Σₖ≤ᵢ exp(Bewertung(i, k))",
      takeaway: "Normiert werden die Zeilen, nicht die Spalten. Eine Spalte kann insgesamt viel mehr oder weniger als 1 erhalten. Ein Gewicht beschreibt, wie viel vom Value einer Position in diese Zeile fließt, nicht wie wichtig das Token für das Modell ist.",
      code: "gewichte = F.softmax(roh, dim=-1)  # letzte Achse: über die Keys einer Zeile",
    },
    {
      kurz: "Mischung",
      title: "Die Values werden gemischt",
      description: "Der Ausgang hᵢ der Zeile i ist die mit den Gewichten dieser Zeile gewichtete Summe der Values. Unten werden die Values nach dem Gewicht der gewählten Zeile hervorgehoben; rechts entsteht hᵢ mit wieder 64 Komponenten.",
      formula: "hᵢ = Σⱼ≤ᵢ aᵢⱼ · vⱼ",
      takeaway: "Weil die Gewichte nichtnegativ sind und sich zu 1 summieren, ist hᵢ ein gewichteter Mittelwert: Jede Komponente liegt zwischen dem kleinsten und dem größten Wert, den die sichtbaren Values in dieser Komponente haben.",
      code: "y = self.dropout(gewichte) @ v  # im Evaluationsmodus ohne Dropout\n# (B, Köpfe, T, T) @ (B, Köpfe, T, 64) → (B, Köpfe, T, 64)",
    },
    {
      kurz: "Zurück",
      title: "Zurück in den Residualstrom",
      description: "Alle sechs Köpfe des Blocks liefern je Position einen 64-dimensionalen Ausgang. Sie werden aneinandergehängt (6 × 64 = 384), mit W_O projiziert und zum Residualstrom addiert. Erst danach folgen LayerNorm und FFN.",
      formula: "Beitrag = Concat(h₁, …, h₆) · W_Oᵀ + b_O    384 → 384\nx_neu = x + Beitrag",
      takeaway: "Die Werkbank zeigt drei der sechs Köpfe je Block und nicht W_O. Ein einzelner Kopf trägt nur über W_O und gemeinsam mit den anderen Köpfen zum Residualstrom bei.",
      code: "y = y.transpose(1, 2).contiguous().view(B, T, C)  # Köpfe aneinanderhängen\ny = self.out(y)                                    # W_O, 384 × 384\n# Block.forward: x = x + self.attn(self.norm1(x), maske)",
    },
  ];

  const state = { prompt: 0, block: 1, kopf: 4, step: 0, ansicht: "roh", zeile: 0, spalte: 0, art: "q", komponente: 0, dim: 0 };
  let daten, sicht, grenzen;
  const stripeCache = new Map();
  let zuMalen = [];

  // ---------- Farben und Skalen ----------
  function farbe(v, limit) {
    const a = [250, 248, 242], b = v < 0 ? [79, 115, 191] : [222, 133, 13], t = Math.min(1, Math.abs(v) / limit);
    return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(",")})`;
  }
  function gewichtFarbe(a) {
    const s = [253, 243, 230], e = [222, 133, 13];
    return `rgb(${s.map((x, i) => Math.round(x + (e[i] - x) * Math.min(1, a))).join(",")})`;
  }
  // 99. Perzentil der Beträge: einzelne Ausreißer sollen die Skala nicht flach machen.
  function grenze(listen) {
    const werte = listen.flat(2).map(Math.abs).sort((a, b) => a - b);
    return werte[Math.floor(0.99 * (werte.length - 1))] || 1;
  }
  function stripeURL(key, werte, limit) {
    const id = `${key}|${limit}`;
    if (stripeCache.has(id)) return stripeCache.get(id);
    const canvas = document.createElement("canvas");
    canvas.width = werte.length; canvas.height = 1;
    const ctx = canvas.getContext("2d");
    werte.forEach((v, i) => { ctx.fillStyle = farbe(v, limit); ctx.fillRect(i, 0, 1, 1); });
    const url = canvas.toDataURL();
    stripeCache.set(id, url);
    return url;
  }
  // Streifen im Inspektor: Canvas-Platzhalter, nach dem Einfügen bemalt.
  function streifen(label, werte, limit, wert = "") {
    zuMalen.push({ werte, limit });
    return `<div class="stripe-row"><span>${label}</span><canvas data-paint="${zuMalen.length - 1}" width="${werte.length}" height="1" role="img" aria-label="${escape(label)}: ${werte.length} Komponenten als Farbstreifen"></canvas><span>${wert}</span></div>`;
  }
  function maleStreifen() {
    for (const canvas of document.querySelectorAll("canvas[data-paint]")) {
      const { werte, limit } = zuMalen[Number(canvas.dataset.paint)];
      const ctx = canvas.getContext("2d");
      werte.forEach((v, i) => { ctx.fillStyle = farbe(v, limit); ctx.fillRect(i, 0, 1, 1); });
    }
  }

  // ---------- Zustand ----------
  function T() { return sicht.prompt.ids.length; }
  function tokens() { return sicht.prompt.tokens; }
  function zeilenMaximum(i) { const a = sicht.kopf.gewichte[i]; return a.indexOf(Math.max(...a)); }
  function aktualisiereSicht() {
    sicht = M.kopfansicht(daten, state.prompt, state.block, state.kopf);
    const k = sicht.kopf;
    grenzen = { x: grenze(sicht.block.x_hat), qk: grenze([k.q, k.k]), vh: grenze([k.v, k.h]), roh: grenze(sicht.rohAlle) };
    state.zeile = Math.min(state.zeile, T() - 1);
    state.spalte = Math.min(state.spalte, T() - 1);
  }
  function koepfeImBlock() { return daten.auswahl.find(a => a.block === state.block).koepfe; }

  // ---------- Kreuzanordnung ----------
  function kreuz() {
    const n = T(), C = 44, HD = daten.head_dim, S = 1.5, s = state.step;
    const k = sicht.kopf, toks = tokens(), xh = sicht.block.x_hat;
    const L = { lab: 8, xh: 102, xhW: 160, wq: 272, wqW: 26, q: 306, qW: HD * S };
    const X0 = L.q + L.qW + 16, XE = X0 + n * C, HX = XE + 16, HW = HD * S;
    const kTop = 64, kH = HD * S, Y0 = kTop + kH + 30, YE = Y0 + n * C;
    const vTop = YE + 26, vBottom = vTop + HD * S, wvY = vBottom + 10;
    const width = HX + HW + 150, height = wvY + 62;
    const rowY = i => Y0 + i * C + 8, rowH = C - 16, colX = j => X0 + j * C + 9, colW = C - 18;
    const dimX = s >= 2 ? "fade" : "", dimQK = s >= 5 ? "fade" : "", dimV = s >= 2 && s <= 4 ? "fade" : "";
    const ansicht = s >= 4 ? state.ansicht : "roh";
    const zeile = state.zeile, spalte = state.spalte;
    let o = `<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Attention-Kopf ${state.kopf} in Block ${state.block}">
      <defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#f3f6f8"/><rect width="3" height="6" fill="#e2e8ec"/></pattern>
      <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#79939e"/></marker></defs>`;

    const segH = (art, t, werte, x, y, w, h, limit) => werte.map((v, d) => `<rect class="seg" data-seg="${art},${t},${d}" x="${(x + d * w / werte.length).toFixed(2)}" y="${y}" width="${(w / werte.length + .2).toFixed(2)}" height="${h}" fill="${farbe(v, limit)}"><title>${art}${t}[${d}] = ${fmt(v, 4)}</title></rect>`).join("") + `<rect class="frame" x="${x}" y="${y}" width="${w}" height="${h}"/>`;
    const segV = (art, t, werte, x, y, w, h, limit) => werte.map((v, d) => `<rect class="seg" data-seg="${art},${t},${d}" x="${x}" y="${(y + d * h / werte.length).toFixed(2)}" width="${w}" height="${(h / werte.length + .2).toFixed(2)}" fill="${farbe(v, limit)}"><title>${art}${t}[${d}] = ${fmt(v, 4)}</title></rect>`).join("") + `<rect class="frame" x="${x}" y="${y}" width="${w}" height="${h}"/>`;
    const platzhalter = (x, y, w, h, text) => `<rect class="placeholder" x="${x}" y="${y}" width="${w}" height="${h}" rx="4"/>${text ? `<text class="placeholder-text" x="${x + w / 2}" y="${y + h / 2 + 4}" text-anchor="middle">${text}</text>` : ""}`;

    // Spaltenseite oben: Herkunft, W_K, Keys
    o += `<text class="sub" x="${X0 + n * C / 2}" y="16" text-anchor="middle">x̂ der Spaltentokens · dieselben Vektoren wie links</text>`;
    o += s >= 1 ? `<g class="${dimX}"><rect class="wbox" x="${X0}" y="26" width="${n * C}" height="26" rx="4"/><text class="wlabel" x="${X0 + n * C / 2}" y="43" text-anchor="middle">W_K,${state.kopf} · 64 × 384</text></g>`
      : platzhalter(X0, 26, n * C, 26, "W_K · ab Schritt 2");
    o += `<text class="sub" x="${X0 - 10}" y="${kTop + kH / 2 + 4}" text-anchor="end">k · 64</text>`;
    // Zeilenseite links: Beschriftungen
    o += `<text class="sub" x="${L.xh}" y="${Y0 - 10}">x̂ · 384</text><text class="sub" x="${L.wq - 2}" y="${Y0 - 10}">W_Q</text><text class="sub" x="${L.q}" y="${Y0 - 10}">q · 64</text><text class="sub" x="${HX}" y="${Y0 - 10}">h · 64</text>`;
    o += s >= 1 ? `<g class="${dimX}"><rect class="wbox" x="${L.wq}" y="${Y0 + 4}" width="${L.wqW}" height="${n * C - 8}" rx="4"/></g>` : platzhalter(L.wq, Y0 + 4, L.wqW, n * C - 8, "");
    // Untere Seite: Values und W_V
    o += `<text class="sub" x="${X0 - 10}" y="${vTop + kH / 2 + 4}" text-anchor="end">v · 64</text>`;
    o += s >= 1 ? `<g class="${dimX}"><rect class="wbox" x="${X0}" y="${wvY}" width="${n * C}" height="26" rx="4"/><text class="wlabel" x="${X0 + n * C / 2}" y="${wvY + 17}" text-anchor="middle">W_V,${state.kopf} · 64 × 384</text></g>`
      : platzhalter(X0, wvY, n * C, 26, "W_V · ab Schritt 2");
    o += `<text class="sub" x="${X0 + n * C / 2}" y="${wvY + 48}" text-anchor="middle">x̂ der Spaltentokens · dieselben Vektoren wie links</text>`;

    for (let i = 0; i < n; i++) {
      const y = rowY(i), aktiv = i === zeile;
      o += `<text class="row-label ${aktiv ? "selected" : ""}" data-row="${i}" x="${L.lab}" y="${y + rowH / 2 + 4}">${i} ${escape(sichtbar(toks[i]))}<title>Position ${i}: ${escape(toks[i])}</title></text>`;
      o += `<g class="${dimX}"><image href="${stripeURL(`x|${state.prompt}|${state.block}|${i}`, xh[i], grenzen.x)}" x="${L.xh}" y="${y}" width="${L.xhW}" height="${rowH}" preserveAspectRatio="none" style="image-rendering:pixelated"/><rect class="frame" x="${L.xh}" y="${y}" width="${L.xhW}" height="${rowH}"/></g>`;
      o += s >= 1 ? `<g class="${dimQK}">${segH("q", i, k.q[i], L.q, y, L.qW, rowH, grenzen.qk)}</g>` : platzhalter(L.q, y, L.qW, rowH, i === 0 ? "q" : "");
      // Spalten: Key oben, Beschriftung, Value unten
      const x = colX(i);
      o += `<text class="col-label ${i === spalte ? "selected" : ""}" data-col="${i}" x="${X0 + i * C + C / 2}" y="${Y0 - 10}" text-anchor="middle">${escape(kurz(toks[i]))}<title>Position ${i}: ${escape(toks[i])}</title></text>`;
      o += s >= 1 ? `<g class="${dimQK}">${segV("k", i, k.k[i], x, kTop, colW, kH, grenzen.qk)}</g>` : platzhalter(x, kTop, colW, kH, "");
      if (s >= 1) {
        const a = k.gewichte[zeile][i], mx = Math.max(...k.gewichte[zeile]);
        const op = s >= 5 ? (i > zeile ? .08 : .12 + .88 * a / mx) : null;
        o += `<g class="${op === null ? dimV : ""}" ${op === null ? "" : `opacity="${op.toFixed(2)}"`}>${segV("v", i, k.v[i], x, vTop, colW, kH, grenzen.vh)}</g>`;
        if (s >= 5) o += `<text class="sub" x="${X0 + i * C + C / 2}" y="${vTop - 8}" text-anchor="middle">${i > zeile ? "–" : fmt(a, 2)}</text>`;
      } else o += platzhalter(x, vTop, colW, kH, "");
      // Kopfausgang rechts
      o += s >= 5 ? `<g class="${s === 5 && i !== zeile ? "fade" : ""}">${segH("h", i, k.h[i], HX, y, HW, rowH, grenzen.vh)}</g>` : platzhalter(HX, y, HW, rowH, i === 0 ? "h · ab Schritt 6" : "");
    }

    // Matrix
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const x = X0 + j * C, y = Y0 + i * C, zukunft = j > i;
      if (s < 2) { o += `<rect class="placeholder" x="${x + 1}" y="${y + 1}" width="${C - 2}" height="${C - 2}" rx="3"/>`; continue; }
      if (zukunft && s >= 3) {
        o += `<rect class="masked cell" data-cell="${i},${j}" x="${x + 1}" y="${y + 1}" width="${C - 2}" height="${C - 2}" rx="3"><title>Zeile ${i}, Spalte ${j}: spätere Position, maskiert</title></rect><text class="cell-text" x="${x + C / 2}" y="${y + C / 2 + 4}" text-anchor="middle" fill="#7d8d96">${ansicht === "roh" ? "−∞" : "0"}</text>`;
        continue;
      }
      const roh = sicht.rohAlle[i][j], a = k.gewichte[i][j];
      const fill = ansicht === "roh" ? farbe(roh, grenzen.roh) : gewichtFarbe(a);
      const dunkel = ansicht === "roh" ? Math.abs(roh) / grenzen.roh > .75 : a > .6;
      const text = ansicht === "roh" ? fmt(roh, 1) : fmt(a, 2);
      o += `<rect class="cell" data-cell="${i},${j}" x="${x + 1}" y="${y + 1}" width="${C - 2}" height="${C - 2}" rx="3" fill="${fill}"><title>Zeile ${i} (${escape(toks[i])}) → Spalte ${j} (${escape(toks[j])}): Bewertung ${fmt(roh, 4)}${zukunft ? "" : `, Gewicht ${fmt(a, 4)}`}</title></rect><text class="cell-text" x="${x + C / 2}" y="${y + C / 2 + 4}" text-anchor="middle" fill="${dunkel ? "white" : "#16252e"}"${zukunft ? ' opacity=".55"' : ""}>${text}</text>`;
    }
    if (s < 2) o += `<text class="placeholder-text" x="${X0 + n * C / 2}" y="${Y0 + n * C / 2 + 4}" text-anchor="middle">Bewertungen · ab Schritt 3</text>`;

    // Auswahl: Zeile, Spalte, Zelle
    o += `<rect class="outline" x="4" y="${Y0 + zeile * C + 2}" width="${HX + HW + 4 - 4}" height="${C - 4}" rx="5"/>`;
    if (s >= 1) o += `<rect class="outline col" x="${X0 + spalte * C + 3}" y="${kTop - 5}" width="${C - 6}" height="${vBottom + 10 - kTop}" rx="5"/>`;
    if (s >= 2) o += `<rect class="outline" x="${X0 + spalte * C}" y="${Y0 + zeile * C}" width="${C}" height="${C}" rx="4" style="stroke-width:3"/>`;

    // Rückweg in den Residualstrom
    if (s >= 6) {
      o += `<path class="arrow" d="M${HX + HW + 8} ${Y0 + n * C / 2} H${HX + HW + 34}"/>`;
      o += `<text class="label" x="${HX + HW + 40}" y="${Y0 + n * C / 2 - 22}">Concat</text><text class="sub" x="${HX + HW + 40}" y="${Y0 + n * C / 2 - 6}">mit den anderen</text><text class="sub" x="${HX + HW + 40}" y="${Y0 + n * C / 2 + 9}">5 Köpfen → 384</text><text class="label" x="${HX + HW + 40}" y="${Y0 + n * C / 2 + 30}">· W_O</text><text class="sub" x="${HX + HW + 40}" y="${Y0 + n * C / 2 + 46}">+ Residualstrom</text>`;
    }
    o += "</svg>";
    $("cross").innerHTML = o;
  }

  // ---------- Inspektor ----------
  function chips(attr, aktuell, bis = T() - 1) {
    return `<div class="chips">${tokens().map((t, i) => `<button data-${attr}="${i}" aria-pressed="${i === aktuell}" ${i > bis ? "disabled" : ""} title="${escape(t)}">${i} ${escape(sichtbar(t))}</button>`).join("")}</div>`;
  }
  function zwilling(t) {
    const id = sicht.prompt.ids[t];
    return sicht.prompt.ids.findIndex((x, i) => x === id && i !== t);
  }

  function detailEingang() {
    const t = state.zeile, p = sicht.prompt, hk = p.herkunft_block1;
    let o = `<div class="mini-label">Tokenposition</div>${chips("zeile", t)}`;
    if (state.block === 1 && hk) {
      const lim = grenze([hk.token_embedding, hk.positions_embedding, hk.summe]);
      const ln = M.layerNorm(hk.summe[t], hk.norm_gamma, hk.norm_beta, hk.norm_epsilon);
      o += `<h3>Woher kommt x̂ in Block 1?</h3>
        ${streifen(`E[${p.ids[t]}]`, hk.token_embedding[t], lim)}
        ${streifen(`+ P[${t}]`, hk.positions_embedding[t], lim)}
        ${streifen("= x", hk.summe[t], lim)}
        ${streifen("x̂ = LN(x)", sicht.block.x_hat[t], grenzen.x)}
        <p class="help">Die ersten drei Streifen teilen eine Farbskala, x̂ hat eine eigene. Dieselben Streifen zeigt die <a href="embeddings-werkbank.html">Embedding-Werkbank</a>. LayerNorm normiert über alle 384 Komponenten dieser Position: μ = ${fmt(ln.mittel, 4)}, σ² = ${fmt(ln.varianz, 4)}; danach folgen die gelernten γ und β.</p>`;
    } else {
      o += `<h3>x̂ in Block ${state.block}</h3>${streifen("x̂", sicht.block.x_hat[t], grenzen.x)}
        <p class="help">Hier ist x nicht mehr „Token plus Position“. Es ist der Residualstrom nach ${state.block - 1} Blöcken: Embedding-Summe plus alle bisherigen Beiträge von Attention und FFN. Erst danach wendet <code>blocks.${state.block - 1}.norm1</code> die LayerNorm an.</p>`;
    }
    const z = zwilling(t);
    if (z >= 0) {
      o += `<h3>Dasselbe Token an anderer Position</h3><p class="help">„${escape(sichtbar(tokens()[t]))}“ steht auch an Position ${z}. Ähnlichkeit der beiden x̂ (Kosinus): <b>${fmt(cos(sicht.block.x_hat[t], sicht.block.x_hat[z]), 2)}</b>. Gleiches Token, aber verschiedene Vektoren: ${state.block === 1 ? "verschiedene Positions-Embeddings" : "verschiedene Position und verschiedener bisheriger Kontext"}.</p>`;
    } else if (state.prompt === 1 && state.block === 1) {
      o += `<p class="help">Tipp: Das erste „fish“ ist ein anderes Token als die beiden folgenden „␠fish“ mit vorangestelltem Leerzeichen. Wähle Position 4 oder 5, um dasselbe Token an zwei Positionen zu vergleichen.</p>`;
    }
    return o;
  }

  function detailProjektion() {
    const art = state.art, t = art === "q" ? state.zeile : state.spalte, c = state.komponente;
    const W = sicht.gewichte[`W_${art.toUpperCase()}`][c], b = sicht.gewichte[`b_${art.toUpperCase()}`][c];
    const x = sicht.block.x_hat[t], produkte = W.map((w, i) => w * x[i]);
    const summe = produkte.reduce((s, v) => s + v, 0), wert = summe + b, exportiert = sicht.kopf[art][t][c];
    const betrag = produkte.reduce((s, v) => s + Math.abs(v), 0);
    const top = produkte.map((v, i) => ({ v, i })).sort((p, q) => Math.abs(q.v) - Math.abs(p.v)).slice(0, 5);
    const anteil = top.reduce((s, p) => s + Math.abs(p.v), 0) / betrag;
    const name = { q: "Query", k: "Key", v: "Value" }[art];
    let o = `<div class="control-row"><span>Projektion</span><span class="segmented">${["q", "k", "v"].map(a => `<button data-art="${a}" aria-pressed="${a === art}">${a}</button>`).join("")}</span></div>
      <div class="mini-label">${art === "q" ? "Zeile (Query-Token)" : "Spalte (Key-/Value-Token)"}</div>${chips(art === "q" ? "zeile" : "spalte", t)}
      <div class="control-row"><label for="komponente">Komponente ${art}[${c}]</label><input id="komponente" type="range" min="0" max="${daten.head_dim - 1}" value="${c}"></div>
      <h3>${name}-Komponente ${c} an Position ${t}</h3>
      ${streifen(`W_${art.toUpperCase()}[${c}, :]`, W, grenze([W]))}
      ${streifen(`x̂ Pos. ${t}`, x, grenzen.x)}
      ${streifen("Produkte", produkte, grenze([produkte]))}
      <div class="formula">${art}[${c}] = Σ (384 Produkte) + b = ${fmt(summe, 4)} + (${fmt(b, 4)}) = ${fmt(wert, 4)}
Export aus PyTorch: ${fmt(exportiert, 4)}</div>
      <p class="help">Alle 384 Komponenten von x̂ tragen bei. Die fünf größten Produkte machen ${fmt(anteil * 100, 0)} % der Summe aller Beträge aus:</p>
      <div class="table-scroll"><table class="data-table"><thead><tr><th>Dimension von x̂</th><th>Gewicht</th><th>x̂</th><th>Produkt</th></tr></thead><tbody>${top.map(p => `<tr><td>d${p.i}</td><td>${fmt(W[p.i], 4)}</td><td>${fmt(x[p.i], 4)}</td><td>${fmt(p.v, 4)}</td></tr>`).join("")}</tbody></table></div>
      <div class="note">Wechsle oben den Kopf: Die Zeile x̂ bleibt gleich, die Gewichtszeile und damit ${art}[${c}] ändern sich. Ein Kopf bekommt keinen Ausschnitt von x̂, sondern rechnet mit allen 384 Komponenten.</div>`;
    const z = zwilling(t);
    if (z >= 0) o += `<p class="help">Gleiches Token an Position ${z}: Kosinus der beiden ${art}-Vektoren in diesem Kopf ${fmt(cos(sicht.kopf[art][t], sicht.kopf[art][z]), 2)}, der beiden x̂ ${fmt(cos(x, sicht.block.x_hat[z]), 2)}.</p>`;
    return o;
  }

  function ebene(i, j, maskiert) {
    const k = sicht.kopf, q = k.q[i], lq = M.norm(q), punkte = M.queryEbene(q, k.k);
    const W = 340, H = 250, l = 16, r = 16, t = 48, b = 30;
    const xmax = Math.max(lq, ...punkte.map(p => Math.abs(p.x))) * 1.1, ymax = Math.max(...punkte.map(p => p.y), 1e-9) * 1.12;
    const sx = x => l + (x + xmax) / (2 * xmax) * (W - l - r), sy = y => H - b - y / ymax * (H - t - b);
    const smax = lq * xmax / Math.sqrt(daten.head_dim);
    const roh = smax / 3, mag = 10 ** Math.floor(Math.log10(roh)), schritt = [1, 2, 5, 10].map(f => f * mag).find(f => f >= roh);
    let o = `<svg class="plane" viewBox="0 0 ${W} ${H}" role="img" aria-label="Exakte Ebene aus Sicht der Query von Position ${i}: Keys als Punkte, waagrecht der Anteil in Richtung der Query, senkrecht der Rest">
      <defs><marker id="qhead" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#b55319"/></marker></defs>
      <text x="${W / 2}" y="12" text-anchor="middle">Bewertung qᵢ·k/8 (gilt senkrecht nach unten)</text>`;
    for (let s = -Math.floor(smax / schritt) * schritt; s <= smax + 1e-9; s += schritt) {
      const x = sx(s * Math.sqrt(daten.head_dim) / lq);
      o += `<line class="iso" x1="${x}" y1="${t - 10}" x2="${x}" y2="${H - b}"/><text x="${x}" y="${t - 16}" text-anchor="middle">${fmt(s, schritt < 1 ? 1 : 0)}</text>`;
    }
    o += `<line class="axis" x1="${l}" y1="${H - b}" x2="${W - r}" y2="${H - b}"/><line class="axis" x1="${sx(0)}" y1="${t - 4}" x2="${sx(0)}" y2="${H - b}"/>
      <line class="qarrow" x1="${sx(0)}" y1="${H - b}" x2="${sx(lq) - 4}" y2="${H - b}"/><text x="${sx(lq)}" y="${H - b - 8}" text-anchor="middle" fill="#b55319">q${i}</text>
      <text x="${W - r}" y="${H - 4}" text-anchor="end">Anteil in Richtung qᵢ →</text><text x="${l}" y="${H - 4}">↑ Rest senkrecht zu qᵢ</text>`;
    punkte.forEach((p, n) => {
      o += `<circle data-spalte="${n}" class="${n === j ? "selected" : ""} ${maskiert && n > i ? "future" : ""}" cx="${sx(p.x)}" cy="${sy(p.y)}" r="${n === j ? 7 : 5.5}"><title>k${n} (${escape(tokens()[n])}): Bewertung ${fmt(p.x * lq / Math.sqrt(daten.head_dim), 3)}</title></circle><text class="point-label" x="${sx(p.x) + 8}" y="${sy(p.y) - 6}">${n}</text>`;
    });
    return o + "</svg>";
  }

  function detailBewertung() {
    const i = state.zeile, j = state.spalte, k = sicht.kopf;
    const produkte = k.q[i].map((v, d) => v * k.k[j][d]), summe = produkte.reduce((s, v) => s + v, 0);
    return `<div class="mini-label">Zeile i (Query)</div>${chips("zeile", i)}<div class="mini-label">Spalte j (Key)</div>${chips("spalte", j)}
      <h3>Zelle (${i}, ${j}): ${escape(sichtbar(tokens()[i]))} fragt ${escape(sichtbar(tokens()[j]))}</h3>
      ${streifen(`q${i}`, k.q[i], grenzen.qk)}${streifen(`k${j}`, k.k[j], grenzen.qk)}${streifen("qᵢ ⊙ kⱼ", produkte, grenze([produkte]))}
      <div class="formula">Σ der 64 Produkte = ${fmt(summe, 4)}
Bewertung = ${fmt(summe, 4)} / 8 = ${fmt(summe / 8, 4)}</div>
      ${j > i ? '<div class="note">Diese Bewertung wird berechnet, aber sie liegt in der Zukunft von Zeile i. Im nächsten Schritt verwirft die kausale Maske sie.</div>' : ""}
      <h3>Die Keys aus Sicht von q${i}</h3>${ebene(i, j, false)}
      <p class="help">Diese Ebene ist für die gewählte Query exakt, keine PCA: Waagrecht steht der Anteil jedes Keys in Richtung qᵢ, senkrecht die Länge seines restlichen Anteils. Die Bewertung hängt nur von der waagrechten Lage ab: weiter rechts bedeutet höhere Bewertung, links der senkrechten Achse ist sie negativ. Winkel und Längen relativ zu qᵢ stimmen; Abstände zwischen zwei Keys dagegen nicht. Wähle eine andere Zeile, und die Ebene richtet sich nach der neuen Query aus.</p>`;
  }

  function zeilenTabelle(i, mitSoftmax) {
    const roh = sicht.rohAlle[i], sichtbarMax = Math.max(...roh.slice(0, i + 1));
    const exps = roh.map((v, j) => j <= i ? Math.exp(v - sichtbarMax) : 0), z = exps.reduce((s, v) => s + v, 0);
    return `<div class="table-scroll"><table class="data-table"><thead><tr><th>Spalte j</th><th>Bewertung</th><th>nach Maske</th>${mitSoftmax ? "<th>exp(· − max)</th><th>Gewicht</th><th></th>" : ""}</tr></thead><tbody>${roh.map((v, j) => `<tr class="${j === state.spalte ? "selected" : ""} ${j > i ? "muted" : ""}"><td>${j} ${escape(sichtbar(tokens()[j]))}</td><td>${fmt(v, 3)}</td><td>${j > i ? "−∞" : fmt(v, 3)}</td>${mitSoftmax ? `<td>${fmt(exps[j], 4)}</td><td>${fmt(exps[j] / z, 4)}</td><td><div class="bar"><div style="width:${100 * exps[j] / z}%"></div></div></td>` : ""}</tr>`).join("")}</tbody></table></div>`;
  }

  function detailMaske() {
    const i = state.zeile;
    return `<div class="mini-label">Zeile i</div>${chips("zeile", i)}
      <p class="help">Zeile ${i} („${escape(sichtbar(tokens()[i]))}“) behält ${i + 1} von ${T()} Bewertungen. Die erste Zeile sieht nur sich selbst, die letzte alle Positionen.</p>
      ${zeilenTabelle(i, false)}
      <h3>Dieselbe Ebene, ohne Zukunft</h3>${ebene(i, state.spalte, true)}
      <p class="help">Gestrichelte Punkte sind Keys späterer Positionen. Sie liegen weiterhin im Raum, nehmen aber an der Softmax dieser Zeile nicht teil.</p>
      <h3>Nur im Training nötig?</h3>
      <p class="help">Nein. Beim Generieren zählt zwar nur die letzte Zeile, und die sieht ohnehin alle Positionen. Ab Block 2 liest sie aber Keys und Values der früheren Positionen, und deren Vektoren hängen davon ab, ob diese Positionen in den Blöcken davor maskiert waren. Ohne Maske entstünden andere Zwischenvektoren als im Training. Gemessen an GuppyLM mit dem Prompt „hello guppy“: Mit Maske lautet die Greedy-Antwort „hi. i just found a nice spot in the corner.“, ohne Maske „hi there. i was just thinking about food. i blew some bubbles earlier.“</p>
      <p class="help">Erst mit einem KV-Cache, der nur noch die neue letzte Zeile berechnet, wird die Maske beim Generieren überflüssig. Er funktioniert aber nur, weil alle früheren Zeilen bereits maskiert berechnet wurden.</p>`;
  }

  function detailSoftmax() {
    const i = state.zeile, a = sicht.kopf.gewichte;
    const spaltensummen = a[0].map((_, j) => a.reduce((s, z) => s + z[j], 0));
    const groesste = spaltensummen.indexOf(Math.max(...spaltensummen));
    return `<div class="mini-label">Zeile i</div>${chips("zeile", i)}
      ${zeilenTabelle(i, true)}
      <div class="result"><div><b>${fmt(a[i].reduce((s, v) => s + v, 0), 4)}</b><span>Summe der Zeile ${i}</span></div><div><b>${fmt(spaltensummen[groesste], 2)}</b><span>Summe der Spalte ${groesste} (${escape(sichtbar(tokens()[groesste]))}) über alle Zeilen</span></div></div>
      <p class="help">Vor exp wird das Maximum der sichtbaren Bewertungen abgezogen. Das ändert die Gewichte nicht, verhindert aber zu große Zahlen. Spalten müssen sich nicht zu 1 summieren: Spalte ${groesste} erhält insgesamt ${fmt(spaltensummen[groesste], 2)}.</p>`;
  }

  function detailMischung() {
    const i = state.zeile, d = state.dim, k = sicht.kopf;
    const reihen = k.gewichte[i].map((a, j) => ({ a, j })).filter(r => r.j <= i).sort((p, q) => q.a - p.a);
    const komp = reihen.map(r => k.v[r.j][d]), lo = Math.min(...komp), hi = Math.max(...komp);
    return `<div class="mini-label">Zeile i</div>${chips("zeile", i)}
      <h3>h${i} aus ${reihen.length} Values</h3>
      ${reihen.map(r => streifen(`${fmt(r.a, 3)} · v${r.j}`, k.v[r.j], grenzen.vh, escape(sichtbar(tokens()[r.j])))).join("")}
      ${streifen(`= h${i}`, k.h[i], grenzen.vh)}
      <div class="control-row"><label for="dim">Komponente h${i}[${d}]</label><input id="dim" type="range" min="0" max="${daten.head_dim - 1}" value="${d}"></div>
      <div class="formula">h${i}[${d}] = ${reihen.slice(0, 4).map(r => `${fmt(r.a, 3)}·(${fmt(k.v[r.j][d], 3)})`).join(" + ")}${reihen.length > 4 ? ` + … (${reihen.length - 4} weitere)` : ""}
= ${fmt(k.h[i][d], 4)}</div>
      <p class="help">Die sichtbaren Values haben in Komponente ${d} Werte von ${fmt(lo, 3)} bis ${fmt(hi, 3)}. h${i}[${d}] = ${fmt(k.h[i][d], 3)} liegt dazwischen, wie bei jedem gewichteten Mittelwert. Der Kopf kann also keine Werte erzeugen, die außerhalb dieses Bereichs liegen.</p>`;
  }

  function detailZurueck() {
    const i = state.zeile;
    return `<div class="mini-label">Zeile i</div>${chips("zeile", i)}
      ${streifen(`h${i} · Kopf ${state.kopf}`, sicht.kopf.h[i], grenzen.vh)}
      <p class="help">Dieser 64-dimensionale Ausgang ist ein Sechstel des Vektors, den W_O verarbeitet. Die Werkbank exportiert drei der sechs Köpfe je Block und nicht W_O; deshalb wird der Beitrag zum Residualstrom hier nicht ausgerechnet.</p>
      <p class="help">Die <a href="transformer-werkbank.html">Transformer-Werkbank</a> zeigt am kleinen Lehrmodell den gesamten Weg: Concat, W_O, Residualaddition und anschließend FFN.</p>`;
  }

  function detail() {
    zuMalen = [];
    return [detailEingang, detailProjektion, detailBewertung, detailMaske, detailSoftmax, detailMischung, detailZurueck][state.step]();
  }

  // ---------- Darstellung ----------
  function render() {
    aktualisiereSicht();
    const s = STEPS[state.step];
    const muster = KOPFMUSTER[`${state.block}:${state.kopf}`];
    $("prompt").value = state.prompt;
    $("blocks").innerHTML = daten.auswahl.map(a => `<button data-block="${a.block}" aria-pressed="${a.block === state.block}">${a.block}</button>`).join("");
    $("heads").innerHTML = koepfeImBlock().map(h => `<button data-kopf="${h}" aria-pressed="${h === state.kopf}">${h}<small>${KOPFMUSTER[`${state.block}:${h}`]?.[0] ?? ""}</small></button>`).join("");
    const gewichteErlaubt = state.step >= 4;
    $("view-raw").setAttribute("aria-pressed", !gewichteErlaubt || state.ansicht === "roh");
    $("view-weights").setAttribute("aria-pressed", gewichteErlaubt && state.ansicht === "gewichte");
    $("view-weights").disabled = !gewichteErlaubt;
    $("view-weights").title = gewichteErlaubt ? "" : "Gewichte entstehen erst durch Softmax (Schritt 5)";
    $("head-note").innerHTML = muster ? `<strong>Block ${state.block}, Kopf ${state.kopf} · ${muster[0]}:</strong> ${escape(muster[1])} Beobachtung an diesen zwei Prompts, keine nachgewiesene Funktion des Kopfes.` : "";
    $("steps").innerHTML = STEPS.map((x, i) => `<li><button data-step="${i}" class="${i < state.step ? "done" : ""}" ${i === state.step ? 'aria-current="step"' : ""}>${i + 1} ${x.kurz}</button></li>`).join("");
    $("previous").disabled = state.step === 0;
    $("next").disabled = state.step === STEPS.length - 1;
    $("stage-caption").textContent = `${(sicht.prompt.text.includes("hello") ? "hello guppy" : "fish fish fish")} im ChatML-Rahmen · ${T()} Tokens · Block ${state.block} · Kopf ${state.kopf}`;
    $("scale-note").textContent = `Farbskalen bei ±${fmt(grenzen.x, 2)} (x̂), ±${fmt(grenzen.qk, 2)} (q, k), ±${fmt(grenzen.vh, 2)} (v, h), ±${fmt(grenzen.roh, 1)} (Bewertungen) gekappt`;
    $("step-number").textContent = `Schritt ${state.step + 1} von ${STEPS.length}`;
    $("step-title").textContent = s.title;
    $("step-description").textContent = s.description;
    $("formula").textContent = s.formula;
    $("takeaway").textContent = s.takeaway;
    $("notebook-code").textContent = s.code;
    kreuz();
    $("detail").innerHTML = detail();
    maleStreifen();
  }

  function setzeSchritt(n) {
    const vorher = state.step;
    state.step = Math.max(0, Math.min(STEPS.length - 1, n));
    if (state.step >= 4 && vorher < 4) state.ansicht = "gewichte";
    if (state.step < 4) state.ansicht = "roh";
    render();
    document.querySelector(".inspector").scrollTop = 0;
  }
  function waehleZeile(i) {
    state.zeile = i;
    if (state.step >= 3 && state.spalte > i) state.spalte = zeilenMaximum(i);
  }

  function klick(event) {
    const el = event.target.closest("[data-seg],[data-cell],[data-row],[data-col],[data-zeile],[data-spalte],[data-art],[data-step],[data-block],[data-kopf],[data-view]");
    if (!el || el.disabled) return;
    const d = el.dataset;
    if (d.seg) {
      const [art, t, n] = d.seg.split(","); const pos = Number(t), komp = Number(n);
      if (art === "q") { waehleZeile(pos); state.art = "q"; state.komponente = komp; }
      if (art === "k" || art === "v") { state.spalte = pos; state.art = art; state.komponente = komp; }
      if (art === "h") { waehleZeile(pos); state.dim = komp; }
    } else if (d.cell) { const [i, j] = d.cell.split(",").map(Number); state.zeile = i; state.spalte = j; }
    else if (d.row !== undefined) waehleZeile(Number(d.row));
    else if (d.zeile !== undefined) waehleZeile(Number(d.zeile));
    else if (d.col !== undefined) state.spalte = Number(d.col);
    else if (d.spalte !== undefined) state.spalte = Number(d.spalte);
    else if (d.art) state.art = d.art;
    else if (d.step !== undefined) return setzeSchritt(Number(d.step));
    else if (d.block) { state.block = Number(d.block); state.kopf = koepfeImBlock()[0]; aktualisiereSicht(); state.spalte = zeilenMaximum(state.zeile); }
    else if (d.kopf) { state.kopf = Number(d.kopf); aktualisiereSicht(); state.spalte = zeilenMaximum(state.zeile); }
    else if (d.view) { if (d.view === "gewichte" && state.step < 4) return; state.ansicht = d.view; }
    render();
  }

  function fehler(text) {
    $("load-error").textContent = text;
    $("load-error").hidden = false;
  }

  function start() {
    daten = window.GuppyAttention;
    if (!daten) {
      fehler("Die Datei Data/attention-daten.js wurde nicht gefunden.\nSie wird im Projektordner mit der Python-Umgebung des Lehrnotebooks erzeugt:\npython Hilfsskripte/exportiere_attention.py Checkpoints/bestes_modell.pt --auswahl 1:4,5,6 6:3,4,5\nEs werden keine Ersatzwerte angezeigt.");
      return;
    }
    try {
      const ergebnis = M.pruefe(daten);
      $("verification").textContent = `${ergebnis.anzahl.toLocaleString("de-DE")} exportierte Werte im Browser nachgerechnet · größte Abweichung ${ergebnis.maxAbw.toExponential(1).replace(".", ",")}`;
    } catch (e) {
      fehler(`Die Attention-Daten sind unvollständig oder passen nicht zusammen: ${e.message}\nBitte den Export neu erzeugen.`);
      return;
    }
    const q = daten.source;
    $("source").textContent = `GuppyLM · ${q.checkpoint} · Trainingsschritt ${q.step} · Evalverlust ${fmt(q.eval_loss, 3)} · Inferenzmodus ohne Dropout`;
    $("prompt").innerHTML = daten.prompts.map((p, i) => `<option value="${i}">${escape(p.text.replace(/\n/g, "↵"))}</option>`).join("");
    state.block = daten.auswahl[0].block;
    state.kopf = daten.auswahl[0].koepfe[0];
    aktualisiereSicht();
    state.zeile = T() - 1;
    state.spalte = zeilenMaximum(state.zeile);
    $("workbench").hidden = false;
    document.querySelector(".workbench").addEventListener("click", klick);
    $("previous").addEventListener("click", () => setzeSchritt(state.step - 1));
    $("next").addEventListener("click", () => setzeSchritt(state.step + 1));
    $("prompt").addEventListener("change", e => {
      state.prompt = Number(e.target.value); aktualisiereSicht(); state.zeile = T() - 1; state.spalte = zeilenMaximum(state.zeile); render();
    });
    $("detail").addEventListener("input", e => {
      if (e.target.id === "komponente") state.komponente = Number(e.target.value);
      else if (e.target.id === "dim") state.dim = Number(e.target.value);
      else return;
      const id = e.target.id;
      render();
      $(id)?.focus();
    });
    render();
  }
  start();
})();

"use strict";

(() => {
  const { Lehrmodell, vokabular, beispiele, konfig, werte } = TransformerModell;
  const $ = id => document.getElementById(id);
  const fmt = (x, n = 3) => Number(x).toLocaleString("de-DE", { minimumFractionDigits: n, maximumFractionDigits: n });
  const escape = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const state = { mode: "structure", step: 0, example: 0, position: 2, head: 0, block: 0, residual: null, norm: null, lr: 0.03, updates: 0, gradients: null, lastUpdate: null, history: [], generated: null, timer: null };
  let model = new Lehrmodell();
  let trace;

  const steps = [
    {
      title: "Am Anfang steht Text",
      description: "Ein Transformer verarbeitet keine Buchstaben direkt. Zuerst legt ein Tokenizer fest, welche Textstücke eigene Tokens sind. Der Tokenizer und das Sprachmodell sind zwei verschiedene Bausteine.",
      formula: "Text → Textstücke → Token-IDs",
      takeaway: "BPE lernt sein Vokabular vor dem Modelltraining. Backpropagation verändert später die Modellgewichte, nicht die Tokenzerlegung.",
      code: 'tokenizer.encode(text).ids',
    },
    {
      title: "Tokens werden zu IDs",
      description: "Jedes Token erhält eine ganze Zahl als Adresse im Vokabular. Die Reihenfolge bleibt erhalten. Im Training lassen wir das letzte Token als Eingabe weg und verschieben die Ziele um eine Position.",
      formula: "Eingabe x = Tokens[:-1]\nZiel y = Tokens[1:]",
      takeaway: "Die Token-ID ist eine Adresse, kein Bedeutungswert. Token 4 ist nicht doppelt so viel wie Token 2.",
      code: 'ids = tokenizer.encode(text).ids\nx = ids[:-1]\ny = ids[1:]',
    },
    {
      title: "Für jedes Token ein Vektor",
      description: "Die ID wählt eine Zeile aus der lernbaren Embeddingmatrix E. So bekommt jede Tokenposition einen Vektor. Dasselbe Token startet an jeder Position mit demselben Token-Embedding.",
      formula: "eₜ = E[Token-IDₜ]",
      takeaway: "Das ist ein Nachschlagen in einer Matrix. Erst das Training passt die Einträge dieser Matrix an die Aufgabe an.",
      code: 'self.tok_emb = nn.Embedding(vocab_size, d_model)\ntoken_embeddings = self.tok_emb(idx)',
    },
    {
      title: "Die Position kommt hinzu",
      description: "Zu jedem Tokenvektor wird ein Positionsvektor addiert. In GuppyLM ist auch diese Tabelle lernbar. Erst die Summe trägt Tokenidentität und Position gemeinsam in den ersten Block.",
      formula: "xₜ = eₜ + P[t]",
      takeaway: "Die Position wird addiert. Sie ist keine zusätzliche Vektordimension und hier auch keine fest vorgegebene Sinuskurve.",
      code: 'pos = torch.arange(T, device=idx.device)\nx = self.tok_emb(idx) + self.pos_emb(pos)',
    },
    {
      title: "Attention verbindet Positionen",
      description: "Nach LayerNorm verarbeitet jeder Kopf den gesamten normalisierten Tokenvektor mit eigenen lernbaren Q-, K- und V-Projektionsmatrizen. Die farbigen Zeilenbereiche im gemeinsamen Projektionsblock zeigen diese eigenen Gewichte. Als mathematische Vereinfachung kann man die Matrizen stapeln, alle Projektionen gemeinsam berechnen und die Ergebnisse auf die Köpfe aufteilen. Das ist exakt gleichwertig und wird hier verwendet. Jeder Kopf berechnet anschließend seine Attention. Die Kopfoutputs werden aneinandergehängt, mit W_O projiziert und zum Eingang addiert.",
      formula: "Je Kopf h: Q_h = X̂ W_Q,hᵀ + b_Q,h; ebenso K_h, V_h\nA_h = softmax(Maske(Q_h K_hᵀ / √dₖ))\nH_h = A_h V_h\nBeitrag = Concat(H₁, H₂, H₃) W_Oᵀ + b_O\nDanach: Eingang x + Attention-Beitrag",
      takeaway: "Jeder Kopf hat eigene Projektionsgewichte und sieht alle bisherigen Tokenpositionen. Die gemeinsame Matrixoperation fasst diese Gewichte nur zusammen; sie werden nicht zwischen den Köpfen geteilt.",
      code: '# Eigene Kopfmatrizen sind in self.qkv gestapelt.\nqkv = self.qkv(x)  # mathematisch gleichwertige Zusammenfassung\nq, k, v = qkv.reshape(B, T, 3, n_heads, head_dim).permute(2, 0, 3, 1, 4)\ngewichte = softmax(maskiere(q @ k.transpose(-2, -1) / sqrt(head_dim)))\ny = concat(gewichte @ v)\ny = self.out(y)\nx = eingang + y',
    },
    {
      title: "Das FFN verarbeitet jede Position",
      description: "Auf den ersten Residualschritt folgen eine zweite LayerNorm und das Feed-Forward-Netz: verbreitern, GELU anwenden, zurück auf die Modellbreite. Dasselbe Netz mit denselben Gewichten wird auf jeden Tokenvektor einzeln angewendet. Dann folgt die zweite Residualaddition.",
      formula: "FFN(x̂) = GELU(x̂ W_hochᵀ + b_hoch) W_runterᵀ + b_runter\nx_neu = x + FFN(LayerNorm(x))",
      takeaway: "Zwischen Tokenpositionen mischt die Attention. Das FFN verändert die Merkmale innerhalb jeder Position. Beide Beiträge werden zum Residualstrom addiert.",
      code: 'x = x + self.attn(self.norm1(x), maske)\nx = x + self.ffn(self.norm2(x))\n\n# Innerhalb von FFN.forward:\nx = self.hoch(x)\nx = F.gelu(x, approximate="tanh")\nx = self.runter(x)',
    },
    {
      title: "Zwei Blöcke — je drei Köpfe",
      description: "Jeder große farbige Bereich ist ein vollständiger Transformer-Block: Er enthält Multi-Head-Attention mit drei parallelen Köpfen, ein FFN, zwei LayerNorms und zwei Residualadditionen. Block 1 und Block 2 werden nacheinander durchlaufen. Jeder Block hat eigene Gewichte.",
      formula: "X⁰ → [Block 1: 3 Köpfe + FFN] → X¹\nX¹ → [Block 2: 3 Köpfe + FFN] → X²",
      takeaway: "Blöcke sind Verarbeitungsschritte hintereinander. Köpfe sind parallele Berechnungswege innerhalb der Attention eines Blocks. Die Positions-Embeddings werden nur vor Block 1 addiert.",
      code: 'for block in self.blocks:\n    x = block(x, maske)',
    },
    {
      title: "Von Vektoren zu Tokenbewertungen",
      description: "Nach dem letzten Block folgt eine Abschlussnormierung. Die Ausgabeprojektion berechnet für jede Position einen Logit pro Vokabulartoken. In GuppyLM nutzt diese Projektion dieselbe Gewichtsmatrix wie das Token-Embedding.",
      formula: "Logits = LayerNorm(X²) Eᵀ",
      takeaway: "Ein Logit ist noch keine Wahrscheinlichkeit. Weight tying bedeutet: E wird am Eingang und am Ausgang verwendet und beim Lernen gemeinsam verändert.",
      code: 'self.lm_head.weight = self.tok_emb.weight\nlogits = self.lm_head(self.norm(x))',
    },
    {
      title: "Eine Verteilung über nächste Tokens",
      description: "Softmax macht aus den Logits eine Wahrscheinlichkeitsverteilung. An jeder Position lautet die Aufgabe: Welches Token kommt als Nächstes? Wähle eine Position, um ihre Verteilung zu sehen.",
      formula: "pᵢ = exp(Logitᵢ) / Σⱼ exp(Logitⱼ)",
      takeaway: "Im Training werden alle gültigen Positionen bewertet. Bei der Generierung entscheidet nur die Verteilung an der letzten Eingabeposition über das nächste Token.",
      code: '# Generierung: nur die letzte Position\nlogits = modell(idx)[0][:, -1, :]\nwahrscheinlichkeiten = F.softmax(logits, dim=-1)',
    },
  ];
  const generationStep = {
    title: "Ein Token anhängen — und von vorn",
    description: "Für diese Demonstration wählen wir das wahrscheinlichste Token an der letzten Position (Greedy). Es wird an den Kontext angehängt. Danach wird der gesamte Kontext wieder durch das Modell gerechnet. Dieser Vorwärtslauf verändert keine Gewichte.",
    formula: "Neuer Kontext = bisheriger Kontext + nächstes Token",
    takeaway: "Generieren ist wiederholtes Vorwärtsrechnen. Ein gewähltes Endtoken oder die Kontextgrenze beendet die Schleife.",
    code: 'naechstes = logits.argmax(dim=-1, keepdim=True)\nidx = torch.cat([idx, naechstes], dim=1)\n# Dann erneut modell(idx) — ohne backward() oder step().',
  };
  const trainingSteps = [
    {
      title: "Wie falsch war die Vorhersage?",
      description: "Die Zieltoken stehen bereits im Trainingsbeispiel. Für jede Position messen wir, wie viel Wahrscheinlichkeit das Modell dem richtigen nächsten Token gibt. Der Mittelwert dieser Einzelverluste ist unser Trainingsverlust.",
      formula: "Lₜ = −ln(pₜ[richtiges Token])\nL = Mittelwert aller gültigen Lₜ",
      takeaway: "Zum Berechnen des Verlusts wird kein Antworttoken ausgewürfelt. Alle richtigen Folgetokens sind als Ziele bekannt. Die kausale Maske verhindert, dass eine Position ihr späteres Zieltoken in der Eingabe sehen kann.",
      code: 'verlust = F.cross_entropy(\n    logits.view(-1, vocab_size),\n    ziele.reshape(-1),\n    ignore_index=pad_id,\n)',
    },
    {
      title: "Backpropagation: Wie wirkt jedes Gewicht?",
      description: "Ausgehend vom Verlust wird die Kettenregel rückwärts durch den Rechengraphen angewendet. Für jedes verwendete Gewicht entsteht eine Ableitung: Wie würde eine winzige Änderung dieses Gewichts den Verlust beeinflussen? Beiträge aus allen Tokenpositionen werden gesammelt.",
      formula: "Gradient g = ∂L / ∂w",
      takeaway: "Backward berechnet Gradienten und ändert noch keine Gewichte. Es läuft durch Ausgabe, alle Blöcke und Embeddings; Token-IDs und der BPE-Algorithmus werden dabei nicht optimiert.",
      code: 'verlust.backward()\n# In p.grad stehen jetzt die gesammelten Ableitungen.\n# Die Werte von p selbst sind noch unverändert.',
    },
    {
      title: "Erst jetzt ändern sich die Gewichte",
      description: "Der Optimierer verwendet die Gradienten für einen kleinen Schritt. Hier zeigt einfaches SGD die Grundidee unmittelbar: Lernrate mal Gradient abziehen. Im Notebook nutzt AdamW zusätzlich laufende Schätzungen von Gradienten und ihren Quadraten sowie Weight Decay.",
      formula: "Lehrmodell / SGD: w_neu = w_alt − η · ∂L/∂w",
      takeaway: "Ein positiver Gradient führt bei SGD zu einem kleineren Gewicht, ein negativer zu einem größeren. Danach beginnt ein neuer Vorwärtslauf. Ein einzelnes Update garantiert bei beliebiger Lernrate keine Verbesserung.",
      code: '# Notebook: Gradienten begrenzen, dann AdamW-Update\nclip_grad_norm_(modell.parameters(), GRAD_CLIP)\noptimierer.step()\noptimierer.zero_grad(set_to_none=True)',
    },
  ];

  function sequence() {
    return beispiele[state.example].map(t => vokabular.indexOf(t));
  }
  function refreshTrace() {
    const seq = sequence();
    const ids = state.mode === "training" || !state.generated ? seq.slice(0, -1) : state.generated;
    const targets = state.mode === "training" || !state.generated ? seq.slice(1) : undefined;
    trace = model.forward(ids, targets);
    state.position = Math.min(state.position, ids.length - 1);
  }
  function clearCycle() { state.gradients = null; state.lastUpdate = null; }
  function currentSteps() { return [...steps, ...(state.mode === "training" ? trainingSteps : [generationStep])]; }
  function stop() {
    if (state.timer) clearInterval(state.timer);
    state.timer = null;
    $("play").textContent = "▶ Abspielen";
    $("play").setAttribute("aria-pressed", "false");
  }

  function matrixIcon(x, y, name) {
    let out = `<rect class="weight-box" x="${x}" y="${y}" width="37" height="47" rx="4"/><text class="weight-label" x="${x + 18.5}" y="${y + 14}" text-anchor="middle">${name}</text>`;
    for (let row = 0; row < konfig.breite; row++) {
      const head = Math.floor(row / konfig.kopfbreite);
      for (let col = 0; col < konfig.breite; col++) out += `<rect class="matrix-cell head-color-${head}" x="${x + 5 + col * 4.5}" y="${y + 20 + row * 4}" width="3.5" height="${row % konfig.kopfbreite === konfig.kopfbreite - 1 ? 2 : 3}"/>`;
    }
    return out;
  }
  function headLegend(svg = false) {
    return Array.from({ length: konfig.koepfe }, (_, head) => svg
      ? `<rect class="head-color-${head}" x="${263 + head * 49}" y="177" width="7" height="7"/><text class="node-sub" x="${273 + head * 49}" y="184">Kopf ${head + 1}</text>`
      : `<span><i class="head-color-${head}" aria-hidden="true"></i>Kopf ${head + 1}${head === state.head ? " (gewählt)" : ""}</span>`).join("");
  }
  function node(stage, x, y, w, h, title, sub = "", extra = "", training = false, context = {}) {
    const selected = state.step === stage && (context.block === undefined || context.block === state.block)
      && (context.head === undefined || context.head === state.head)
      && (state.norm ? context.norm === state.norm : context.norm === undefined);
    const visited = state.mode !== "structure" && state.step > stage;
    const attrs = Object.entries(context).map(([key, value]) => `data-${key}="${value}"`).join(" ");
    const label = `${context.block === undefined ? "" : `Block ${context.block + 1}: `}${title}`;
    return `<g class="node ${selected ? "selected" : ""} ${visited ? "visited" : ""} ${training ? "training-node" : ""}" role="button" tabindex="0" aria-label="${escape(label)}" aria-pressed="${selected}" data-stage="${stage}" ${attrs}><rect class="box" x="${x}" y="${y}" width="${w}" height="${h}" rx="8"/><text class="node-title" x="${x + w / 2}" y="${y + (extra ? 22 : h / 2 - (sub ? 3 : -5))}" text-anchor="middle">${escape(title)}</text>${sub ? `<text class="node-sub" x="${x + w / 2}" y="${y + h / 2 + 16}" text-anchor="middle">${escape(sub)}</text>` : ""}${extra}</g>`;
  }
  function wire(d, active = false) { return `<path class="wire ${active ? "active-wire" : ""}" d="${d}"/>`; }
  function residualRoute(d, label, x, y, block, part) {
    const stage = part === "attention" ? 4 : 5;
    return `<g class="residual-route" role="button" tabindex="0" aria-label="Block ${block + 1}: Residualpfad ${part === "attention" ? "Attention" : "FFN"} erklären" data-stage="${stage}" data-block="${block}" data-residual="${part}"><path class="residual-hit" d="${d}"/><path class="residual-copy" d="${d}"/><text class="residual-label" x="${x}" y="${y}">${label}</text></g>`;
  }

  function blockDiagram(block) {
    const ctx = { block };
    const backwards = state.mode === "training" && state.step >= 10;
    let neurons = "";
    const layers = [[335, [454, 473]], [432, [445, 458, 471, 484]], [530, [454, 473]]];
    for (let l = 0; l < 2; l++) for (const a of layers[l][1]) for (const b of layers[l + 1][1]) neurons += `<line class="neuron-connection" x1="${layers[l][0]}" y1="${a}" x2="${layers[l + 1][0]}" y2="${b}"/>`;
    for (const [x, ys] of layers) for (const y of ys) neurons += `<circle class="neuron" cx="${x}" cy="${y}" r="4"/>`;
    const headY = [57, 122, 187];
    let svg = `<svg viewBox="0 0 860 650" role="group" aria-label="Block ${block + 1}: drei parallele Attention-Köpfe und ein FFN, mit zwei Residualpfaden">
      <rect class="sublayer-boundary" x="95" y="45" width="705" height="320" rx="10"/>
      <text class="sublayer-label" x="110" y="30">A · MULTI-HEAD-ATTENTION · 3 KÖPFE PARALLEL</text>
      <rect class="sublayer-boundary" x="95" y="410" width="705" height="160" rx="10"/>
      <text class="sublayer-label" x="110" y="398">B · FEED-FORWARD-NETZ · JE TOKENPOSITION</text>
      <text class="input-label" x="25" y="16">${block ? "Eingang x¹ aus Block 1" : "Eingang x⁰ = Token-Embedding + Positions-Embedding"}</text>
      ${wire("M65 32 V130 H109")}
      <circle class="split-junction" cx="65" cy="130" r="5"/>
      <text class="residual-label" x="28" y="115">x</text>
      ${wire("M225 132 H259")}
      ${wire("M410 132 H426 V83 H444")}
      ${wire("M410 132 H426 V148 H444")}
      ${wire("M410 132 H426 V213 H444")}
      ${wire("M595 83 H615 V146 H634")}
      ${wire("M595 148 H634")}
      ${wire("M595 213 H615 V146 H634")}
      ${wire("M710 176 V210")}${wire("M710 271 V299")}
      ${residualRoute("M65 130 V330 H634", "Unverändert weiterreichen: x", 110, 318, block, "attention")}
      ${node(4, 110, 105, 115, 54, "LayerNorm", "nur dieser Zweig", "", false, { ...ctx, norm: "attention" })}
      ${node(4, 260, 75, 150, 115, "Q/K/V-Projektionen", "", '<text class="node-sub" x="335" y="111" text-anchor="middle">aller Köpfe · eigene Gewichte</text>' + matrixIcon(271, 116, "W_Q") + matrixIcon(316, 116, "W_K") + matrixIcon(361, 116, "W_V") + headLegend(true), false, ctx)}
      <text class="small-label" x="335" y="209" text-anchor="middle">Je Farbe: 2 × 6 eigene Gewichte</text>
      <text class="small-label" x="335" y="225" text-anchor="middle">pro Kopf und Projektion</text>
      ${headY.map((y, head) => node(4, 445, y, 150, 52, `Kopf ${head + 1}`, "QKᵀ → Maske → A V", `<rect class="head-color-${head}" x="451" y="${y + 10}" width="5" height="32" rx="2"/>`, false, { block, head })).join("")}
      ${node(4, 635, 116, 150, 60, "Concat", "3 × 2 = 6 Komponenten", "", false, ctx)}
      ${node(4, 635, 211, 150, 60, "Projektion W_O", "Attention-Beitrag", "", false, ctx)}
      ${node(4, 635, 300, 150, 60, "+", "x + Attention-Beitrag", "", false, { block, residual: "attention" })}
      ${wire("M710 361 V382 H65 V452 H109")}
      <text class="small-label" x="305" y="376">z = Ergebnis der ersten Addition</text>
      <circle class="split-junction" cx="65" cy="452" r="5"/>
      <text class="residual-label" x="28" y="438">z</text>
      ${wire("M225 452 H299")}${wire("M570 452 H634")}
      ${residualRoute("M65 452 V548 H710 V486", "Unverändert weiterreichen: z", 110, 535, block, "ffn")}
      ${node(5, 110, 425, 115, 54, "LayerNorm", "nur dieser Zweig", "", false, { ...ctx, norm: "ffn" })}
      ${node(5, 300, 415, 270, 90, "FFN · 6 → 24 → 6", "", neurons, false, ctx)}
      ${node(5, 635, 425, 150, 60, "+", "z + FFN-Beitrag", "", false, { block, residual: "ffn" })}
      ${wire("M785 455 H820 V592 H430 V624")}
      <text class="output-label" x="430" y="645" text-anchor="middle">${block ? "Blockausgang x² → Abschlussnormierung" : "Blockausgang x¹ → Eingang von Block 2"}</text>`;
    if (backwards) svg += `<path class="backward-path moving" d="M15 610 V45"/><text class="small-label" style="fill:var(--orange)" x="35" y="600">Gradienten rückwärts durch diesen Block</text>`;
    if (state.mode !== "structure" && state.block === block) {
      if (state.step === 4) svg += `<path class="data-flow" d="M65 32 V130 H109 M225 132 H259 M410 132 H426 V${headY[state.head] + 26} H444 M595 ${headY[state.head] + 26} H615 V146 H634 M710 176 V210 M710 271 V299"/>`;
      if (state.step === 5) svg += `<path class="data-flow" d="M710 361 V382 H65 V452 H109 M225 452 H299 M570 452 H634"/>`;
    }
    svg += "</svg>";
    return `<section class="transformer-block block-${block + 1} ${state.block === block && state.step >= 4 && state.step <= 6 ? "focused-block" : ""}" data-block-card="${block}" id="block-${block}">
      <header class="block-heading"><button class="block-title" data-stage="6" data-block="${block}"><span class="block-number">${block + 1}</span><span>Transformer-Block ${block + 1}</span></button><span class="block-membership">3 Attention-Köpfe + 1 FFN</span></header>
      <p class="block-definition">Der gesamte farbige Bereich ist <strong>ein Block</strong>. Seine drei Köpfe gehören zur Attention und rechnen parallel.</p>
      ${svg}
    </section>`;
  }

  function diagram() {
    const training = state.mode === "training";
    const backwards = training && state.step >= 10;
    const defs = `<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#79939e"/></marker><marker id="residual-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#316ca9"/></marker><marker id="gradient-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#b55319"/></marker></defs>`;
    const connector = label => `<div class="between-blocks"><span>↓ ${label}</span>${backwards ? '<span class="gradient-return">↑ Gradienten</span>' : ""}</div>`;
    let html = `<section class="map-section preparation" id="map-preparation"><h3>Vorbereitung: Text wird zu Vektoren</h3><p>Diese Schritte stehen vor den Transformer-Blöcken.</p><svg viewBox="0 0 860 160" role="group" aria-label="Text, Tokenisierung und Embeddings vor dem ersten Transformer-Block">${defs}
      ${wire("M180 57 H219")}${wire("M395 57 H434")}${wire("M610 57 H644")}
      ${node(0, 20, 25, 160, 65, "Text", trace.ids.map(id => vokabular[id]).join(" ").slice(0, 23))}
      ${node(1, 220, 25, 175, 65, "Tokenisierung", "Textstücke → IDs")}
      ${node(2, 435, 25, 175, 65, "Token-Embedding", "ID → Vektor · E")}
      ${node(3, 645, 25, 195, 65, "+ Positions-Embedding", "Summe ergibt x⁰")}
      ${wire("M742 91 V119 H430 V150")}
      ${backwards ? '<path class="backward-path moving" d="M522 150 V91"/><path class="backward-path moving" d="M742 150 V91"/>' : ""}
      ${state.mode !== "structure" && state.step > 0 && state.step < 4 ? `<path class="data-flow" d="${["", "M180 57 H219", "M395 57 H434", "M610 57 H644"][state.step]}"/>` : ""}
      </svg></section>`;
    for (let block = 0; block < konfig.bloecke; block++) {
      html += connector(block ? "Vektoren aus Block 1 werden weiterverarbeitet" : "x⁰: ein Vektor mit 6 Komponenten pro Tokenposition");
      html += blockDiagram(block);
    }
    html += connector("Ausgang aus Block 2");
    html += `<section class="map-section output-section" id="map-output"><h3>Ausgabe${training ? " und Trainingsschritt" : " und nächstes Token"}</h3><svg viewBox="0 0 860 280" role="group" aria-label="Vom letzten Block zur Vorhersage${training ? ', zum Verlust und zum Gewichtsupdate' : ''}">
      ${wire("M430 0 V30 H107 V49")}
      ${node(7, 20, 50, 175, 65, "LayerNorm", "Abschluss", "", false, { norm: "final" })}
      ${wire("M195 82 H234")}${node(7, 235, 50, 175, 65, "Ausgabe · Eᵀ", "Vektor → Logits")}
      ${wire("M410 82 H449")}${node(8, 450, 50, 175, 65, "Softmax", "Logits → p(Token)")}
      ${wire("M625 82 H664")}${node(9, 665, 50, 175, 65, training ? "Verlust L" : "Token auswählen", training ? "mit Zielen vergleichen" : "z. B. Greedy", "", training)}
      ${training ? `${wire("M752 116 V192 H625")}${node(10, 450, 160, 175, 65, "Backward", "Gradienten berechnen", "", true)}${wire("M450 192 H410")}${node(11, 235, 160, 175, 65, "Optimierer", "Gewichte ändern", "", true)}<text class="small-label" x="20" y="256">Vorwärtslauf → Verlust → Gradienten → Gewichtsupdate → neuer Vorwärtslauf</text>`
        : `${wire("M752 116 V192 H625")}${node(9, 450, 160, 175, 65, "Token anhängen", "erneut vorwärts rechnen")}<text class="small-label" x="20" y="256">Neuer Kontext → Tokenisierung / IDs → Embeddings → beide Blöcke → nächste Vorhersage</text>`}
      ${backwards ? '<path class="backward-path moving" d="M752 50 V15 H430 V1"/>' : ""}
      </svg></section>`;
    $("diagram").innerHTML = html;
  }

  function tokenRow(ids, targets = false, interactive = false) {
    return `<div class="token-row">${ids.map((id, t) => interactive
      ? `<button class="token ${t === state.position ? "selected" : ""}" data-position="${t}" aria-pressed="${t === state.position}">${escape(vokabular[id])}<small>Position ${t}</small></button>`
      : `<span class="token ${targets ? "target" : ""}">${escape(vokabular[id])}<small>ID ${id} · Pos. ${t}</small></span>`).join("")}</div>`;
  }
  function positionControl() { return `<div class="mini-label">Untersuchte Eingabeposition</div>${tokenRow(trace.ids, false, true)}`; }
  function blockControl(includeHead = false) {
    return `<div class="control-row"><label>Block <select id="block-select">${Array.from({ length: konfig.bloecke }, (_, i) => `<option value="${i}" ${i === state.block ? "selected" : ""}>${i + 1}</option>`).join("")}</select></label>${includeHead ? `<label>Kopf in diesem Block <select id="head-select">${Array.from({ length: konfig.koepfe }, (_, i) => `<option value="${i}" ${i === state.head ? "selected" : ""}>${i + 1}</option>`).join("")}</select></label>` : ""}</div><p class="help">Block ${state.block + 1} ist die große farbige Einheit. ${includeHead ? `Kopf ${state.head + 1} ist einer ihrer drei parallelen Attention-Köpfe.` : "Er umfasst die gesamte Attention, das FFN, Normierungen und Residualadditionen."}</p>`;
  }
  function vectors(rows, labels = null, columns = null) {
    const tokenRows = labels === null;
    labels = labels || trace.ids.map(id => vokabular[id]);
    const numbers = werte(rows);
    columns = columns || Array.from({ length: numbers[0].length }, (_, i) => `d${i}`);
    return `<div class="table-scroll"><table class="data-table"><thead><tr><th>Token / Vektor</th>${columns.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>${numbers.map((row, t) => `<tr class="${tokenRows && t === state.position ? "selected-row" : ""}"><td>${escape(labels[t])}</td>${row.map(v => `<td>${fmt(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  function probabilities(position) {
    const probs = werte(trace.wahrscheinlichkeiten[position]);
    const target = trace.ziele?.[position];
    const order = probs.map((p, id) => ({ p, id })).sort((a, b) => b.p - a.p);
    return order.map(({ p, id }) => `<div class="bar-row ${id === target && state.mode === "training" ? "correct" : ""}"><span>${escape(vokabular[id])}</span><div class="bar-track"><div class="bar-fill" style="width:${100 * p}%"></div></div><span>${fmt(p * 100, 1)} %</span></div>`).join("");
  }
  function heatmap(head) {
    const a = werte(head.gewichte);
    return `<div class="table-scroll"><table class="data-table heatmap"><thead><tr><th>Query ↓ / Key →</th>${trace.ids.map((id, t) => `<th>${t}: ${escape(vokabular[id])}</th>`).join("")}</tr></thead><tbody>${a.map((row, t) => `<tr><th>${t}: ${escape(vokabular[trace.ids[t]])}</th>${row.map((v, j) => j > t ? '<td class="masked" title="Zukünftige Position: vor Softmax auf −∞ maskiert">0</td>' : `<td style="background:rgba(9,109,120,${0.08 + v * .65});color:${v > .7 ? "white" : "var(--ink)"}" title="Attentiongewicht ${v}">${fmt(v, 2)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  function tinyMatrix(rows, name) {
    return `<div><div class="stage-badge">${name} · ${rows.length} × ${rows[0].length}</div><div class="matrix-preview" style="grid-template-columns:repeat(${rows[0].length},1fr)">${werte(rows).map((row, r) => row.map((v, c) => {
      const head = Math.floor(r / konfig.kopfbreite);
      return `<span class="head-color-${head}${head === state.head ? " chosen-head" : ""}" style="opacity:${.45 + Math.min(Math.abs(v) * 3, .55)};${r > 0 && r % konfig.kopfbreite === 0 ? "margin-top:4px;" : ""}" title="${name} · Kopf ${head + 1} · Ausgabe ${r % konfig.kopfbreite + 1}, Eingabe ${c + 1}: ${fmt(v, 4)}"></span>`;
    }).join("")).join("")}</div></div>`;
  }
  function network() {
    const counts = [konfig.breite, 8, konfig.breite], xs = [45, 175, 305];
    const y = (n, i) => 22 + (i + .5) * 88 / n;
    let s = '<svg class="network-detail" viewBox="0 0 350 140" role="img" aria-label="FFN: sechs Eingaben, 24 versteckte Einheiten auszugsweise dargestellt, sechs Ausgaben">';
    for (let l = 0; l < 2; l++) for (let a = 0; a < counts[l]; a++) for (let b = 0; b < counts[l + 1]; b++) s += `<line x1="${xs[l]}" y1="${y(counts[l], a)}" x2="${xs[l + 1]}" y2="${y(counts[l + 1], b)}"/>`;
    for (let l = 0; l < 3; l++) {
      for (let i = 0; i < counts[l]; i++) s += `<circle cx="${xs[l]}" cy="${y(counts[l], i)}" r="4"/>`;
      s += `<text x="${xs[l]}" y="131" text-anchor="middle">${["6", "24 (Auszug)", "6"][l]}</text>`;
    }
    return s + "</svg>";
  }

  function ensureGradients() {
    if (state.gradients) return;
    state.gradients = model.backward(trace);
  }
  function gradientGroups() {
    ensureGradients();
    const groups = new Map();
    for (const p of state.gradients) groups.set(p.gruppe, (groups.get(p.gruppe) || 0) + p.gradient ** 2);
    const norms = [...groups.entries()].map(([name, sum]) => ({ name, norm: Math.sqrt(sum) }));
    const max = Math.max(...norms.map(g => g.norm), 1e-9);
    return norms.map(({ name, norm }) => `<div class="bar-row" style="grid-template-columns:125px 1fr 50px"><span>${escape(name)}</span><div class="bar-track"><div class="bar-fill" style="background:var(--orange);width:${100 * norm / max}%"></div></div><span>${fmt(norm)}</span></div>`).join("");
  }
  function historyPlot() {
    if (state.history.length < 2) return "";
    const lo = Math.min(...state.history), hi = Math.max(...state.history);
    const points = state.history.map((v, i) => `${i ? "L" : "M"}${5 + i / (state.history.length - 1) * 310},${55 - (v - lo) / Math.max(hi - lo, .001) * 45}`).join(" ");
    return `<div class="mini-label">Verlust auf diesem Beispiel nach jedem Update</div><svg class="sparkline" viewBox="0 0 320 65" role="img" aria-label="Verlustverlauf: ${state.history.map(x => fmt(x)).join(', ')}"><path d="${points}"/></svg>`;
  }
  function updateTable() {
    ensureGradients();
    const top = [...state.gradients].sort((a, b) => Math.abs(b.gradient) - Math.abs(a.gradient)).slice(0, 5);
    const applied = !!state.lastUpdate;
    return `<div class="mini-label">Fünf Gewichte mit größtem |Gradient|</div><div class="table-scroll"><table class="data-table"><thead><tr><th>Gewicht</th><th>vorher</th><th>∂L/∂w</th><th>${applied ? "nachher" : "geplant"}</th></tr></thead><tbody>${top.map(p => `<tr><td>${escape(p.name)}</td><td>${fmt(p.vorher, 4)}</td><td>${fmt(p.gradient, 4)}</td><td>${fmt(p.vorher - (state.lastUpdate?.lr ?? state.lr) * p.gradient, 4)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function residualExplanation(part) {
    const b = trace.bloecke[state.block], t = state.position;
    const attention = part === "attention";
    const input = attention ? b.eingang[t] : b.residual1[t];
    const contribution = attention ? b.attention[t] : b.ffn[t];
    const output = attention ? b.residual1[t] : b.ausgang[t];
    const symbol = attention ? "x" : "z";
    const name = attention ? "Attention" : "FFN";
    return `${blockControl()}${positionControl()}<div class="residual-explanation"><h3>Ein Eingang, zwei Wege, eine Addition</h3>
      <p>Am blauen Punkt geht <strong>derselbe vollständige Vektor ${symbol}</strong> in zwei Wege. Das ist keine Aufteilung auf Köpfe und kein eigener Transformer-Block.</p>
      <svg class="residual-detail" viewBox="0 0 600 220" role="img" aria-label="Der vollständige Eingang mit sechs Komponenten geht unverändert auf dem blauen Weg zum Pluszeichen. Der zweite Weg führt über LayerNorm und ${name}, liefert ebenfalls sechs Komponenten und wird dort addiert.">
        <text x="15" y="27">Eingang ${symbol} · 6 Komponenten</text>
        <path class="copy-line" d="M20 58 H475"/><circle cx="100" cy="58" r="5" class="copy-dot"/>
        <text x="170" y="46">unverändert · Identitätsweg</text>
        <path class="branch-line" d="M100 58 V120 H135 M255 120 H295 M445 120 H490 V74"/>
        <rect x="135" y="97" width="120" height="46" rx="7"/><text x="195" y="125" text-anchor="middle">LayerNorm</text>
        <rect x="295" y="97" width="150" height="46" rx="7"/><text x="370" y="125" text-anchor="middle">${name === "Attention" ? "Köpfe + W_O" : "FFN"}</text>
        <text x="295" y="165">Beitrag · 6 Komponenten</text>
        <circle cx="490" cy="58" r="16"/><text x="490" y="64" text-anchor="middle" class="plus-label">+</text>
        <path class="branch-line" d="M506 58 H580"/><text x="540" y="27" text-anchor="middle">Ausgang y</text>
        <text x="15" y="204">Je Tokenposition: 6 + 6 → 6 Komponenten · keine Verkettung</text>
      </svg>
      <div class="residual-equation"><span>blauer Weg: ${symbol} unverändert</span><b>+</b><span>Berechnungsweg: ${name}(LayerNorm(${symbol}))</span></div>
      <p>Die blaue Verbindung enthält <strong>keine LayerNorm und keine lernbare Matrix</strong>. Sie bringt den Eingang unverändert zum Pluszeichen. Der andere Weg berechnet den neuen Beitrag. Das Plus addiert beide Vektoren komponentenweise.</p>
      <div class="formula">Komponente 0: ${fmt(input[0].wert)} + (${fmt(contribution[0].wert)}) = ${fmt(output[0].wert)}</div>
      ${attention ? state.block === 0 ? '<p>In Block 1 ist x bereits die <strong>Summe aus Token- und Positions-Embedding</strong>. Die blaue Spur transportiert also diese ganze Summe; sie addiert die Position nicht ein zweites Mal.</p>' : '<p>In Block 2 ist x der <strong>Ausgang von Block 1</strong>. Dieser Vektor wird unverändert weitergereicht. Die Positions-Embeddings werden hier nicht erneut addiert.</p>' : '<p>Hier ist z bereits das Ergebnis der ersten Residualaddition. Es wird am FFN vorbeigeführt und um dessen Beitrag ergänzt.</p>'}
      </div><div class="mini-label">Die tatsächliche Addition · Position ${t} · Block ${state.block + 1}</div>
      ${vectors([input, contribution, output], [`${symbol} unverändert`, `${name}-Beitrag`, "Summe am +"])}
      <p class="help">Alle drei Zeilen haben 6 Komponenten. ${attention ? "Die Attention liefert hier bereits das Ergebnis aus allen drei Köpfen nach der Ausgabeprojektion W_O. Ihre Attentiongewichte können Informationen aus allen bisher sichtbaren Tokenpositionen einbeziehen." : "Das FFN liefert nach der Projektion von 24 zurück auf 6 Dimensionen seinen Beitrag. Es verarbeitet jede Tokenposition einzeln."} Die Addition am Pluszeichen erfolgt dann für jede Position und jede Dimension einzeln. Im Lehrmodell gibt es zwei solche Additionen pro Block, insgesamt vier.</p>
      <h3>1 · Beim Training: Änderungen leichter lernen</h3>
      <p class="help">Der Berechnungszweig lernt einen Beitrag zum bisherigen Zustand. Ein Beitrag nahe null lässt den Eingang nahezu unverändert passieren. Das erleichtert es, eine bereits brauchbare Darstellung beizubehalten und schrittweise anzupassen. Eine Initialisierung mit kleinen Zweigoutputs kann diesen Start nahe der Identität unterstützen. Der Residualpfad allein garantiert aber keine kleinen Anfangsoutputs; das hängt von der Initialisierung ab.</p>
      <p class="help">Auch beim Rückwärtsrechnen teilt sich das Signal am Pluszeichen auf: Der ankommende Gradient wird an beide Eingänge der Addition weitergegeben. Auf dem blauen Weg muss er keine LayerNorm oder Gewichtsmatrix dieses Zweigs durchlaufen. Dieser direkte Weg erleichtert die Optimierung tiefer Netze und wirkt dem Schwinden von Gradienten entgegen.</p>
      <details><summary>Warum taucht bei der Ableitung eine 1 auf?</summary>
        <div class="formula">Y = X + F(X)
∂Y / ∂X = I + J_F(X)
Gradient am Eingang = G + J_F(X)ᵀ G</div>
        <p class="help">F steht für den gesamten Berechnungszweig einschließlich LayerNorm. X und Y bezeichnen hier die gesamte Tokensequenz mit jeweils 6 Komponenten pro Position, G den vom weiteren Netz kommenden Gradienten. I ist die Identitätsmatrix: Die Ableitung einer unverändert weitergereichten Komponente nach sich selbst ist 1. J_F enthält die Ableitungen des Zweigs. Der direkte Beitrag G wird zum Beitrag aus diesem Zweig addiert. Dadurch gibt es einen kurzen Gradientenweg; der Gesamtgradient kann durch die Summe trotzdem kleiner oder größer werden. Residualverbindungen garantieren daher weder unveränderte Gradienten durch das ganze Netz noch eine vollständig stabile Optimierung.</p>
      </details>
      <h3>2 · Bei der Inferenz: Zustand und Beitrag kombinieren</h3>
      <p class="help">Beim Generieren wird dieselbe Addition ausgeführt; es werden dabei keine Gradienten berechnet. Der bisherige Zustand erreicht das Pluszeichen direkt und wird mit dem neuen Beitrag kombiniert. In Block 1 enthält dieser Zustand Token- und Positions-Embedding, später bereits die Ergebnisse vorheriger Berechnungen. Die Addition bewahrt einen direkten Informationsweg, garantiert aber keinen unveränderten „Bedeutungskern“: Der gelernte Beitrag kann Komponenten verstärken, abschwächen oder sogar aufheben. Attention kann mehr als eine kleine Kontextnuance beitragen.</p>
      <div class="formula">Falls der Beitrag 0 ist: y = ${symbol} + 0 = ${symbol}
Falls der Beitrag klein ist: y ≈ ${symbol}</div>
      <p class="help">Ein Zweig kann also wenig zur aktuellen Darstellung beitragen. Das ist kein tatsächliches Überspringen der Schicht: LayerNorm und ${name} werden hier weiterhin berechnet. Erst ein Modell mit einem zusätzlichen Mechanismus zum Auslassen von Berechnungen könnte dadurch Rechenarbeit sparen.</p>
      <button class="secondary" id="show-calculation">${name}-Berechnung ansehen →</button>`;
  }

  function layerNormData() {
    const t = state.position, b = trace.bloecke[state.block];
    const final = state.norm === "final", attention = state.norm === "attention";
    const input = final ? trace.bloecke.at(-1).ausgang[t] : attention ? b.eingang[t] : b.residual1[t];
    const parameters = final ? model.norm : attention ? model.bloecke[state.block].norm1 : model.bloecke[state.block].norm2;
    const output = final ? trace.normFinal[t] : attention ? b.norm1[t] : b.norm2[t];
    const x = werte(input), gamma = werte(parameters.gamma), beta = werte(parameters.beta);
    const stats = values => {
      const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
      return { mean, variance: values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length };
    };
    const { mean, variance } = stats(x), epsilon = 1e-5;
    const denominator = Math.sqrt(variance + epsilon);
    const normalized = x.map(v => (v - mean) / denominator);
    return { x, gamma, beta, output: werte(output), mean, variance, epsilon, denominator, normalized,
      normalizedStats: stats(normalized), outputStats: stats(werte(output)),
      firstInput: attention && state.block === 0,
      location: final ? "Abschluss nach Block 2" : `Block ${state.block + 1} · vor ${attention ? "Attention" : "FFN"}` };
  }

  function layerNormExplanation() {
    const d = layerNormData(), t = state.position, width = d.x.length;
    const next = state.norm === "attention" ? "Attention" : state.norm === "ffn" ? "FFN" : "Ausgabe";
    return `${state.norm === "final" ? "" : blockControl()}${positionControl()}
      <div class="mini-label">${d.location} · Token „${escape(vokabular[trace.ids[t]])}“ · Position ${t}</div>
      <h3>1 · Woher kommt der Vektor?</h3>
      ${d.firstInput ? `<p class="help">Die Token-ID wählt einen ${width}-dimensionalen Vektor aus der gelernten Embeddingtabelle. Dazu addieren wir das ebenfalls gelernte Positions-Embedding. Das Ergebnis hat weiterhin ${width} Komponenten. Die Zahlen stammen aus dem aktuellen Lehrmodell; die einzelnen Dimensionen haben hier keine vorgegebenen Bedeutungen.</p>${vectors([trace.embeddings[t], trace.positionen[t], trace.start[t]], ["Token-Embedding", "+ Positions-Embedding", "= Eingang x⁰"])}`
        : `<p class="help">${state.norm === "final" ? "Hier kommt der Eingang aus dem letzten Transformer-Block." : state.norm === "attention" ? "Hier kommt der Eingang aus Block 1." : "Hier kommt der Eingang aus der ersten Residualaddition: Blockeingang plus Attention-Beitrag."} Er enthält bereits die bisher verarbeiteten Token- und Positionsinformationen. Es wird kein weiteres Positions-Embedding addiert.</p>`}
      <h3>2 · Mittelwert und Varianz berechnen</h3>
      <p class="help">LayerNorm betrachtet nur die ${width} Komponenten dieser einen Tokenposition. Sie mittelt weder über Tokens noch über Köpfe oder den Batch. Für jede Tokenposition wird dieselbe Rechnung mit deren eigenen Werten ausgeführt.</p>
      <div class="formula">x = [${d.x.map(v => fmt(v, 4)).join("; ")}]
μ = (${d.x.map(v => `(${fmt(v, 4)})`).join(" + ")}) / ${width} = ${fmt(d.mean, 6)}
σ² = Σᵢ (xᵢ − μ)² / ${width} = ${fmt(d.variance, 6)}
ε = 0,00001
√(σ² + ε) = ${fmt(d.denominator, 6)}</div>
      <h3>3 · Zentrieren und skalieren</h3>
      <p class="help">Von jeder Komponente wird derselbe Mittelwert abgezogen. Anschließend teilen wir durch dieselbe stabilisierte Standardabweichung. ε hält den Nenner auch bei einem konstanten Eingabevektor größer als null.</p>
      <div class="formula">zᵢ = (xᵢ − μ) / √(σ² + ε)
Beispiel d0: (${fmt(d.x[0], 6)} − (${fmt(d.mean, 6)})) / ${fmt(d.denominator, 6)} = ${fmt(d.normalized[0], 6)}</div>
      <h3>4 · Lernbare Skalierung und Verschiebung</h3>
      <p class="help">Die reine Normalisierung z entspricht γ = 1 und β = 0. Die tatsächliche LayerNorm verwendet danach pro Dimension eigene lernbare Werte: ${width} Werte für γ und ${width} für β, insgesamt ${2 * width} Parameter dieser Normierung. Dieselben Parameter gelten an allen Tokenpositionen. Jede LayerNorm im Modell hat ihren eigenen Parametersatz. Zu Beginn gilt γ = 1 und β = 0; Training kann das ändern.</p>
      <div class="formula">yᵢ = γᵢ · zᵢ + βᵢ</div>
      <div class="table-scroll"><table class="data-table"><thead><tr><th>Dimension</th><th>Eingang x</th><th>nur normiert z</th><th>γ</th><th>β</th><th>Ausgang y</th></tr></thead><tbody>${d.x.map((v, i) => `<tr><td>d${i}</td><td>${fmt(v, 4)}</td><td>${fmt(d.normalized[i], 4)}</td><td>${fmt(d.gamma[i], 4)}</td><td>${fmt(d.beta[i], 4)}</td><td>${fmt(d.output[i], 4)}</td></tr>`).join("")}</tbody></table></div>
      <h3>Was hat sich verändert?</h3>
      <p class="help">Der Vektor bleibt ${width}-dimensional. Bei z ist der Mittelwert bis auf Rundungsfehler 0. Seine Varianz ist σ² / (σ² + ε), also bei positiver Eingangsvarianz etwas kleiner als 1. Bei konstantem Eingang ist sie 0. Mit gelernten γ- und β-Werten muss der tatsächliche Ausgang y weder Mittelwert 0 noch Varianz 1 haben.</p>
      <div class="formula">Nur normiert z: Mittelwert ${fmt(d.normalizedStats.mean, 6)} · Varianz ${fmt(d.normalizedStats.variance, 6)}
Tatsächlicher Ausgang y: Mittelwert ${fmt(d.outputStats.mean, 6)} · Varianz ${fmt(d.outputStats.variance, 6)}</div>
      <p class="help">Vor γ und β bleibt die Reihenfolge der Komponenten erhalten. Ihre Abstände werden alle durch denselben Wert geteilt, bleiben also proportional, aber nicht unverändert. Eine Zahl unter dem ursprünglichen Mittelwert wird negativ, eine darüber positiv. Diese kontrollierte Skalierung unterstützt stabiles Lernen. Alle Anzeigen sind gerundet; gerechnet wird mit ungerundeten Werten.</p>
      ${state.norm === "final" ? '<p class="help">Der Ausgang geht in die Ausgabeprojektion für die Logits.</p>' : '<p class="help">Der normalisierte Ausgang geht nur in den Berechnungszweig. Der blaue Residualpfad reicht den Eingang unverändert weiter.</p>'}
      <button class="secondary" id="show-calculation">${next}-Berechnung ansehen →</button>`;
  }

  function content() {
    if (state.norm) return layerNormExplanation();
    const t = state.position;
    const b = trace.bloecke[state.block];
    switch (state.step) {
      case 0:
        return `<div class="mini-label">Ein vollständiges Lehrbeispiel</div><div class="token-loop">${escape(beispiele[state.example].join(" "))}</div><p class="help">Hier ist die Tokenzerlegung absichtlich vorgegeben. Die fertige <a href="tokenizer-werkbank.html">BPE-Werkbank</a> zeigt, wie ein echtes Vokabular entsteht. Im Notebook enthalten die Texte zusätzlich ChatML-Rollenmarkierungen.</p><div class="mini-label">Zwei verschiedene Lernvorgänge</div><p class="help"><b>Tokenizertraining:</b> Textstücke und IDs festlegen.<br><b>Modelltraining:</b> Vorhersagen verbessern, indem Gewichte verändert werden.</p>`;
      case 1:
        return `<div class="mini-label">Eingabe x</div>${tokenRow(trace.ids)}${trace.ziele ? `<div class="mini-label">Ziel y — genau eine Position voraus</div>${tokenRow(trace.ziele, true)}<p class="help">An Position 0 steht „${escape(vokabular[trace.ids[0]])}“. Dort soll „${escape(vokabular[trace.ziele[0]])}“ vorhergesagt werden. Die Tokenfolge ist vollständig bekannt, spätere Positionen werden aber maskiert.</p>` : '<p class="help">Bei der Generierung sind die richtigen Folgetokens unbekannt. Es gibt keine Zielzeile und keinen Trainingsverlust.</p>'}`;
      case 2:
        return `${positionControl()}<span class="stage-badge">E: 8 Tokens × 6 Dimensionen · lernbar</span>${vectors(trace.embeddings)}<p class="help">Gezeigt sind die tatsächlich nachgeschlagenen Zeilen von E. Das Notebook verwendet die gemessene BPE-Vokabulargröße × 384 Dimensionen.</p>`;
      case 3:
        return `${positionControl()}<div class="mini-label">Addition an Position ${t}</div>${vectors([trace.embeddings[t], trace.positionen[t], trace.start[t]], ["Token e", "Position P", "Summe x⁰"])}<span class="stage-badge">P: 8 Positionen × 6 Dimensionen · lernbar</span><p class="help">Die Zahl der Vektorkomponenten bleibt 6. Die Summe x⁰ geht in Block 1 sowohl in den Berechnungsweg als auch unverändert in den blauen Residualpfad.</p><button class="secondary" data-explain-residual="attention" data-explain-block="0">Warum führen zwei Wege zum Pluszeichen?</button>`;
      case 4: {
        if (state.residual === "attention") return residualExplanation("attention");
        const h = b.heads[state.head];
        const weights = model.bloecke[state.block].qkv;
        const q = werte(h.q[t]), k = werte(h.k[t]);
        const score = werte(h.scores[t][t]);
        return `${blockControl(true)}<button class="secondary" data-explain-residual="attention">Blauen Residualpfad und Pluszeichen erklären</button><div class="qkv-grid">${tinyMatrix(weights.slice(0, 6), "W_Q")}${tinyMatrix(weights.slice(6, 12), "W_K")}${tinyMatrix(weights.slice(12, 18), "W_V")}</div><div class="head-legend">${headLegend()}</div><p class="help">Jede Farbe markiert die eigenen Gewichte eines Kopfes: je eine Q-, K- und V-Matrix mit <strong>2 × 6</strong> Einträgen (Ausgabe × Eingabe). Jede ihrer beiden Zeilen verarbeitet alle 6 Eingabekomponenten. Die Farben entsprechen den Köpfen in der Grafik.</p><details><summary>Mathematische Vereinfachung: gemeinsam projizieren</summary><p class="help">Man kann nach LayerNorm für jeden Kopf separat Q, K und V berechnen. Mathematisch exakt gleichwertig ist es, die drei Kopfmatrizen je Projektion untereinander zu einer <strong>6 × 6</strong>-Matrix zu stapeln. Auch diese drei Matrizen lassen sich zu einer <strong>18 × 6</strong>-Matrix zusammenfassen: im Notebook <code>qkv.weight</code>. Die Biasvektoren werden ebenso zusammengefasst. Diese Werkbank verwendet die gemeinsame Berechnung und teilt danach Q, K und V in je 2 Komponenten pro Kopf auf. Das vereinfacht die Berechnung, ohne Parameter einzusparen oder Gewichte zwischen Köpfen zu teilen.</p><div class="formula">W_Q = Stapel(W_Q,1; W_Q,2; W_Q,3)
Q = X̂ W_Qᵀ + b_Q = Concat(Q₁, Q₂, Q₃)
Ebenso für K und V.</div></details>${positionControl()}<div class="mini-label">Q, K und V · Block ${state.block + 1} · Kopf ${state.head + 1}</div>${vectors([h.q[t], h.k[t], h.v[t]], ["Query", "Key", "Value"], ["d₀", "d₁"])}<details><summary class="help">Eine Scoreberechnung nachvollziehen</summary><div class="formula">Score(${t}, ${t}) = (${fmt(q[0])} × ${fmt(k[0])} + ${fmt(q[1])} × ${fmt(k[1])}) / √2 = ${fmt(score)}</div><p class="help">Beispiel: Query und Key derselben Position. Für jede andere sichtbare Position wird derselbe Rechenweg mit deren Key verwendet.</p></details><div class="mini-label">Attentiongewichte nach kausaler Maske und Softmax</div>${heatmap(h)}<p class="help">Jede Zeile summiert sich zu 1. Schraffierte Felder liegen in der Zukunft und erhalten Gewicht 0. Der Kopfoutput ist die so gewichtete Summe der Value-Vektoren.</p><div class="mini-label">Von den Köpfen zurück zum Residualstrom · Position ${t}</div>${vectors([b.concat[t], b.attention[t], b.residual1[t]], ["Concat H₁, H₂, H₃", "Projektion W_O", "+ Eingang x"])} `;
      }
      case 5:
        if (state.residual === "ffn") return residualExplanation("ffn");
        return `${blockControl()}<button class="secondary" data-explain-residual="ffn">Blauen Residualpfad und Pluszeichen erklären</button>${positionControl()}${network()}<p class="help">Kreise stehen für skalare Einheiten. In der Mitte sind 8 von 24 dargestellt. Verbindungen stehen für lernbare Gewichte. Diese Skizze ist ein Auszug des FFN.</p><div class="mini-label">Position ${t}: vor und nach FFN-Beitrag</div>${vectors([b.norm2[t], b.ffn[t], b.ausgang[t]], ["nach Normierung", "FFN-Beitrag", "+ Residualstrom"])}<div class="mini-label">Die ersten 4 von 24 versteckten Einheiten</div>${vectors([b.hoch[t].slice(0, 4), b.aktiviert[t].slice(0, 4)], ["vor GELU", "nach GELU"])}`;
      case 6:
        return `<div class="table-scroll"><table class="data-table"><thead><tr><th>Begriff</th><th>Hier im Lehrmodell</th></tr></thead><tbody><tr><td>Transformer-Block</td><td>2 nacheinander</td></tr><tr><td>Attention-Köpfe</td><td>3 parallel pro Block</td></tr><tr><td>Was gehört in einen Block?</td><td>Attention + FFN + Normierungen + Residualpfade</td></tr></tbody></table></div>${positionControl()}<div class="mini-label">Derselbe Tokenvektor durch beide Blöcke</div>${vectors([trace.start[t], ...trace.bloecke.map(block => block.ausgang[t])], ["vor Block 1", "nach Block 1", "nach Block 2"])}<p class="help">Die Zeilen zeigen dieselbe Tokenposition vor und nach den beiden Blöcken. Die beiden Blöcke rechnen nacheinander; die drei Köpfe innerhalb jeder Attention parallel.</p>`;
      case 7:
        return `${positionControl()}<div class="mini-label">Letzter Vektor nach Abschlussnormierung</div>${vectors([trace.normFinal[t]], [vokabular[trace.ids[t]]])}<span class="stage-badge">Ausgabe nutzt dieselbe Matrix E wie das Token-Embedding</span><div class="table-scroll"><table class="data-table"><thead><tr><th>mögliches nächstes Token</th><th>Logit</th></tr></thead><tbody>${werte(trace.logits[t]).map((v, id) => `<tr><td>${escape(vokabular[id])}</td><td>${fmt(v)}</td></tr>`).join("")}</tbody></table></div>`;
      case 8:
        return `${positionControl()}<div class="mini-label">Nach „${escape(trace.ids.slice(0, t + 1).map(id => vokabular[id]).join(" "))}“</div>${probabilities(t)}${state.mode === "training" ? '<p class="help">Orange: das richtige Zieltoken. Alle Balken zusammen ergeben 100 %.</p>' : '<p class="help">Alle Balken zusammen ergeben 100 %. Noch wurde kein Token ausgewählt.</p>'}`;
      case 9:
        if (state.mode !== "training") {
          const next = nextToken();
          const finished = trace.ids.at(-1) === vokabular.indexOf("<end>");
          const full = trace.ids.length >= konfig.kontext;
          return `<div class="mini-label">Aktueller Kontext</div>${tokenRow(trace.ids)}<div class="stat-pair"><div class="stat"><span>Greedy-Auswahl an der letzten Position</span><b>${escape(vokabular[next])}</b></div></div><p class="help">${finished ? 'Das Endtoken wurde bereits angehängt. Die Generierung ist beendet.' : full ? 'Die Kontextgrenze von 8 Tokens ist erreicht.' : 'Beim Anhängen wird der nächste Vorwärtslauf tatsächlich mit der längeren Eingabe berechnet.'}</p><button class="primary" id="append-token" ${finished || full ? "disabled" : ""}>Token anhängen & neu rechnen ↻</button><p class="help">Das zufällig initialisierte Lehrmodell erzeugt zunächst keine sinnvollen Sätze. Du kannst im Trainingsmodus seine Gewichte verändern und dann zurückkehren.</p>`;
        }
        return `${positionControl()}<div class="mini-label">Richtiges Zieltoken und Einzelverlust</div>${trace.ziele.map((id, i) => `<div class="loss-row ${t === i ? "selected-row" : ""}"><span>Pos. ${i} → ${escape(vokabular[id])}</span><span>−ln(${fmt(werte(trace.wahrscheinlichkeiten[i][id]))}) = ${fmt(werte(trace.einzelverluste[i]))}</span></div>`).join("")}<div class="stat-pair"><div class="stat training"><b>${fmt(trace.verlust.wert)}</b><span>mittlerer Verlust L</span></div><div class="stat"><b>${fmt(Math.log(vokabular.length))}</b><span>Referenz: Gleichverteilung ln(8)</span></div></div><p class="help">Hier zählen alle ${trace.ids.length} Positionen. Im Notebook zählen alle gültigen Positionen im Batch; Paddingziele werden ignoriert.</p>`;
      case 10:
        return `<div class="mini-label">Tatsächliche Gradientennorm je Parametergruppe</div>${gradientGroups()}<p class="help">Die Balken fassen √Σg² pro Gruppe zusammen. Sie messen die Größe der Ableitungen, keine „Wichtigkeit“ und keine Aktivierung.</p><div class="warning-note">Die Gewichte haben noch genau ihre Werte aus dem Vorwärtslauf. Erst der nächste Schritt verändert sie.</div>`;
      case 11:
        ensureGradients();
        return `<div class="control-row"><label>Lernrate η <input id="learning-rate" type="range" min="0.005" max="0.15" step="0.005" value="${state.lr}" ${state.lastUpdate ? "disabled" : ""}></label><output id="lr-value">${fmt(state.lr)}</output></div>${updateTable()}${state.lastUpdate ? `<div class="stat-pair"><div class="stat training"><b>${fmt(state.lastUpdate.before)}</b><span>Verlust vor dem Update</span></div><div class="stat training"><b>${fmt(state.lastUpdate.after)}</b><span>erneuter Vorwärtslauf danach</span></div></div><p class="help">Update ${state.updates} ausgeführt. Geändert wurden die Modellparameter; Token-IDs und Ziele blieben gleich.</p>${historyPlot()}<button class="primary training update-button" id="repeat-cycle">Nächsten Trainingsschritt untersuchen ↻</button>` : '<button class="primary training update-button" id="apply-update">Gewichte jetzt ändern →</button><p class="help">„Geplant“ zeigt w − ηg. Erst der Klick führt das Update aus und berechnet den Verlust neu.</p>'}`;
    }
    return "";
  }

  function nextToken() {
    const probs = werte(trace.wahrscheinlichkeiten.at(-1));
    return probs.indexOf(Math.max(...probs));
  }
  function appendToken() {
    stop();
    if (trace.ids.length >= konfig.kontext || trace.ids.at(-1) === vokabular.indexOf("<end>")) return;
    state.generated = [...trace.ids, nextToken()];
    state.position = state.generated.length - 1;
    refreshTrace();
    state.step = 1;
    render();
  }
  function applyUpdate() {
    stop();
    if (state.lastUpdate) return;
    ensureGradients();
    const before = trace.verlust.wert;
    if (!state.history.length) state.history.push(before);
    model.update(state.lr);
    state.updates++;
    refreshTrace();
    state.lastUpdate = { before, after: trace.verlust.wert, lr: state.lr };
    state.history.push(trace.verlust.wert);
    render();
  }
  function newCycle() {
    stop(); clearCycle(); refreshTrace(); state.step = 0; render();
  }
  function setStep(step, context = null) {
    if (state.lastUpdate && step !== 11) clearCycle();
    state.step = Math.max(0, Math.min(step, currentSteps().length - 1));
    state.residual = context?.residual || null;
    state.norm = context?.norm || null;
    if (context?.block !== undefined) state.block = Number(context.block);
    else if (step === 6) state.block = 1;
    else if (step <= 3) state.block = 0;
    if (context?.head !== undefined) state.head = Number(context.head);
    render();
    document.querySelector(".inspector").scrollTop = 0;
    if (!context && window.innerWidth > 800) {
      const selector = step <= 3 ? "#map-preparation" : step <= 6 ? `#block-${state.block}` : "#map-output";
      document.querySelector(selector)?.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    }
  }
  function next() {
    if (state.step < currentSteps().length - 1) setStep(state.step + 1);
    else if (state.mode === "training") state.lastUpdate ? newCycle() : applyUpdate();
    else if (state.mode === "forward") appendToken();
  }
  function render() {
    const all = currentSteps();
    let current = all[state.step];
    if (state.norm) {
      const d = layerNormData();
      current = { ...current,
        title: "Die LayerNorm · Schritt für Schritt",
        description: `${d.location}: Wir verfolgen den tatsächlichen ${d.x.length}-dimensionalen Vektor der gewählten Tokenposition vom Eingang bis zum normalisierten Ausgang. Die Werte passen sich an Beispiel, Position, Block und Trainingsstand an.`,
        formula: "μ = Σᵢ xᵢ / 6; σ² = Σᵢ (xᵢ − μ)² / 6\nzᵢ = (xᵢ − μ) / √(σ² + ε)\nyᵢ = γᵢ · zᵢ + βᵢ",
        takeaway: "LayerNorm normalisiert pro Token über alle 6 Modelldimensionen. Die Dimension bleibt erhalten. γ und β sind lernbar; es gibt hier keine Aufteilung in die 2 Dimensionen eines Attention-Kopfes.",
        code: 'norm = nn.LayerNorm(6, eps=1e-5)\n# x: (Batch, Tokenpositionen, 6)\ny = norm(x)  # dieselbe Form; Statistik je Token über die letzte Achse',
      };
    }
    if (state.residual && (state.step === 4 || state.step === 5)) {
      const attention = state.residual === "attention";
      const symbol = attention ? "x" : "z";
      const name = attention ? "Attention" : "FFN";
      current = { ...current,
        title: "Die Residualverbindung",
        description: `Block ${state.block + 1}: Ein Weg berechnet einen ${name}-Beitrag, der blaue Weg reicht den Eingang ${symbol} unverändert weiter. Am Pluszeichen treffen beide Wege zusammen. Das ist eine Residualverbindung.`,
        formula: `${symbol} + ${name}(LayerNorm(${symbol}))`,
        takeaway: "Der blaue Weg erhält den bisherigen Zustand. Der Berechnungsweg liefert einen Beitrag dazu. Die Addition arbeitet komponentenweise, nicht mit Token-IDs oder Text.",
        code: `${symbol}_eingang = ${symbol}\nbeitrag = self.${attention ? "attn" : "ffn"}(self.${attention ? "norm1" : "norm2"}(${symbol}_eingang))\ny = ${symbol}_eingang + beitrag  # je Token: 6 + 6 → 6 Komponenten`,
      };
    }
    const training = state.mode === "training";
    $("step-number").textContent = `${state.mode === "structure" ? "Baustein" : "Schritt"} ${String(state.step + 1).padStart(2, "0")} / ${all.length}`;
    $("phase-chip").textContent = state.step >= 10 ? "Lernen" : state.mode === "structure" ? "Struktur & Funktion" : "Vorwärtslauf";
    $("phase-chip").classList.toggle("training", training && state.step >= 9);
    if (training && state.step === 9) $("phase-chip").textContent = "Vorhersage bewerten";
    $("step-title").textContent = current.title;
    $("step-description").textContent = current.description;
    $("formula").textContent = current.formula;
    $("takeaway").textContent = current.takeaway;
    $("takeaway").classList.toggle("training", training && state.step >= 9);
    $("notebook-code").textContent = current.code;
    $("step-content").innerHTML = content();
    $("previous").disabled = state.step === 0;
    $("next").textContent = state.step === all.length - 1
      ? training ? state.lastUpdate ? "Neuer Trainingsschritt ↻" : "Gewichte ändern →"
        : state.mode === "forward" ? "Token anhängen ↻" : "Ende der Übersicht"
      : "Weiter →";
    $("next").disabled = state.step === all.length - 1 && (state.mode === "structure" || (state.mode === "forward" && (trace.ids.length >= konfig.kontext || trace.ids.at(-1) === vokabular.indexOf("<end>"))));
    $("next").classList.toggle("training", training && state.step >= 9);
    $("progress").style.width = `${(state.step + 1) / all.length * 100}%`;
    $("progress").classList.toggle("training-progress", training && state.step >= 9);
    $("progress-label").textContent = `${state.step + 1} von ${all.length} · ${training ? `${state.updates} Gewichtsupdates` : state.mode === "structure" ? "Überblick" : "Gewichte unverändert"}`;
    $("map-caption").textContent = state.mode === "training" ? "Ein Trainingsschritt im Gesamtmodell" : state.mode === "forward" ? "Vom Text zum nächsten Token" : "Die Gesamtstruktur · Decoder-Transformer";
    for (const button of document.querySelectorAll("[data-mode]")) {
      button.classList.toggle("active", button.dataset.mode === state.mode);
      button.setAttribute("aria-pressed", button.dataset.mode === state.mode);
    }
    diagram();
    $("parameter-count").textContent = `${model.parameter.length.toLocaleString("de-DE")} lernbare Parameter im Lehrmodell.`;
  }

  document.querySelectorAll("[data-mode]").forEach(button => button.addEventListener("click", () => {
    stop(); state.mode = button.dataset.mode; state.step = 0; state.block = 0; state.residual = null; state.norm = null; state.generated = null; clearCycle(); refreshTrace(); render();
  }));
  $("example").addEventListener("change", event => {
    stop(); state.example = Number(event.target.value); state.position = sequence().length - 2;
    state.generated = null; state.history = []; clearCycle(); refreshTrace(); render();
  });
  $("reset").addEventListener("click", () => {
    stop(); model = new Lehrmodell(); state.step = 0; state.updates = 0; state.history = [];
    state.generated = null; state.block = 0; state.head = 0; state.residual = null; state.norm = null; state.position = sequence().length - 2; clearCycle(); refreshTrace(); render();
  });
  $("assumptions").addEventListener("click", () => {
    const open = $("model-note").hidden;
    $("model-note").hidden = !open;
    $("assumptions").setAttribute("aria-expanded", open);
  });
  $("previous").addEventListener("click", () => { stop(); setStep(state.step - 1); });
  $("next").addEventListener("click", () => { stop(); next(); });
  $("play").addEventListener("click", () => {
    if (state.timer) return stop();
    if (state.step === currentSteps().length - 1) setStep(0);
    $("play").textContent = "Ⅱ Pause";
    $("play").setAttribute("aria-pressed", "true");
    // Automatisches Abspielen erklärt die Schritte; Updates bleiben eine bewusste Aktion.
    state.timer = setInterval(() => {
      if (state.step >= currentSteps().length - 1) return stop();
      setStep(state.step + 1);
      if (state.step >= currentSteps().length - 1) stop();
    }, 2800);
  });
  $("diagram").addEventListener("click", event => {
    const node = event.target.closest("[data-stage]");
    if (node) { stop(); setStep(Number(node.dataset.stage), node.dataset); }
  });
  $("diagram").addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") {
      const node = event.target.closest("[data-stage]");
      if (node) { event.preventDefault(); stop(); setStep(Number(node.dataset.stage), node.dataset); }
    }
  });
  $("step-content").addEventListener("click", event => {
    const position = event.target.closest("[data-position]");
    if (position) { state.position = Number(position.dataset.position); render(); }
    if (event.target.id === "apply-update") applyUpdate();
    if (event.target.id === "repeat-cycle") newCycle();
    if (event.target.id === "append-token") appendToken();
    if (event.target.id === "show-calculation") { state.residual = null; state.norm = null; render(); document.querySelector(".inspector").scrollTop = 0; }
    const explanation = event.target.closest("[data-explain-residual]");
    if (explanation) {
      const residual = explanation.dataset.explainResidual;
      setStep(residual === "attention" ? 4 : 5, { residual, block: Number(explanation.dataset.explainBlock ?? state.block) });
    }
  });
  $("step-content").addEventListener("change", event => {
    if (event.target.id === "block-select") { state.block = Number(event.target.value); render(); }
    if (event.target.id === "head-select") { state.head = Number(event.target.value); render(); }
  });
  $("step-content").addEventListener("input", event => {
    if (event.target.id !== "learning-rate") return;
    state.lr = Number(event.target.value);
    $("lr-value").textContent = fmt(state.lr);
    const table = $("step-content").querySelector(".table-scroll");
    if (table) {
      const wrapper = document.createElement("div");
      wrapper.innerHTML = updateTable();
      table.replaceWith(wrapper.querySelector(".table-scroll"));
    }
  });
  refreshTrace(); render();
})();

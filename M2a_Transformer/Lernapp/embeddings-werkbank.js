"use strict";
(() => {
  const { Tokenizer, examples, stats, validateBundle, verifyChecksum, forward } = EmbeddingModell;
  const $ = id => document.getElementById(id);
  const escape = value => String(value).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const fmt = (x, n = 5) => Number(x).toLocaleString("de-DE", { minimumFractionDigits: n, maximumFractionDigits: n });
  const integer = n => Number(n).toLocaleString("de-DE");
  const visible = token => token.replace(/Ġ/g, "␠").replace(/Ċ/g, "↵").replace(/ĉ/g, "⇥");
  const PAGE_SIZE = 12;
  let tokenizer = null, bundle = null, ids = [], rows = [], selected = 0, dimension = 0, page = 0, timer;
  let range = [0, 0], sharedLimit = 1, normLimit = 1;

  function error(message = "") { $("load-error").textContent = message; $("load-error").hidden = !message; }
  function busy(active) {
    for (const id of ["weights-file", "tokenizer-file"]) $(id).disabled = active;
    $("source-status").setAttribute("aria-busy", active);
  }
  function setupRanges(width) {
    const options = [[0, width, `Alle ${width} Dimensionen`]];
    if (width > 64) for (let from = 0; from < width; from += 64) options.push([from, Math.min(width, from + 64), `d${from}–d${Math.min(width, from + 64) - 1}`]);
    $("dimension-range").innerHTML = options.map(([a, b, label]) => `<option value="${a}:${b}">${label}</option>`).join("");
    range = [0, width];
    $("dimension").max = width - 1;
  }
  async function installWeights(data, filename) {
    const candidate = validateBundle(data);
    await verifyChecksum(data);
    tokenizer = candidate; bundle = data; dimension = 0;
    setupRanges(data.config.d_model);
    $("source-status").textContent = `${filename} · ${data.source?.checkpoint || "Checkpoint"} · Trainingsschritt ${data.source?.step ?? "unbekannt"} · ${integer(data.config.d_model)} Dimensionen · ${integer(data.config.max_seq_len)} Positionen`;
    $("verification").textContent = "Tokenizer-Prüfsumme und PyTorch-Referenzwerte geprüft";
    $("embedding-description").textContent = `${integer(data.config.vocab_size)} Zeilen × ${integer(data.config.d_model)} Dimensionen. Für jede Token-ID lesen wir genau eine trainierte Zeile.`;
    $("position-description").textContent = `${integer(data.config.max_seq_len)} Positionen × ${integer(data.config.d_model)} Dimensionen. Die Position wählt die Zeile aus derselben trainierten Tabelle.`;
    $("sum-description").textContent = `${data.config.d_model} + ${data.config.d_model} → ${data.config.d_model} Komponenten pro Token. Die Vektoren werden addiert, nicht aneinandergehängt.`;
    activate();
  }
  function installTokenizer(data, filename) {
    const candidate = new Tokenizer(data);
    tokenizer = candidate; bundle = null;
    $("source-status").textContent = `${filename} · nur Tokenizer geladen. Für die Originalvektoren bitte den Checkpoint-Export öffnen.`;
    $("verification").textContent = "Nur Tokenizer geladen · keine Gewichte";
    activate();
  }
  function activate() {
    $("example-select").disabled = false;
    $("sentence").disabled = false;
    $("vocab-info").textContent = `${integer(tokenizer.tokens.length)} Tokens im Vokabular`;
    $("import-help").open = false;
    error();
    updateSentence();
  }
  function updateSentence() {
    selected = 0; page = 0;
    try {
      ids = tokenizer.encode($("sentence").value);
      renderTokens();
      rows = [];
      $("weights-empty").hidden = !!bundle;
      $("vector-workspace").hidden = true;
      if (!ids.length) { $("sentence-status").textContent = "Bitte einen Text eingeben."; return; }
      if (!bundle) { $("sentence-status").textContent = `${ids.length} Tokens · Die IDs sind bereit; für die Vektoren fehlen noch die Gewichte.`; return; }
      rows = forward(bundle, ids);
      $("sentence-status").textContent = `${ids.length} Tokens · Positionen 0–${ids.length - 1} · ${bundle.config.d_model} Komponenten pro Token. ␠ steht für ein Leerzeichen, ↵ für einen Zeilenumbruch im ByteLevel-Token.`;
      sharedLimit = 0; normLimit = 0;
      for (const row of rows) {
        for (const key of ["embedding", "positional", "sum"]) for (const x of row[key]) sharedLimit = Math.max(sharedLimit, Math.abs(x));
        for (const x of row.output) normLimit = Math.max(normLimit, Math.abs(x));
      }
      sharedLimit = sharedLimit || 1; normLimit = normLimit || 1;
      $("shared-scale").textContent = `Stationen 02–04: gemeinsame Skala von −${fmt(sharedLimit, 3)} bis +${fmt(sharedLimit, 3)}. Alle Dimensionen fließen in die Berechnung ein.`;
      $("norm-scale").textContent = `Eigene Farbskala nach LayerNorm: −${fmt(normLimit, 3)} bis +${fmt(normLimit, 3)}. Farbstärken sind deshalb nur innerhalb dieser Station direkt vergleichbar.`;
      $("vector-workspace").hidden = false;
      renderVectors();
    } catch (err) {
      rows = [];
      $("vector-workspace").hidden = true;
      $("sentence-status").textContent = err.message;
    }
  }
  function renderTokens() {
    $("token-list").innerHTML = ids.map((id, t) => `<button class="token${selected === t ? " selected" : ""}" data-position="${t}" aria-pressed="${selected === t}" title="Vokabulartoken: ${escape(tokenizer.tokens[id])}"><span>${escape(visible(tokenizer.tokens[id]))}</span><small>ID ${id} · Pos. ${t}</small></button>`).join("");
  }
  function choose(position, dim = dimension) {
    selected = position; dimension = dim; page = Math.floor(position / PAGE_SIZE);
    renderTokens();
    if (rows.length) renderVectors();
  }
  function color(value, limit) {
    const a = [250, 248, 242], b = value < 0 ? [79, 115, 191] : [222, 133, 13], t = Math.min(1, Math.abs(value) / limit);
    return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",")})`;
  }
  function heatmap(target, key, limit) {
    const from = page * PAGE_SIZE, shown = rows.slice(from, from + PAGE_SIZE), [start, end] = range;
    $(target).innerHTML = `<div class="heatmap-scroll"><div class="heatmap-body"><div class="row-labels">${shown.map(row => `<button class="row-label${selected === row.position ? " selected" : ""}" data-position="${row.position}" aria-pressed="${selected === row.position}" title="Position ${row.position}, ID ${row.id}: ${escape(tokenizer.tokens[row.id])}">${row.position} · ${escape(visible(tokenizer.tokens[row.id]))} <small>#${row.id}</small></button>`).join("")}</div><canvas width="${(end - start) * 3}" height="${shown.length * 30}" style="height:${shown.length * 30}px" role="img" aria-label="${key}: ${shown.length} Tokenzeilen, Dimensionen d${start} bis d${end - 1}. Einzelwerte stehen unten unter Eine Komponente nachrechnen."></canvas></div></div><div class="axis"><span>d${start}</span><span>${end - start} Dimensionen sichtbar</span><span>d${end - 1}</span></div><p class="map-readout" aria-live="off">Blau: negativ · hell: nahe 0 · orange: positiv</p>`;
    const canvas = $(target).querySelector("canvas"), ctx = canvas.getContext("2d");
    for (let r = 0; r < shown.length; r++) {
      for (let d = start; d < end; d++) {
        ctx.fillStyle = color(shown[r][key][d], limit);
        ctx.fillRect((d - start) * 3, r * 30 + 2, 3, 26);
      }
      if (shown[r].position === selected) { ctx.strokeStyle = "#23343d"; ctx.lineWidth = 1; ctx.strokeRect(.5, r * 30 + .5, canvas.width - 1, 29); }
    }
    const point = event => {
      const rect = canvas.getBoundingClientRect();
      return [Math.min(shown.length - 1, Math.max(0, Math.floor((event.clientY - rect.top) / rect.height * shown.length))),
        Math.min(end - 1, Math.max(start, start + Math.floor((event.clientX - rect.left) / rect.width * (end - start))))];
    };
    canvas.addEventListener("pointermove", event => {
      const [r, d] = point(event), row = shown[r];
      $(target).querySelector(".map-readout").textContent = `Position ${row.position} · ID ${row.id} · d${d}: ${fmt(row[key][d], 7)}`;
    });
    canvas.addEventListener("click", event => { const [r, d] = point(event); choose(shown[r].position, d); });
  }
  function renderVectors() {
    $("rows-info").textContent = `Zeilen ${page * PAGE_SIZE + 1}–${Math.min(rows.length, (page + 1) * PAGE_SIZE)} von ${rows.length}`;
    $("previous-rows").disabled = page === 0;
    $("next-rows").disabled = (page + 1) * PAGE_SIZE >= rows.length;
    for (const [target, key] of [["embedding-map", "embedding"], ["positional-map", "positional"], ["sum-map", "sum"]]) heatmap(target, key, sharedLimit);
    heatmap("output-map", "output", normLimit);
    renderDetail();
  }
  function renderDetail() {
    const row = rows[selected], d = dimension, w = bundle.weights, width = bundle.config.d_model;
    $("dimension").value = d;
    $("selection-info").textContent = `Token ${tokenizer.tokens[row.id]} · ID ${row.id} · Position ${selected} · Dimension d${d} von d0–d${width - 1}`;
    const after = stats(row.output);
    $("calculation").innerHTML = `<div class="equation">E[${row.id}, ${d}] + P[${selected}, ${d}]
${fmt(row.embedding[d], 7)} + (${fmt(row.positional[d], 7)}) = ${fmt(row.sum[d], 7)}</div><div class="equation">Statistik über alle ${width} Komponenten dieses Tokenvektors:
μ = ${fmt(row.mean, 7)} · σ² = ${fmt(row.variance, 7)} · ε = ${w.norm_epsilon}
z[d${d}] = (x[d${d}] − μ) / √(σ² + ε)
= (${fmt(row.sum[d], 7)} − (${fmt(row.mean, 7)})) / √(${fmt(row.variance, 7)} + ${w.norm_epsilon})
= ${fmt(row.normalized[d], 7)}
y[d${d}] = γ[d${d}] · z[d${d}] + β[d${d}]
= ${fmt(w.norm_gamma[d], 7)} × (${fmt(row.normalized[d], 7)}) + (${fmt(w.norm_beta[d], 7)})
= ${fmt(row.output[d], 7)}</div><p class="help">Nach trainierter LayerNorm: Mittelwert ${fmt(after.mean, 6)}, Varianz ${fmt(after.variance, 6)}. Vor γ und β hat z einen Mittelwert nahe 0 und eine Varianz von σ² / (σ² + ε). Die reine Normierung und die trainierte affine Transformation sind in der Tabelle getrennt. Anzeigen sind gerundet; JavaScript rechnet mit doppelter Genauigkeit. Kleine Abweichungen zu PyTorch-float32 sind möglich und werden anhand der exportierten Referenzwerte geprüft.</p>`;
    const from = Math.max(0, d - 3), to = Math.min(width, from + 8);
    $("value-table").innerHTML = `<table><thead><tr><th>Dimension</th><th>Token E</th><th>Position P</th><th>Summe x</th><th>nur normiert z</th><th>γ</th><th>β</th><th>Ausgang y</th></tr></thead><tbody>${Array.from({ length: to - from }, (_, offset) => {
      const i = from + offset;
      return `<tr${i === d ? ' class="chosen-dimension"' : ""}><td>d${i}</td>${[row.embedding[i], row.positional[i], row.sum[i], row.normalized[i], w.norm_gamma[i], w.norm_beta[i], row.output[i]].map(v => `<td>${fmt(v, 6)}</td>`).join("")}</tr>`;
    }).join("")}</tbody></table>`;
  }
  async function importFile(event, weights) {
    const file = event.target.files[0];
    if (!file) return;
    busy(true); error();
    try {
      if (file.size > 150 * 1024 ** 2) throw new Error("Die JSON-Datei ist größer als 150 MiB. Bitte den Embedding-Export statt des vollständigen Checkpoints laden.");
      const data = JSON.parse(await file.text());
      if (weights) await installWeights(data, file.name); else installTokenizer(data, file.name);
    } catch (err) { error(`Datei konnte nicht geladen werden: ${err.message}`); }
    finally { busy(false); event.target.value = ""; }
  }
  $("example-select").innerHTML = examples.map((text, i) => `<option value="${i}">${i === examples.length - 1 ? "Chat-Format mit Sondertokens" : escape(text)}</option>`).join("");
  $("weights-file").addEventListener("change", event => importFile(event, true));
  $("tokenizer-file").addEventListener("change", event => importFile(event, false));
  $("example-select").addEventListener("change", () => { clearTimeout(timer); $("sentence").value = examples[Number($("example-select").value)]; updateSentence(); });
  $("sentence").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(updateSentence, 180); });
  document.addEventListener("click", event => {
    const target = event.target.closest("[data-position]");
    if (target) choose(Number(target.dataset.position));
  });
  $("dimension-range").addEventListener("change", () => { range = $("dimension-range").value.split(":").map(Number); dimension = Math.max(range[0], Math.min(range[1] - 1, dimension)); renderVectors(); });
  $("dimension").addEventListener("input", () => {
    const value = Number($("dimension").value);
    if ($("dimension").value === "" || !Number.isInteger(value) || value < 0 || value >= bundle.config.d_model) return;
    dimension = value;
    if (value < range[0] || value >= range[1]) { range = [0, bundle.config.d_model]; $("dimension-range").value = range.join(":"); }
    renderVectors();
  });
  $("dimension").addEventListener("change", () => { $("dimension").value = dimension; });
  $("previous-rows").addEventListener("click", () => choose((page - 1) * PAGE_SIZE));
  $("next-rows").addEventListener("click", () => choose((page + 1) * PAGE_SIZE));
  async function boot() {
    busy(true);
    let exportError = null;
    if (location.protocol !== "file:") {
      try {
        const response = await fetch("../Data/embeddings-checkpoint.json");
        if (response.ok) { await installWeights(await response.json(), "embeddings-checkpoint.json"); busy(false); return; }
        if (response.status !== 404) throw new Error(`HTTP ${response.status}`);
      } catch (err) { exportError = err.message; }
      try {
        const response = await fetch("../Data/tokenizer.json");
        if (response.ok) installTokenizer(await response.json(), "Data/tokenizer.json");
      } catch (err) { /* Dateiauswahl bleibt verfügbar. */ }
    }
    if (!tokenizer) {
      $("source-status").textContent = "Bitte den Checkpoint-Export oder Data/tokenizer.json auswählen. Die Dateien werden lokal gelesen.";
      $("import-help").open = true;
    }
    if (exportError) error(`Der vorhandene Checkpoint-Export konnte nicht verwendet werden: ${exportError}`);
    busy(false);
  }
  boot();
})();

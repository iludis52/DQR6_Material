# GPT-Vortrag 2026 – Änderungsprotokoll

Ausgangsdatei: `GPT_Vortrag_Version2026.pptx` (42 Folien, unverändert)
Neue Fassung: `GPT_Vortrag_Version2026_rev.pptx` (57 Folien, Runde 1) → `GPT_Vortrag_Version2026_rev2.pptx` (61 Folien, Runde 2)
Referenz: GuppyLM-Lehrnotebooks (alle Zahlen aus den gespeicherten Ausgaben von `guppylm_lehrnotebook_b.ipynb`, Tokenisierung mit `Data/tokenizer.json`)

## Rahmen

- Kopfzeile auf allen Folien: „WIE FUNKTIONIERT EIN TRANSFORMER? | iludis.de“; Kepler-Logo entfernt; Autorenzeile „Thomas Jörg · Dozent · iludis.de“.
- Formeln: 24 native PowerPoint-Formeln (OMML) mit Bild-Fallback für Keynote/LibreOffice.
- Gelöscht: F3 (GPT-4-„Sezier“-Tabelle), F31 (Serrano-Grundaufbau, ersetzt durch eigene Übersicht), F35 („Blank“-Darstellung des Decoders, ersetzt durch Maskenfolie), F41 (Hinton-Zitate), Bill-Gates-Zitat auf F1.
- Gliederung: 0 Tokenisierung · 1 Embeddings · 2 Positionskodierung · 3 Attention · 4 Transformer-Block · 5 Ausgabe/Decoder-only · 6 Training · 7 Inferenz · 8 Größenordnungen/Emergenz · Literatur.

## Korrekturen an bestehenden Folien (neue Nr. ← alte Nr.)

| Neu | Alt | Problem | Korrektur | Beleg |
|---|---|---|---|---|
| 3 | 4 | Slogan „Attention is all you need“ als Sachaussage | als Artikeltitel gekennzeichnet; Hinweis auf Rang-Kollaps reiner Attention | Dong et al. 2021 |
| 4 | 5 | Add & Norm, Maske, Cross-Attention, Ausgabeschicht fehlten | Bausteinliste vollständig; Base-Modell-Kennzahlen | Vaswani et al. 2017, Abschn. 3 |
| 7 | 6 | „gleiche Richtung = Skalarprodukt maximal“ gilt nur bei gleicher Länge | a·b = \|a\|\|b\|cos θ; Kosinusähnlichkeit als Richtungsmaß | – (Mathematik) |
| 8 | 7 | Firth-Zitat bibliografisch ungenau | Titel des Aufsatzes, Philological Society | ACL-Wiki „Distributional Hypothesis“ |
| 9 | 8 | Harris fehlte | Harris 1954 ergänzt; Brücke zum Next-Token-Training | Harris 1954 |
| 11–14 | 10–13 | word2vec als Vorstufe des GPT-Inputs dargestellt | als **historischer Exkurs** gekennzeichnet; F13: „GPT übernimmt diese Vektoren nicht“ | Mikolov et al. 2013; Vaswani 2017; Radford 2018 |
| 12 | 11 | GPT-3 „ca. 12 000“; word2vec-Länge als d_model bezeichnet | d_model GPT-3 = 12 288, Guppy = 384; 300 ist word2vec-Hyperparameter | Brown et al. 2020, Tab. 2.1 |
| 17/18 | 14/15 | „Synonyme“; Begründung der PE unscharf | Permutations-Äquivarianz der Self-Attention als Grund | Vaswani 2017, Abschn. 3.5 |
| 22/23 | 17/18 | Score = Gewicht gleichgesetzt; Zeilen/Spalten vertauscht beschrieben | Gewicht = Softmax(Score); Zeilen = Query, Spalten = Key | Vaswani 2017, Abschn. 3.2.1 |
| 25 | 20 | Titel „Kontextvektoren bilden den Attention-Score“ | Kontextvektoren sind die Ausgabe | – |
| 26 | 21 | – | Hinweis: zuerst LayerNorm (Pre-LN) | Brown et al. 2020, Abschn. 2.1 |
| 27/28 | 22/23 | Q/K/V aus „neuronalen Netzen“ | lineare Projektionen q = xW_Q usw.; eigene Matrizen je Kopf und Block | Vaswani 2017 |
| 29 | 24 | Skalierung und Softmax fehlten; „Ähnlichkeit“ | Score = q·k, gelernt und asymmetrisch | Vaswani 2017 |
| 35 | 28 | „Head 3“ doppelt; Spezialisierung als Konstruktionsprinzip | Beobachtung, viele Köpfe entbehrlich | Michel et al. 2019 |
| 36 | 33 | „6 Einzel-Attentionscores“ | Concat der Kopf-Ausgaben + W_O, mit Formel | Vaswani 2017, Abschn. 3.2.2 |
| 40/41 | 29/30 | „Attention-Layer hintereinander“; Hierarchie Satz→Kapitel | ganze Blöcke mit eigenen Gewichten; Tiefe = Komposition | Elhage et al. 2021 |
| 42 | 38 | „Wissen steckt in den FFN“ unbelegt | Befunde mit Gegenposition | Geva 2021; Meng 2022; Hase 2023 |
| 43 | 39 | „GPT-4: 50x in FFN“ ohne Quelle | gestrichen; GPT-4-Architektur nicht veröffentlicht | OpenAI 2023 |
| 45 | 34 | Bard; „Eingabe wird encodiert“; „weniger Ressourcen“ | Gemini; Prompt läuft durch denselben maskierten Stapel; GPT-1 Post-LN vs. GPT-2 Pre-LN | Radford 2018; Gemini Team 2023 |
| 51 | 36 | **FFN liefert Wahrscheinlichkeiten** (falsch) | LayerNorm → LM-Head → Softmax; AllenNLP-Demo durch Lernapp ersetzt | Vaswani 2017, Abschn. 3.4 |
| 52 | 37 | „Alte Attentions werden recycelt“ | KV-Cache: Keys/Values früherer Tokens | Pope et al. 2022 |
| 54 | 42 | „45 TB ≈ gesamtes Internet“; „800 GB“ (Quelle betraf GPT-J) | 45 TB komprimiert vor, 570 GB nach Filterung, 300 Mrd. Tokens; 175 Mrd. × 2 Byte ≈ 350 GB | Brown et al. 2020, Abschn. 2.2 |
| 55 | 40 | Bubeck-Zitat nur sinngemäß; Emergenz unkritisch | Originalwortlaut; Gegenposition | Bubeck 2023, Abschn. 1; Schaeffer et al. 2023 |

## Neue Folien

| Nr. | Thema | Kernaussage / Formel | Beleg |
|---|---|---|---|
| 5 | Überblick | Pipeline Text → Tokens → Embedding+Position → N Blöcke → LN → LM-Head → Softmax; Guppy vs. GPT-3 | Notebook; Brown 2020 |
| 6 | Tokenisierung | BPE; Guppy-Beispiele („Gut Ding braucht Weile“ = 15 Tokens) | Sennrich 2016; tokenizer.json |
| 15 | Embeddings im Transformer | x⁽⁰⁾ = W_E[tok] + p; end-to-end trainiert; Weight Tying | Vaswani 2017; Radford 2018 |
| 16 | Statisch vs. kontextuell | Anisotropie; <5 % Varianz durch statisches Embedding | Ethayarajh 2019 |
| 19 | Sinus-Positionskodierung | PE-Formeln, Heatmap mit Guppy-Maßen | Vaswani 2017, Abschn. 3.5 |
| 20 | Gelernt / fest / keine PE | GPT-1–3 gelernt; NoPE bei kausalen LMs | Radford 2018; Haviv 2022 |
| 30 | Attention-Formel | s = q·k/√d_k; Softmax; z = Σαv; Matrixform mit M | Vaswani 2017 |
| 33 | Kausale Maske | M mit 0/−∞; konsistent renormierte Gewichte | Vaswani 2017, Abschn. 3.2.3; Devlin 2019 |
| 37 | Residualstrom | h = x + MHA(LN(x)); x' = h + FFN(LN(h)) | He 2016; Dong 2021; Elhage 2021 |
| 38 | LayerNorm | LN-Formel; Post-LN vs. Pre-LN | Ba 2016; Xiong 2020; Brown 2020 |
| 39 | FFN je Block | FFN-Formel; „different parameters from layer to layer“; 2/3-Anteil (Guppy 66,6 %) | Vaswani 2017; Geva 2021 |
| 44 | Ausgabe | Logits = LN(h)·W_Eᵀ; Softmax | Vaswani 2017; Press & Wolf 2017 |
| 47 | Trainingsziel | x/y-Verschiebung; Kreuzentropie; Startverlust ≈ ln V | Radford 2018; Notebook |
| 48 | Trainingsschritt | θ ← θ − η∇L; alle Parameter; Guppy-Hyperparameter | Notebook; Loshchilov & Hutter 2019 |
| 49 | Verlustkurve | Guppy-Lauf; Datenüberschneidung Train/Validierung | Notebook |
| 50 | Vortraining → Feinabstimmung | GPT-4: Next-Token-Pretraining + RLHF | OpenAI 2023 |
| 53 | Sampling | Temperatur-Softmax, top-k, Guppy-Antworten | Notebook |
| 56/57 | Literatur | 30 Einträge | – |

## Offen / bewusst nicht geändert

- Grafiken mit „Wort“-Beschriftungen (Bilddateien) bleiben. Folie 6 erklärt die Vereinfachung „Wort“ = Token.
- Moderne Varianten (RoPE, RMSNorm, SwiGLU, GQA, MoE) sind nur auf Folie 20 angekündigt und kommen in einem nächsten Schritt.
- Die Unterschiede zwischen Notebook a und b (gelernte vs. Sinus-Positionskodierung, α-Skalierung) werden auf den Folien nicht aufgedeckt, damit die Studierenden-Aufgabe erhalten bleibt.
- Native Formeln wurden mit LibreOffice (Bild-Fallback) geprüft, aber nicht in PowerPoint selbst.

## Runde 2 (Rückmeldung TJ)

### a) Beispielmatrix „Gut Ding braucht Weile“ kausal umgebaut
Die markierten Bezüge lagen oberhalb der Diagonale, die Maske hätte sie gelöscht. Sie zeigen jetzt vom späteren auf das frühere Token (Zeile = Query, Spalte = Key):

| | Gut | Ding | braucht | Weile |
|---|---|---|---|---|
| Gut | 0.4 | 0.3 | 0.2 | 0.1 |
| Ding | **0.6** (rot) | 0.2 | 0.1 | 0.1 |
| braucht | 0.2 | **0.4** (grün) | 0.2 | 0.2 |
| Weile | 0.1 | 0.2 | **0.5** (blau) | 0.2 |

Mit Maske (Folie 33, renormiert): Gut 1 | Ding 0.75 / 0.25 | braucht 0.25 / 0.5 / 0.25 | Weile unverändert. Die markierten Bezüge bleiben erhalten.

Angepasst wurden:
- Bogenpfeile auf F21–24 (umgedreht)
- Tabellen auf F22, 23, 25 und 29
- F24: Einzelzeile jetzt „Ding“
- Kontextzeilen und Value-Zeilen auf F24, 25, 31 und 32
- Maskenfolie F33
- F51 und F52: Q/K-Grafiken jetzt K1→K3 von links nach rechts, Zukunftsfelder 0; beim KV-Cache ist die neue Zeile grün statt der neuen Spalte

### Eindeutige Symbole (Konvention nach Brown et al. 2020, Tab. 2.1)

| alt | neu | Grund |
|---|---|---|
| V (Vokabular) | n_vocab | Kollision mit Value-Matrix V |
| N (Blöcke) | n_layers | einheitlich mit GPT-3-Tabelle |
| h (Köpfe) | n_heads; h = Kopf-Index | Kollision mit Residualvektor |
| h (Residual-Zwischenwert) | x̃; Ausgang x⁽ⁿˡᵃʸᵉʳˢ⁾ | – |
| T (Temperatur) | τ | Kollision mit Sequenzlänge T |
| ℓ (Block-Index) | b | Kollision mit Logits ℓ |
| i (PE-Dimension) | m | Kollision mit Query-Position i |
| Σ_l (Softmax) | Σ_j′ | eindeutiger Laufindex |
| x_t (Token im Verlust) | tok_t | Unterscheidung Token ↔ Vektor x |

### b) Formelsammlung (Anhang, F56–59)
- F56 Schreibweisen und Operationen (u. a. ⊙ mit Beispiel, ᵀ, Σ, ∇, ←, P(A|B), ℝ^(m×n))
- F57 Größen mit Guppy-Werten und Bezeichnern
- F58–59: alle 16 Formeln mit Erklärung und Folienverweis
- Literatur ergänzt: Hendrycks & Gimpel (2016), GELU

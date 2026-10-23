# Transformer-Lehrbuch – Änderungsprotokoll

Ausgangsdatei: `Dokumente/Transformer_Lehrbuch.md`, Stand vor der Korrektur gesichert als
`Hilfsskripte/AddOns/Transformer_Lehrbuch_Stand_vor_Korrektur_2026-10-23.md`.
Grundlage: Prüfung vom 23.10.2026 gegen Lehrnotebook a und b, Export-Notebook, Begleittexte,
Aufgaben, Quiz, Vortrag (PDF) und die Datensätze in `Data/`.

## Umgesetzte Korrekturen (Nummern der Prüfliste)

| Nr | Stelle | Änderung | Beleg |
|---|---|---|---|
| 1 | Kap. 1 | Absatz zu GPT-2 als direktem Vorbild; Abweichungen vom Original; Link zum Export-Notebook | Radford et al. 2019; Export-Notebook Abschn. 3 |
| 2 | Kap. 1, Mermaid-Diagramm | Knoten „Finale LayerNorm“ ergänzt | Notebook `GuppyLM.forward` |
| 3 | Kap. 1 | Token kann auch ein einzelnes Byte sein | Radford et al. 2019, Abschn. 2.2 |
| 4 | Kap. 3 | Beispiel Hund/Katze ersetzt durch „Die Katze jagt die Maus“ / „Die Maus jagt die Katze“ | – |
| 5 | Kap. 3 | „GuppyLM verwendet“ → „Das GuppyLM-Hauptnotebook …“ | Notebook b nutzt Sinus |
| 6 | Kap. 3 | Wellenlängen, Motivation, „nahezu gleiche Ergebnisse“, GPT-1 bis 3 gelernt. **√d_model bewusst nicht erwähnt** (Aufgabe Notebook b) | Vaswani et al. 2017, Abschn. 3.5, Tab. 3; Radford et al. 2018, Abschn. 4.1 |
| 7 | durchgehend | $L,H$ → $n_{\mathrm{layers}},n_{\mathrm{heads}}$; $P$ → $E_{\mathrm{pos}}$ bzw. $\mathrm{PE}$; $m_{b,t}$ → $\mathbf 1_{b,t}$; Dropout-Rate $p_{\mathrm{drop}}$. Übrige Symbole beibehalten, Abgleich mit Vortrag/Notebook im Symbolverzeichnis | Vortrag-Anhang |
| 8 | Kap. 3, 4, 8, 9 | Semikolon als Trenner von Vektorkomponenten; Konvention in Kap. 3 eingeführt | – |
| 9 | Kap. 4 | „Value-Mittelwert“ → gewichteter Mittelwert mit Wertebereichsaussage; Matrixform ergänzt | Vaswani et al. 2017, Abschn. 3.2.1 |
| 10 | Kap. 4 | Kasten „Zum Ausprobieren“ Attention-Werkbank (aus Kap. 11 verlegt) | – |
| 11 | Kap. 5 | Neuer Abschnitt „Die Maske gilt auch bei der Inferenz“ mit Fehlvorstellungskasten | Begleittext Attention-Werkbank, Schritt 4 |
| 12 | Kap. 6, 7 | Post-LN vs. Pre-LN; Begründung der finalen LayerNorm | Vaswani et al. 2017, Abschn. 3.1; Radford et al. 2019, Abschn. 2.3; Xiong et al. 2020 |
| 13 | Kap. 8 | Perplexität als effektive Zahl gleich wahrscheinlicher Alternativen; Guppy-Zahlenwerte | Jurafsky 2021 |
| 14 | Kap. 9 | Zielklasse „zweite Klasse (Index 1)“ | – |
| 15 | Kap. 9, Mermaid-Diagramm | Kanten „unverändert“ bzw. „über Ableitung von F“ korrigiert | – |
| 16 | Vorwort, Kap. 9, 11 | Voraussetzungen an Aufgaben angeglichen; Kapitelanfänge knüpfen an bekannten Trainingszyklus an | `guppylm_aufgaben.md` |
| 17 | Kap. 11, Verständnisprüfung | `loss` → `verlust` | Notebook |
| 18 | Kap. 11 | Taylor-Argument auf Batchverlust bezogen; Hinweis zu AdamW | – |
| 19 | Kap. 11 | „wie PyTorch es umsetzt“; Hinweis Weight Decay auf alle Parameter vs. nanoGPT. **Notebook unverändert** | PyTorch-Doku AdamW; Karpathy, nanoGPT |
| 20 | Kap. 12 | Sperre von `<pad>` und `<\|im_start\|>` in `erzeuge` | Notebook `erzeuge` |
| 21 | Kap. 12 | Gleitendes Trainingsmittel und Checkpointauswahl als Gründe ergänzt | Notebook Abschn. 5 |
| 22 | Kap. 12 | Datenlage: 15.613 verschiedene Dialoge, 713 Fragen, 2.999/3.000 Validierungsfragen im Training | eigene Auszählung `train.jsonl`, `eval.jsonl` |
| 23 | Materialien | toter Link `guppylm_lehrtext.md` entfernt; Begleittexte und Export-Notebook verlinkt | – |
| 24 | durchgehend | Kurzbelege „Autor Jahr, Abschn.“ und Literaturverzeichnis (28 Einträge) | siehe Lehrbuch |
| 25 | Kap. 4, 5, 8, 9, 10, 12 | acht Kästen „Typische Fehlvorstellung“, ersetzen die bisherigen Fließtextstellen | – |
| 26 | Kap. 10 | Kasten „Kapitel 10 in drei Sätzen“ | – |
| 27 | Verständnisprüfung | Fragen 7–10 mit Kurzantworten | – |
| 28 | Kap. 1 | Sprichwort unverändert (deckungsgleich mit Vortrag) | – |
| neu | Ende | Formelsammlung: Schreibweisen, Symbolverzeichnis mit Abgleich Vortrag/Notebook, 40 Formeln mit Erklärung und Kapitelverweis | – |

## Prüfung der neuen Fassung

- 395 Formeln mit KaTeX 0.16 ohne Fehler gerendert.
- Vier Mermaid-Diagramme mit mermaid-cli 11.4 erfolgreich gerendert.
- Alle lokalen Links im Ordner vorhanden.
- Alle Tabellen mit einheitlicher Spaltenzahl.

## Nicht im Lehrbuch, aber aufgefallen

- `Checkpoints/` enthält nur `bestes_modell_b.pt`; die Werkbank-Exporte stammen aus `bestes_modell.pt`
  (Schritt 2999, Validierungsverlust 0,398).
- `exportiere_attention.py` sucht `Hilfsskripte/vergleich_referenz.json`, die Datei liegt im Projektordner.
  Die Reproduktionsprüfung wird deshalb übersprungen. Die Datei enthält inzwischen die Greedy-Antwort des b-Laufs.

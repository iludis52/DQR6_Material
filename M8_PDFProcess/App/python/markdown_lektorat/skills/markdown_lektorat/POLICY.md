# Policy

- Bildreferenzen dürfen weder verändert noch verschoben werden.
- Seitenumbruchmarker dürfen nicht verändert werden.
- Keine fachliche Modernisierung oder freie stilistische Umformulierung.
- Korrigiere nur OCR-, Grammatik-, Rechtschreib- oder Strukturfehler, die aus dem Kontext ausreichend sicher ableitbar sind.
- Caption-, Tabellen- und Lesereihenfolgeentscheidungen sind semantische Entscheidungen des Modells.
- Bei Mehrdeutigkeit: `unresolved`.
- Gib für jede Entscheidung einen Confidence-Score zwischen 0 und 1 und eine kurze Begründung an.

- Gib nur tatsächliche Änderungen und echte `unresolved`-Fälle zurück. Unveränderte Blöcke werden nicht einzeln als `keep_unchanged` ausgegeben.
- Halte `reason` kurz und präzise, um die strukturierte Ausgabe klein zu halten.

# Reviewbericht: Cross-Artifact-Analyse Constitution → Spec → Plan → Tasks

**Datum:** 2026-09-08  
**Rolle:** Unabhängiger Reviewer (read-only Cross-Artifact-Analyse)  
**Geprüfte Artefakte:** `constitution.md`, `spec_final.md`, `plan.md`, `tasks.md`  
**Rangfolge bei Widersprüchen:** Constitution → Spec → Plan → Tasks

---

## 1. Gesamturteil

**READY WITH MINOR FIXES**

Die vier Artefakte sind in Kernarchitektur, Invarianten, Confidence-Modell und Prozessfluss weitgehend konsistent. Die Constitution-Prinzipien (Quelltreue, geschützte Elemente, LLM/Python-Trennung, kein Round-Trip-Rendering, Auditierbarkeit, Living-Spec) werden durch Plan und Tasks systematisch aufgegriffen. Keine Constitution-Verletzung gefunden. Es existieren jedoch wenige Spec-Anforderungen ohne Plan-/Task-Abdeckung und eine lückenhafte Regressionstest-Korpus-Liste, die vor Implementierungsstart behoben werden sollten.

---

## 2. Kritische Befunde

Keine Blocker. Insbesondere:

- Kein Widerspruch zwischen Constitution V/VI und Plan/Tasks: Source-Patching statt Neu-Rendering (plan.md §2, §9.3), strikte Operations-Whitelist (T031–T034), `unresolved`-Policy (T053/T054), Integritäts-Hard-Fail (T025/T026, T128/T129) sind konsistent mit Constitution IV, V, VI, VIII.
- Keine semantische Python-Heuristik in Plan/Tasks erkennbar; Negativtests T055/T080/T114 sichern dies explizit ab.
- Human-in-the-loop (Phase 22) und Living-Spec-Loop (Phase 23) entsprechen Constitution XII/XIII inkl. Fehlerklassifizierung (T176–T179).

---

## 3. Wichtige Befunde

| # | Artefakt | Stelle | Problem | Korrekturebene |
|---|---|---|---|---|
| B1 | tasks.md | T138 | T138 nennt 11 Fallklassen; FR-161 fordert mindestens 16. Fehlend u. a.: fehlerfreier Fließtext, fehlerhafte Wortzusammenziehung, intakte Markdown-Tabelle, Seitenumbrüche als eigener Fall, Tabellenbeschriftung, absichtlich nicht eindeutig lösbare Fälle (jenseits mehrdeutiger Captions). FR-161 ist mit „enthält mindestens" verbindlich. | Tasks |
| B2 | spec/plan/tasks | FR-005 vs. plan §5 `OutputConfig` | Spec erlaubt konfigurierbaren alternativen Ausgabeordner; Plan-`OutputConfig` enthält nur `overwrite`, `write_intermediate_artifacts`, `write_raw_responses`; kein Task deckt FR-005 ab. | Plan + Tasks |
| B3 | spec/tasks | FR-122 | „Durch Änderungen entstandene formale Markdown-Fehler müssen erkannt werden" — es existiert nur ein Tabellenvalidator-Task (T092/T093) und Protected-Integritätstests (T021–T026), aber kein RED/GREEN-Task für allgemeine formale Markdown-Strukturvalidierung des Ergebnisdokuments. | Tasks |
| B4 | spec/plan | FR-032/FR-164 vs. plan §5 `ConfidenceConfig` | Spec erlaubt/expliziert modellabhängige Schwellen; Plan sieht nur einen globalen Schwellensatz vor. Entweder per-Modell-Kalibrierung in `ConfidenceConfig` aufnehmen oder Einschränkung dokumentieren (Living-Spec-relevant, falls später benötigt). | Plan |
| B5 | plan/tasks | Phase 9 vs. Phase 10 | Prompt-Komposition (T071/T072) referenziert Ziel-/Kontextblöcke, deren Konzept erst in Phase 10 (Chunking, T074–T077) definiert und getestet wird. Reihenfolge Phase 9 ↔ 10 tauschen oder Prompt-Komposition auf Chunking-Vokabular erst nach T077 testen lassen. | Tasks |
| B6 | spec/plan | FR-006 | Spec delegiert die konkrete Kodierungsstrategie an `plan.md`; Plan enthält nur ein `encoding`-Feld ohne Strategie (read/write-Encoding, Fehlerbehandlung bei Dekodierproblemen). Kleine Lücke, aber explizit von der Spec gefordert. | Plan |
| B7 | spec/tasks | FR-052, FR-053 | Listen-Normalisierung und konservativer Umgang mit Math-Markup sind in der Spec definiert, aber in Plan-Operationsliste und Tasks nicht adressiert (allenfalls über generisches `replace_text` erreichbar — dann reicht eine Zuordnungsnotiz). | Plan oder Tasks (Dokumentation) |
| B8 | spec/tasks | FR-113 / FR-132 Punkt 7 | Mittlere/niedrige Konfidenz muss „im Reviewbericht ausgewiesen" werden. T116 nennt „Reviewfälle" generisch; ein expliziter Test, dass nicht angewandte mittelkonfidente Vorschläge im Review erscheinen, fehlt in Phase 11/15. | Tasks |

---

## 4. Überkomplexität

Insgesamt angemessen für die invariantenlastige Domäne; drei Anmerkungen:

1. **Negativtests auf Code-Abwesenheit (T055, T080, T114):** „Datei darf keine Heuristik enthalten" ist nicht sinnvoll automatisiert testbar; ein Test kann nur APIs prüfen, nicht die Abwesenheit von Logik. Empfehlung: als Code-Review-Checkliste in Phase 21 (T165) führen statt als RED/GREEN-Task — Constitution II.2 erlaubt diese Ausnahme ausdrücklich.
2. **23 Phasen / 184 Tasks** sind für ein einzelnes Post-Processing-Modul sehr feingranular, aber durch das strikte RED/GREEN-Modell begründet; keine Reduktion gefordert, nur Bewusstsein für den Verwaltungsaufwand.
3. **Optionale Raw-Request/Response-Artefakte + Checkpoints (T126/T127)** sind nice-to-have; konfigurierbar und damit ok, aber kein Abbruchkriterium, falls sie später gestrichen werden müssten.

---

## 5. Testabdeckung

Positiv: Nahezu alle testbaren Spec-Anforderungen folgen sauberem RED→GREEN-Paar-Schema mit konkreten Dateipfaden; Integrationstests mit Fake-LLM decken AC-001 bis AC-020 weitgehend ab; die Verhaltens-Invarianten (Quelle unverändert, Bild/Seitenumbruch, `unresolved`, Konfidenz-Gates) sind mehrfach redundant abgesichert — vorbildlich.

Lücken (bereits in Abschnitt 3): B1 (Korpus-Abdeckung vs. FR-161), B3 (FR-122), B8 (FR-113-Reviewausweis). Ferner: Spec §16 „Vorhandensein referenzierter Block-IDs" als Python-Prüfung hat keinen expliziten Test (implizit über Source-Match T039 streckbar, aber nicht benannt).

---

## 6. Coverage-Matrix (Auszug)

| Requirement / AC | Plan-Abdeckung | Task-Abdeckung | Status |
|---|---|---|---|
| FR-002 Quelle unverändert / AC-001 | §11, §26 | T007/T008, T136/T137 | ✅ |
| FR-003/004/AC-002/003 Ausgabenamen | §3.1 | T005/T006 | ✅ |
| FR-005 alternativer Ausgabeordner | — | — | ❌ (B2) |
| FR-010–014 / AC-004–006 Protected | §10 | T019–T026 | ✅ |
| FR-022 Silbentrennung | §12 Pass 1 | T082/T083 | ✅ |
| FR-027 Sprachartefakt | — | T088/T089 (generisch) | ✅ |
| FR-030–036 Confidence/unresolved | §15 | T027–T034, T049–T056 | ✅ |
| FR-032/164 modellabhängige Schwellen | §5 (nur global) | T153/T154 | ⚠️ (B4) |
| FR-040–044 Duplikate/Lesereihenfolge | §12 Pass 3 | T098–T105 | ✅ |
| FR-052/053 Listen/Math | — | — | ⚠️ (B7) |
| FR-060–064 Tabellen | §12 Pass 2, §23 | T090–T097 | ✅ |
| FR-070–077 Captions | §12 Pass 4, §24 | T106–T115 | ✅ |
| FR-080–083 Tabellenbeschriftungen | §12 Pass 4 | T112/T113 | ✅ |
| FR-090–099 LLM-Vertrag | §6, §7 | T027–T036, T057–T066 | ✅ |
| FR-110–115 Anwendungspolitik | §15 | T049–T054, T104/T105 | ✅ |
| FR-113 mittlere Konf. im Review | §16 | T116 (teils) | ⚠️ (B8) |
| FR-120–125 Validierung | §23, §25 | T092–T095, T128/T129 | ⚠️ FR-122 (B3) |
| FR-130–136 Reviewbericht / AC-017 | §16 | T116–T123 | ✅ |
| FR-140–144 Fehlerverhalten | §18 | T059–T066, T130/T131 | ✅ |
| FR-150–154 Modellunabhängigkeit | §5, §21 | T057–T060, T145–T155 | ✅ |
| FR-160–165 Regressionstest-Korpus | §20 | T138–T144 | ⚠️ FR-161 (B1) |
| FR-170–172 Skill/Policy | §14 | T067–T073 | ✅ |
| Constitution XII/XIII HITL/Living-Spec | — | Phase 22/23 (T168–T184) | ✅ |
| AC-020 keine Python-Heuristik | — | T055/T080/T114 | ✅ (Methodik siehe §4.1) |

---

## 7. Empfohlene Änderungen vor Implementierungsstart

Priorisierung: **P0** = blockierend, **P1** = wichtig, **P2** = optional.

1. **P1** — tasks.md T138: Fallliste auf die vollständigen FR-161-Mindestklassen erweitern (fehlerfreier Fließtext, Wortzusammenziehung, intakte Tabelle, Seitenumbruch-Fall, Tabellenbeschriftung, nicht eindeutig lösbare Fälle).
2. **P1** — plan.md `OutputConfig` um `output_dir` ergänzen; RED/GREEN-Task-Paar in Phase 2 ergänzen (FR-005).
3. **P1** — tasks.md: RED/GREEN-Paar für formale Markdown-Gesamtstrukturvalidierung des Ergebnisses ergänzen (FR-122), z. B. in Phase 16 neben T128/T129.
4. **P1** — Abhängigkeitsreihenfolge: Phase 9 (Prompts) hinter Phase 10 (Chunking) legen oder in T071 nur Chunking-unabhängige Promptbestandteile testen.
5. **P2** — plan.md: `ConfidenceConfig` für modellabhängige Schwellen öffnen (FR-032/FR-164) oder Einschränkung explizit dokumentieren.
6. **P2** — plan.md: Kodierungsstrategie konkretisieren (read/write-Encoding, Fehlerverhalten bei Dekodierung) — FR-006 delegiert dies ausdrücklich an den Plan.
7. **P2** — tasks.md: T055/T080/T114 als Review-Checklisteneinträge in Phase 21 (T165) umformulieren statt als automatisierte Negativtests.
8. **P2** — tasks.md: Test ergänzen, dass nicht angewandte mittel-/niedrigkonfidente Vorschläge im Reviewbericht ausgewiesen werden (FR-113/FR-132.7).
9. **P2** — plan.md/tasks.md: Zuordnung notieren, wie FR-052 (Listen) und FR-053 (Math) über bestehende Operationen (`replace_text`/Klasse-B-Policy) abgedeckt sind.
10. **P2** — tasks.md: Validierungstest „referenzierte Block-ID existiert" explizit benennen (Spec §16), auch wenn implizit über T039 streckbar.

---

## Fazit

Nach Behebung der P1-Punkte (1–4) ist das Artefakt-Set implementierungsbereit; die P2-Punkte können im Living-Spec-Fluss nachgezogen werden, ohne Architektur oder Constitution zu berühren.

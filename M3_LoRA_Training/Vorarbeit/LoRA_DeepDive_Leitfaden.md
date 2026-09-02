# Ein tiefgreifender Leitfaden zu Low Rank Adaptation (LoRA)

Dieses Tutorial bietet einen vollständigen und detaillierten Einstieg in das Konzept der **Low Rank Adaptation (LoRA)**. Es baut die grundlegenden Mechanismen großer Sprachmodelle (LLMs) Schritt für Schritt auf und erklärt, wie LoRA diese Architektur nutzt, um effizientes Fine-Tuning zu ermöglichen, ohne vorhandenes Wissen zu zerstören.

---

## 1. Das Grundproblem: Die hochdimensionale Schatzsuche

Moderne große Sprachmodelle (LLMs) besitzen oft Milliarden oder gar Billionen von Parametern. Wenn man ein solches Modell für eine neue, spezifische Aufgabe trainieren möchte (Fine-Tuning), steht man vor einem enormen Rechenaufwand. 

Um dieses Problem zu veranschaulichen, hilft eine Metapher: Stell dir vor, du suchst nach dem perfekten Modell (dem "Schatz") in einem gigantischen, hochdimensionalen Wald (dem Parameterraum). Da du dich in Millionen von Richtungen gleichzeitig bewegen kannst, ist die Suche extrem ineffizient und teuer.
Die Lösung von LoRA ist die **Dimensionsreduktion**. Anstatt sich völlig frei im Wald zu bewegen, baut man gewissermaßen "Schienen" und schränkt seine Bewegung auf vorgegebene Pfade ein. Man verliert zwar die absolute Freiheit und trifft den perfekten theoretischen Punkt vielleicht nicht haargenau, aber man nähert sich dem Ziel mit einem Bruchteil des Rechenaufwands.

---

## 2. Das Fundament: Wie "denkt" ein Transformer?

Um zu verstehen, wo und wie LoRA ansetzt, muss man zunächst die Architektur betrachten, auf der heutige LLMs basieren: den **Decoder-only Transformer**. 
Ein Transformer besteht aus einem riesigen Stapel vieler identischer Schichten (oft 32, 80 oder mehr). In jeder dieser Schichten wechseln sich zwei Kernkomponenten ab:

### A) Die Self-Attention-Schicht: Der "Kontext-Sucher"
Wenn ein Modell einen Text verarbeitet, betrachtet es Wörter (Tokens) nicht isoliert. In der Attention-Schicht "schaut" jedes Wort auf alle vorherigen Wörter im Satz und berechnet, wie wichtig diese für seine eigene Bedeutung sind. Hier tauschen die Wörter Informationen aus, und der *Kontext* entsteht (z.B. die Entscheidung, ob das Wort "Bank" im aktuellen Satz ein Finanzinstitut oder eine Sitzgelegenheit meint).

### B) Das Feed-Forward-Netzwerk (FFN): Das "Fakten-Gedächtnis"
Nach der Kontextbildung durchlaufen die Wörter eine Feed-Forward-Schicht. Hier betrachten die Wörter einander nicht mehr; jedes Token wird isoliert durch gigantische Matrizen gepresst. In diesen Matrizen ist das meiste antrainierte "Weltwissen" und die komplexe Mustererkennung des Modells gespeichert.

Dieses ständige Alternieren – Kontext sammeln, Fakten abrufen, Kontext sammeln, Fakten abrufen – ermöglicht es dem Modell, komplexe Sprache zu generieren.

---

## 3. Das Konzept LoRA: Der parallele Bypass

Wenn wir nun das Modell anpassen wollen, greifen wir nicht in das gigantische Original-Wissen ein. LoRA fügt sich als **paralleler Bypass** (ein Seitenweg) an die bestehenden Matrizen des Modells an. Dies geschieht in drei logischen Schritten:

1. **Einfrieren (Freeze):** Das gigantische Basiswissen (die Original-Matrizen $W$) des Transformers wird komplett eingefroren. Während des LoRA-Trainings wird hier absolut nichts verändert.
2. **Der Bypass:** Neben die eingefrorene Matrix wird ein kleiner Seitenweg gebaut. Dieser besteht aus zwei winzigen Matrizen, $A$ und $B$. Die Originalmatrix $\Delta W$ wird hierbei in diese zwei stark komprimierten Matrizen zerlegt, was man als Matrix mit niedrigem Rang ("Low Rank") bezeichnet.
3. **Die Addition:** Wenn nun ein Daten-Input ($x$) ankommt, fließt er durch beide Wege gleichzeitig. Das Modell rechnet:
   $$h = Wx + BAx$$
   *(Ausgabe = Altes Basiswissen + Neues LoRA-Korrektursignal)*

### Die Art der "neuen Informationen"
Das LoRA liefert also ein Korrektursignal. Es erzeugt in der Regel kein massives neues Weltwissen, da es dafür zu klein ist. Stattdessen wirkt es wie ein Regisseur. Es lenkt die Gewichte so um, dass das Modell einen neuen **Schreibstil** (z. B. Chatbot-Verhalten), einen neuen **Tonfall** oder **spezifisches Fachvokabular** adaptiert. Das Basismodell bleibt die riesige Festplatte für Weltwissen; das LoRA ist der Arbeitsspeicher, der die aktuellen Verhaltensregeln vorgibt.

---

## 4. Architektur und Platzierung: Wo greift LoRA ein?

Wo platziert man diesen Bypass im Transformer? Die Verarbeitung in den übereinandergestapelten Schichten eines Modells erfolgt **hierarchisch**:
* **Untere Schichten:** Analysieren grundlegende Syntax und Wortkombinationen.
* **Mittlere Schichten:** Bauen den lokalen Kontext auf und lösen Bezüge zwischen Sätzen.
* **Obere Schichten:** Verarbeiten komplexe Logik, abstrakte Konzepte und den finalen Tonfall.

Daher platziert man LoRA im modernen Fine-Tuning (wie bei QLoRA) **in der Regel in allen Schichten gleichzeitig**. Wenn man einem Modell ein neues Verhalten (z.B. den Sprachstil eines Piraten) beibringen möchte, reicht es nicht, nur die finale Ausgabe umzubiegen. Man muss den Gedankenfluss des Modells sanft und kontinuierlich von der ersten Silbe (unten) bis zur finalen abstrakten Logik (oben) in die gewünschte Richtung lenken.

Innerhalb einer Schicht kann man LoRA nur an die Attention-Matrizen (speziell *Queries* und *Values*) hängen, um extrem viel Speicher zu sparen. Moderner und leistungsfähiger ist es jedoch, LoRA an *alle* linearen Schichten – also auch an die FFN-Schichten ("Fakten-Gedächtnis") – zu koppeln.

---

## 5. Konfiguration: Wie konstruiert man ein LoRA?

Als Architekt eines LoRA-Modells muss man die Größe der Matrizen $A$ und $B$ festlegen. Dies geschieht primär über zwei Parameter:

### A) Der Rang ($r$)
Der Rang bestimmt die Größe des "Flaschenhalses" im Bypass. Je größer $r$, desto mehr Freiheitsgrade hat das LoRA, sich anzupassen.
* **$r = 4$ bis $8$:** Ausreichend für einfache Stil-Anpassungen (z. B. Ausgabeformatierungen erzwingen).
* **$r = 16$ bis $32$:** Der Standard für "Instruction Tuning", um dem Modell das Befolgen komplexer Anweisungen und Logik-Schritte beizubringen.
* **$r = 64$ bis $256$:** Nötig, wenn fundamental neues Fachwissen (Medizin, Jura, neue Sprachen) antrainiert werden soll. 
*Hinweis:* Ein zu hoher Rang führt oft zu "Overfitting" (sturem Auswendiglernen) und zerstört den Effizienzvorteil.

### B) LoRA Alpha ($lpha$)
Alpha ist der Verstärker (Skalierungsfaktor). Er bestimmt, wie "laut" das Korrektursignal des LoRA dem Basismodell überlagert wird. Als Faustregel setzt man Alpha meist auf **das Doppelte des Rangs** (z. B. $r=16 ightarrow lpha=32$).

---

## 6. Das Training: Wie formen sich die Matrizen?

Damit sich die Matrizen $A$ und $B$ korrekt formen, nutzt man **Supervised Fine-Tuning (SFT)**. Das Modell wird mit strukturierten Frage-Antwort-Paaren (meist im JSONL-Format) gefüttert.

Zwei gängige Formate sind:
1. **Instruction-Format (Alpaca-Style):** Bestehend aus `instruction`, `input` und dem erwarteten `output`.
2. **Chat-Format (ChatML):** Ein Konversationsprotokoll mit verteilten Rollen (`system`, `user`, `assistant`).

**Der Trainingsablauf:**
Das Trainingsprogramm leitet den Input (z. B. die Frage des Nutzers) durch das Modell. Das Modell wandert durch alle Schichten und generiert eine Antwort. Diese Antwort wird mit der perfekten Musterantwort aus den Trainingsdaten verglichen. Daraus errechnet sich ein mathematischer Fehlerwert (der **Loss**).
Dieses Fehlersignal wird nun rückwärts durch das Netz geschickt (Backpropagation). Da die Basis-Matrizen $W$ eingefroren sind, prallt das Update dort ab. Der Fehlerwert darf **ausschließlich** die Zahlen in den winzigen Matrizen $A$ und $B$ anpassen. Mit tausenden Beispielen verschieben sich diese Zahlen exakt so, dass sie künftig das perfekte Korrektursignal aussenden.

---

## 7. Der entscheidende Vorteil: Schutz vor Catastrophic Forgetting

Das klassische Fine-Tuning hat ein gewaltiges Problem: das **Catastrophic Forgetting** (katastrophales Vergessen). Wenn man beim traditionellen Training alle Parameter eines Modells aktualisiert, um ihm beispielsweise Medizinwissen beizubringen, zerstört man dabei oft die fragile Balance der Originalgewichte. Das Modell wird zum Medizin-Experten, vergisst aber womöglich seine französische Grammatik.

**LoRA löst dieses Problem durch Parameter-Isolation:**
Da das Fundament (die Original-Matrix $W$) beim LoRA-Training vollständig eingefroren bleibt, ist das ursprüngliche Weltwissen und die Basis-Grammatik absolut sicher. Das neue medizinische Fachwissen wird exklusiv und isoliert in die winzigen Bypässe ($A$ und $B$) geschrieben. 
Dies ermöglicht es, das neue Wissen flexibel wie eine externe Festplatte an das Modell anzudocken. Schaltet man das LoRA ab, befindet sich das Basismodell wieder im exakt gleichen, unberührten Zustand wie vor dem Training – es hat nichts vergessen.

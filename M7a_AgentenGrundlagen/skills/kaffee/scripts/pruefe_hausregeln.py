import sys, re

text = open(sys.argv[1], encoding="utf-8").read()

regeln = {
    "Gramm statt Loeffel":   bool(re.search(r"\d+\s?g\b", text)) and not re.search(r"[Ll]öffel", text),
    "genau drei Schritte":   len(re.findall(r"^\s*\d[\.\)]", text, re.M)) == 3,
    "Temperatur + Toleranz": bool(re.search(r"\d+\s?°\s?C\s*±", text)),
    "Fehlersatz am Ende":    bool(re.search(r"(?i)h(ä|ae|a)ufigster\s+fehler\s*:", text)),
}

for regel, erfuellt in regeln.items():
    print(("OK     " if erfuellt else "FEHLER ") + regel)

print("Erfuellt:", sum(regeln.values()), "von", len(regeln))
# Herkunft und Lizenzen

## GuppyLM
Dieses Lehrmaterial ist eine Bearbeitung von
https://github.com/arman-bd/guppylm (Autor: arman-bd)
Das Original steht laut README unter der MIT-Lizenz.

Trainingsdaten: arman-bd/guppylm-60k-generic (MIT),
DOI: 10.57967/hf/8339

### Was in dieser Fassung geändert wurde
- Notebook auf lokale Ausführung umgestellt (Colab-Abhängigkeiten entfernt)
- Didaktischer Neuaufbau: Modell in Bausteinen statt %%writefile,
  Beobachtungszellen, Trainingsschleife offen im Notebook
- Übersetzung ins Deutsche
- FFN-Aktivierung ReLU -> GELU, ffn_hidden 768 -> 1536
  (Voraussetzung für den Export nach GGUF)
- Ergänzt: Exportweg nach GPT-2/GGUF für LM Studio

## llama.cpp
Im Exportnotebook wird https://github.com/ggml-org/llama.cpp geklont
(MIT). Es wird nicht mitverteilt.
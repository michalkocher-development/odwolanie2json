### Treningowy UZP (180 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 1.000 | 0.25 s | $0.000 | 0.00 |
| **Hybryda (nasz system)** | 1.000 | 0.50 s | $0.022 | 0.72 |
| Hybryda bez LLM (regex + model decyzyjny) | 1.000 | 0.44 s | $0.006 | 0.65 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 1.000 | 0.27 s | $0.014 | 0.07 |
| Samo LLM: tekst (8k znaków) + wzór JSON | 0.885 | 2.74 s | $0.275 | 1.00 |
| Samo LLM: cały tekst + wzór JSON | 0.888 | 3.96 s | $0.347 | 1.00 |
| Samo LLM: tekst + wymuszony JSON Schema | 0.891 | 3.05 s | $0.271 | 1.00 |
| Samo LLM wizyjne: obrazy stron + wzór JSON | 0.712 | 5.66 s | $0.234 | 1.00 |

### Adwersaryjny kontrolny (90 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 0.535 | 0.08 s | $0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.884 | 1.82 s | $0.134 | 1.81 |
| Hybryda bez LLM (regex + model decyzyjny) | 0.633 | 0.38 s | $0.010 | 0.76 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 0.800 | 1.10 s | $0.103 | 0.83 |
| Samo LLM: tekst (8k znaków) + wzór JSON | 0.827 | 2.43 s | $0.217 | 1.00 |
| Samo LLM: cały tekst + wzór JSON | 0.831 | 2.48 s | $0.208 | 1.00 |
| Samo LLM: tekst + wymuszony JSON Schema | 0.826 | 2.61 s | $0.207 | 1.00 |
| Samo LLM wizyjne: obrazy stron + wzór JSON | 0.714 | 3.40 s | $0.193 | 1.00 |

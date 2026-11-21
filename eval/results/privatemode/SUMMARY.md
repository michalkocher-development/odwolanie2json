### Treningowy UZP (180 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 1.000 | 0.29 s | €0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.999 | 14.80 s | €0.071 | 1.30 |
| Hybryda bez LLM (regex + model decyzyjny) | 0.999 | 13.50 s | €0.040 | 1.23 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 1.000 | 2.96 s | €0.031 | 0.07 |
| Samo LLM: cały tekst + wzór JSON | 0.893 | 11.84 s | €0.619 | 1.00 |

### Adwersaryjny kontrolny (90 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 0.572 | 0.10 s | €0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.885 | 28.80 s | €0.300 | 2.51 |
| Hybryda bez LLM (regex + model decyzyjny) | 0.646 | 26.90 s | €0.070 | 1.93 |
| Hybryda bez modelu decyzyjnego (regex + LLM) | 0.806 | 6.47 s | €0.203 | 0.83 |
| Samo LLM: cały tekst + wzór JSON | 0.836 | 16.68 s | €0.354 | 1.00 |

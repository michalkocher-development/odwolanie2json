### Treningowy UZP (180 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 0.998 | 0.16 s | €0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.998 | 0.55 s | €0.071 | 0.80 |
| Samo LLM: cały tekst + wzór JSON | 0.905 | 3.03 s | €0.623 | 1.00 |

### Adwersaryjny kontrolny (90 dok.)

| wariant | F1 | śr. czas / dok. | koszt / 1000 dok. | wywołań modeli / dok. |
|---|---|---|---|---|
| Same regexy/reguły (bez modeli) | 0.562 | 0.06 s | €0.000 | 0.00 |
| **Hybryda (nasz system)** | 0.881 | 2.44 s | €0.301 | 1.98 |
| Samo LLM: cały tekst + wzór JSON | 0.822 | 2.57 s | €0.356 | 1.00 |

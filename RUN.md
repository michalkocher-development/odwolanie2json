# RUN – uruchomienie oceny

Komenda (z katalogu `/opt/solution`):

```bash
sudo docker compose --profile cli run --rm cli
```

- Przetwarza wszystkie PDF-y z `/opt/solution/input` (także w podkatalogach) i zapisuje wyniki do
  `/opt/solution/output` – jeden plik JSON na dokument, ta sama nazwa i struktura katalogów
  (`input/<sprawa>/odwolanie.pdf` -> `output/<sprawa>/odwolanie.json`). Dokument spoza obsługiwanych klas -> `{}`.
- Kończy się sama, bez interakcji. Postęp na stderr. Ślad ekstrakcji (metoda i cytat dla pól): `/opt/solution/trace`.
- Obraz Dockera jest zbudowany wcześniej na serwerze (`odwolanie2json:latest`); komenda go nie pobiera.

## Usługi zewnętrzne

- **Privatemode** (Edgeless Systems, serwery w UE) – API zgodne z OpenAI, model open-source **GLM-5.3-Flash** (MIT):
  OCR skanów (model wizyjny), model decyzyjny (wybory, klasyfikacja) i uzupełnianie pól, których nie znalazły reguły.
- Klucz: `/opt/solution/.env` -> `PRIVATEMODE_API_KEY=...` (wzór: `.env.example`). Bez klucza system działa w trybie
  samych reguł (regexy z YAML), bez OCR skanów.

Konfiguracja (dostawca, klasy dokumentów, walidacja): `config/` – opis w `README.md` i `docs/`.

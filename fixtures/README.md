# Fixtures sintetici

Dati **finti** per provare gli import senza usare anagrafiche reali (che contengono dati di
minori e dati sensibili e **non vanno mai versionati**).

- `sample_coca.csv`    -> `uv run python manage.py import_coca fixtures/sample_coca.csv --dry-run`
- `sample_ragazzi.csv` -> `uv run python manage.py import_ragazzi fixtures/sample_ragazzi.csv --dry-run`
- `sample_evento.csv`  -> `uv run python manage.py import_evento fixtures/sample_evento.csv --edizione 1 --dry-run`

Mappatura colonne completa: vedi `docs/Plancia_Progettazione.md`, Appendice D.

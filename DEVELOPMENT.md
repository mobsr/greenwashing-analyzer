# Entwicklerdokumentation

## Entwicklungsumgebung einrichten

### 1. Repository klonen und Dependencies installieren

```bash
git clone https://github.com/mobsr/greenwashing-analyzer.git
cd greenwashing-analyzer

# Virtuelle Umgebung erstellen
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt
```

### 2. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
# .env bearbeiten und OPENAI_API_KEY hinzufügen
```

### 3. Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage
pytest --cov=src tests/

# Einzelner Test
pytest tests/test_analyzer.py::TestGreenwashingAnalyzer::test_analyzer_initialization -v
```

## Code-Qualität

### Formatierung mit Black

```bash
# Code formatieren
black src/ tests/ --line-length 100

# Nur prüfen (CI)
black src/ tests/ --line-length 100 --check
```

### Linting mit Flake8

```bash
# Linting durchführen
flake8 src/ tests/ --max-line-length 100 --ignore=E501,W503

# Mit Konfiguration
flake8 src/ tests/
```

### Type Checking mit mypy

```bash
# Type Checking
mypy src/ --ignore-missing-imports
```

## Projekt-Struktur

```
greenwashing-analyzer/
├── src/                          # Hauptcode
│   ├── __init__.py              # Package Exports
│   ├── analyzer.py              # Greenwashing-Analyse Logik
│   ├── loader.py                # PDF-Verarbeitung
│   └── logger_config.py         # Logging-Konfiguration
├── tests/                        # Unit Tests
│   ├── __init__.py
│   └── test_analyzer.py
├── app.py                        # Streamlit UI
├── requirements.txt              # Dependencies
├── pytest.ini                    # Test-Konfiguration
├── .env.example                  # Umgebungsvariablen-Vorlage
├── README.md                     # Projektdokumentation
├── SECURITY.md                   # Sicherheitshinweise
└── DEVELOPMENT.md                # Diese Datei
```

## Neue Features entwickeln

### 1. Branch erstellen

```bash
git checkout -b feature/mein-feature
```

### 2. Code schreiben

- Folgen Sie den bestehenden Code-Konventionen
- Fügen Sie Docstrings hinzu (Google-Style)
- Schreiben Sie Tests für neue Funktionalität

### 3. Tests schreiben

```python
# tests/test_mein_feature.py
import pytest
from src.mein_modul import MeineKlasse

class TestMeineKlasse:
    def test_grundfunktion(self):
        obj = MeineKlasse()
        assert obj.methode() == "erwartetes_ergebnis"
```

### 4. Code formatieren und testen

```bash
black src/ tests/
flake8 src/ tests/
pytest
```

### 5. Commit und Push

```bash
git add .
git commit -m "feat: Beschreibung des Features"
git push origin feature/mein-feature
```

## Logging Best Practices

```python
from src.logger_config import setup_logger

logger = setup_logger("modul_name")

# Verschiedene Log-Levels
logger.debug("Detaillierte Debug-Information")
logger.info("Normale Information")
logger.warning("Warnung")
logger.error("Fehler aufgetreten")
logger.exception("Fehler mit Traceback")
```

## Fehlerbehandlung

### DO ✅

```python
try:
    result = api_call()
except SpecificException as e:
    logger.error(f"API-Fehler: {str(e)}")
    return None
```

### DON'T ❌

```python
try:
    result = api_call()
except:  # Zu breite Exception
    pass  # Silent fail
```

## Performance-Optimierung

### Caching nutzen

```python
# ReportLoader nutzt automatisch Caching
loader = ReportLoader("report.pdf")
chunks = loader.load(use_cache=True)  # Lädt aus Cache falls vorhanden
```

### Parallele Verarbeitung

```python
# ThreadPoolExecutor für I/O-intensive Tasks
with ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(task, arg) for arg in args]
    results = [f.result() for f in as_completed(futures)]
```

## Debugging

### Streamlit Debug Mode

```bash
streamlit run app.py --logger.level=debug
```

### Python Debugger

```python
# Breakpoint setzen
import pdb; pdb.set_trace()

# Oder in Python 3.7+
breakpoint()
```

### Logging für Debugging

```python
logger.debug(f"Variable x hat Wert: {x}")
logger.debug(f"Funktion wurde mit args={args} aufgerufen")
```

## Häufige Probleme

### Problem: "ModuleNotFoundError"

**Lösung**: Dependencies installieren
```bash
pip install -r requirements.txt
```

### Problem: OpenAI API Fehler

**Lösung**: API Key prüfen
```bash
# .env Datei prüfen
cat .env | grep OPENAI_API_KEY

# Oder in Python
import os
print(os.getenv("OPENAI_API_KEY"))
```

### Problem: Tests schlagen fehl

**Lösung**: 
1. Virtual Environment aktivieren
2. Dependencies neu installieren
3. Pytest Cache löschen: `rm -rf .pytest_cache`

## Commit-Konventionen

Verwenden Sie Conventional Commits:

- `feat:` Neues Feature
- `fix:` Bugfix
- `docs:` Dokumentation
- `test:` Tests hinzufügen/ändern
- `refactor:` Code-Refactoring
- `style:` Formatierung
- `chore:` Tooling, Dependencies

Beispiel:
```
feat: Add support for custom greenwashing tags
fix: Resolve highlighting issue with multi-line quotes
docs: Update README with installation instructions
```

## Weiterführende Ressourcen

- [Streamlit Documentation](https://docs.streamlit.io/)
- [OpenAI API Reference](https://platform.openai.com/docs/)
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)
- [pytest Documentation](https://docs.pytest.org/)

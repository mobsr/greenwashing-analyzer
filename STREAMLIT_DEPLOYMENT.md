# Streamlit Cloud Deployment Guide

## Problembehebung: Analyse funktioniert nicht auf Streamlit Cloud

### Ursachen und Lösungen:

#### 1. **API-Schlüssel nicht konfiguriert** ⭐ WICHTIGSTER FEHLER
**Problem:** Der OpenAI API-Schlüssel wird auf Streamlit Cloud nicht gefunden.

**Lösung:**
1. Öffne deine App auf Streamlit Cloud
2. Klicke auf **☰ → Settings → Secrets**
3. Füge folgende Zeile ein:
   ```
   OPENAI_API_KEY = "sk-dein-openai-api-schluessel"
   ```
4. Speichern und die App neu laden (⚡ Rerun)

#### 2. **Fehlerbehandlung verbessert**
Die App zeigt jetzt detaillierte Fehlermeldungen bei:
- Fehlenden API-Schlüsseln
- JSON-Parsing-Fehlern
- API-Timeouts
- Authentifizierungsproblemen

#### 3. **Lokale Entwicklung (.env)**
Für die lokale Entwicklung:
```bash
# .env erstellen
OPENAI_API_KEY=sk-dein-openai-api-schluessel
```

### Deployment Checklist:

- [ ] OpenAI API-Schlüssel in Streamlit Cloud Secrets eintragen
- [ ] `requirements.txt` ist aktuell (siehe unten)
- [ ] App lokal mit `streamlit run app.py` getestet
- [ ] PDF-Upload funktioniert
- [ ] Analyse wird gestartet und gibt keine Fehler

### Installierte Pakete:

```bash
pip install -r requirements.txt
```

### Lokales Testing:
```bash
# Virtuelle Umgebung aktivieren
python -m venv venv
venv\Scripts\activate

# Abhängigkeiten installieren
pip install -r requirements.txt

# App starten
streamlit run app.py
```

### Häufige Fehlermeldungen:

| Fehler | Ursache | Lösung |
|--------|--------|--------|
| `API-Schlüssel nicht gefunden` | OPENAI_API_KEY nicht in Secrets | Siehe Schritt 1 oben |
| `JSON Parsing-Fehler` | OpenAI API gibt ungültiges JSON | Timeout erhöhen, Modell downgraden auf gpt-4o-mini |
| `RateLimitError` | Zu viele API-Aufrufe gleichzeitig | Maximal 20 Seiten pro Bericht testen |
| `Timeout` | API antwortet nicht rechtzeitig | Kleinere PDFs testen (max 10 Seiten) |

### Support:
Wenn die Analyse immer noch nicht funktioniert:
1. Überprüfe die Streamlit Cloud Logs (App Dashboard → Logs)
2. Teste mit einer kleinen PDF (5 Seiten)
3. Versuche mit dem Modell `gpt-4o-mini` statt `gpt-4o`

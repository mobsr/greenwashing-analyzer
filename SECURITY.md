# Sicherheitshinweise

## Bekannte Sicherheitsaspekte

### 1. API-Key Verwaltung

**Status**: ✅ Implementiert

- API-Keys werden über Umgebungsvariablen (.env) oder Streamlit Secrets verwaltet
- `.env` Datei ist in `.gitignore` ausgeschlossen
- Keine Hardcoded Secrets im Code

**Empfehlung für Produktion**:
- Verwenden Sie ein Secrets Management System (z.B. AWS Secrets Manager, Azure Key Vault)
- Rotieren Sie API-Keys regelmäßig

### 2. Passwort-Hashing

**Status**: ⚠️ Verbesserungsbedarf

- Aktuell: SHA256-Hashing für App-Passwort
- Problem: SHA256 ist nicht für Passwort-Hashing optimiert

**Empfehlung für Produktion**:
```python
# Statt SHA256:
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

### 3. Input-Validierung

**Status**: ⚠️ Verbesserungsbedarf

- Aktuell: Minimale Validierung von User-Inputs
- Potenzielle Risiken:
  - Unvalidierte Seitennummern
  - Ungeprüfte Datei-Uploads
  - Keine Schema-Validierung für JSON-Responses

**Empfehlung**:
- Verwenden Sie Pydantic für Input-Validierung
- Prüfen Sie Datei-Typen und -Größen vor Upload
- Validieren Sie alle User-Inputs

### 4. Rate Limiting

**Status**: ⚠️ Nicht implementiert

- Keine Rate Limits für API-Aufrufe
- Risiko: Kostenexplosion bei Missbrauch

**Empfehlung für Produktion**:
- Implementieren Sie Rate Limiting (z.B. mit Streamlit Session State)
- Setzen Sie Budget-Limits für OpenAI API
- Monitoring der API-Kosten

### 5. Datenschutz

**Status**: ✅ Grundlegend implementiert

- Hochgeladene PDFs werden lokal gespeichert
- Keine Weitergabe an Dritte (außer OpenAI für Analyse)
- Cache-Daten werden lokal gespeichert

**Wichtige Hinweise**:
- PDFs können sensible Unternehmensdaten enthalten
- OpenAI API: Daten werden nicht für Training verwendet (gemäß OpenAI Policy)
- Cache-Daten sollten regelmäßig gelöscht werden

### 6. XSS-Schutz

**Status**: ⚠️ Teilweise implementiert

- `unsafe_allow_html=True` wird für Styling verwendet
- Potenzielle XSS-Risiken bei User-generierten Inhalten

**Empfehlung**:
- Sanitizen Sie alle User-Inputs vor HTML-Rendering
- Verwenden Sie `st.markdown()` ohne `unsafe_allow_html` wo möglich

## Melden von Sicherheitslücken

Falls Sie eine Sicherheitslücke entdecken:

1. **Nicht öffentlich** im GitHub Issue-Tracker melden
2. Kontaktieren Sie den Autor direkt
3. Beschreiben Sie das Problem detailliert
4. Geben Sie ggf. einen Proof-of-Concept an

## Best Practices für Deployment

1. **Umgebungsvariablen**: Verwenden Sie Streamlit Secrets für API-Keys
2. **HTTPS**: Stellen Sie sicher, dass die App über HTTPS läuft
3. **Monitoring**: Implementieren Sie Logging und Monitoring
4. **Updates**: Halten Sie Dependencies aktuell (`pip-audit`, `safety`)
5. **Backups**: Regelmäßige Backups von wichtigen Daten

## Abhängigkeiten-Sicherheit

Prüfen Sie regelmäßig auf verwundbare Dependencies:

```bash
# Mit pip-audit
pip install pip-audit
pip-audit

# Mit safety
pip install safety
safety check
```

## Compliance

Für akademische/Forschungszwecke:
- Beachten Sie Datenschutzrichtlinien Ihrer Institution
- Anonymisieren Sie sensible Daten in Beispielen
- Dokumentieren Sie Datenverarbeitungsprozesse

Für kommerzielle Nutzung zusätzlich:
- DSGVO-Compliance prüfen
- OpenAI Terms of Service beachten
- Ggf. Data Processing Agreement mit OpenAI abschließen

# Architecture Documentation

## System Overview

Der Greenwashing Analyzer ist eine KI-gestützte Anwendung zur Analyse von CSR-Berichten. Das System verwendet einen hybriden Ansatz, der sowohl textuelle als auch visuelle Informationen aus PDF-Dokumenten extrahiert und analysiert.

## High-Level Architektur

```
┌─────────────┐
│   User UI   │ (Streamlit)
└──────┬──────┘
       │
       ├─────────────────────────────────┐
       │                                 │
┌──────▼──────┐                   ┌─────▼─────┐
│ ReportLoader│                   │  Analyzer  │
│  (loader.py)│                   │(analyzer.py│
└──────┬──────┘                   └─────┬─────┘
       │                                 │
       ├── PDF Processing                ├── Pass 1: Analysis
       ├── Vision API (GPT-4o)           ├── Pass 2: Verification
       └── Text Extraction               └── LLM Orchestration
                  │                             │
                  └─────────┬──────────────────┘
                            │
                     ┌──────▼──────┐
                     │  OpenAI API │
                     └─────────────┘
```

## Komponenten-Details

### 1. User Interface (app.py)

**Verantwortlichkeiten:**
- Streamlit-basierte Web-Oberfläche
- Session State Management
- Authentifizierung (Password Hash)
- Feedback-System und CSV-Export
- Visualisierung (Plotly Charts)

**Technologien:**
- Streamlit 1.31+
- Plotly für interaktive Charts
- Session State für Client-Side Storage

**Hauptfunktionen:**
- `_init_api_key()`: API Key Initialisierung
- `_require_auth()`: Passwort-basierte Authentifizierung
- Tab 1: PDF Upload und Vorschau
- Tab 2: Analyse und Dashboard

### 2. Report Loader (src/loader.py)

**Verantwortlichkeiten:**
- PDF-zu-Text Extraktion (pymupdf4llm)
- Vision API Integration für Bilder
- Parallele Verarbeitung (ThreadPoolExecutor)
- Caching (JSON-basiert)
- Highlight-Generierung für Zitate

**Datenfluss:**
```
PDF Input
  └─> PyMuPDF (Layout-Analyse)
      └─> Seiten-Bilder (PNG)
          └─> GPT-4o Vision API (parallel, max 2 workers)
              └─> Kombinierter Text + Vision Output
                  └─> JSON Cache
```

**Caching-Strategie:**
```
data/
└── processed/
    └── {document_name}/
        ├── data.json          # Processed chunks
        ├── images/            # Original page images
        │   └── page_1.png
        └── highlights/        # Quote-highlighted images
            └── p1_abc123.png
```

**Performance-Optimierungen:**
- ThreadPoolExecutor mit max 2 Workers (Rate Limit Protection)
- Exponential Backoff bei Rate Limit Errors
- Image Caching (kein Re-Rendering)

### 3. Greenwashing Analyzer (src/analyzer.py)

**Zweistufiger Analyse-Prozess:**

#### Pass 1: Sequential Analysis
```python
for each chunk in document:
    1. Kontext: [prev_page, current_page, next_page]
    2. LLM Call mit System Prompt:
       - Finde Greenwashing-Indikatoren
       - Extrahiere neue Claims
       - Verifiziere bekannte Claims
    3. Update Memory:
       - findings[] (mit Seite, Kategorie, Zitat)
       - claims_memory[] (mit ID, Status, Evidence)
```

**Kontextfenster-Strategie:**
- Vorherige Seite: Satzübergänge verstehen
- Aktuelle Seite: Hauptanalyse
- Nächste Seite: Fortsetzungen erkennen
- **Wichtig**: Nur aktuelle Seite wird bewertet

#### Pass 2: Deep Verification
```python
for each OPEN claim:
    keywords = extract_significant_words(claim.text)
    
    for each chunk (except origin page):
        if keyword_match > 30%:
            verification = LLM_verify(claim, chunk)
            if verification.is_evidence == true:
                claim.status = POTENTIALLY_VERIFIED
                break
```

**Anti-Self-Verification:**
- Claims können sich nicht selbst belegen
- Nur andere Seiten werden als Evidenz akzeptiert

**LLM Prompting-Strategie:**

1. **System Prompt** (analyzer.py:137-163):
   - Rolle: "Vorsichtiger, wissenschaftlicher Auditor"
   - Sprache: Deskriptiv (Indiz, Hinweis)
   - JSON-Response Format

2. **User Prompt** (analyzer.py:168-185):
   - Kontext-Injection (prev/current/next)
   - Memory-Liste (bekannte Claims)
   - Offene Ziele zur Verifizierung

3. **Response Format**:
```json
{
    "findings": [
        {
            "category": "VAGUE|INCONSISTENCY|DATA_GAP",
            "quote": "...",
            "reasoning": "..."
        }
    ],
    "new_claims": [
        {
            "claim": "...",
            "context": "..."
        }
    ],
    "claim_updates": [
        {
            "id": 1,
            "status": "POTENTIALLY_VERIFIED",
            "reason": "..."
        }
    ]
}
```

## Datenmodelle

### Chunk (Processed Document Page)
```python
{
    "text": str,  # Kombiniert: Layout-Text + Vision-Description
    "metadata": {
        "page": int,
        "source": str,  # Filename
        "len": int,
        "image_path": str  # PNG path
    }
}
```

### Finding (Greenwashing Indicator)
```python
{
    "page": int,
    "category": "VAGUE|INCONSISTENCY|DATA_GAP",
    "quote": str,  # Textausschnitt
    "reasoning": str  # LLM Begründung
}
```

### Claim (Strategic Goal)
```python
{
    "id": int,
    "text": str,
    "context": str,
    "page": int,
    "status": "OPEN|POTENTIALLY_VERIFIED",
    "evidence": str | None
}
```

## API-Integration

### OpenAI API Calls

**1. Vision API (loader.py:110-122)**
```python
model: gpt-4o
messages: [
    system: "Neutraler Daten-Erfasser..."
    user: [text, image_url]
]
max_tokens: 600
retry: 3x mit 2s delay
```

**2. Analysis API (analyzer.py:188-197)**
```python
model: gpt-4o-mini | gpt-4o (user choice)
messages: [system, user]
response_format: json_object
temperature: 0.0  # Deterministic
timeout: 30s
```

**3. Verification API (analyzer.py:226-231)**
```python
model: same as analysis
response_format: json_object
temperature: 0.0
```

**Rate Limiting:**
- ThreadPoolExecutor: max 2 workers
- Sleep 0.5s zwischen Vision Calls
- RateLimitError → 2s sleep + retry

## Sicherheit

### Authentifizierung
- SHA-256 Hash-basierte Passwortprüfung
- Session-basiert (Streamlit Session State)
- Secrets via `.env` oder Streamlit Secrets

### API Key Management
- Umgebungsvariablen (OPENAI_API_KEY)
- Fallback zu Streamlit Secrets
- Kein Hardcoding im Code

### Input Validation
⚠️ **Aktuell begrenzt:**
- Keine File-Size Limits
- Keine PDF-Malware-Prüfung
- Kein Input Sanitization für Quotes

## Performance-Überlegungen

### Bottlenecks
1. **Vision API**: ~2-3s pro Seite (paralleler Aufruf)
2. **Analysis Pass 1**: ~1-2s pro Seite (sequenziell)
3. **Deep Verification**: Variable (abhängig von Claim-Anzahl)

### Optimierungen
- JSON Caching (skip re-processing)
- Parallel Vision Calls (2x speedup)
- Keyword Pre-Filtering (Deep Verification)

### Skalierungs-Limits
- **Max Document Size**: ~100 Seiten (sonst Timeout-Risiko)
- **Memory**: Session State (limitiert durch Browser)
- **Concurrent Users**: 1 (Streamlit Single-Instance)

## Erweiterungspunkte

### Geplante Verbesserungen
1. **Database**: SQLite für Feedback-Persistenz
2. **Batch Processing**: Mehrere Dokumente parallel
3. **Fine-Tuning**: Feedback-Loop für Modell-Verbesserung
4. **Advanced Filtering**: ML-basierte Keyword-Extraktion
5. **Multi-Language**: i18n Support

### Plugin-Architecture (Konzept)
```python
class GreenwashingIndicator(ABC):
    @abstractmethod
    def detect(self, chunk: Dict) -> List[Finding]:
        pass

# Custom Indicators via Registry
analyzer.register_indicator(CustomVagueDetector())
```

## Testing-Strategie

### Unit Tests (geplant)
- `ReportLoader._get_visual_description()`: Mock OpenAI
- `GreenwashingAnalyzer._analyze_single_chunk()`: JSON parsing
- `get_highlighted_image()`: Quote matching

### Integration Tests
- End-to-End: PDF → Analysis → CSV
- API Error Handling (Mocked)

### Test Data
- Sample CSR Reports (anonymisiert)
- Edge Cases: Empty Pages, Tables, Charts

## Deployment

### Local Development
```bash
streamlit run app.py
```

### GitHub Codespaces
- `.devcontainer/devcontainer.json` vorkonfiguriert
- Auto-Start auf Port 8501

### Streamlit Cloud
- Secrets Management via UI
- Auto-Deploy bei Git Push

## Lizenz & Hinweise

Bachelor-Thesis Projekt - Prototyp-Status
Nicht für Production ohne weitere Härtung geeignet.

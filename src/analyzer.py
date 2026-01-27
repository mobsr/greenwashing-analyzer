import os
import json
from openai import OpenAI
from typing import List, Dict, Callable, Optional

class GreenwashingAnalyzer:
    """
    KI-gestützter Analyzer für Greenwashing-Indikatoren in CSR-Berichten.
    
    Verwendet einen zweistufigen Analyse-Prozess:
    - Pass 1: Sequenzielle Analyse aller Seiten mit Kontext-Fenster
    - Pass 2: Deep Verification für unbelegte strategische Ziele (Claims)
    
    Attributes:
        client: OpenAI API Client
        api_ready: Status der API-Verbindung
        model: Name des verwendeten LLM-Modells (z.B. "gpt-4o-mini")
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        """
        Initialisiert den Greenwashing Analyzer.
        
        Args:
            model_name: OpenAI Modell-Name (default: "gpt-4o-mini")
                       Unterstützt: "gpt-4o-mini", "gpt-4o"
        
        Raises:
            Keine - API-Fehler werden durch api_ready=False signalisiert
        """
        try:
            self.client = OpenAI()
            self.api_ready = True
        except Exception:
            self.client = None
            self.api_ready = False
        self.model = model_name
        print(f"🔧 Analyzer initialisiert mit Modell: {self.model}")

    def analyze_report(self, chunks: List[Dict], progress_callback: Optional[Callable] = None, 
                      custom_definitions: Optional[Dict[str, str]] = None) -> Dict:
        """
        Pass 1: Sequenzielle Analyse aller Dokument-Chunks.
        
        Analysiert jeden Chunk (Seite) im Kontext der vorherigen/nächsten Seite.
        Erkennt Greenwashing-Indikatoren und extrahiert strategische Ziele (Claims).
        
        Args:
            chunks: Liste von Dokument-Chunks mit Text und Metadaten
                   Format: [{"text": str, "metadata": {"page": int, ...}}, ...]
            progress_callback: Optional callback function(progress: float, message: str)
                              für Fortschritts-Updates
            custom_definitions: Optional dict mit custom Tag-Definitionen
                               Format: {"TAG_NAME": "Definition für LLM"}
        
        Returns:
            Dict mit Analyse-Ergebnissen:
            {
                "findings": List[Dict],  # Greenwashing-Indikatoren
                "claim_registry": List[Dict],  # Strategische Ziele
                "total_chunks": int,  # Anzahl analysierter Chunks
                "model_used": str,  # Verwendetes Modell
                "error": str  # Optional bei Fehlern
            }
        
        Example:
            >>> analyzer = GreenwashingAnalyzer()
            >>> results = analyzer.analyze_report(chunks)
            >>> print(f"Found {len(results['findings'])} indicators")
        """
        if not self.api_ready: return {"error": "API Key fehlt."}

        findings = []
        claims_memory = []
        claim_counter = 1
        
        if custom_definitions is None: custom_definitions = {}

        total_chunks = len(chunks)
        total_ops = total_chunks
        current_op = 0
        print(f"🕵️ Starte Pass 1 ({self.model})...")

        failed_pages = []
        for i, chunk in enumerate(chunks):
            current_op += 1
            if progress_callback: progress_callback(current_op / total_ops, f"Pass 1: Seite {i+1}/{total_chunks}")
            
            # GANZE vorherige/nächste Seite als Kontext
            prev_text = chunks[i-1]['text'] if i > 0 else ""
            next_text = chunks[i+1]['text'] if i < total_chunks - 1 else ""
            
            result = self._analyze_single_chunk(chunk, prev_text, next_text, claims_memory, custom_definitions)
            
            if result is None:
                failed_pages.append(chunk['metadata']['page'])
            elif result:
                if result.get("findings"):
                    for f in result["findings"]:
                        f["page"] = chunk['metadata']['page']
                        findings.append(f)

                if result.get("new_claims"):
                    for item in result["new_claims"]:
                        if isinstance(item, dict):
                            claim_text = item.get("claim")
                            claim_ctx = item.get("context")
                        else:
                            claim_text = str(item)
                            claim_ctx = "Kein Kontext."

                        # LLM should handle duplicate detection now, just add if valid
                        if claim_text and claim_text.strip():
                            claims_memory.append({
                                "id": claim_counter,
                                "text": claim_text,
                                "context": claim_ctx,
                                "page": chunk['metadata']['page'],
                                "status": "OPEN", 
                                "evidence": None
                            })
                            claim_counter += 1

                if result.get("claim_updates"):
                    for update in result["claim_updates"]:
                        if update.get("status") != "POTENTIALLY_VERIFIED":
                            continue
                        target_id = update.get("id")
                        for claim in claims_memory:
                            if claim["id"] == target_id and claim["status"] == "OPEN":
                                claim["status"] = "POTENTIALLY_VERIFIED"
                                claim["evidence"] = f"Seite {chunk['metadata']['page']}: {update.get('reason')}"

        if progress_callback: progress_callback(1.0, "Pass 1 Fertig!")
        
        if failed_pages:
            return {
                "findings": findings,
                "claim_registry": claims_memory,
                "error": f"API-Fehler auf Seiten: {', '.join(map(str, failed_pages))}"
            }

        return {
            "findings": findings,
            "claim_registry": claims_memory,
            "total_chunks": total_chunks,
            "model_used": self.model
        }

    def deep_verify_claims(self, chunks: List[Dict], current_claims: List[Dict], 
                          progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Pass 2: Deep Verification für unbelegte Claims.
        
        Durchsucht das gesamte Dokument nach Evidenz für noch offene Claims.
        Verwendet Keyword-Matching zur Vorfilterung und LLM zur finalen Verifizierung.
        
        Args:
            chunks: Liste aller Dokument-Chunks
            current_claims: Liste der Claims aus Pass 1
                           Format: [{"id": int, "text": str, "status": str, ...}]
            progress_callback: Optional callback für Fortschritts-Updates
        
        Returns:
            Aktualisierte Claims-Liste mit verifizierten Claims
            Status wird von "OPEN" zu "POTENTIALLY_VERIFIED" geändert wenn Evidenz gefunden
        
        Note:
            - Claims können sich nicht selbst belegen (Origin-Page wird übersprungen)
            - Keyword-Threshold: 30% der signifikanten Wörter (>5 Zeichen)
            - Nur explizite LLM-Bestätigung ("is_evidence": true) zählt als Beleg
        """
        print("🕵️ Starte Pass 2: Deep Verification...")
        open_claims = [c for c in current_claims if c['status'] == 'OPEN']
        if not open_claims: return current_claims

        total_ops = len(open_claims) * len(chunks)
        current_op = 0

        for claim in open_claims:
            keywords = [w for w in claim['text'].split() if len(w) > 5]
            if not keywords: continue

            for chunk in chunks:
                current_op += 1
                
                # REGEL: Ein Claim darf sich nicht selbst belegen!
                if chunk['metadata']['page'] == claim['page']:
                    continue

                hits = sum(1 for k in keywords if k.lower() in chunk['text'].lower())
                
                if hits / len(keywords) > 0.3:
                    if progress_callback: progress_callback(current_op / total_ops, f"Deep-Check ID {claim['id']}...")
                    
                    verification = self._verify_claim_with_llm(claim, chunk['text'])
                    
                    # STRENGERE PRÜFUNG: Nur wenn explizit "is_evidence": true
                    if verification and verification.get('is_evidence') is True:
                        claim['status'] = 'POTENTIALLY_VERIFIED'
                        claim['evidence'] = f"Deep-Search (S. {chunk['metadata']['page']}): {verification.get('reason')}"
                        break 

        if progress_callback: progress_callback(1.0, "Fertig!")
        return current_claims

    def _analyze_single_chunk(self, chunk: Dict, prev_text: str, next_text: str, 
                             claims_memory: List[Dict], custom_definitions: Dict[str, str]) -> Optional[Dict]:
        """
        Analysiert einen einzelnen Chunk im Kontext.
        
        Args:
            chunk: Aktueller Chunk mit Text und Metadaten
            prev_text: Text der vorherigen Seite (für Kontext)
            next_text: Text der nächsten Seite (für Kontext)
            claims_memory: Liste bereits erkannter Claims
            custom_definitions: Tag-Definitionen für LLM
        
        Returns:
            Dict mit Analyse-Ergebnissen oder None bei Fehler:
            {
                "findings": List[Dict],  # Neue Findings
                "new_claims": List[Dict],  # Neue Claims
                "claim_updates": List[Dict]  # Status-Updates für bestehende Claims
            }
        
        Note:
            - Nur die aktuelle Seite (chunk) wird bewertet
            - Kontext-Seiten dienen nur zum Verständnis von Satzübergängen
        """
        tag_definitions_str = "\n".join([f"- {tag}: {definition}" for tag, definition in custom_definitions.items()])
        
        system_prompt = f"""Du bist ein vorsichtiger, wissenschaftlicher Auditor für Nachhaltigkeitsberichte.
Deine Sprache ist rein deskriptiv ("Indiz", "Hinweis", "Potenziell"). Vermeide absolute Urteile.

WICHTIG: Du bewertest NUR die Seite in 'AKTUELLE SEITE (ZU BEWERTEN)'.
Die Kontextseiten dienen nur zum Verständnis von Satzübergängen – extrahiere dort KEINE Findings/Claims!

AUFGABEN:
1. RISIKO-INDIKATOREN (Findings) - Nutze exakt diese Definitionen:
{tag_definitions_str}
   → NUR aus 'AKTUELLE SEITE (ZU BEWERTEN)' extrahieren!

2. STRATEGISCHE ZIELE (Claims):
   - Extrahiere neue Ziele ("Wir werden...", "Bis 2030...").
   - PRÜFE die Liste "BEREITS ERKANNTE STRATEGISCHE ZIELE" im User-Prompt!
   - Extrahiere NUR Claims, die semantisch NEU sind (keine Umformulierungen/Wiederholungen).
   → NUR aus 'AKTUELLE SEITE (ZU BEWERTEN)' extrahieren!

3. VERIFIZIERUNG (Memory Check):
   - Prüfe die Liste "OFFENE ZIELE".
   - Nur setzen, wenn wirklich ein Beleg vorliegt: Status "POTENTIALLY_VERIFIED".

ANTWORTE NUR VALIDES JSON (keine weiteren Erklärungen):
{{
    "findings": [{{"category": "VAGUE|INCONSISTENCY|DATA_GAP", "quote": "...", "reasoning": "..."}}],
    "new_claims": [{{"claim": "...", "context": "..."}}],
    "claim_updates": [{{"id": 1, "status": "POTENTIALLY_VERIFIED", "reason": "..."}}]
}}"""

        current_text = chunk['text']
        current_page = chunk['metadata']['page']

        user_prompt = f"""
=== KONTEXT: VORHERIGE SEITE (NUR ZUM LESEN) ===
{prev_text if prev_text else "(Keine vorherige Seite)"}

=== AKTUELLE SEITE (ZU BEWERTEN) - Seite {current_page} ===
{current_text}

=== KONTEXT: NÄCHSTE SEITE (NUR ZUM LESEN) ===
{next_text if next_text else "(Keine nächste Seite)"}

---

BEREITS ERKANNTE STRATEGISCHE ZIELE:
{chr(10).join([f"- ID {c['id']} (S. {c['page']}): {c['text']}" for c in claims_memory]) if claims_memory else "(Noch keine Claims erkannt)"}

OFFENE ZIELE (für Verifizierung):
{chr(10).join([f"- ID {c['id']}: {c['text']}" for c in claims_memory if c['status'] == 'OPEN']) if any(c['status'] == 'OPEN' for c in claims_memory) else "(Keine offenen Ziele)"}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=30
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Analyzer Fehler S.{current_page}: {e}")
            return None

    def _verify_claim_with_llm(self, claim: Dict, text_chunk: str) -> Optional[Dict]:
        """
        LLM-basierte Verifizierung eines Claims gegen einen Text-Chunk.
        
        Verwendet strenge Kriterien: Nur harte Fakten (Zahlen, konkrete Maßnahmen)
        werden als Evidenz akzeptiert, keine Wiederholungen des Ziels.
        
        Args:
            claim: Claim-Dict mit "text", "context", etc.
            text_chunk: Potenzieller Beleg-Text (max 1500 Zeichen)
        
        Returns:
            Dict mit Verifizierungs-Ergebnis oder None bei Fehler:
            {
                "is_evidence": bool,  # True nur bei zweifelsfreiem Beleg
                "reason": str  # Kurze Begründung
            }
        
        Example:
            >>> result = analyzer._verify_claim_with_llm(
            ...     {"text": "CO2-Reduktion um 50%"}, 
            ...     "Im Jahr 2023 reduzierten wir CO2 von 100t auf 50t"
            ... )
            >>> assert result["is_evidence"] == True
        """
        try:
            prompt = f"""
            STRENGE FAKTEN-PRÜFUNG
            
            Zu prüfende Behauptung (Strategisches Ziel): 
            "{claim['text']}"
            Hintergrund-Kontext: "{claim.get('context','')}"
            
            Möglicher Beleg-Text:
            "{text_chunk[:1500]}..."
            
            DEINE AUFGABE:
            Entscheide, ob der 'Möglicher Beleg-Text' zweifelsfrei beweist, dass die 'Behauptung' umgesetzt wurde oder konkrete Maßnahmen/Daten dazu nennt.
            
            REGELN:
            - Wenn der Text nur das Ziel wiederholt ("Wir planen..."), ist das KEIN Beweis -> false.
            - Wenn der Text vage bleibt ("Wir haben Fortschritte gemacht"), ist das KEIN Beweis -> false.
            - Nur harte Fakten (Zahlen, "Abgeschlossen", "Erreicht", "Budget freigegeben") zählen als Beweis -> true.
            
            Antworte JSON: {{ "is_evidence": true, "reason": "Sehr kurze Begründung warum (nicht)" }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, temperature=0.0
            )
            return json.loads(response.choices[0].message.content)
        except Exception: return None
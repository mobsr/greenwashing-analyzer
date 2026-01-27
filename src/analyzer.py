import os
import json
from openai import OpenAI
from typing import List, Dict, Optional
from .logger_config import setup_logger

logger = setup_logger("analyzer")

class GreenwashingAnalyzer:
    """
    KI-gestützte Analyse von Greenwashing-Indikatoren in Nachhaltigkeitsberichten.
    
    Diese Klasse implementiert eine Zwei-Pass-Analyse zur Erkennung von Greenwashing:
    1. Pass 1: Sequenzielle Analyse zur Erkennung von Risiko-Indikatoren und Claims
    2. Pass 2: Deep Verification zur dokumentweiten Verifizierung von Claims
    
    Attributes:
        client (OpenAI): OpenAI API Client
        api_ready (bool): Gibt an, ob die API verfügbar ist
        model (str): Name des verwendeten LLM-Modells (z.B. "gpt-4o-mini")
    
    Example:
        >>> analyzer = GreenwashingAnalyzer(model_name="gpt-4o-mini")
        >>> results = analyzer.analyze_report(chunks)
        >>> print(f"Gefundene Risiken: {len(results['findings'])}")
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        """
        Initialisiert den Greenwashing Analyzer.
        
        Args:
            model_name: Name des OpenAI-Modells (Standard: "gpt-4o-mini")
        
        Raises:
            Exception: Falls OpenAI API Key fehlt (wird abgefangen, api_ready=False)
        """
        try:
            self.client = OpenAI()
            self.api_ready = True
        except Exception:
            self.client = None
            self.api_ready = False
        self.model = model_name
        logger.info(f"Analyzer initialisiert mit Modell: {self.model}")

    def analyze_report(self, chunks: List[Dict], progress_callback=None, custom_definitions: Optional[Dict[str, str]] = None) -> Dict:
        """
        Pass 1: Sequenzielle Analyse des Nachhaltigkeitsberichts.
        
        Analysiert jeden Chunk (Seite) sequenziell und extrahiert:
        - Greenwashing-Risiko-Indikatoren (Findings)
        - Strategische Nachhaltigkeitsziele (Claims)
        - Initiale Claim-Verifizierung
        
        Args:
            chunks: Liste von Dokument-Chunks mit Text und Metadaten
            progress_callback: Optional callback(progress: float, message: str) für Fortschritt
            custom_definitions: Dictionary mit benutzerdefinierten Tag-Definitionen
                                Format: {"TAG_NAME": "Definition für KI"}
        
        Returns:
            Dictionary mit Analyse-Ergebnissen:
            {
                "findings": List[Dict],  # Risiko-Indikatoren
                "claim_registry": List[Dict],  # Erkannte Claims
                "total_chunks": int,  # Anzahl analysierter Chunks
                "model_used": str,  # Verwendetes Modell
                "error": str  # Optional: Fehlermeldung bei Problemen
            }
        
        Example:
            >>> chunks = loader.load()
            >>> custom_tags = {"VAGUE": "Unspezifische Aussagen ohne Belege"}
            >>> results = analyzer.analyze_report(chunks, custom_definitions=custom_tags)
        """
        if not self.api_ready: return {"error": "API Key fehlt."}

        findings = []
        claims_memory = []
        claim_counter = 1
        
        if custom_definitions is None: custom_definitions = {}

        total_chunks = len(chunks)
        total_ops = total_chunks
        current_op = 0
        logger.info(f"Starte Pass 1 mit {self.model} ({total_chunks} Chunks)...")

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
                logger.warning(f"Analyse-Fehler auf Seite {chunk['metadata']['page']}")
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
        logger.info(f"Pass 1 abgeschlossen: {len(findings)} Findings, {len(claims_memory)} Claims")
        
        if failed_pages:
            logger.error(f"API-Fehler auf {len(failed_pages)} Seiten: {failed_pages}")
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

    def deep_verify_claims(self, chunks: List[Dict], current_claims: List[Dict], progress_callback=None) -> List[Dict]:
        """
        Pass 2: Dokumentweite Verifizierung offener Claims.
        
        Führt eine tiefgehende Suche nach Belegen für unbestätigte Claims durch:
        1. Keyword-basiertes Pre-Filtering für Effizienz
        2. LLM-gestützte Evidenz-Prüfung für relevante Chunks
        3. Strenges Matching (nur harte Fakten, keine Wiederholungen)
        
        Args:
            chunks: Liste aller Dokument-Chunks
            current_claims: Liste der zu prüfenden Claims
            progress_callback: Optional callback(progress: float, message: str)
        
        Returns:
            Aktualisierte Liste der Claims mit verifizierten Status-Updates
        
        Note:
            Ein Claim kann sich nicht selbst belegen (Seite wird ausgeschlossen).
            Status wird nur auf "POTENTIALLY_VERIFIED" gesetzt bei explizitem Beleg.
        
        Example:
            >>> open_claims = [c for c in claims if c['status'] == 'OPEN']
            >>> verified = analyzer.deep_verify_claims(chunks, claims)
        """
        logger.info("Starte Pass 2: Deep Verification...")
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

    def _analyze_single_chunk(self, chunk: Dict, prev_text: str, next_text: str, claims_memory: List[Dict], custom_definitions: Dict[str, str]) -> Optional[Dict]:
        """
        Analysiert einen einzelnen Chunk mit Kontext-Awareness.
        
        Args:
            chunk: Aktueller Dokument-Chunk (zu bewerten)
            prev_text: Text der vorherigen Seite (nur Kontext)
            next_text: Text der nächsten Seite (nur Kontext)
            claims_memory: Liste bereits erkannter Claims (Duplikat-Prävention)
            custom_definitions: Benutzerdefinierte Tag-Definitionen
        
        Returns:
            Dictionary mit Analyse-Ergebnissen oder None bei Fehler:
            {
                "findings": List[Dict],  # Neue Risiko-Indikatoren
                "new_claims": List[Dict],  # Neue strategische Ziele
                "claim_updates": List[Dict]  # Status-Updates für bestehende Claims
            }
        
        Note:
            Verwendet structured JSON output für zuverlässiges Parsing.
            Temperatur=0.0 für deterministische Ergebnisse.
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
            logger.error(f"Analyzer Fehler Seite {current_page}: {str(e)}")
            return None

    def _verify_claim_with_llm(self, claim: Dict, text_chunk: str) -> Optional[Dict]:
        """
        LLM-gestützte Verifizierung eines Claims gegen einen Text-Chunk.
        
        Verwendet strenge Prüfkriterien:
        - Nur harte Fakten (Zahlen, "Abgeschlossen", konkrete Maßnahmen) zählen
        - Bloße Wiederholungen des Ziels sind kein Beleg
        - Vage Aussagen ("Fortschritte gemacht") sind kein Beleg
        
        Args:
            claim: Claim-Dictionary mit 'text' und 'context'
            text_chunk: Potenzieller Beleg-Text (max 1500 Zeichen)
        
        Returns:
            Dictionary mit Verifizierungsergebnis oder None bei Fehler:
            {
                "is_evidence": bool,  # True nur bei zweifelsfrei harten Belegen
                "reason": str  # Kurze Begründung
            }
        
        Example:
            >>> claim = {"text": "Wir werden CO2-neutral bis 2030", "context": "..."}
            >>> result = analyzer._verify_claim_with_llm(claim, chunk_text)
            >>> if result and result.get('is_evidence'):
            ...     print("Beleg gefunden!")
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
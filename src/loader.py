import fitz  # PyMuPDF
import base64
import os
import json
import hashlib
from typing import List, Dict, Callable, Optional
from openai import OpenAI, RateLimitError
from langchain_text_splitters import MarkdownTextSplitter
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None

class ReportLoader:
    """
    Hybrid PDF Loader mit Text- und Vision-Extraktion.
    
    Verarbeitet PDF-Dokumente und extrahiert sowohl textuellen Inhalt (via pymupdf4llm)
    als auch visuelle Informationen (via GPT-4o Vision API). Unterstützt Caching
    und parallele Verarbeitung für Performance.
    
    Attributes:
        file_path: Pfad zur PDF-Datei
        max_pages: Maximum Anzahl zu verarbeitender Seiten
        model: OpenAI Vision-Modell Name (z.B. "gpt-4o")
        client: OpenAI API Client
        api_ready: Status der API-Verbindung
        cache_dir: Verzeichnis für gecachte Daten
        images_dir: Verzeichnis für extrahierte Seitenbilder
        highlights_dir: Verzeichnis für Highlight-Bilder
    """
    
    def __init__(self, file_path: str, max_pages: int = 5, vision_model: str = "gpt-4o"):
        """
        Initialisiert den Report Loader.
        
        Args:
            file_path: Pfad zur PDF-Datei
            max_pages: Maximum Anzahl zu verarbeitender Seiten (default: 5)
            vision_model: OpenAI Vision-Modell (default: "gpt-4o")
        
        Note:
            Erstellt automatisch Cache-Verzeichnisse unter data/processed/
        """
        self.file_path = file_path
        self.max_pages = max_pages
        
        self.base_name = os.path.basename(file_path).replace(".pdf", "")
        self.cache_dir = os.path.join("data", "processed", self.base_name)
        self.json_path = os.path.join(self.cache_dir, "data.json")
        self.images_dir = os.path.join(self.cache_dir, "images")
        self.highlights_dir = os.path.join(self.cache_dir, "highlights") # NEU
        
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.highlights_dir, exist_ok=True)

        try:
            self.client = OpenAI()
            self.api_ready = True
        except Exception:
            self.client = None
            self.api_ready = False
            
        self.model = vision_model
        self.text_splitter = MarkdownTextSplitter(chunk_size=1500, chunk_overlap=200)

    def get_highlighted_image(self, page_num: int, quote: str) -> Optional[str]:
        """
        Erstellt ein Bild der Seite mit gelben Markierungen für ein Zitat.
        
        Verwendet 'Anchor-Cluster'-Suche für robustes Text-Matching:
        - Zerlegt lange Zitate in 3-Wort-Snippets (N-Grams)
        - Sucht jeden Snippet separat (überbrückt Zeilenumbrüche)
        - Markiert alle gefundenen Stellen gelb
        
        Args:
            page_num: Seitennummer (1-basiert)
            quote: Zu markierender Text-Ausschnitt
        
        Returns:
            Pfad zum generierten Highlight-Bild oder None bei Fehler
        
        Note:
            - Verwendet MD5-Hash des Quotes für Caching
            - Fallback: Normalisierter Full-Text-Search bei N-Gram-Fehler
        
        Example:
            >>> loader = ReportLoader("report.pdf")
            >>> img_path = loader.get_highlighted_image(5, "CO2 Reduktion um 50%")
            >>> if img_path:
            ...     st.image(img_path)
        """
        # Hash für Dateinamen (Caching der Highlights)
        quote_hash = hashlib.md5(quote.encode()).hexdigest()[:8]
        img_path = os.path.join(self.highlights_dir, f"p{page_num}_{quote_hash}.png")
        
        # Wenn schon da, direkt zurückgeben
        if os.path.exists(img_path):
            return img_path

        try:
            doc = fitz.open(self.file_path)
            # Seite laden (0-basiert)
            if page_num - 1 >= len(doc): return None
            page = doc[page_num - 1]
            
            # --- ANCHOR-CLUSTER SUCHE ---
            # Wir zerlegen das Zitat in Schnipsel (3 Wörter), um Zeilenumbrüche zu überbrücken
            words = quote.split()
            search_terms = []
            
            if len(words) > 3:
                # N-Grams erstellen
                for i in range(len(words) - 2):
                    search_terms.append(" ".join(words[i:i+3]))
            else:
                # Bei kurzen Zitaten einfach den ganzen String nehmen
                search_terms.append(quote)

            # Suchen & Markieren
            found_any = False
            for term in search_terms:
                # quads=True liefert die genauen Koordinaten (auch schräg/mehrzeilig)
                quads = page.search_for(term, quads=True)
                if quads:
                    found_any = True
                    for q in quads:
                        # Gelbes Highlight hinzufügen
                        annot = page.add_highlight_annot(q)
                        annot.set_opacity(0.5)
                        annot.update()

            # Fallback: Wenn N-Grams scheitern, probiere einmal den ganzen Satz (Fuzzy-Clean)
            if not found_any:
                clean_quote = " ".join(quote.split()) # Leerzeichen normalisieren
                quads = page.search_for(clean_quote, quads=True)
                for q in quads:
                    annot = page.add_highlight_annot(q)
                    annot.set_opacity(0.5)
                    annot.update()

            # Rendern und Speichern
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            pix.save(img_path)
            return img_path
            
        except Exception as e:
            print(f"Highlight Error: {e}")
            return None

    def _get_visual_description(self, base64_image: str) -> str:
        """
        Extrahiert visuelle Informationen aus einem Seitenbild via Vision API.
        
        Verwendet GPT-4o Vision zur Analyse von:
        - Tabellen und Diagrammen (Daten-Transkription)
        - Visuellen Motiven, Farben
        - Zertifikaten und Labels
        
        Args:
            base64_image: Base64-encodiertes PNG-Bild
        
        Returns:
            Formatierter String mit visueller Beschreibung oder "" bei Fehler/irrelevant
        
        Note:
            - 3 Retry-Versuche bei Rate Limit (2s sleep)
            - Returns "" wenn LLM "KEINE_RELEVANTEN_DATEN" antwortet
            - Max 600 Tokens pro Beschreibung
        """
        if not self.client: return ""
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Du bist ein neutraler Daten-Erfasser. Beschreibe rein sachlich: 1. DATEN: Transkribiere Tabellen/Diagramme. 2. VISUELL: Beschreibe Motive, Farben. 3. LABELS: Nenne Zertifikate. Antworte mit 'KEINE_RELEVANTEN_DATEN', falls nur Text."},
                        {"role": "user", "content": [{"type": "text", "text": "Scan."}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}]}
                    ],
                    max_tokens=600
                )
                content = response.choices[0].message.content
                if "KEINE_RELEVANTEN_DATEN" in content: return ""
                return f"\n--- [VISUELLE DATEN (KI)] ---\n{content}\n"
            except RateLimitError: time.sleep(2)
            except Exception: return ""
        return ""

    def load(self, use_cache: bool = True, progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Lädt und verarbeitet das PDF-Dokument.
        
        Workflow:
        1. Check Cache (wenn use_cache=True)
        2. Layout-Analyse mit pymupdf4llm
        3. Seiten-Bilder extrahieren
        4. Parallel Vision API Calls (max 2 workers)
        5. Kombiniere Text + Vision
        6. Cache Results als JSON
        
        Args:
            use_cache: Wenn True, nutze gecachte Daten falls vorhanden
            progress_callback: Optional callback(progress: float, message: str)
        
        Returns:
            Liste von Chunks (Seiten):
            [
                {
                    "text": str,  # Kombiniert: Layout-Text + Vision
                    "metadata": {
                        "page": int,  # 1-basiert
                        "source": str,  # Dateiname
                        "len": int,  # Text-Länge
                        "image_path": str  # Pfad zum PNG
                    }
                },
                ...
            ]
        
        Note:
            - Parallel Processing für Vision (2x speedup)
            - Rate Limit Protection (0.5s delay + retry logic)
            - Cache unter data/processed/{filename}/data.json
        
        Example:
            >>> loader = ReportLoader("report.pdf", max_pages=10)
            >>> chunks = loader.load(use_cache=True)
            >>> print(f"Loaded {len(chunks)} pages")
        """
        if use_cache and os.path.exists(self.json_path):
            if progress_callback: progress_callback(1.0, "Daten aus Cache geladen!")
            with open(self.json_path, "r", encoding="utf-8") as f: return json.load(f)

        print(f"🚀 Starte Processing für: {self.base_name}")
        if progress_callback: progress_callback(0.1, "Layout-Analyse...")
        try: md_pages = pymupdf4llm.to_markdown(self.file_path, page_chunks=True)
        except Exception: md_pages = []
        doc = fitz.open(self.file_path)
        final_chunks = []
        if not md_pages: md_pages = [{"text": ""} for _ in range(len(doc))]
        total_pages = min(len(doc), self.max_pages)

        # Prepare all images first (without API calls)
        images_data = []
        for i in range(total_pages):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_path = os.path.join(self.images_dir, f"page_{i + 1}.png")
            pix.save(img_path)
            img_data = pix.tobytes("png")
            base64_image = base64.b64encode(img_data).decode("utf-8")
            text_content = md_pages[i]["text"] if i < len(md_pages) else ""
            
            images_data.append({
                'page_num': i + 1,
                'base64': base64_image,
                'text_content': text_content,
                'img_path': img_path
            })
        
        # Process max 2 images concurrently (safer than 5)
        max_workers = 2
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._process_page_vision, img_data): idx 
                for idx, img_data in enumerate(images_data)
            }
            
            for future in as_completed(futures):
                try:
                    idx = futures[future]
                    vis_description = future.result()
                    if vis_description:
                        images_data[idx]['text_content'] += vis_description
                    
                    if progress_callback:
                        progress_callback(
                            (idx + 1) / total_pages, 
                            f"Seite {images_data[idx]['page_num']}: Vision verarbeitet"
                        )
                except Exception as e:
                    print(f"Vision API Error for page {idx + 1}: {e}")
                    # Continue without vision for this page
        
        # Build chunks
        for img_data in images_data:
            if img_data['text_content'].strip():
                final_chunks.append({
                    "text": img_data['text_content'],
                    "metadata": {
                        "page": img_data['page_num'],
                        "source": os.path.basename(self.file_path),
                        "len": len(img_data['text_content']),
                        "image_path": img_data['img_path']
                    }
                })
        with open(self.json_path, "w", encoding="utf-8") as f: json.dump(final_chunks, f, ensure_ascii=False, indent=2)
        if progress_callback: progress_callback(1.0, "Fertig!")
        return final_chunks

    def _process_page_vision(self, img_data: Dict) -> str:
        """
        Wrapper für parallele Vision API Verarbeitung.
        
        Args:
            img_data: Dict mit page_num, base64, text_content, img_path
        
        Returns:
            Vision-Beschreibung als String oder "" bei Fehler
        
        Note:
            - 0.5s delay zur Rate Limit Prevention
            - Retry bei RateLimitError (2s sleep)
        """
        if not self.api_ready:
            return ""
        
        try:
            # Add small delay to avoid rate limit spike
            time.sleep(0.5)
            return self._get_visual_description(img_data['base64'])
        except RateLimitError:
            time.sleep(2)
            return self._get_visual_description(img_data['base64'])
        except Exception as e:
            print(f"Vision error: {e}")
            return ""
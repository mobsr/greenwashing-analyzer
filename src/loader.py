import fitz  # PyMuPDF
from typing import List, Dict

class ReportLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Dict]:
        """
        Lädt das PDF und extrahiert Text seitenweise mit Metadaten.
        Rückgabe: Liste von Dictionaries [{'page': 1, 'text': '...', 'source': 'datei.pdf'}]
        """
        doc = fitz.open(self.file_path)
        documents = []

        print(f"Lade Datei: {self.file_path} mit {len(doc)} Seiten.")

        for page_num, page in enumerate(doc):
            # 'get_text("blocks")' ist mächtig: Es gruppiert Text visuell (Spalten!).
            # sort=True versucht, die natürliche Lesereihenfolge (Spalten) einzuhalten.
            text = page.get_text("text", sort=True)
            
            # Einfache Bereinigung (zu kurze Seiten/leere Seiten überspringen)
            if len(text.strip()) < 50:
                continue

            documents.append({
                "page": page_num + 1,  # Menschliche Zählweise (fängt bei 1 an)
                "content": text,
                "source": self.file_path.split("/")[-1] # Nur der Dateiname
            })
            
        return documents

# Kleiner Test-Block, wenn man die Datei direkt ausführt
if __name__ == "__main__":
    # Zum Testen: Pfad zu einer PDF anpassen
    loader = ReportLoader("data/raw/beispiel_bericht.pdf")
    try:
        docs = loader.load()
        print(f"Erfolgreich {len(docs)} Seiten extrahiert.")
        print("Vorschau Seite 1:")
        print(docs[0]['content'][:200]) # Zeige die ersten 200 Zeichen
    except Exception as e:
        print(f"Fehler: {e}")
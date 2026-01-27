# Wir nutzen ein schlankes Python 3.11 Image als Basis
FROM python:3.11-slim

# Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# System-Updates und notwendige Tools installieren
# (curl ist nützlich für Healthchecks, build-essential für manche Python-Pakete)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Zuerst nur die Requirements kopieren (für besseres Caching)
COPY requirements.txt .

# Abhängigkeiten installieren
# --no-cache-dir hält das Image klein
RUN pip install --no-cache-dir -r requirements.txt

# Den restlichen Code kopieren
COPY . .

# Streamlit Port freigeben
EXPOSE 8501

# Healthcheck hinzufügen (Optional, aber professionell)
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Der Start-Befehl
# server.address=0.0.0.0 ist WICHTIG, damit Docker den Port nach außen reicht
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
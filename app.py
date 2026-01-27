import streamlit as st
import os
import pandas as pd
import json
import csv
from datetime import datetime
import plotly.express as px
from dotenv import load_dotenv
from src.loader import ReportLoader
from src.analyzer import GreenwashingAnalyzer

load_dotenv()
st.set_page_config(page_title="Greenwashing Analyzer - Muhammad Baschir", page_icon="🕵️", layout="wide")

# CSS mit Dark Mode Support
st.markdown("""<style>
.chunk-card{
    background-color: var(--background-color);
    border: 1px solid var(--secondary-background-color);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
}
.vision-block{
    background-color: rgba(255, 179, 0, 0.15);
    border-left: 5px solid #ffb300;
    padding: 15px;
    margin-top: 15px;
}
.meta-tag{
    background-color: var(--secondary-background-color);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8em;
    margin-right: 10px;
}
.finding-card{
    background-color: rgba(255, 68, 68, 0.1);
    border-left: 5px solid #ff4444;
    padding: 15px;
    margin-bottom: 10px;
}
.claim-card{
    background-color: rgba(0, 123, 255, 0.1);
    border-left: 5px solid #007bff;
    padding: 10px;
    margin-bottom: 5px;
    font-size: 0.9em;
}
</style>""", unsafe_allow_html=True)

if 'chunks' not in st.session_state: st.session_state.chunks = []
if 'audit_results' not in st.session_state: st.session_state.audit_results = None
if 'feedbacks' not in st.session_state: st.session_state.feedbacks = {}  # Format: {finding_id: {'feedback': 'CORRECT/FALSE_POSITIVE', 'page': X, 'category': '...', 'quote': '...', 'report': '...'}}
if 'custom_tags' not in st.session_state:
    # Default Tags
    st.session_state.custom_tags = [
        {"tag": "VAGUE", "definition": "Nutze dieses Label für unspezifische Begriffe wie 'umweltfreundlich', 'grün', 'wir engagieren uns', wenn KEINE konkreten Maßnahmen oder Zahlen genannt werden."},
        {"tag": "INCONSISTENCY", "definition": "Achte auf Widersprüche zwischen Bild (siehe '📸 Visuelle Erfassung') und Text. Beispiel: Bild zeigt Natur, Text spricht von Schwerindustrie."},
        {"tag": "DATA_GAP", "definition": "Wenn eine Zahl genannt wird (z.B. '-50% CO2'), aber keine Quelle oder Basisjahr angegeben ist -> 'Hinweis auf fehlende Datenquelle'."}
    ]

st.title("Greenwashing Analyzer")

with st.sidebar:
    st.header("Navigation")
    if st.button("Neustart"):
        st.session_state.chunks = []
        st.session_state.audit_results = None
        st.session_state.feedbacks = {}  # Reset Feedbacks
        st.rerun()
    st.divider()
    if st.session_state.chunks:
        st.success(f"Bericht geladen\n{len(st.session_state.chunks)} Seiten")
        if st.session_state.audit_results:
            st.divider()
            st.write("**Daten-Export**")
            
            # CSV Export für Findings
            findings_df = pd.DataFrame(st.session_state.audit_results.get('findings', []))
            if not findings_df.empty:
                csv_findings = findings_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button("Tags (CSV)", csv_findings, "audit_findings.csv", "text/csv")
            
            # CSV Export für Claims
            claims_df = pd.DataFrame(st.session_state.audit_results.get('claim_registry', []))
            if not claims_df.empty:
                csv_claims = claims_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button("Claims (CSV)", csv_claims, "audit_claims.csv", "text/csv")
            
            # Session-Feedback Statistiken
            st.divider()
            st.write("Aktuelle Analyse")
            
            if st.session_state.feedbacks:
                feedback_list = list(st.session_state.feedbacks.values())
                total = len(feedback_list)
                correct = sum(1 for f in feedback_list if f.get('feedback') == 'CORRECT')
                false_pos = sum(1 for f in feedback_list if f.get('feedback') == 'FALSE_POSITIVE')
                
                if total > 0:
                    precision = (correct / total) * 100
                    col_s1, col_s2 = st.columns(2)
                    col_s1.metric("Bewertet", total)
                    col_s2.metric("Präzision", f"{precision:.1f}%")
                    st.caption(f"✅ {correct} korrekt | ❌ {false_pos} falsch-positiv")
                    
                    # Export Session-Feedback zu CSV
                    if st.button("Session-Feedback exportieren"):
                        log_file = "evaluation_log.csv"
                        file_exists = os.path.exists(log_file)
                        
                        with open(log_file, 'a', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            if not file_exists:
                                writer.writerow(['Timestamp', 'Report', 'Finding_ID', 'Page', 'Category', 'Quote', 'Feedback'])
                            
                            for finding_id, fb_data in st.session_state.feedbacks.items():
                                writer.writerow([
                                    datetime.now().isoformat(),
                                    fb_data.get('report', 'unknown'),
                                    finding_id,
                                    fb_data.get('page', 0),
                                    fb_data.get('category', ''),
                                    fb_data.get('quote', '')[:100],
                                    fb_data.get('feedback', '')
                                ])
                        
                        st.success(f"✅ {total} Bewertungen in evaluation_log.csv gespeichert!")
                        st.session_state.feedbacks = {}  # Reset nach Export
                        st.rerun()
            else:
                st.info("Noch keine Bewertungen in dieser Session.")
            
            # Historische Daten (optional anzeigen)
            if os.path.exists("evaluation_log.csv"):
                st.divider()
                with st.expander("Historische Evaluation (alle Analysen)"):
                    eval_df = pd.read_csv("evaluation_log.csv")
                    total_hist = len(eval_df)
                    correct_hist = len(eval_df[eval_df['Feedback'] == 'CORRECT'])
                    false_pos_hist = len(eval_df[eval_df['Feedback'] == 'FALSE_POSITIVE'])
                    
                    if total_hist > 0:
                        precision_hist = (correct_hist / total_hist) * 100
                        st.metric("Gesamt exportiert", total_hist)
                        st.metric("Durchschnittliche Präzision", f"{precision_hist:.1f}%")
                        st.caption(f"✅ {correct_hist} korrekt | ❌ {false_pos_hist} falsch-positiv")
                        
                        # Download existing log
                        with open("evaluation_log.csv", 'r', encoding='utf-8') as f:
                            eval_csv = f.read()
                        st.download_button("Historische Evaluation", eval_csv, "evaluation_log.csv", "text/csv")

tab1, tab2 = st.tabs(["Nachhaltigkeitsericht laden", "Analyse & Dashboard"])

# TAB 1: READER (Unverändert)
with tab1:
    if not st.session_state.chunks:
        st.info("Lade einen Bericht hoch, um die hybride Extraktion (Text + Vision) zu starten.")
        uploaded_file = st.file_uploader("PDF Bericht", type="pdf")
        if uploaded_file:
            col1, col2 = st.columns(2)
            with col1: max_pages = st.number_input("Seiten-Limit (0=Alle)", value=0, min_value=0)
            with col2: use_cache = st.checkbox("Cache nutzen", value=True)
            if st.button("Einlesen"):
                save_path = os.path.join("data", "raw", uploaded_file.name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f: f.write(uploaded_file.getbuffer())
                with st.status("Verarbeite Dokument...") as s:
                    loader = ReportLoader(save_path, max_pages=max_pages if max_pages > 0 else 9999, vision_model="gpt-4o")
                    st.session_state.chunks = loader.load(use_cache=use_cache, progress_callback=lambda p,m: s.write(m))
                    s.update(label="Fertig!", state="complete")
                st.rerun()
    else:
        pages = sorted(list(set(c['metadata']['page'] for c in st.session_state.chunks)))
        if pages:
            sel_page = st.selectbox("Seite anzeigen:", pages)
            chunk = next((c for c in st.session_state.chunks if c['metadata']['page'] == sel_page), None)
            if chunk:
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.markdown("### Extrahierter Text & Daten")
                    parts = chunk['text'].split("--- [VISUELLE DATEN")
                    st.markdown(f"<div class='chunk-card'>{parts[0]}</div>", unsafe_allow_html=True)
                    if len(parts)>1: 
                        vis_text = parts[1].replace("(KI)] ---", "").strip()
                        st.markdown(f"<div class='vision-block'><b>📸 Vision:</b><br>{vis_text}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown("### Original Seite")
                    img_path = chunk['metadata'].get('image_path')
                    if img_path and os.path.exists(img_path): st.image(img_path, use_container_width=True)
                    else: st.warning("Kein Bild verfügbar.")

# TAB 2: AUDIT (Mit Highlighting!)
with tab2:
    if not st.session_state.chunks:
        st.warning("Bitte erst Daten in Tab 1 laden.")
    else:
        if st.session_state.audit_results is None:
            st.write("Konfiguration & Start")
            col_m1, col_m2 = st.columns(2)
            with col_m1: model_choice = st.selectbox("KI-Modell:", ["gpt-4o-mini", "gpt-4o"])
            with col_m2: 
                active_tags = ", ".join([t["tag"] for t in st.session_state.custom_tags if t["tag"]])
                st.info(f"Modell: **{model_choice}**\n\nAktive Indikator-Tags: {active_tags if active_tags else 'Keine'}")
            
            with st.expander("Experteneinstellungen: Indikator-Tags & Definitionen"):
                st.info("Definiere eigene Risiko-Kategorien oder passe die Standards an.")
                
                # Dynamic Tag Editor
                tags_to_delete = []
                for idx, tag_config in enumerate(st.session_state.custom_tags):
                    col_tag, col_def, col_del = st.columns([2, 5, 1])
                    
                    with col_tag:
                        new_tag = st.text_input(
                            "Tag", 
                            value=tag_config["tag"], 
                            key=f"tag_name_{idx}",
                            placeholder="z.B. VAGUE"
                        )
                        st.session_state.custom_tags[idx]["tag"] = new_tag.strip().upper()
                    
                    with col_def:
                        new_def = st.text_area(
                            "Definition/Anweisung für KI",
                            value=tag_config["definition"],
                            key=f"tag_def_{idx}",
                            height=100,
                            placeholder="Beschreibe, wann dieser Tag verwendet werden soll..."
                        )
                        st.session_state.custom_tags[idx]["definition"] = new_def.strip()
                    
                    with col_del:
                        st.write("")  # Spacing
                        st.write("")  # Spacing
                        if st.button("🗑️", key=f"del_tag_{idx}"):
                            tags_to_delete.append(idx)
                    
                    st.divider()
                
                # Remove deleted tags
                for idx in reversed(tags_to_delete):
                    st.session_state.custom_tags.pop(idx)
                    st.rerun()
                
                # Add new tag button
                if st.button("➕ Neues Tag hinzufügen"):
                    st.session_state.custom_tags.append({"tag": "", "definition": ""})
                    st.rerun()

            if st.button("Analyse jetzt starten"):
                incomplete_tags = [
                    t for t in st.session_state.custom_tags
                    if not t.get("tag") or not t.get("definition")
                ]
                if incomplete_tags:
                    st.warning(f"⚠️ {len(incomplete_tags)} Tag(s) sind unvollständig und werden ignoriert.")
                custom_defs = {
                    tag_config["tag"]: tag_config["definition"] 
                    for tag_config in st.session_state.custom_tags 
                    if tag_config["tag"] and tag_config["definition"]  # ← Filter vorhanden, aber...
                }
                
                analyzer = GreenwashingAnalyzer(model_name=model_choice)
                prog = st.progress(0)
                stat = st.empty()
                res = analyzer.analyze_report(st.session_state.chunks, lambda p,m: (prog.progress(p), stat.text(m)), custom_definitions=custom_defs)
                st.session_state.audit_results = res
                st.rerun()
        else:
            res = st.session_state.audit_results
            findings = res.get("findings", [])
            claims = res.get("claim_registry", [])
            
            st.markdown("### Übersicht")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Risiko-Hinweise", len(findings))
            k2.metric("Strategische Ziele", len(claims))
            k3.metric("Geprüfte Seiten", res.get("total_chunks", 0))
            k4.metric("Modell", res.get("model_used", "?"))
            
            if findings:
                df_findings = pd.DataFrame(findings)
                if not df_findings.empty:
                    fig = px.pie(df_findings, names='category', title='Verteilung der Risiko-Kategorien', hole=0.4, height=300)
                    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()
            
            # FINDINGS MIT HIGHLIGHTING
            st.subheader("Details")
            if findings:
                # WICHTIG: enumerate nutzen, um eindeutige Index-ID zu bekommen!
                for idx, f in enumerate(findings):
                    finding_id = f"finding_{f['page']}_{idx}"
                    
                    # Feedback Status anzeigen
                    feedback_status = ""
                    if finding_id in st.session_state.feedbacks:
                        fb_data = st.session_state.feedbacks[finding_id]
                        if fb_data.get('feedback') == 'CORRECT':
                            feedback_status = "✅ Als korrekt markiert"
                        elif fb_data.get('feedback') == 'FALSE_POSITIVE':
                            feedback_status = "❌ Als falsch-positiv markiert"
                    
                    with st.expander(f"S. {f['page']}: {f['category']} {feedback_status}"):
                        # Feedback Buttons oben
                        col_fb1, col_fb2, col_fb3 = st.columns([1, 1, 4])
                        with col_fb1:
                            if st.button("👍 Korrekt", key=f"correct_{finding_id}"):
                                report_name = st.session_state.chunks[0]['metadata'].get('source', 'unknown')
                                st.session_state.feedbacks[finding_id] = {
                                    'feedback': 'CORRECT',
                                    'page': f['page'],
                                    'category': f['category'],
                                    'quote': f['quote'],
                                    'report': report_name
                                }
                                st.success("Feedback gespeichert!")
                                st.rerun()
                        with col_fb2:
                            if st.button("👎 Falsch Positiv", key=f"false_{finding_id}"):
                                report_name = st.session_state.chunks[0]['metadata'].get('source', 'unknown')
                                st.session_state.feedbacks[finding_id] = {
                                    'feedback': 'FALSE_POSITIVE',
                                    'page': f['page'],
                                    'category': f['category'],
                                    'quote': f['quote'],
                                    'report': report_name
                                }
                                st.warning("Als falsch-positiv markiert.")
                                st.rerun()
                        
                        st.divider()
                        col_txt, col_ev = st.columns([2, 1])
                        with col_txt:
                            st.markdown(f"**Zitat:** _{f['quote']}_")
                            st.markdown(f"**Analyse:** {f['reasoning']}")
                        with col_ev:
                            try:
                                source_file = st.session_state.chunks[0]['metadata']['source']
                                file_path = os.path.join("data", "raw", source_file)
                                
                                if not os.path.exists(file_path):
                                     st.warning(f"Datei nicht gefunden: {file_path}")
                                else:
                                    # FIX: Eindeutiger Key durch 'idx'
                                    if st.checkbox(f"Beleg anzeigen (S.{f['page']})", key=f"btn_{f['page']}_{idx}"):
                                        temp_loader = ReportLoader(file_path)
                                        hl_path = temp_loader.get_highlighted_image(f['page'], f['quote'])
                                        
                                        if hl_path:
                                            st.image(hl_path, caption="Gelb markierter Text im Original")
                                        else:
                                            st.warning("Kein exakter Text-Match für Highlight.")
                                            chunk = next((c for c in st.session_state.chunks if c['metadata']['page'] == f['page']), None)
                                            if chunk and chunk['metadata'].get('image_path'):
                                                st.image(chunk['metadata']['image_path'])
                            except Exception as e:
                                st.error(f"Fehler: {e}")

            else:
                st.success("Keine Auffälligkeiten.")

            st.divider()
            c_head, c_btn = st.columns([3, 1])
            with c_head: 
                st.subheader("Claims")
                st.info("Ampel-System: 🟢 Hinweis: Potenziell belegt | 🟠 Potenzielles Risiko: Unbelegt")
            
            open_claims_count = sum(1 for c in claims if c['status'] == 'OPEN')
            if open_claims_count > 0:
                with c_btn:
                    if st.button(f"2nd Search ({open_claims_count} offen)"):
                        # Use same model as initial analysis
                        model_used = res.get('model_used', 'gpt-4o-mini')
                        analyzer = GreenwashingAnalyzer(model_name=model_used)
                        prog = st.progress(0)
                        stat = st.empty()
                        updated = analyzer.deep_verify_claims(st.session_state.chunks, claims, lambda p,m: (prog.progress(p), stat.text(m)))
                        st.session_state.audit_results['claim_registry'] = updated
                        st.success("Tiefenprüfung fertig!")
                        st.rerun()

            for c in sorted(claims, key=lambda x: x['status']):
                if c['status'] == 'OPEN':
                    color, icon, msg = "#ff9800", "🟠", "Potenzielles Risiko: Unbelegt"
                    bg_rgba = "rgba(255, 152, 0, 0.15)"
                elif c['status'] == 'POTENTIALLY_VERIFIED':
                    color, icon, msg = "#00c851", "🟢", "Hinweis: Potenziell belegt"
                    bg_rgba = "rgba(0, 200, 81, 0.15)"
                else:
                    color, icon, msg = "#999", "⚪", f"Status: {c['status']}"
                    bg_rgba = "rgba(128, 128, 128, 0.1)"
                
                st.markdown(f"""
                <div style="border-left:5px solid {color}; padding:10px; background:{bg_rgba}; margin-bottom:5px; border-radius:4px;">
                    <b>{icon} ID {c['id']} (S. {c['page']})</b>: {c['text']}<br>
                    <span style="font-size:0.8em; opacity:0.8">{msg} | {c.get('evidence', '')}</span>
                </div>
                """, unsafe_allow_html=True)
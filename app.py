import streamlit as st
import requests
import pandas as pd
import io

# TES CREDENTIALS (ne pas partager en prod !)
CLIENT_ID = "PAR_mehdi_1cb67173257a433ced027b120f0031709c3931337aa63efe3addb49ccef60743"
CLIENT_SECRET = "dae785ee5f3711af2424612ca758272be8457193eeccbe09a95fdfa334d0e7d7"

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
API_BASE = "https://api.francetravail.io/partenaire/rome-metiers"
SCOPES = "nomenclatureRome api_rome-metiersv1"

def get_token():
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPES,
    }
    r = requests.post(TOKEN_URL, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def get_metier(code_rome):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    champs = (
        "code,"
        "domaineprofessionnel(libelle,code,granddomaine(libelle,code)),"
        "definition,"
        "contextestravail(libelle),"
        "emploicadre,"
        "formacodes(libelle,code),"
        "libelle,"
        "secteursactivites(code,libelle),"
        "themes(code,libelle),"
        "transitiondemographique,"
        "transitionecologique,"
        "transitionecologiquedetaillee,"
        "transitionnumerique"
    )
    
    url = f"{API_BASE}/v1/metiers/metier/{code_rome}"
    params = {"champs": champs}
    
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

def flatten_dict(d, parent_key='', sep='_'):
    """Aplatit un dictionnaire imbriqué pour l'Excel"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
            
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((f"{new_key}_{i}", item))
        else:
            items.append((new_key, v))
            
    return dict(items)

def json_to_df(metier_data):
    flat_data = flatten_dict(metier_data)
    return pd.DataFrame([flat_data])

# ────────────────────────────────────────────────
#                  INTERFACE STREAMLIT
# ────────────────────────────────────────────────

st.title("🔎 Recherche Métier ROME")
st.markdown("Entrez un code ROME et téléchargez le résultat **en Excel (.xlsx)**")

code_rome = st.text_input("Code ROME (ex: A1413)", "").strip().upper()

if st.button("🔍 Rechercher"):
    if not code_rome:
        st.warning("⚠️ Veuillez entrer un code ROME valide.")
    else:
        with st.spinner("Recherche en cours..."):
            try:
                metier = get_metier(code_rome)
                libelle = metier.get('libelle', 'Sans libellé')
                st.success(f"✅ Métier trouvé : **{libelle}** ({code_rome})")
                
                with st.expander("📋 Voir le JSON brut"):
                    st.json(metier)
                
                # Conversion en DataFrame
                df = json_to_df(metier)
                
                # Préparation du fichier Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(
                        writer, 
                        sheet_name='Metier_ROME', 
                        index=False,
                        freeze_panes=(1,0),           # figer la ligne d'en-tête
                        engine_kwargs={'options': {'strings_to_formulas': False}}
                    )
                
                excel_buffer.seek(0)
                
                # Bouton de téléchargement principal → Excel
                st.download_button(
                    label="📊 Télécharger en Excel (.xlsx)",
                    data=excel_buffer.getvalue(),
                    file_name=f"{code_rome}_{libelle.replace(' ', '_')[:40]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Fichier Excel avec tous les champs aplatis",
                )
                
                # Option secondaire CSV (facultatif)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="Télécharger en CSV (optionnel)",
                    data=csv_buffer.getvalue(),
                    file_name=f"{code_rome}_metier.csv",
                    mime="text/csv",
                )
                
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else "?"
                st.error(f"❌ Erreur API (code {status}) — Code ROME probablement invalide")
                if e.response is not None:
                    with st.expander("Détail de l'erreur"):
                        st.code(e.response.text)
            except Exception as e:
                st.error(f"❌ Erreur inattendue : {e}")
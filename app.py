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
        "libelle,"
        "contextestravail(categorie,libelle),"
    )
    
    url = f"{API_BASE}/v1/metiers/metier/{code_rome}"
    params = {"champs": champs}
    
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

def extract_contextes_by_categorie(contextes, categorie):
    """Extrait les libellés des contextes pour une catégorie donnée"""
    result = []
    if 'contextestravail' in contextes:
        for ctx in contextes['contextestravail']:
            if ctx.get('categorie') == categorie:
                result.append(ctx.get('libelle', ''))
    return result

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

def json_to_df(metiers_data):
    """Convertit une liste de métiers en DataFrame"""
    flat_data = []
    for metier in metiers_data:
        flat_metier = flatten_dict(metier)
        flat_data.append(flat_metier)
    return pd.DataFrame(flat_data)

# ────────────────────────────────────────────────
#                  INTERFACE STREAMLIT
# ────────────────────────────────────────────────

st.title("🔎 Recherche Multi-Métiers ROME")
st.markdown("**Entrez plusieurs codes ROME (1 par ligne) et téléchargez le résultat en Excel**")

# Zone de saisie multi-lignes
codes_input = st.text_area(
    "Codes ROME (un par ligne, ex: A1413\nM1805\nH1203)", 
    height=150,
    placeholder="A1413\nM1805\nH1203"
)

if st.button("🔍 Rechercher TOUS les métiers", type="primary"):
    if not codes_input.strip():
        st.warning("⚠️ Veuillez entrer au moins un code ROME.")
    else:
        codes_list = [code.strip().upper() for code in codes_input.strip().split('\n') if code.strip()]
        
        if not codes_list:
            st.warning("⚠️ Aucun code ROME valide détecté.")
        else:
            st.info(f"🔄 Recherche de **{len(codes_list)}** métiers...")
            
            progress_bar = st.progress(0)
            metiers_data = []
            statuts = []
            
            for i, code_rome in enumerate(codes_list):
                try:
                    with st.spinner(f"Recherche {code_rome}..."):
                        metier = get_metier(code_rome)
                        libelle = metier.get('libelle', 'Sans libellé')
                        metiers_data.append(metier)
                        statuts.append(f"✅ **{libelle}** ({code_rome})")
                except requests.HTTPError:
                    statuts.append(f"❌ **{code_rome}** (non trouvé)")
                except Exception as e:
                    statuts.append(f"❌ **{code_rome}** (erreur: {str(e)[:30]}...)")
                
                progress_bar.progress((i + 1) / len(codes_list))
            
            # Affichage des résultats
            st.subheader("📋 Résultats de la recherche")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**✅ Métiers trouvés :**")
                for statut in statuts:
                    st.markdown(statut)
            
            with col2:
                reussis = sum(1 for s in statuts if s.startswith("✅"))
                st.metric("Taux de réussite", f"{reussis}/{len(codes_list)}", f"{reussis/len(codes_list)*100:.0f}%")
            
            # Extraction des contextes spécifiques
            if any("✅" in s for s in statuts):
                st.subheader("⚙️ Conditions de travail & Horaires")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 🏭 **Conditions de travail et risques professionnels**")
                    conditions_travail = []
                    for metier in metiers_data:
                        ctx = extract_contextes_by_categorie(metier, "CONDITIONS_TRAVAIL")
                        conditions_travail.extend(ctx)
                    
                    if conditions_travail:
                        for libelle in conditions_travail:
                            st.markdown(f"- **{libelle}**")
                    else:
                        st.info("Aucun contexte CONDITIONS_TRAVAIL trouvé")
                
                with col2:
                    st.markdown("### ⏰ **Horaires et durée du travail**")
                    horaires_travail = []
                    for metier in metiers_data:
                        ctx = extract_contextes_by_categorie(metier, "HORAIRE_ET_DUREE_TRAVAIL")
                        horaires_travail.extend(ctx)
                    
                    if horaires_travail:
                        for libelle in horaires_travail:
                            st.markdown(f"- **{libelle}**")
                    else:
                        st.info("Aucun contexte HORAIRE_ET_DUREE_TRAVAIL trouvé")
            
            # JSON brut (expander)
            if metiers_data:
                with st.expander("📋 Voir tous les JSON bruts"):
                    st.json(metiers_data)
            
            # Téléchargements
            if metiers_data:
                df = json_to_df(metiers_data)
                
                # Excel multi-feuilles
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Tous_les_metiers', index=False)
                    
                    # Feuille récap contextes
                    contextes_df = []
                    for metier in metiers_data:
                        row = {'code': metier.get('code', ''), 'libelle': metier.get('libelle', '')}
                        
                        # Conditions de travail
                        ctx_cond = extract_contextes_by_categorie(metier, "CONDITIONS_TRAVAIL")
                        row['conditions_travail'] = "; ".join(ctx_cond)
                        
                        # Horaires
                        ctx_horaires = extract_contextes_by_categorie(metier, "HORAIRE_ET_DUREE_TRAVAIL")
                        row['horaires_travail'] = "; ".join(ctx_horaires)
                        
                        contextes_df.append(row)
                    
                    pd.DataFrame(contextes_df).to_excel(writer, sheet_name='Récap_Contextes', index=False)
                
                excel_buffer.seek(0)
                
                st.download_button(
                    label=f"📊 Télécharger Excel ({len(metiers_data)} métiers)",
                    data=excel_buffer.getvalue(),
                    file_name=f"ROME_{len(metiers_data)}_metiers.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# Exemple
with st.expander("💡 Exemple d'utilisation"):
    st.code("""
A1413
M1805
H1203
K2110
""", language="text")

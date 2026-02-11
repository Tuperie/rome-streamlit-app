import streamlit as st
import requests
import pandas as pd
import io
from openpyxl.utils import get_column_letter

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
        "contextestravail(categorie,libelle),"  # Note : on garde cette syntaxe pour l'API
    )
    
    url = f"{API_BASE}/v1/metiers/metier/{code_rome}"
    params = {"champs": champs}
    
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

def get_contextes_by_categorie(metier, categorie):
    """Extrait les libellés pour une catégorie spécifique"""
    contextes = []
    if 'contextesTravail' in metier:  # ← Clé réelle dans le JSON reçu
        for ctx in metier['contextesTravail']:
            if ctx.get('categorie') == categorie:
                libelle = ctx.get('libelle', '').strip()
                if libelle:
                    contextes.append(libelle)
    return contextes

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

def create_enriched_df(metiers_data):
    """Crée un DataFrame avec colonnes aplaties + deux colonnes condensées"""
    rows = []
    
    for metier in metiers_data:
        flat = flatten_dict(metier)
        
        # Extraction des deux listes condensées
        conditions = get_contextes_by_categorie(metier, "CONDITIONS_TRAVAIL")
        horaires = get_contextes_by_categorie(metier, "HORAIRE_ET_DUREE_TRAVAIL")
        
        flat['Conditions de travail et risques professionnels'] = '; '.join(conditions) if conditions else ''
        flat['Horaires et durée du travail'] = '; '.join(horaires) if horaires else ''
        
        rows.append(flat)
    
    df = pd.DataFrame(rows)
    
    # Réordonner : code → libelle → conditions → horaires → reste
    desired_order = ['code', 'libelle']
    if 'Conditions de travail et risques professionnels' in df.columns:
        desired_order.append('Conditions de travail et risques professionnels')
    if 'Horaires et durée du travail' in df.columns:
        desired_order.append('Horaires et durée du travail')
    
    final_order = desired_order
    
    return df[final_order]

# ────────────────────────────────────────────────
# INTERFACE STREAMLIT
# ────────────────────────────────────────────────

st.title("🔎 Recherche Multi-Métiers ROME")
st.markdown("**Entrez plusieurs codes ROME (1 par ligne) et consultez les résultats détaillés**")

codes_input = st.text_area(
    "Codes ROME (un par ligne, ex: A1413\nM1805\nH1203)",
    height=150,
    placeholder="A1413\nM1805\nH1203"
)

if st.button("🔍 Rechercher TOUS les métiers", type="primary"):
    if not codes_input.strip():
        st.warning("⚠️ Veuillez entrer au moins un code ROME.")
    else:
        codes_list = list(set(code.strip().upper() for code in codes_input.strip().split('\n') if code.strip()))
        
        if not codes_list:
            st.warning("⚠️ Aucun code ROME valide détecté.")
        else:
            st.info(f"🔄 Recherche de **{len(codes_list)}** métiers...")
            
            progress_bar = st.progress(0)
            metiers_data = []
            statuts = []
            
            for i, code_rome in enumerate(codes_list):
                try:
                    metier = get_metier(code_rome)
                    libelle = metier.get('libelle', 'Sans libellé')
                    metiers_data.append(metier)
                    statuts.append({
                        'code': code_rome,
                        'libelle': libelle,
                        'metier_data': metier,
                        'success': True
                    })
                except requests.HTTPError:
                    statuts.append({
                        'code': code_rome,
                        'libelle': 'Non trouvé',
                        'success': False
                    })
                except Exception as e:
                    statuts.append({
                        'code': code_rome,
                        'libelle': f'Erreur: {str(e)[:30]}…',
                        'success': False
                    })
                
                progress_bar.progress((i + 1) / len(codes_list))
            
            # Résultats à l'écran
            st.subheader("📋 Résultats détaillés par métier")
            
            reussis = sum(1 for s in statuts if s.get('success', False))
            col1, col2 = st.columns([3, 1])
            with col1:
                st.metric("Taux de réussite", f"{reussis}/{len(codes_list)}")
            
            for statut in statuts:
                code_rome = statut['code']
                libelle = statut['libelle']
                
                if statut.get('success', False):
                    st.success(f"✅ **{libelle}** ({code_rome})")
                    
                    conditions_ctx = get_contextes_by_categorie(statut['metier_data'], "CONDITIONS_TRAVAIL")
                    st.markdown("**🏭 Conditions de travail et risques professionnels :**")
                    if conditions_ctx:
                        for ctx in conditions_ctx:
                            st.markdown(f"- {ctx}")
                    else:
                        st.markdown("*Aucune condition trouvée*")
                    
                    horaires_ctx = get_contextes_by_categorie(statut['metier_data'], "HORAIRE_ET_DUREE_TRAVAIL")
                    st.markdown("**⏰ Horaires et durée du travail :**")
                    if horaires_ctx:
                        for ctx in horaires_ctx:
                            st.markdown(f"- {ctx}")
                    else:
                        st.markdown("*Aucun horaire spécifique trouvé*")
                    
                    st.divider()
                else:
                    st.error(f"❌ **{code_rome}** - {libelle}")
                    st.divider()
            
            # Téléchargement Excel
            reussis_data = [s['metier_data'] for s in statuts if s.get('success', False)]
            if reussis_data:
                df = create_enriched_df(reussis_data)
                
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Metiers_ROME', index=False)
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Metiers_ROME']
                    
                    # Ajustement largeur colonnes basé sur les en-têtes
                    for col_idx, column_cells in enumerate(worksheet.columns, start=1):
                        column_letter = get_column_letter(col_idx)
                        header_value = worksheet[f"{column_letter}1"].value
                        
                        if header_value:
                            length = len(str(header_value)) + 5  # marge
                            width = min(length, 80)  # limite raisonnable
                            worksheet.column_dimensions[column_letter].width = width
                    
                    worksheet.freeze_panes = "A2"
                
                excel_buffer.seek(0)
                
                st.download_button(
                    label=f"📊 Télécharger Excel ({len(reussis_data)} métiers)",
                    data=excel_buffer.getvalue(),
                    file_name=f"ROME_multi_metiers_{len(reussis_data)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

with st.expander("💡 Exemple d'utilisation"):
    st.code("""
A1413
M1805
H1203
K2110
""", language="text")


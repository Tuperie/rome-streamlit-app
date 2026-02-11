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

def get_contextes_by_categorie(metier, categorie):
    """Extrait les libellés pour une catégorie spécifique"""
    contextes = []
    if 'contextestravail' in metier:
        for ctx in metier['contextestravail']:
            if ctx.get('categorie') == categorie:
                contextes.append(ctx.get('libelle', ''))
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
st.markdown("**Entrez plusieurs codes ROME (1 par ligne) et consultez les résultats détaillés**")

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
                        'libelle': f'Erreur: {str(e)[:30]}',
                        'success': False
                    })
                
                progress_bar.progress((i + 1) / len(codes_list))
            
            # Affichage des résultats - CHAQUE MÉTIER avec ses contextes
            st.subheader("📋 Résultats détaillés par métier")
            
            reussis = sum(1 for s in statuts if s.get('success', False))
            col1, col2 = st.columns([3, 1])
            with col1:
                st.metric("Taux de réussite", f"{reussis}/{len(codes_list)}")
            with col2:
                st.metric("Temps total", f"{len(codes_list)*2:.0f}s estimés")
            
            # Affichage par métier
            for statut in statuts:
                code_rome = statut['code']
                libelle = statut['libelle']
                
                if statut.get('success', False):
                    st.success(f"✅ **{libelle}** ({code_rome})")
                    
                    # Conditions de travail pour CE métier
                    conditions_ctx = get_contextes_by_categorie(statut['metier_data'], "CONDITIONS_TRAVAIL")
                    if conditions_ctx:
                        st.markdown("**🏭 Conditions de travail et risques professionnels :**")
                        for ctx in conditions_ctx:
                            st.markdown(f"• {ctx}")
                    else:
                        st.markdown("**🏭** *Aucune condition de travail*")
                    
                    # Horaires pour CE métier
                    horaires_ctx = get_contextes_by_categorie(statut['metier_data'], "HORAIRE_ET_DUREE_TRAVAIL")
                    if horaires_ctx:
                        st.markdown("**⏰ Horaires et durée du travail :**")
                        for ctx in horaires_ctx:
                            st.markdown(f"• {ctx}")
                    else:
                        st.markdown("**⏰** *Aucun horaire spécifique*")
                    
                    st.divider()  # Séparateur visuel entre les métiers
                else:
                    st.error(f"❌ **{code_rome}** - {libelle}")
                    st.divider()
            
            # JSON brut (expander)
            if any(s.get('success', False) for s in statuts):
                with st.expander("📋 Voir tous les JSON bruts"):
                    st.json([s['metier_data'] for s in statuts if s.get('success', False)])
            
            # Téléchargements
            reussis_data = [s['metier_data'] for s in statuts if s.get('success', False)]
            if reussis_data:
                df = json_to_df(reussis_data)
                
                # Excel multi-feuilles
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Tous_les_metiers', index=False)
                
                excel_buffer.seek(0)
                
                st.download_button(
                    label=f"📊 Télécharger Excel ({len(reussis_data)} métiers)",
                    data=excel_buffer.getvalue(),
                    file_name=f"ROME_{len(reussis_data)}_metiers.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# Exemple
with st.expander("💡 Exemple d'utilisation"):
    st.code("""
A1413    ← Chef de projet numérique
          ↓
✅ Chef de projet numérique (A1413)
🏭 Conditions de travail :
• Risques de chutes
• Bruit
⏰ Horaires :
• Travail de nuit
• Horaires irréguliers

M1805    ← Développeur web
          ↓
✅ Développeur web (M1805)
🏭 Conditions de travail :
• Poste sédentaire
⏰ Horaires :
• 35h/semaine
""", language="text")

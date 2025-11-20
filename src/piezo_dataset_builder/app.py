"""
Application Streamlit - Piezo Dataset Builder.

Refondue pour une meilleure gestion d'état et modularité.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import time

from piezo_dataset_builder.core.validator import extract_station_codes, validate_station_codes
from piezo_dataset_builder.core.dataset_builder import DatasetBuilder
from piezo_dataset_builder.utils.export import to_csv, to_excel, to_json, get_export_stats

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('piezo_dataset_builder.log')
    ]
)

logger = logging.getLogger(__name__)

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Piezo Dataset Builder",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour améliorer l'UI
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #00BFFF;
    }
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .step-container {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        margin-bottom: 20px;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-color: #c3e6cb;
        color: #155724;
        border-radius: .25rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# STATE MANAGEMENT
# ============================================================

class AppState:
    """Gère l'état global de l'application."""
    
    STEP_UPLOAD = 1
    STEP_CONFIG = 2
    STEP_BUILD = 3  # Transient step, usually skips quickly to RESULT if successful
    STEP_RESULT = 4

    @staticmethod
    def init():
        if 'app_state' not in st.session_state:
            st.session_state.app_state = {
                'current_step': AppState.STEP_UPLOAD,
                'codes_bss': [],
                'valid_codes': [],
                'invalid_codes': [],
                'df_result': None,
                'build_logs': [],
                'config': {
                    'date_start': datetime.now() - timedelta(days=30),
                    'date_end': datetime.now(),
                    'include_stations': True,
                    'include_chroniques': True,
                    'include_meteo': True,
                    'station_fields': {
                        'libelle_station': True,
                        'nom_commune': True,
                        'nom_departement': True
                    },
                    'chronique_fields': {
                        'niveau_nappe_ngf': True,
                        'profondeur_nappe': True
                    },
                    'meteo_vars': {
                        'precip': True,
                        'temp': True,
                        'et': True,
                        'temp_min': False,
                        'temp_max': False,
                        'humidity': False,
                        'wind': False,
                        'radiation': False
                    },
                    'daily_aggregation': True,
                    'timeout': 30,
                    'rate_limit_hubeau': 0.1,
                    'rate_limit_meteo': 10.0
                }
            }

    @staticmethod
    def get(key):
        return st.session_state.app_state.get(key)

    @staticmethod
    def set(key, value):
        st.session_state.app_state[key] = value

    @staticmethod
    def update_config(key, value):
        st.session_state.app_state['config'][key] = value

    @staticmethod
    def update_meteo_var(var, value):
        st.session_state.app_state['config']['meteo_vars'][var] = value
        
    @staticmethod
    def update_station_field(field, value):
        st.session_state.app_state['config']['station_fields'][field] = value

    @staticmethod
    def update_chronique_field(field, value):
        st.session_state.app_state['config']['chronique_fields'][field] = value

    @staticmethod
    def set_step(step):
        st.session_state.app_state['current_step'] = step
        # Force rerun to update UI immediately
        st.rerun()

    @staticmethod
    def reset():
        # Keep config but reset data
        config = st.session_state.app_state['config']
        del st.session_state.app_state
        AppState.init()
        st.session_state.app_state['config'] = config
        st.rerun()

# Initialize state
AppState.init()

# ============================================================
# UI COMPONENTS
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.title("💧 Navigation")
        
        step = AppState.get('current_step')
        
        st.markdown(f"""
        **Étapes :**
        1. {"🟢" if step == 1 else "⚪"} Upload CSV
        2. {"🟢" if step == 2 else "⚪"} Configuration
        3. {"🟢" if step >= 3 else "⚪"} Résultat
        """)
        
        st.markdown("---")
        
        if step > 1:
            if st.button("🔄 Recommencer", use_container_width=True):
                AppState.reset()
        
        st.markdown("---")
        st.caption("Documentation")
        st.info("""
        **Attributs Stations :**
        Informations sur le point de mesure (Lieu, altitude, etc.)
        
        **Niveaux de nappe :**
        Mesures piézométriques issues de Hub'Eau
        
        **Météo :**
        Données climatiques (Pluie, Temp...) issues d'Open-Meteo
        """)
        
        st.markdown("""
        <div style='font-size: 0.8rem; color: #666; margin-top: 20px;'>
            v1.1.0<br>
            Powered by Hub'Eau & Open-Meteo
        </div>
        """, unsafe_allow_html=True)

def render_header():
    st.markdown("<h1 class='main-header'>💧 Piezo Dataset Builder</h1>", unsafe_allow_html=True)
    st.markdown("""
    Construisez facilement un dataset hydrologique complet (niveaux de nappe + météo) 
    pour vos analyses ou modèles IA.
    """)
    st.markdown("---")

def render_step_1_upload():
    st.header("1️⃣ Import des stations")
    
    with st.container():
        st.markdown("Chargez un fichier CSV contenant une liste de codes BSS (ex: `07548X0009/F`).")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "Fichier CSV",
                type=["csv"],
                key="file_uploader"
            )
            
        with col2:
            st.info("""
            **Format supporté :**
            - CSV standard
            - Une colonne avec codes BSS
            - Détection automatique de la colonne
            """)
            
        if uploaded_file is not None:
            try:
                # Tentative de lecture auto-détectée, sinon essai avec ;
                try:
                    df_input = pd.read_csv(uploaded_file)
                    # Si on a qu'une seule colonne et qu'elle contient des ; ou , dans les valeurs, c'est suspect
                    if len(df_input.columns) == 1 and df_input.iloc[0].astype(str).str.contains(';|,').any():
                         uploaded_file.seek(0)
                         df_input = pd.read_csv(uploaded_file, sep=';')
                except:
                     uploaded_file.seek(0)
                     df_input = pd.read_csv(uploaded_file, sep=';')

                # Si plusieurs colonnes, afficher sélecteur
                selected_column = None
                if len(df_input.columns) > 1:
                    st.info(f"📋 Le fichier contient {len(df_input.columns)} colonnes. Sélectionnez celle contenant les codes BSS.")

                    # Suggestion automatique basée sur les patterns
                    suggested_col = None
                    for col in df_input.columns:
                        col_lower = col.lower()
                        if any(pattern in col_lower for pattern in ['code_bss', 'bss_id', 'bss', 'code']):
                            suggested_col = col
                            break

                    # Index de la colonne suggérée
                    default_index = 0
                    if suggested_col:
                        default_index = list(df_input.columns).index(suggested_col)

                    selected_column = st.selectbox(
                        "Colonne contenant les codes BSS:",
                        options=df_input.columns.tolist(),
                        index=default_index,
                        help="Sélectionnez la colonne qui contient les codes de stations piézométriques (BSS)"
                    )

                    st.caption(f"Aperçu des 5 premières valeurs de '{selected_column}':")
                    st.code("\n".join([str(v) for v in df_input[selected_column].head(5).tolist()]))
                else:
                    st.info(f"📋 Une seule colonne détectée: '{df_input.columns[0]}' - Utilisation automatique")

                codes_bss = extract_station_codes(df_input, column_name=selected_column)

                if not codes_bss:
                    st.error("❌ Aucun code BSS valide trouvé dans la colonne sélectionnée.")
                    return

                st.success(f"✅ {len(codes_bss)} codes BSS détectés dans la colonne '{selected_column or df_input.columns[0]}'.")
                
                # Validation optionnelle mais recommandée
                with st.expander("🔍 Validation des codes (Échantillon)", expanded=True):
                    with st.spinner("Validation rapide via Hub'Eau..."):
                        valid, invalid = validate_station_codes(codes_bss, sample_size=5)
                    
                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        st.metric("Codes testés valides", len(valid))
                    with col_v2:
                        st.metric("Codes testés invalides", len(invalid))
                        
                    if invalid:
                        st.warning(f"Certains codes semblent invalides (ex: {invalid[0]}). Ils seront ignorés lors de la construction.")
                
                if st.button("Passer à la configuration ➡️", type="primary"):
                    AppState.set('codes_bss', codes_bss)
                    AppState.set_step(AppState.STEP_CONFIG)
                    
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier : {e}")

def render_step_2_config():
    st.header("2️⃣ Configuration du dataset")
    
    codes = AppState.get('codes_bss')
    st.markdown(f"**Stations sélectionnées :** {len(codes)}")
    
    with st.form("config_form"):
        # --- PÉRIODE ---
        st.subheader("📅 Période temporelle")
        col_date1, col_date2 = st.columns(2)
        
        config = AppState.get('config')
        
        with col_date1:
            d_start = st.date_input(
                "Date de début",
                value=config['date_start'],
                min_value=datetime(1940, 1, 1).date(),  # Open-Meteo historical data starts in 1940
                max_value=datetime.now().date()
            )
        with col_date2:
            d_end = st.date_input(
                "Date de fin",
                value=config['date_end'],
                min_value=datetime(1940, 1, 1).date(),
                max_value=datetime.now().date()
            )
            
        st.caption(f"Durée : {(d_end - d_start).days + 1} jours")
        
        st.markdown("---")
        st.subheader("🛠️ Sources de données & Attributs")
        
        # --- 1. STATIONS ---
        st.markdown("#### 📍 Stations Piézométriques")
        col_s_check, col_s_opts = st.columns([1, 3])
        
        with col_s_check:
            inc_stations = st.checkbox("Inclure Attributs Stations", value=config['include_stations'])
        
        # Init vars
        s_fields = config['station_fields']
        sf_lib = s_fields['libelle_station']
        sf_com = s_fields['nom_commune']
        sf_dept = s_fields['nom_departement']

        if inc_stations:
            with col_s_opts:
                with st.expander("Choisir les attributs", expanded=True):
                    sc1, sc2 = st.columns(2)
                    with sc1:
                        sf_lib = st.checkbox("Libellé", value=s_fields['libelle_station'])
                        sf_com = st.checkbox("Commune", value=s_fields['nom_commune'])
                    with sc2:
                        sf_dept = st.checkbox("Département", value=s_fields['nom_departement'])

        st.markdown("") # Spacer

        # --- 2. CHRONIQUES ---
        st.markdown("#### 💧 Niveaux de nappe (Hub'Eau)")
        col_c_check, col_c_opts = st.columns([1, 3])
        
        with col_c_check:
            inc_chroniques = st.checkbox("Inclure Chroniques", value=config['include_chroniques'])

        # Init vars
        c_fields = config['chronique_fields']
        cf_ngf = c_fields['niveau_nappe_ngf']
        cf_prof = c_fields['profondeur_nappe']

        if inc_chroniques:
            with col_c_opts:
                with st.expander("Choisir les champs", expanded=True):
                    cf_ngf = st.checkbox("Niveau NGF (altitude nappe)", value=c_fields['niveau_nappe_ngf'])
                    cf_prof = st.checkbox("Profondeur nappe", value=c_fields['profondeur_nappe'])

        st.markdown("") # Spacer

        # --- 3. MÉTÉO ---
        st.markdown("#### 🌦️ Météo (Open-Meteo)")
        col_m_check, col_m_opts = st.columns([1, 3])
        
        with col_m_check:
            inc_meteo = st.checkbox("Inclure Météo", value=config['include_meteo'])

        # Init vars
        meteo_vars = config['meteo_vars']
        vp = meteo_vars['precip']
        vtmin = meteo_vars['temp_min']
        vt = meteo_vars['temp']
        vtmax = meteo_vars['temp_max']
        vet = meteo_vars['et']
        vhum = meteo_vars['humidity']
        vwind = meteo_vars['wind']
        vrad = meteo_vars['radiation']

        if inc_meteo:
            with col_m_opts:
                with st.expander("Choisir les variables", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        vp = st.checkbox("Précipitations", value=meteo_vars['precip'])
                        vtmin = st.checkbox("Temp. Min", value=meteo_vars['temp_min'])
                    with c2:
                        vt = st.checkbox("Température", value=meteo_vars['temp'])
                        vtmax = st.checkbox("Temp. Max", value=meteo_vars['temp_max'])
                    with c3:
                        vet = st.checkbox("Évapotranspiration", value=meteo_vars['et'])
                        vhum = st.checkbox("Humidité", value=meteo_vars['humidity'])
                    with c4:
                        vwind = st.checkbox("Vent", value=meteo_vars['wind'])
                        vrad = st.checkbox("Rayonnement", value=meteo_vars['radiation'])
        
        st.markdown("---")

        # --- OPTIONS GLOBALES ---
        st.subheader("⚙️ Traitement")
        daily = st.checkbox("Agrégation journalière (Moyenne)", value=config['daily_aggregation'])

        # Options avancées
        with st.expander("Paramètres avancés API"):
            c_to, c_rl1, c_rl2 = st.columns(3)
            timeout = c_to.number_input("Timeout (s)", value=config['timeout'], min_value=5)
            rl_h = c_rl1.number_input("Rate Limit Hub'Eau (s)", value=config['rate_limit_hubeau'], min_value=0.1)
            rl_m = c_rl2.number_input("Rate Limit Météo (s)", value=config['rate_limit_meteo'], min_value=5.0, max_value=20.0)

        st.markdown("---")
        submitted = st.form_submit_button("🚀 Lancer la construction", type="primary", use_container_width=True)
        
        if submitted:
            # Validation
            if d_start >= d_end:
                st.error("La date de début doit être antérieure à la date de fin.")
                return
                
            # Mise à jour du state
            AppState.update_config('date_start', d_start)
            AppState.update_config('date_end', d_end)
            AppState.update_config('include_stations', inc_stations)
            AppState.update_config('include_chroniques', inc_chroniques)
            AppState.update_config('include_meteo', inc_meteo)
            AppState.update_config('daily_aggregation', daily)
            AppState.update_config('timeout', timeout)
            AppState.update_config('rate_limit_hubeau', rl_h)
            AppState.update_config('rate_limit_meteo', rl_m)
            
            # Update meteo vars
            if inc_meteo:
                new_vars = {
                    'precip': vp, 'temp': vt, 'et': vet, 'temp_min': vtmin,
                    'temp_max': vtmax, 'humidity': vhum, 'wind': vwind, 'radiation': vrad
                }
                for k, v in new_vars.items():
                    AppState.update_meteo_var(k, v)
            
            # Update station fields
            if inc_stations:
                new_s_fields = {
                    'libelle_station': sf_lib,
                    'nom_commune': sf_com,
                    'nom_departement': sf_dept
                }
                for k, v in new_s_fields.items():
                    AppState.update_station_field(k, v)

            # Update chronique fields
            if inc_chroniques:
                new_c_fields = {
                    'niveau_nappe_ngf': cf_ngf,
                    'profondeur_nappe': cf_prof
                }
                for k, v in new_c_fields.items():
                    AppState.update_chronique_field(k, v)

            # Transition vers l'étape de construction
            AppState.set_step(AppState.STEP_BUILD)
            
def run_build_process():
    st.header("3️⃣ Construction en cours...")
    
    config = AppState.get('config')
    codes = AppState.get('codes_bss')
    
    # Préparer la liste des variables météo
    meteo_vars_list = []
    mvars = config['meteo_vars']
    mapping = {
        'precip': 'precipitation', 'temp': 'temperature', 'et': 'evapotranspiration',
        'temp_min': 'temperature_min', 'temp_max': 'temperature_max',
        'humidity': 'humidity', 'wind': 'wind', 'radiation': 'radiation'
    }
    for k, v in mvars.items():
        if v: meteo_vars_list.append(mapping[k])
    
    # Préparer listes champs stations et chroniques
    station_fields_list = []
    if config['include_stations']:
        for k, v in config['station_fields'].items():
            if v: station_fields_list.append(k)
            
    chronique_fields_list = []
    if config['include_chroniques']:
        for k, v in config['chronique_fields'].items():
            if v: chronique_fields_list.append(k)
    
    # UI de progression
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Zone de logs en temps réel (expandable)
    with st.expander("📋 Logs en temps réel", expanded=True):
        log_area = st.empty()

    logs = []

    def progress_callback(pct, msg):
        progress_bar.progress(pct / 100)
        status_text.markdown(f"**{msg}**")
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        # Affiche tous les logs (limité aux 20 derniers pour la performance)
        log_area.code("\n".join(logs[-20:]), language="log")
        
    try:
        builder = DatasetBuilder(
            timeout=config['timeout'],
            rate_limit_hubeau=config['rate_limit_hubeau'],
            rate_limit_meteo=config['rate_limit_meteo']
        )
        
        df = builder.build_dataset(
            codes_bss=codes,
            date_start=pd.Timestamp(config['date_start']),
            date_end=pd.Timestamp(config['date_end']),
            include_stations=config['include_stations'],
            include_chroniques=config['include_chroniques'],
            include_meteo=config['include_meteo'],
            meteo_variables=meteo_vars_list,
            station_fields=station_fields_list,
            chronique_fields=chronique_fields_list,
            daily_aggregation=config['daily_aggregation'],
            progress_callback=progress_callback
        )
        
        AppState.set('df_result', df)
        AppState.set('build_logs', logs)
        AppState.set_step(AppState.STEP_RESULT)
        
    except Exception as e:
        st.error(f"Une erreur est survenue : {str(e)}")
        st.exception(e)
        if st.button("Retour à la configuration"):
            AppState.set_step(AppState.STEP_CONFIG)

def render_step_4_result():
    st.header("4️⃣ Résultat")

    df = AppState.get('df_result')
    build_logs = AppState.get('build_logs')

    if df is None or df.empty:
        st.warning("Le dataset généré est vide.")
        if st.button("Recommencer"):
            AppState.set_step(AppState.STEP_CONFIG)
        return

    st.markdown(f"""
    <div class="success-box">
        ✅ Dataset généré avec succès ! ({len(df)} lignes, {len(df.columns)} colonnes)
    </div>
    """, unsafe_allow_html=True)

    # Afficher les logs de construction
    if build_logs:
        with st.expander("📋 Logs de construction", expanded=False):
            st.code("\n".join(build_logs), language="log")

    # Onglets
    tab1, tab2, tab3 = st.tabs(["📋 Aperçu", "📊 Statistiques", "💾 Export"])
    
    with tab1:
        st.dataframe(df.head(100), use_container_width=True)
        
    with tab2:
        stats = get_export_stats(df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lignes", stats['nb_lignes'])
        c2.metric("Colonnes", stats['nb_colonnes'])
        c3.metric("Stations", stats.get('nb_stations', 'N/A'))
        c4.metric("Taille Est.", f"{stats['taille_mo']:.2f} Mo")
        
        if 'taux_na' in stats:
            st.caption(f"Taux de valeurs manquantes global : {stats['taux_na']:.1f}%")
            
    with tab3:
        st.subheader("Téléchargement")
        filename = f"dataset_piezo_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.download_button(
                "📥 Télécharger CSV",
                data=to_csv(df),
                file_name=f"{filename}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with c2:
            st.download_button(
                "📥 Télécharger Excel",
                data=to_excel(df),
                file_name=f"{filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        with c3:
            st.download_button(
                "📥 Télécharger JSON",
                data=to_json(df),
                file_name=f"{filename}.json",
                mime="application/json",
                use_container_width=True
            )

# ============================================================
# MAIN
# ============================================================

def main():
    render_sidebar()
    render_header()
    
    step = AppState.get('current_step')
    
    if step == AppState.STEP_UPLOAD:
        render_step_1_upload()
    elif step == AppState.STEP_CONFIG:
        render_step_2_config()
    elif step == AppState.STEP_BUILD:
        run_build_process()
    elif step == AppState.STEP_RESULT:
        render_step_4_result()

if __name__ == "__main__":
    main()

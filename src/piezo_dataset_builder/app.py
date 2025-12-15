"""
Streamlit Application - Piezo Dataset Builder.

Refactored for better state management and modularity.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import time

from piezo_dataset_builder.core.validator import extract_station_codes, validate_station_codes
from piezo_dataset_builder.core.dataset_builder import DatasetBuilder
from piezo_dataset_builder.utils.export import to_csv, to_excel, to_json, to_zip_by_station, get_export_stats

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

# Custom CSS to improve the UI
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
    """Manages the global application state."""
    
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
                    'date_start': datetime.now() - timedelta(days=365),
                    'date_end': datetime.now(),
                    'include_stations': True,
                    'include_chroniques': True,
                    'include_meteo': True,
                    'era5_source': 'Download from Copernicus API',
                    'copernicus_api_token': '',
                    'era5_local_file': None,
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
                        'humidity': False,
                        'wind': False,
                        'radiation': False
                    },
                    'timeout': 30,
                    'rate_limit_hubeau': 0.1
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
        **Steps:**
        1. {"🟢" if step == 1 else "⚪"} Upload CSV
        2. {"🟢" if step == 2 else "⚪"} Configuration
        3. {"🟢" if step >= 3 else "⚪"} Result
        """)
        
        st.markdown("---")
        
        if step > 1:
            if st.button("🔄 Start Over", use_container_width=True):
                AppState.reset()
        
        st.markdown("---")
        st.caption("Documentation")
        st.info("""
        **Station Attributes:**
        Information about the measurement point (location, altitude, etc.)
        
        **Groundwater Levels:**
        Piezometric measurements from Hub'Eau
        
        **Weather:**
        Historical climate data (since 1940) from ERA5 (Copernicus)
        """)

        st.markdown("""
        <div style='font-size: 0.8rem; color: #666; margin-top: 20px;'>
            v2.0.0<br>
            Powered by Hub'Eau & ERA5 (Copernicus)
        </div>
        """, unsafe_allow_html=True)

def render_header():
    st.markdown("<h1 class='main-header'>💧 Piezo Dataset Builder</h1>", unsafe_allow_html=True)
    st.markdown("""
    Easily build a complete hydrological dataset (groundwater levels + weather) 
    for your analyses or AI models.
    """)
    st.markdown("---")

def render_step_1_upload():
    st.header("1️⃣ Station Import")
    
    with st.container():
        st.markdown("Load a CSV file containing a list of BSS codes (e.g., `07548X0009/F`).")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "CSV File",
                type=["csv"],
                key="file_uploader"
            )
            
        with col2:
            st.info("""
            **Supported format:**
            - Standard CSV
            - One column with BSS codes
            - Automatic column detection
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
                    st.info(f"📋 The file contains {len(df_input.columns)} columns. Select the one containing BSS codes.")

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
                        "Column containing BSS codes:",
                        options=df_input.columns.tolist(),
                        index=default_index,
                        help="Select the column containing piezometer station codes (BSS)"
                    )

                    st.caption(f"Preview of first 5 values from '{selected_column}':")
                    st.code("\n".join([str(v) for v in df_input[selected_column].head(5).tolist()]))
                else:
                    st.info(f"📋 Single column detected: '{df_input.columns[0]}' - Automatic use")

                codes_bss = extract_station_codes(df_input, column_name=selected_column)

                if not codes_bss:
                    st.error("❌ No valid BSS code found in the selected column.")
                    return

                st.success(f"✅ {len(codes_bss)} BSS codes detected in column '{selected_column or df_input.columns[0]}'.")
                
                # Validation optionnelle mais recommandée
                with st.expander("🔍 Code Validation (Sample)", expanded=True):
                    with st.spinner("Quick validation via Hub'Eau..."):
                        valid, invalid = validate_station_codes(codes_bss, sample_size=5)
                    
                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        st.metric("Valid tested codes", len(valid))
                    with col_v2:
                        st.metric("Invalid tested codes", len(invalid))
                        
                    if invalid:
                        st.warning(f"Some codes appear invalid (e.g., {invalid[0]}). They will be ignored during construction.")
                
                if st.button("Proceed to Configuration ➡️", type="primary"):
                    AppState.set('codes_bss', codes_bss)
                    AppState.set_step(AppState.STEP_CONFIG)
                    
            except Exception as e:
                st.error(f"Error reading the file: {e}")

def render_step_2_config():
    st.header("2️⃣ Dataset Configuration")

    codes = AppState.get('codes_bss')
    st.markdown(f"**Selected stations:** {len(codes)}")

    # Section AVANT le formulaire pour gérer l'upload ERA5 et la détection des dates
    config = AppState.get('config')

    # Pré-affichage du choix de source ERA5 (en dehors du form pour permettre la réactivité)
    st.markdown("---")
    st.subheader("🌦️ ERA5 Data Source")

    era5_source_preview = st.radio(
        "Choose your weather source",
        options=["Download from Copernicus API", "Use local NetCDF file"],
        help="If you have an ERA5 file, it will be used to automatically detect the data period",
        horizontal=True,
        key="era5_source_selector"
    )

    # Si fichier local, permettre l'upload en dehors du form
    era5_file_preview = None
    if era5_source_preview == "Use local NetCDF file":
        st.info("📁 **Load your ERA5 file to automatically detect dates**")
        era5_file_preview = st.file_uploader(
            "ERA5 NetCDF file (.nc)",
            type=["nc"],
            help="Start/end dates will be automatically detected from this file",
            key="era5_file_preview_uploader"
        )

        if era5_file_preview:
            # Lire les métadonnées du NetCDF pour extraire les dates
            try:
                import xarray as xr
                import tempfile
                import os

                # Sauvegarder temporairement pour lire avec xarray
                with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp:
                    tmp.write(era5_file_preview.getvalue())
                    tmp_path = tmp.name

                try:
                    with xr.open_dataset(tmp_path, engine="netcdf4") as ds:
                        # Détecter la dimension temporelle
                        time_dim = "valid_time" if "valid_time" in ds.dims else "time"

                        # Extraire dates min/max
                        time_values = ds[time_dim].values
                        date_min = pd.to_datetime(time_values[0]).date()
                        date_max = pd.to_datetime(time_values[-1]).date()

                        # Détecter zone géographique
                        lat_dim = "latitude" if "latitude" in ds.dims else "lat"
                        lon_dim = "longitude" if "longitude" in ds.dims else "lon"
                        lat_min = float(ds[lat_dim].values.min())
                        lat_max = float(ds[lat_dim].values.max())
                        lon_min = float(ds[lon_dim].values.min())
                        lon_max = float(ds[lon_dim].values.max())

                        # Afficher les infos et mettre à jour le state
                        st.success(f"✅ File loaded: {era5_file_preview.name} ({era5_file_preview.size / (1024*1024):.2f} MB)")

                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.metric("📅 Detected period", f"{date_min} → {date_max}")
                            st.caption(f"{(date_max - date_min).days} days of data")
                        with col_info2:
                            st.metric("🌍 Geographic zone", f"Lat: {lat_min:.1f}°→{lat_max:.1f}°")
                            st.caption(f"Lon: {lon_min:.1f}°→{lon_max:.1f}°")

                        # Mettre à jour les dates dans le state
                        AppState.update_config('date_start', date_min)
                        AppState.update_config('date_end', date_max)

                        st.info("💡 Dates have been automatically adjusted to match your ERA5 file")

                finally:
                    os.remove(tmp_path)

            except Exception as e:
                st.warning(f"⚠️ Unable to read file metadata: {e}")
                st.caption("You can continue by manually entering the dates below")

    st.markdown("---")

    # Maintenant le formulaire avec les dates (potentiellement mises à jour)
    with st.form("config_form"):
        # --- PÉRIODE ---
        st.subheader("📅 Time Period")

        if era5_source_preview == "Use local NetCDF file" and era5_file_preview:
            st.caption("🔄 Dates auto-detected from ERA5 file. You can adjust them if needed.")

        col_date1, col_date2 = st.columns(2)

        # Récupérer les dates (possiblement mises à jour par la lecture du NetCDF)
        config = AppState.get('config')

        with col_date1:
            d_start = st.date_input(
                "Start date",
                value=config['date_start'],
                min_value=datetime(1940, 1, 1).date(),  # ERA5 historical data starts in 1940
                max_value=datetime.now().date()
            )
        with col_date2:
            d_end = st.date_input(
                "End date",
                value=config['date_end'],
                min_value=datetime(1940, 1, 1).date(),  # ERA5 data up to present
                max_value=datetime.now().date()
            )

        st.markdown("---")
        st.subheader("🛠️ Data Sources & Attributes")
        
        # --- 1. STATIONS ---
        st.markdown("#### 📍 Piezometric Stations")
        col_s_check, col_s_opts = st.columns([1, 3])
        
        with col_s_check:
            inc_stations = st.checkbox("Include Station Attributes", value=config['include_stations'])
        
        # Init vars
        s_fields = config['station_fields']
        sf_lib = s_fields['libelle_station']
        sf_com = s_fields['nom_commune']
        sf_dept = s_fields['nom_departement']

        if inc_stations:
            with col_s_opts:
                with st.expander("Choose attributes", expanded=True):
                    sc1, sc2 = st.columns(2)
                    with sc1:
                        sf_lib = st.checkbox("Label", value=s_fields['libelle_station'])
                        sf_com = st.checkbox("Municipality", value=s_fields['nom_commune'])
                    with sc2:
                        sf_dept = st.checkbox("Department", value=s_fields['nom_departement'])

        st.markdown("") # Spacer

        # --- 2. CHRONIQUES ---
        st.markdown("#### 💧 Groundwater Levels (Hub'Eau)")
        col_c_check, col_c_opts = st.columns([1, 3])
        
        with col_c_check:
            inc_chroniques = st.checkbox("Include Time Series", value=config['include_chroniques'])

        # Init vars
        c_fields = config['chronique_fields']
        cf_ngf = c_fields['niveau_nappe_ngf']
        cf_prof = c_fields['profondeur_nappe']

        if inc_chroniques:
            with col_c_opts:
                with st.expander("Choose fields", expanded=True):
                    cf_ngf = st.checkbox("Groundwater Level (NGF altitude)", value=c_fields['niveau_nappe_ngf'])
                    cf_prof = st.checkbox("Groundwater Depth", value=c_fields['profondeur_nappe'])

        st.markdown("") # Spacer

        # --- 3. MÉTÉO ---
        # La configuration ERA5 (source + fichier/token) est maintenant AVANT le formulaire
        # Ici on gère juste l'activation et les variables
        st.markdown("#### 🌦️ Weather (ERA5 - Options)")

        col_m_check, col_m_opts = st.columns([1, 3])

        with col_m_check:
            inc_meteo = st.checkbox("Include Weather", value=config['include_meteo'])

        # Gérer le token API si mode API (dans le form pour pouvoir valider)
        copernicus_api_token = ''
        if era5_source_preview == "Download from Copernicus API":
            st.info("🔑 **Copernicus CDS API Token** (required for ERA5)")
            copernicus_api_token = st.text_input(
                "Copernicus API Token",
                value=config.get('copernicus_api_token', ''),
                type="password",
                help="Your Copernicus CDS account API token",
                placeholder="abcd1234-5678-90ab-cdef-1234567890ab"
            )

        # Init vars
        meteo_vars = config['meteo_vars']
        vp = meteo_vars['precip']
        vt = meteo_vars['temp']
        vet = meteo_vars['et']
        vhum = meteo_vars['humidity']
        vwind = meteo_vars['wind']
        vrad = meteo_vars['radiation']

        if inc_meteo:
            with col_m_opts:
                with st.expander("Choose variables", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        vp = st.checkbox("Precipitation", value=meteo_vars['precip'])
                        vt = st.checkbox("Temperature", value=meteo_vars['temp'])
                    with c2:
                        vet = st.checkbox("Evapotranspiration", value=meteo_vars['et'])
                        vhum = st.checkbox("Humidity", value=meteo_vars['humidity'])
                    with c3:
                        vwind = st.checkbox("Wind", value=meteo_vars['wind'])
                        vrad = st.checkbox("Radiation", value=meteo_vars['radiation'])
        
        st.markdown("---")

        # Options avancées
        with st.expander("Advanced API Parameters"):
            c_to, c_rl1 = st.columns(2)
            timeout = c_to.number_input("Timeout (s)", value=config['timeout'], min_value=5)
            rl_h = c_rl1.number_input("Hub'Eau Rate Limit (s)", value=config['rate_limit_hubeau'], min_value=0.1)
            st.info("ℹ️ ERA5 has no restrictive rate limit. Downloads may take several minutes depending on request size.")

        st.markdown("---")
        submitted = st.form_submit_button("🚀 Launch Construction", type="primary", use_container_width=True)
        
        if submitted:
            # Validation
            if d_start >= d_end:
                st.error("Start date must be before end date.")
                return

            # Validation credentials si météo incluse
            if inc_meteo:
                if era5_source_preview == "Download from Copernicus API" and not copernicus_api_token:
                    st.error("❌ You must provide your Copernicus API token to use ERA5 weather data.")
                    return
                elif era5_source_preview == "Use local NetCDF file" and not era5_file_preview:
                    st.error("❌ You must provide an ERA5 NetCDF file to use local weather data.")
                    return

            # Mise à jour du state
            AppState.update_config('date_start', d_start)
            AppState.update_config('date_end', d_end)
            AppState.update_config('include_stations', inc_stations)
            AppState.update_config('include_chroniques', inc_chroniques)
            AppState.update_config('include_meteo', inc_meteo)
            AppState.update_config('era5_source', era5_source_preview)
            AppState.update_config('copernicus_api_token', copernicus_api_token)
            AppState.update_config('era5_local_file', era5_file_preview)
            AppState.update_config('timeout', timeout)
            AppState.update_config('rate_limit_hubeau', rl_h)
            
            # Update meteo vars
            if inc_meteo:
                new_vars = {
                    'precip': vp, 'temp': vt, 'et': vet,
                    'humidity': vhum, 'wind': vwind, 'radiation': vrad
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
    st.header("3️⃣ Building in progress...")
    
    config = AppState.get('config')
    codes = AppState.get('codes_bss')
    
    # Préparer la liste des variables météo
    meteo_vars_list = []
    mvars = config['meteo_vars']
    mapping = {
        'precip': 'precipitation', 'temp': 'temperature', 'et': 'evapotranspiration',
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
    with st.expander("📋 Real-time Logs", expanded=True):
        log_area = st.empty()

    logs = []

    def progress_callback(pct, msg):
        progress_bar.progress(pct / 100)
        status_text.markdown(f"**{msg}**")
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        # Affiche tous les logs (limité aux 20 derniers pour la performance)
        log_area.code("\n".join(logs[-20:]), language="log")
        
    try:
        # Gestion du fichier ERA5 local si utilisé
        era5_local_path = None
        if config.get('era5_source') == "Use local NetCDF file" and config.get('era5_local_file'):
            import tempfile
            import os
            # Sauvegarder le fichier uploadé dans un fichier temporaire
            era5_uploaded_file = config['era5_local_file']
            temp_fd, era5_local_path = tempfile.mkstemp(suffix=".nc")
            try:
                os.write(temp_fd, era5_uploaded_file.read())
            finally:
                os.close(temp_fd)
            logger.info(f"Saved uploaded ERA5 file to temporary path: {era5_local_path}")

        builder = DatasetBuilder(
            timeout=config['timeout'],
            rate_limit_hubeau=config['rate_limit_hubeau'],
            copernicus_api_token=config.get('copernicus_api_token'),
            era5_local_file=era5_local_path
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
            progress_callback=progress_callback
        )

        # Nettoyer le fichier temporaire
        if era5_local_path and os.path.exists(era5_local_path):
            os.remove(era5_local_path)
            logger.info(f"Cleaned up temporary ERA5 file: {era5_local_path}")

        AppState.set('df_result', df)
        AppState.set('build_logs', logs)
        AppState.set_step(AppState.STEP_RESULT)

    except Exception as e:
        st.error(f"❌ An error occurred: {str(e)}")
        st.exception(e)

        # Try to salvage partial data if available
        partial_df = getattr(builder, '_partial_dataset', None)

        if partial_df is not None and not partial_df.empty:
            st.warning(f"⚠️ Processing failed, but **{len(partial_df)} rows of partial data** were recovered.")
            st.info("""
            💡 Partial data contains information collected before the error:
            - Piezometric stations
            - Groundwater level time series (if available)
            - Partial weather data (up to the chunk that failed)
            """)

            with st.expander("📋 Partial Data Preview", expanded=True):
                st.dataframe(partial_df.head(100))
                st.caption(f"Total: {len(partial_df)} lignes × {len(partial_df.columns)} colonnes")

                if 'code_bss' in partial_df.columns:
                    nb_stations = partial_df['code_bss'].nunique()
                    st.caption(f"Stations: {nb_stations}")

            st.markdown("---")
            st.subheader("💾 Download Partial Data")

            filename = f"dataset_piezo_partial_{datetime.now().strftime('%Y%m%d_%H%M')}"

            col1, col2, col3 = st.columns(3)

            with col1:
                from piezo_dataset_builder.utils.export import to_csv
                st.download_button(
                    "📥 Download CSV",
                    data=to_csv(partial_df),
                    file_name=f"{filename}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )

            with col2:
                from piezo_dataset_builder.utils.export import to_excel
                st.download_button(
                    "📥 Download Excel",
                    data=to_excel(partial_df),
                    file_name=f"{filename}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            with col3:
                from piezo_dataset_builder.utils.export import to_json
                st.download_button(
                    "📥 Download JSON",
                    data=to_json(partial_df),
                    file_name=f"{filename}.json",
                    mime="application/json",
                    use_container_width=True
                )

        st.markdown("---")
        if st.button("Back to Configuration"):
            AppState.set_step(AppState.STEP_CONFIG)

def render_step_4_result():
    st.header("4️⃣ Result")

    df = AppState.get('df_result')
    build_logs = AppState.get('build_logs')

    if df is None or df.empty:
        st.warning("The generated dataset is empty.")
        if st.button("Start Over"):
            AppState.set_step(AppState.STEP_CONFIG)
        return

    st.markdown(f"""
    <div class="success-box">
        ✅ Dataset generated successfully! ({len(df)} rows, {len(df.columns)} columns)
    </div>
    """, unsafe_allow_html=True)

    # Afficher les logs de construction
    if build_logs:
        with st.expander("📋 Build Logs", expanded=False):
            st.code("\n".join(build_logs), language="log")

    # Onglets
    tab1, tab2, tab3 = st.tabs(["📋 Preview", "📊 Statistics", "💾 Export"])
    
    with tab1:
        st.dataframe(df.head(100), use_container_width=True)
        
    with tab2:
        stats = get_export_stats(df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", stats['nb_lignes'])
        c2.metric("Columns", stats['nb_colonnes'])
        c3.metric("Stations", stats.get('nb_stations', 'N/A'))
        c4.metric("Est. Size", f"{stats['taille_mo']:.2f} MB")
        
        if 'taux_na' in stats:
            st.caption(f"Global missing values rate: {stats['taux_na']:.1f}%")
            
    with tab3:
        st.subheader("Download")
        filename = f"dataset_piezo_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.download_button(
                "📥 Download CSV",
                data=to_csv(df),
                file_name=f"{filename}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with c2:
            st.download_button(
                "📥 Download Excel",
                data=to_excel(df),
                file_name=f"{filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        with c3:
            st.download_button(
                "📥 Download JSON",
                data=to_json(df),
                file_name=f"{filename}.json",
                mime="application/json",
                use_container_width=True
            )

        st.divider()
        st.subheader("Archive by Station")
        st.caption("Download a ZIP archive containing one file per station")

        c4, c5 = st.columns(2)

        with c4:
            st.download_button(
                "📦 Archive ZIP (CSV)",
                data=to_zip_by_station(df, 'csv'),
                file_name=f"{filename}_par_station.zip",
                mime="application/zip",
                use_container_width=True
            )

        with c5:
            st.download_button(
                "📦 Archive ZIP (Excel)",
                data=to_zip_by_station(df, 'excel'),
                file_name=f"{filename}_par_station.zip",
                mime="application/zip",
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

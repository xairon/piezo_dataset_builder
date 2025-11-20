"""
Construction du dataset complet depuis les codes de stations piézométriques.

Données intégrées:
- Hub'Eau Piézométrie: attributs stations + niveaux de nappe
- ERA5 (Copernicus): données météorologiques réanalysées depuis 1940
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
import logging

from ..api.hubeau import HubEauClient
from ..api.era5 import ERA5Client

logger = logging.getLogger(__name__)


class DatasetBuilder:
    """Construit un dataset complet depuis une liste de codes BSS (stations piézométriques)."""

    # Limites raisonnables pour éviter les requêtes excessives
    MAX_STATIONS = 500
    MAX_DAYS = 730  # 2 ans

    def __init__(
        self,
        timeout: int = 30,
        rate_limit_hubeau: float = 0.3,
        copernicus_api_token: str = None
    ):
        """
        Initialise le builder pour piézométrie.

        Args:
            timeout: Timeout pour les requêtes HTTP (secondes)
            rate_limit_hubeau: Rate limit pour Hub'Eau (secondes entre requêtes)
            copernicus_api_token: Token API du compte Copernicus CDS (pour ERA5)
        """
        self.hubeau_client = HubEauClient(
            timeout=timeout,
            rate_limit=rate_limit_hubeau
        )
        self.meteo_client = ERA5Client(api_token=copernicus_api_token)

        logger.info(
            f"Initialized DatasetBuilder for Piezometry "
            f"(timeout={timeout}s, hubeau_rate={rate_limit_hubeau}s, "
            f"weather_source=ERA5)"
        )

    def build_dataset(
        self,
        codes_bss: List[str],
        date_start: datetime,
        date_end: datetime,
        include_stations: bool = True,
        include_chroniques: bool = True,
        include_meteo: bool = True,
        meteo_variables: List[str] = None,
        station_fields: List[str] = None,
        chronique_fields: List[str] = None,
        daily_aggregation: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> pd.DataFrame:
        """
        Construit le dataset complet pour stations piézométriques.

        Args:
            codes_bss: Liste des codes BSS (ex: ["07548X0009/F", "BSS000AUZM"])
            date_start: Date début
            date_end: Date fin
            include_stations: Inclure attributs stations (coordonnées GPS, commune, etc.)
            include_chroniques: Inclure chroniques de niveaux de nappe
            include_meteo: Inclure données météo (température air, précipitations, etc.)
            meteo_variables: Variables météo à récupérer (default: precipitation, temperature, evapotranspiration)
            station_fields: Liste des attributs stations à conserver (None = tous)
            chronique_fields: Liste des attributs chroniques à conserver (None = tous)
            daily_aggregation: Agréger les données au niveau journalier
            progress_callback: Optional callback(progress_pct, message) for progress updates

        Returns:
            DataFrame complet avec toutes les données

        Raises:
            ValueError: Si les inputs sont invalides
        """
        # Validation des inputs
        self._validate_inputs(codes_bss, date_start, date_end)

        logger.info(
            f"Building piezometry dataset for {len(codes_bss)} stations "
            f"from {date_start.date()} to {date_end.date()}"
        )

        def update_progress(pct: int, msg: str):
            """Helper pour update progress."""
            if progress_callback:
                progress_callback(pct, msg)
            logger.info(f"[{pct}%] {msg}")

        update_progress(0, f"Starting dataset build for {len(codes_bss)} piezometric stations")

        # 1. Récupérer attributs stations piézométriques
        # Nécessaire si demandé explicitement OU pour les coordonnées Météo
        need_stations = include_stations or include_meteo
        
        if need_stations:
            update_progress(10, "Fetching piezometric station attributes...")
            df_stations = self._get_stations_data(codes_bss)
            
            # Filtrage des colonnes stations
            if not df_stations.empty:
                cols_to_keep = {'code_bss'}
                
                # Si météo demandée, il faut garder les coordonnées pour la requête météo
                # (on pourra les supprimer à la fin si non demandées dans l'export, mais ici on en a besoin)
                if include_meteo:
                    cols_to_keep.update({'latitude', 'longitude'})
                
                # Si l'utilisateur veut les infos stations
                if include_stations:
                    if station_fields:
                        cols_to_keep.update(station_fields)
                    else:
                        # Si pas de filtre spécifique, on garde toutes les colonnes reçues
                        cols_to_keep.update(df_stations.columns)
                
                # Intersection avec les colonnes existantes pour ne pas planter
                actual_cols = [c for c in df_stations.columns if c in cols_to_keep]
                df_stations = df_stations[actual_cols]
                
            update_progress(20, f"Retrieved {len(df_stations)} piezometric stations")
        else:
            df_stations = pd.DataFrame({'code_bss': codes_bss})
            update_progress(20, "Skipping station attributes")

        if df_stations.empty:
            logger.error("No piezometric stations found in Hub'Eau")
            return pd.DataFrame()

        # 2. Récupérer chroniques de niveaux de nappe
        if include_chroniques:
            update_progress(30, "Fetching groundwater level chroniques...")
            df_chroniques = self._get_chroniques_data(
                codes_bss,
                date_start,
                date_end
            )
            
            # Filtrage des colonnes chroniques
            if not df_chroniques.empty and chronique_fields:
                # Toujours garder code_bss et date
                cols_to_keep = {'code_bss', 'date'}

                # Mapping: noms utilisateur → noms réels API Hub'Eau
                chronique_field_mapping = {
                    'niveau_nappe_ngf': 'niveau_nappe_eau',  # UI name → API name
                    'profondeur_nappe': 'profondeur_nappe',
                    'qualification': 'qualification',
                    'mode_obtention': 'mode_obtention',
                    'statut': 'statut'
                }

                # Ajouter les noms réels API correspondant aux champs demandés
                for user_field in chronique_fields:
                    real_field = chronique_field_mapping.get(user_field, user_field)
                    if real_field in df_chroniques.columns:
                        cols_to_keep.add(real_field)

                actual_cols = [c for c in df_chroniques.columns if c in cols_to_keep]
                df_chroniques = df_chroniques[actual_cols]

                # Renommer les colonnes selon le mapping inverse pour l'export
                inverse_mapping = {v: k for k, v in chronique_field_mapping.items() if v in df_chroniques.columns}
                df_chroniques = df_chroniques.rename(columns=inverse_mapping)
            
            update_progress(50, f"Retrieved {len(df_chroniques)} groundwater level records")

            if not df_chroniques.empty:
                # Merger avec stations
                df_base = df_chroniques.merge(
                    df_stations,
                    on='code_bss',
                    how='left',
                    suffixes=('', '_station')
                )
                logger.info(f"Merged chroniques with stations: {len(df_base)} rows")
            else:
                # Pas de chroniques, créer grille date x station
                logger.warning("No chroniques found, creating date×station grid")
                update_progress(50, "No chroniques found, creating date grid...")
                df_base = self._create_date_station_grid(
                    df_stations,
                    date_start,
                    date_end
                )
        else:
            # Créer grille sans chroniques
            update_progress(30, "Creating date×station grid...")
            df_base = self._create_date_station_grid(
                df_stations,
                date_start,
                date_end
            )
            update_progress(50, f"Created grid: {len(df_base)} rows")

        # 3. Ajouter données météo (température AIR, précipitations, etc.)
        if include_meteo and 'latitude' in df_base.columns:
            update_progress(60, "Fetching weather data (air temperature, precipitation, etc.)...")
            df_base = self._add_meteo_data(
                df_base,
                date_start,
                date_end,
                meteo_variables or ['precipitation', 'temperature', 'evapotranspiration']
            )
            update_progress(80, "Weather data added")
        else:
            if include_meteo and 'latitude' not in df_base.columns:
                logger.warning("Cannot add weather data: no GPS coordinates available")
            update_progress(80, "Skipping weather data")

        # 4. Agrégation journalière si demandée
        if daily_aggregation and not df_base.empty:
            update_progress(85, "Performing daily aggregation...")
            df_base = self._aggregate_daily(df_base)

        # Tri final
        if not df_base.empty and 'date' in df_base.columns:
            df_base = df_base.sort_values(['code_bss', 'date'])

        # 5. Nettoyage final : Supprimer UNIQUEMENT les colonnes qui n'ont pas été demandées
        # Attention : df_base a déjà été filtré lors des étapes précédentes (df_stations, df_chroniques)
        # MAIS le merge de la grille temporelle ou de la météo a pu réintroduire des colonnes (latitude, longitude...)
        
        # On reconstruit la liste de ce qu'on veut vraiment garder à la fin
        desired_columns = {'code_bss', 'date'} # Toujours garder les clés
        
        # 1. Champs stations demandés
        if include_stations and station_fields:
            desired_columns.update(station_fields)
        elif include_stations:
            # Si pas de filtre spécifié, on garde toutes les colonnes initiales de df_stations (avant merge)
            # C'est complexe à retrouver ici.
            # Pour l'instant, on fait confiance au filtre appliqué à l'étape 1
            # Si station_fields est None, on garde tout ce qui est là.
            pass

        # 2. Champs chroniques demandés
        if include_chroniques and chronique_fields:
             desired_columns.update(chronique_fields)
        
        # 3. Champs météo demandés
        if include_meteo and meteo_variables:
             desired_columns.update(meteo_variables)
             
        # Si on a défini des filtres explicites, on nettoie le DF final
        if (station_fields or chronique_fields or meteo_variables):
            # On ne garde que les colonnes présentes qui sont dans desired_columns
            # SAUF si on est en mode "include_stations=True" sans "station_fields" (on garde tout)
            
            # Logique "safe" : On supprime ce qu'on sait être en trop
            # Cas typique : latitude/longitude récupérés pour la météo mais pas cochés par l'user
            
            cols_to_drop = []
            
            # Gestion spécifique lat/lon
            if include_meteo and (not include_stations or (include_stations and station_fields and 'latitude' not in station_fields)):
                 if 'latitude' in df_base.columns: cols_to_drop.append('latitude')
                 if 'longitude' in df_base.columns: cols_to_drop.append('longitude')

            if cols_to_drop:
                logger.info(f"Dropping technical columns not requested: {cols_to_drop}")
                df_base = df_base.drop(columns=cols_to_drop)

        update_progress(100, f"Dataset complete: {len(df_base)} rows × {len(df_base.columns)} columns")

        logger.info(
            f"Piezometric dataset build complete: {len(df_base)} rows, "
            f"{len(df_base.columns)} columns"
        )

        return df_base

    def _validate_inputs(
        self,
        codes_bss: List[str],
        date_start: datetime,
        date_end: datetime
    ):
        """
        Validate input parameters.

        Args:
            codes_bss: BSS station codes list
            date_start: Start date
            date_end: End date

        Raises:
            ValueError: If inputs are invalid
        """
        if not codes_bss:
            raise ValueError("codes_bss cannot be empty")

        if len(codes_bss) > self.MAX_STATIONS:
            raise ValueError(
                f"Too many stations: {len(codes_bss)} (max: {self.MAX_STATIONS}). "
                "Please split into smaller batches to avoid API overload."
            )

        if date_start >= date_end:
            raise ValueError(
                f"date_start ({date_start.date()}) must be before "
                f"date_end ({date_end.date()})"
            )

        # Note: ERA5 n'a pas de limites strictes, mais on garde un warning pour info
        days_diff = (date_end - date_start).days
        if days_diff > 36500:  # ~100 ans
            logger.warning(
                f"Very large date range requested: {days_diff} days "
                f"({days_diff/365:.1f} years). "
                "ERA5 CDS download may take significant time."
            )

        logger.debug(f"Input validation passed: {len(codes_bss)} stations, {days_diff} days")

    def _get_stations_data(self, codes_bss: List[str]) -> pd.DataFrame:
        """Récupère attributs stations piézométriques depuis Hub'Eau."""
        df = self.hubeau_client.get_stations(codes_bss)

        if df.empty:
            return pd.DataFrame()

        # S'assurer que code_bss existe
        if 'code_bss' not in df.columns:
            logger.error("No 'code_bss' column in station data")
            return pd.DataFrame()

        # Nettoyer coordonnées GPS
        if 'latitude' in df.columns:
            df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        if 'longitude' in df.columns:
            df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

        return df

    def _get_chroniques_data(
        self,
        codes_bss: List[str],
        date_start: datetime,
        date_end: datetime
    ) -> pd.DataFrame:
        """Récupère chroniques de niveaux de nappe depuis Hub'Eau."""
        df = self.hubeau_client.get_chroniques_batch(codes_bss, date_start, date_end)

        if df.empty:
            return pd.DataFrame()

        # S'assurer qu'il y a une colonne date
        if 'date' not in df.columns:
            # Chercher colonne date
            date_cols = [col for col in df.columns if 'date' in col.lower()]
            if date_cols:
                # Prendre première colonne date et convertir
                df['date'] = pd.to_datetime(df[date_cols[0]], errors='coerce').dt.date
                logger.debug(f"Created unified 'date' column from '{date_cols[0]}'")

        return df

    def _create_date_station_grid(
        self,
        df_stations: pd.DataFrame,
        date_start: datetime,
        date_end: datetime
    ) -> pd.DataFrame:
        """
        Crée une grille date × station de manière optimisée.
        Utile pour avoir données météo même sans mesures de nappe.

        Optimisation: Utilise MultiIndex.from_product au lieu de boucles imbriquées.
        """
        logger.debug("Creating optimized date×station grid")

        # Générer range de dates
        dates = pd.date_range(date_start, date_end, freq='D').date

        # Extraire codes BSS uniques
        df_stations_unique = df_stations.drop_duplicates(subset=['code_bss'])
        codes_bss = df_stations_unique['code_bss'].values

        # Créer produit cartésien avec MultiIndex (beaucoup plus rapide)
        index = pd.MultiIndex.from_product(
            [codes_bss, dates],
            names=['code_bss', 'date']
        )

        # Créer DataFrame à partir du MultiIndex
        df_grid = pd.DataFrame(index=index).reset_index()

        # Joindre avec les attributs stations
        df_grid = df_grid.merge(df_stations, on='code_bss', how='left')

        logger.info(
            f"Created grid: {len(codes_bss)} stations × {len(dates)} days "
            f"= {len(df_grid)} rows"
        )

        return df_grid

    def _add_meteo_data(
        self,
        df: pd.DataFrame,
        date_start: datetime,
        date_end: datetime,
        variables: List[str]
    ) -> pd.DataFrame:
        """Ajoute données météo ERA5 (température, précipitations, etc.) au DataFrame."""
        # Extraire stations uniques avec coordonnées
        stations_cols = ['code_bss', 'latitude', 'longitude']
        stations_cols = [c for c in stations_cols if c in df.columns]

        if 'latitude' not in stations_cols or 'longitude' not in stations_cols:
            logger.warning("GPS coordinates missing, cannot add weather data")
            return df

        stations_unique = df[stations_cols].drop_duplicates()

        # Filtrer stations avec coordonnées valides
        stations_valid = stations_unique[
            stations_unique['latitude'].notna() &
            stations_unique['longitude'].notna()
        ]

        if stations_valid.empty:
            logger.warning("No stations with valid GPS coordinates")
            return df

        logger.info(
            f"Adding weather data for {len(stations_valid)} stations "
            f"with valid coordinates"
        )

        # Préparer locations pour batch
        locations = []
        for _, row in stations_valid.iterrows():
            locations.append({
                'code_station': row['code_bss'],  # Pour meteo client
                'latitude': row['latitude'],
                'longitude': row['longitude']
            })

        # Requête batch météo
        df_meteo = self.meteo_client.get_weather_batch(
            locations,
            date_start,
            date_end,
            variables
        )

        if df_meteo.empty:
            logger.warning("No weather data retrieved")
            return df

        # Renommer code_station → code_bss pour le merge
        if 'code_station' in df_meteo.columns:
            df_meteo = df_meteo.rename(columns={'code_station': 'code_bss'})

        # Joindre avec données principales
        merge_cols = ['code_bss', 'date']

        # S'assurer que les types correspondent
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
        if 'date' in df_meteo.columns:
            df_meteo['date'] = pd.to_datetime(df_meteo['date'], errors='coerce').dt.date

        # Merge en évitant les doublons de latitude/longitude
        df = df.merge(
            df_meteo.drop(columns=['latitude', 'longitude'], errors='ignore'),
            on=merge_cols,
            how='left'
        )

        logger.info(f"Weather data merged: {len(df)} rows")

        return df

    def _aggregate_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Agrège les données au niveau journalier.
        Moyenne pour valeurs numériques, première valeur pour le reste.
        """
        if 'date' not in df.columns:
            logger.warning("No 'date' column found, skipping aggregation")
            return df

        # Colonnes de groupement
        group_cols = ['code_bss', 'date']

        # Ajouter colonnes non-numériques importantes (si elles existent)
        for col in ['latitude', 'longitude', 'nom_commune', 'libelle_commune']:
            if col in df.columns and col not in group_cols:
                group_cols.append(col)

        # Colonnes numériques à moyenner
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        numeric_cols = [c for c in numeric_cols if c not in group_cols]

        if not numeric_cols:
            # Pas de colonnes numériques à agréger, juste dédupliquer
            logger.debug("No numeric columns to aggregate, deduplicating")
            return df.drop_duplicates(subset=group_cols)

        # Agrégation
        agg_dict = {col: 'mean' for col in numeric_cols}

        # Garder première valeur pour colonnes texte
        text_cols = df.select_dtypes(include=['object']).columns.tolist()
        text_cols = [c for c in text_cols if c not in group_cols]
        for col in text_cols:
            agg_dict[col] = 'first'

        logger.debug(
            f"Aggregating {len(numeric_cols)} numeric columns "
            f"and {len(text_cols)} text columns"
        )

        df_agg = df.groupby(group_cols, as_index=False).agg(agg_dict)

        logger.info(
            f"Daily aggregation complete: {len(df)} rows -> {len(df_agg)} rows "
            f"({len(df) - len(df_agg)} duplicates removed)"
        )

        return df_agg

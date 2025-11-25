"""
Client API Hub'Eau - Piézométrie (niveaux nappes phréatiques).

Documentation : https://hubeau.eaufrance.fr/page/api-piezometrie

Features:
- Automatic retry logic with exponential backoff
- Rate limiting to respect API limits
- Comprehensive logging
- Thread-safe operations
- Proper error handling
"""

import requests
import pandas as pd
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import time
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ==============================================================================
# GLOBAL THREAD-SAFE RATE LIMITER
# ==============================================================================

class GlobalRateLimiter:
    """
    Thread-safe rate limiter to prevent API bombardment.
    Ensures we don't exceed Hub'Eau API rate limits.
    """
    _lock = threading.Lock()
    _last_request_time = 0.0

    @classmethod
    def wait(cls, rate_limit: float):
        """
        Thread-safe rate limiting.

        Args:
            rate_limit: Minimum seconds between requests
        """
        with cls._lock:
            elapsed = time.time() - cls._last_request_time
            if elapsed < rate_limit:
                sleep_time = rate_limit - elapsed
                time.sleep(sleep_time)
            cls._last_request_time = time.time()


# ==============================================================================
# CLIENT
# ==============================================================================

class HubEauClient:
    """
    Client pour l'API Hub'Eau Piézométrie avec retry logic et rate limiting.

    API Endpoint: https://hubeau.eaufrance.fr/api/v1/niveaux_nappes
    """

    BASE_URL = 'https://hubeau.eaufrance.fr/api/v1/niveaux_nappes'
    STATIONS_ENDPOINT = '/stations'
    CHRONIQUES_ENDPOINT = '/chroniques'

    def __init__(self, timeout: int = 30, rate_limit: float = 0.1):
        """
        Initialise le client Hub'Eau Piézométrie.

        Args:
            timeout: Timeout requêtes HTTP en secondes
            rate_limit: Délai minimum entre requêtes (secondes)
        """
        self.base_url = self.BASE_URL
        self.timeout = timeout
        self.rate_limit = rate_limit

        # Setup session with connection pooling and retry logic
        self.session = requests.Session()

        # Retry strategy: exponential backoff
        retry_strategy = Retry(
            total=5,  # Max 5 retries
            backoff_factor=2,  # 2^x seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP codes to retry
            allowed_methods=["GET"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info(
            f"Initialized HubEauClient for Piezometry "
            f"(timeout={timeout}s, rate_limit={rate_limit}s)"
        )

    def _make_request(
        self,
        url: str,
        params: Dict[str, Any],
        context: str = ""
    ) -> Optional[requests.Response]:
        """
        Make HTTP GET request with rate limiting and error handling.

        Args:
            url: URL to request
            params: Query parameters
            context: Context string for logging

        Returns:
            Response object or None if error
        """
        # Apply rate limiting
        GlobalRateLimiter.wait(self.rate_limit)

        try:
            logger.debug(f"{context} - Requesting: {url} with params: {params}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response

        except requests.exceptions.Timeout as e:
            logger.error(f"{context} - Timeout after {self.timeout}s: {e}")
            return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"{context} - Rate limit exceeded (HTTP 429), backing off...")
            else:
                logger.error(f"{context} - HTTP error {e.response.status_code}: {e}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"{context} - Request error: {e}")
            return None

    def get_stations(self, codes_bss: List[str]) -> pd.DataFrame:
        """
        Récupère les attributs des stations piézométriques.

        Args:
            codes_bss: Liste des codes BSS (ex: "07548X0009/F")

        Returns:
            DataFrame avec attributs stations (code_bss, latitude, longitude, commune, etc.)
        """
        if not codes_bss:
            logger.warning("get_stations called with empty codes_bss list")
            return pd.DataFrame()

        logger.info(f"Fetching piezometric station data for {len(codes_bss)} stations")

        url = self.base_url + self.STATIONS_ENDPOINT

        # Hub'Eau accepte max ~50 codes par requête
        batch_size = 50
        all_data = []

        num_batches = (len(codes_bss) + batch_size - 1) // batch_size

        for i in range(0, len(codes_bss), batch_size):
            batch = codes_bss[i:i+batch_size]
            batch_num = i // batch_size + 1

            params = {
                'code_bss': ','.join(batch),
                'size': 1000,
                'format': 'json'
            }

            response = self._make_request(
                url,
                params,
                context=f"Stations Batch {batch_num}/{num_batches}"
            )

            if not response:
                logger.warning(f"Batch {batch_num}/{num_batches} failed, skipping")
                continue

            try:
                data = response.json()

                # Extraction données selon structure API
                if 'data' in data:
                    all_data.extend(data['data'])
                    logger.debug(f"Batch {batch_num}: Got {len(data['data'])} stations")
                else:
                    logger.warning(f"Batch {batch_num}: No 'data' field in response")

            except (ValueError, KeyError) as e:
                logger.error(f"Batch {batch_num}: Error parsing response: {e}")
                continue

        if not all_data:
            logger.warning("No station data retrieved from API")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        logger.info(f"Successfully retrieved {len(df)} station records")

        # Normaliser colonne code_bss si nécessaire
        if 'code_bss' not in df.columns:
            logger.error("No 'code_bss' column found in response")
            return pd.DataFrame()

        # Extraire coordonnées GPS depuis geometry ou x/y
        # L'API Hub'Eau retourne 'x' (longitude) et 'y' (latitude) en WGS84
        # ET un champ 'geometry' avec les coordonnées
        if 'geometry' in df.columns:
            # Extraire depuis geometry (plus fiable)
            def extract_coords(geom):
                """Extract lat/lon from geometry object."""
                if isinstance(geom, dict) and 'coordinates' in geom:
                    coords = geom['coordinates']
                    if isinstance(coords, list) and len(coords) >= 2:
                        return pd.Series({'longitude': coords[0], 'latitude': coords[1]})
                return pd.Series({'longitude': None, 'latitude': None})

            coords_df = df['geometry'].apply(extract_coords)
            df['longitude'] = pd.to_numeric(coords_df['longitude'], errors='coerce')
            df['latitude'] = pd.to_numeric(coords_df['latitude'], errors='coerce')
            logger.debug("Extracted GPS coordinates from geometry field")

        elif 'x' in df.columns and 'y' in df.columns:
            # Fallback: utiliser x (longitude) et y (latitude)
            df['longitude'] = pd.to_numeric(df['x'], errors='coerce')
            df['latitude'] = pd.to_numeric(df['y'], errors='coerce')
            logger.debug("Extracted GPS coordinates from x/y fields")

        else:
            logger.warning("No GPS coordinate fields (geometry, x/y) found in station data")

        return df

    def get_chroniques(
        self,
        code_bss: str,
        date_debut: datetime,
        date_fin: datetime
    ) -> pd.DataFrame:
        """
        Récupère les chroniques de niveaux de nappe pour une station.

        Args:
            code_bss: Code BSS de la station (ex: "07548X0009/F")
            date_debut: Date de début
            date_fin: Date de fin

        Returns:
            DataFrame avec chroniques (date_mesure, niveau_nappe_ngf, profondeur_nappe, etc.)
        """
        logger.debug(
            f"Fetching chroniques for station {code_bss} "
            f"from {date_debut.date()} to {date_fin.date()}"
        )

        url = self.base_url + self.CHRONIQUES_ENDPOINT

        params = {
            'code_bss': code_bss,
            'size': 20000,
            'date_debut_mesure': date_debut.strftime("%Y-%m-%d"),
            'date_fin_mesure': date_fin.strftime("%Y-%m-%d")
        }

        response = self._make_request(
            url,
            params,
            context=f"Chroniques for {code_bss}"
        )

        if not response:
            return pd.DataFrame()

        try:
            data = response.json()

            if 'data' in data:
                df = pd.DataFrame(data['data'])
                logger.debug(f"Station {code_bss}: Got {len(df)} measurement records")
            else:
                logger.warning(f"Station {code_bss}: No 'data' field in response")
                df = pd.DataFrame()

            if not df.empty:
                # Normaliser colonnes dates
                if 'date_mesure' in df.columns:
                    df['date_mesure'] = pd.to_datetime(df['date_mesure'], errors='coerce')
                    # Créer colonne date unifiée (sans heure)
                    df['date'] = df['date_mesure'].dt.date

                # Normaliser colonne code
                df['code_bss'] = code_bss

            return df

        except (ValueError, KeyError) as e:
            logger.error(f"Station {code_bss}: Error parsing response: {e}")
            return pd.DataFrame()

    def get_chroniques_batch(
        self,
        codes_bss: List[str],
        date_debut: datetime,
        date_fin: datetime
    ) -> pd.DataFrame:
        """
        Récupère les chroniques pour plusieurs stations piézométriques.

        IMPORTANT: Fait des requêtes station par station (pas de batch)
        pour éviter les problèmes de pagination avec URLs trop longues.
        La pagination Hub'Eau avec plusieurs codes_bss crée des liens 'next'
        avec URLs dépassant la limite HTTP → erreur 400.

        Args:
            codes_bss: Liste des codes BSS
            date_debut: Date de début
            date_fin: Date de fin

        Returns:
            DataFrame concatené avec toutes les chroniques
        """
        if not codes_bss:
            logger.warning("get_chroniques_batch called with empty codes_bss list")
            return pd.DataFrame()

        logger.info(
            f"Fetching chroniques for {len(codes_bss)} stations "
            f"from {date_debut.date()} to {date_fin.date()} (station by station with pagination)"
        )

        all_data = []
        url = self.base_url + self.CHRONIQUES_ENDPOINT

        # IMPORTANT: On itère station par station au lieu de batcher
        # Raison: La pagination avec multiple codes crée des URLs trop longues (HTTP 400)
        for idx, code_bss in enumerate(codes_bss, 1):
            # Pagination pour cette station
            current_url = url
            page_count = 0
            station_records = []

            params = {
                'code_bss': code_bss,  # UN SEUL code à la fois !
                'size': 20000,  # Max par page
                'date_debut_mesure': date_debut.strftime("%Y-%m-%d"),
                'date_fin_mesure': date_fin.strftime("%Y-%m-%d")
            }

            while current_url:
                page_count += 1
                context_str = f"Station {idx}/{len(codes_bss)} ({code_bss}) - Page {page_count}"

                # Pour page 1: utiliser url + params
                # Pour page > 1: utiliser current_url (lien 'next') sans params
                request_params = params if page_count == 1 else None

                response = self._make_request(
                    current_url,
                    request_params,
                    context=context_str
                )

                if not response:
                    logger.warning(f"{context_str} failed, stopping pagination for this station")
                    break

                try:
                    data = response.json()

                    # Récupérer les données
                    if 'data' in data and data['data']:
                        df = pd.DataFrame(data['data'])

                        # Normaliser colonnes dates
                        if 'date_mesure' in df.columns:
                            df['date_mesure'] = pd.to_datetime(df['date_mesure'], errors='coerce')
                            df['date'] = df['date_mesure'].dt.date

                        station_records.append(df)
                        logger.debug(f"{context_str}: Got {len(df)} records")
                    else:
                        # Pas de données, fin de pagination ou période vide
                        logger.debug(f"{context_str}: No data returned")
                        break

                    # Gérer la pagination via le lien 'next'
                    if 'next' in data and data['next']:
                        current_url = data['next']
                    else:
                        current_url = None

                except (ValueError, KeyError) as e:
                    logger.error(f"{context_str}: Error parsing response: {e}")
                    break

            # Concat les données de cette station
            if station_records:
                station_df = pd.concat(station_records, ignore_index=True)
                all_data.append(station_df)
                logger.debug(f"Station {code_bss}: Total {len(station_df)} records across {page_count} page(s)")
            else:
                logger.debug(f"Station {code_bss}: No chroniques found")

        if not all_data:
            logger.warning("No chroniques data retrieved for any station")
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)

        # Supprimer les doublons potentiels (sécurité)
        if not result.empty and 'code_bss' in result.columns and 'date_mesure' in result.columns:
            before_dedup = len(result)
            result = result.drop_duplicates(subset=['code_bss', 'date_mesure'])
            if before_dedup != len(result):
                logger.debug(f"Deduplicated {before_dedup - len(result)} records")

        logger.info(
            f"Successfully retrieved chroniques: {len(result)} total records "
            f"from {result['code_bss'].nunique()}/{len(codes_bss)} stations"
        )

        return result

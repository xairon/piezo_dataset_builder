"""
Validation et extraction des codes stations piézométriques (BSS).
"""

import pandas as pd
from typing import List, Tuple
import logging
import re
from ..api.hubeau import HubEauClient

logger = logging.getLogger(__name__)


def clean_bss_code(code: str) -> str:
    """
    Nettoie et normalise un code BSS.
    Tente d'extraire un code BSS valide s'il est noyé dans d'autres caractères.
    """
    if not code:
        return ""
        
    # Patterns BSS
    # 1. Nouveau format : BSS000ABCD (10 chars, commence par BSS)
    pattern_new = r'(BSS[0-9A-Z]{7})'
    # 2. Ancien format : 01234X0001/F (10 chars racine + optionnel /S, /F, /P...)
    #    On accepte 4 ou 5 chiffres au début (parfois le 0 initial saute), lettre X/Y/Z, 3 ou 4 chiffres
    pattern_old = r'(\d{4,5}[X-Z]\d{3,4}(?:\/[A-Z0-9]+)?)'
    
    # Essai pattern nouveau
    match_new = re.search(pattern_new, code)
    if match_new:
        return match_new.group(1)
        
    # Essai pattern ancien
    match_old = re.search(pattern_old, code)
    if match_old:
        # Si on a trouvé quelque chose comme 00471X0095/2013, c'est probablement valide jusqu'au slash
        # Mais le suffixe /2013 n'est pas standard pour l'API.
        # L'API attend généralement /F, /S, /P ou rien.
        base = match_old.group(1)
        
        # Si suffixe long (> 2 chars après /), c'est suspect (ex: /2013)
        if '/' in base:
            parts = base.split('/')
            if len(parts[1]) > 2: 
                # Suffixe trop long, on garde juste la racine ?
                # Hub'Eau accepte la racine souvent pour retrouver l'ouvrage
                return parts[0]
        return base
        
    # Si rien ne matche, on renvoie tel quel nettoyé des espaces
    return code.strip()


def extract_station_codes(df: pd.DataFrame) -> List[str]:
    """
    Extrait automatiquement les codes BSS (stations piézométriques) du CSV.

    Stratégie :
    1. Si une seule colonne → la prendre
    2. Si plusieurs colonnes → chercher patterns (code*, bss*, station*)
    3. Sinon → prendre première colonne

    Args:
        df: DataFrame du CSV uploadé

    Returns:
        Liste des codes BSS uniques (strings)
    """
    if df.empty:
        logger.warning("extract_station_codes called with empty DataFrame")
        return []

    logger.debug(f"Extracting BSS codes from DataFrame with {len(df.columns)} columns")

    # Cas 1 : Une seule colonne
    if len(df.columns) == 1:
        col = df.columns[0]
        logger.info(f"Single column detected: using '{col}'")
    else:
        # Cas 2 : Chercher colonne avec pattern bss/code/station
        candidates = []
        for col in df.columns:
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in ['bss', 'code', 'station', 'piezo']):
                candidates.append(col)

        # Prioriser colonnes avec 'bss' ou 'code'
        if candidates:
            logger.debug(f"Found {len(candidates)} candidate columns: {candidates}")

            # Ordre de priorité pour piézométrie
            for pattern in ['code_bss', 'bss_id', 'bss', 'code_station', 'code']:
                for cand in candidates:
                    if pattern in cand.lower():
                        col = cand
                        logger.info(f"Selected column '{col}' (matched pattern '{pattern}')")
                        break
                else:
                    continue
                break
            else:
                # Aucun pattern exact, prendre premier candidat
                col = candidates[0]
                logger.info(f"No exact pattern match, using first candidate: '{col}'")
        else:
            # Cas 3 : Prendre première colonne
            col = df.columns[0]
            logger.warning(
                f"No column with 'bss'/'code'/'station' found, "
                f"defaulting to first column: '{col}'"
            )

    # Extraire codes uniques
    codes = df[col].dropna().unique()
    logger.debug(f"Found {len(codes)} unique values in column '{col}'")

    # Convertir en strings et nettoyer
    codes_clean = []
    seen = set()
    invalid_count = 0
    
    for code in codes:
        code_str = str(code).strip()
        if code_str and code_str.lower() not in ['nan', 'none', '', 'null']:
            # Application du nettoyage intelligent
            cleaned = clean_bss_code(code_str)
            if cleaned and cleaned not in seen:
                codes_clean.append(cleaned)
                seen.add(cleaned)
        else:
            invalid_count += 1

    if invalid_count > 0:
        logger.warning(f"Filtered out {invalid_count} invalid/empty codes")

    logger.info(f"Extracted {len(codes_clean)} valid BSS codes")

    return codes_clean


def validate_station_codes(
    codes_bss: List[str],
    sample_size: int = 5
) -> Tuple[List[str], List[str]]:
    """
    Valide un échantillon de codes BSS via API Hub'Eau Piézométrie.

    Args:
        codes_bss: Liste de codes BSS à valider
        sample_size: Nombre de codes à tester (default: 5)

    Returns:
        Tuple (codes_valides, codes_invalides)
        - codes_valides: Codes BSS trouvés dans l'API
        - codes_invalides: Codes BSS non trouvés
    """
    if not codes_bss:
        logger.warning("validate_station_codes called with empty codes_bss list")
        return [], []

    # Prendre échantillon
    sample_codes = codes_bss[:min(sample_size, len(codes_bss))]
    logger.info(f"Validating {len(sample_codes)} sample BSS codes (out of {len(codes_bss)} total)")

    try:
        logger.debug("Testing codes with Hub'Eau Piezometry API")
        client = HubEauClient()
        df_stations = client.get_stations(sample_codes)

        if df_stations.empty:
            logger.error("API returned no stations - all codes may be invalid or API unreachable")
            return [], sample_codes

        # Récupérer codes trouvés
        if 'code_bss' not in df_stations.columns:
            logger.error("API response missing 'code_bss' column")
            return [], sample_codes

        # Normaliser codes trouvés (strip whitespace, convert to string)
        codes_found = [str(c).strip() for c in df_stations['code_bss'].tolist()]

        codes_valid = [c for c in sample_codes if c in codes_found]
        codes_invalid = [c for c in sample_codes if c not in codes_found]

        logger.info(
            f"Validation complete: {len(codes_valid)}/{len(sample_codes)} codes valid, "
            f"{len(codes_invalid)} invalid"
        )

        return codes_valid, codes_invalid

    except Exception as e:
        logger.error(f"Error during validation: {e}")
        return [], sample_codes

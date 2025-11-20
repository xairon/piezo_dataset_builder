"""
Test script to verify ERA5 integration.
"""
import pandas as pd
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

from src.piezo_dataset_builder.api.era5 import ERA5Client

def test_era5_single_location():
    """Test ERA5 with a single location."""
    print("Testing ERA5 single location...")

    try:
        client = ERA5Client()
        print("✓ ERA5 client initialized successfully")

        # Test with a location in France
        # Paris coordinates
        latitude = 48.8566
        longitude = 2.3522

        # Test with 1 month of data
        date_start = datetime(2023, 1, 1)
        date_end = datetime(2023, 1, 31)

        print(f"\nFetching data for Paris ({latitude}, {longitude})")
        print(f"Period: {date_start.date()} to {date_end.date()}")

        df = client.get_weather_data(
            latitude=latitude,
            longitude=longitude,
            date_debut=date_start,
            date_fin=date_end,
            variables=['precipitation', 'temperature', 'evapotranspiration']
        )

        if df.empty:
            print("✗ No data returned")
            return False

        print(f"\n✓ Retrieved {len(df)} records")
        print(f"Columns: {df.columns.tolist()}")
        print("\nFirst 5 rows:")
        print(df.head())

        # Check data quality
        print("\n--- Data Quality ---")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Missing values: {df.isnull().sum().to_dict()}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_era5_batch():
    """Test ERA5 with multiple locations (batch)."""
    print("\n" + "="*60)
    print("Testing ERA5 batch request...")

    try:
        client = ERA5Client()

        # Test with 3 locations in France
        locations = [
            {'latitude': 48.8566, 'longitude': 2.3522, 'code_station': 'PARIS'},
            {'latitude': 45.7640, 'longitude': 4.8357, 'code_station': 'LYON'},
            {'latitude': 43.2965, 'longitude': 5.3698, 'code_station': 'MARSEILLE'}
        ]

        # Test with 1 week of data
        date_start = datetime(2023, 1, 1)
        date_end = datetime(2023, 1, 7)

        print(f"\nFetching data for {len(locations)} locations")
        print(f"Period: {date_start.date()} to {date_end.date()}")

        df = client.get_weather_batch(
            locations=locations,
            date_debut=date_start,
            date_fin=date_end,
            variables=['precipitation', 'temperature', 'evapotranspiration']
        )

        if df.empty:
            print("✗ No data returned")
            return False

        print(f"\n✓ Retrieved {len(df)} records for {df['code_station'].nunique()} stations")
        print(f"Columns: {df.columns.tolist()}")
        print("\nSample data:")
        print(df.head(10))

        # Check data quality
        print("\n--- Data Quality ---")
        print(f"Stations: {df['code_station'].unique().tolist()}")
        print(f"Records per station: {df.groupby('code_station').size().to_dict()}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Missing values: {df.isnull().sum().to_dict()}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("ERA5 Integration Test")
    print("="*60)
    print("\nNOTE: This test requires:")
    print("1. A Copernicus CDS account")
    print("2. ~/.cdsapirc file configured with your API key")
    print("3. Internet connection")
    print("\nIf you see authentication errors, please set up your CDS account:")
    print("https://cds.climate.copernicus.eu/how-to-api")
    print("="*60)

    input("\nPress Enter to continue with tests...")

    # Run tests
    test1_passed = test_era5_single_location()
    test2_passed = test_era5_batch()

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Single location test: {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"Batch request test:   {'✓ PASSED' if test2_passed else '✗ FAILED'}")
    print("="*60)

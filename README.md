# Piezo Dataset Builder

Streamlit application to build complete datasets from piezometer station codes (BSS).

## 🎯 Concept

**Input**: A simple CSV with BSS codes (piezometer stations)
**Output**: A complete dataset with station attributes, groundwater levels, and meteorological data

The tool automatically queries:
- **Hub'Eau Piezometry API**: Station attributes + groundwater level time series
- **ERA5 (Copernicus)**: Historical meteorological data since 1940 (temperature, precipitation, evapotranspiration, etc.)

### 🌟 Key Features

- ✅ **Automatic validation** of BSS codes before construction
- ✅ **GPS coordinates extraction** from Hub'Eau API (geometry/x/y → latitude/longitude)
- ✅ **Complete piezometric data**: groundwater level NGF, water table depth
- ✅ **Automatic meteorological enrichment** based on GPS coordinates
- ✅ **Daily aggregation** to avoid duplicates
- ✅ **Intuitive interface** with fine selection of fields to export
- ✅ **Multi-format export**: CSV, Excel, JSON
- ✅ **Rate limiting and retry logic** to respect API limits

## 📋 Prerequisites

- Python 3.9+
- Internet connection (for APIs)

## 🚀 Installation

### Option 1: Docker (Recommended) 🐳

**Advantages:** No Python configuration, works on all OS, ready for deployment

```bash
# Quick start
docker-compose up -d

# Or use the startup script
# Windows:
start-docker.bat

# Linux/Mac:
./start-docker.sh
```

The application will be accessible at http://localhost:8501

📖 **Complete documentation:** See [DOCKER.md](DOCKER.md) for more details (CI/CD, deployment, etc.)

### Option 2: Classic Python Installation

```bash
# Clone the repository
git clone https://scm.univ-tours.fr/ringuet/piezo_dataset_builder.git
cd piezo-dataset-builder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install the package
pip install -e .
```

## 💻 Usage

### With Docker

```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### Without Docker

```bash
streamlit run src/piezo_dataset_builder/app.py
```

The application opens in your browser (http://localhost:8501)

### 2. Prepare your CSV file

Create a CSV with a column containing BSS codes (piezometer stations):

```csv
code_bss
07548X0009/F
BSS000AUZM
BSS000BDNZ
```

The column name doesn't matter, the tool will automatically detect BSS codes.

### 3. Workflow in the application

1. **Upload**: Load your CSV containing BSS codes
   - Automatic code validation with sampling
   - Automatic detection of the column containing BSS codes
2. **Period**: Select start/end dates for time series data
3. **Data configuration**:
   - **Stations**: Label, municipality, department
   - **Time series**: NGF level (water table altitude), water table depth
   - **Weather**: Precipitation, temperature, evapotranspiration, humidity, wind, radiation
4. **Advanced options**: Timeout, rate limits, daily aggregation
5. **Build**: Launch dataset construction
   - Real-time progress bar
   - Detailed operation logs
6. **Export**: Download in CSV, Excel or JSON

## 📊 Generated Dataset Example

| code_bss | date | nom_commune | niveau_nappe_ngf | profondeur_nappe | precipitation | temperature | evapotranspiration | nom_departement |
|----------|------|-------------|------------------|------------------|---------------|-------------|--------------------|-----------------| 
| 07548X0009/F | 2025-11-13 | Saint-Estèphe | 21.86 | -15.88 | 0.0 | 17.1 | 1.77 | Gironde |
| 07548X0009/F | 2025-11-14 | Saint-Estèphe | 21.94 | -15.96 | 0.2 | 17.2 | 1.91 | Gironde |
| 07548X0009/F | 2025-11-15 | Saint-Estèphe | 21.94 | -15.96 | 8.3 | 14.5 | 1.41 | Gironde |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

**Important notes:**
- `niveau_nappe_ngf`: Water table altitude in meters NGF (French General Leveling)
- `profondeur_nappe`: Water table depth relative to ground (negative values = water table below ground)
- `precipitation`: Daily precipitation in mm
- `temperature`: Daily average temperature in °C
- `evapotranspiration`: Reference evapotranspiration in mm

## 🔧 Configuration

### APIs Used

- **Hub'Eau Piezometry API**: https://hubeau.eaufrance.fr/page/api-piezometrie
  - Piezometer station attributes
  - Groundwater level time series
  - France only data

- **ERA5-Land (Copernicus CDS)**: https://cds.climate.copernicus.eu/
  - ECMWF atmospheric reanalysis
  - Historical weather data since 1940
  - Resolution: ~9 km
  - Variables: temperature, precipitation, evapotranspiration, humidity, wind, radiation
  - Worldwide data
  - ⚠️ **Free account required**: [Create an account](https://cds.climate.copernicus.eu/)
  - ⚠️ **ERA5-Land license to accept**: [Accept the license](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download#manage-licences)

### Limitations and Best Practices

- **Hub'Eau**:
  - France only data
  - Maximum recommended: 500 stations per batch
  - Configured rate limit: 0.1s between requests
  - Automatic retry on error

- **ERA5 (Copernicus)**:
  - Free account required with API token
  - ERA5-Land license to accept (free, one click)
  - No restrictive rate limit
  - Downloads optimized by 2-year chunks
  - Only necessary grid points extracted

- **Time period**:
  - Data available since 1940
  - Recommended: up to 10 years per request
  - Beyond that, automatic chunking

- **Daily aggregation**:
  - Enabled by default to avoid duplicates
  - Average for numeric values, first value for text

## 📁 Project Structure

```
piezo-dataset-builder/
├── src/piezo_dataset_builder/
│   ├── app.py                  # Streamlit application
│   ├── api/                    # API clients
│   │   ├── hubeau.py          # Hub'Eau Piezometry client
│   │   └── era5.py            # ERA5 (Copernicus) client
│   ├── core/                   # Business logic
│   │   ├── validator.py       # BSS code validation
│   │   └── dataset_builder.py # Dataset construction
│   └── utils/                  # Utilities
│       └── export.py          # CSV/Excel/JSON/ZIP export
├── examples/                    # Example CSV files
│   └── codes_stations_piezo.csv
├── Dockerfile                   # Docker configuration
├── docker-compose.yml          # Docker orchestration
├── .gitlab-ci.yml              # CI/CD pipeline
├── DOCKER.md                   # Docker documentation
├── pyproject.toml              # Python configuration
└── README.md                   # Documentation
```

## 🔍 Available Data

### Hub'Eau Piezometry

**Available station fields:**
- `code_bss`: Unique station code (BSS)
- `libelle_station`: Station name/label
- `nom_commune`: Municipality where the station is located
- `nom_departement`: Department
- `latitude` / `longitude`: GPS coordinates (WGS84) - automatically extracted from geometry/x/y

**Available time series fields:**
- `date`: Measurement date
- `niveau_nappe_ngf`: Water table altitude in meters NGF (extracted from `niveau_nappe_eau` API field)
- `profondeur_nappe`: Water table depth relative to ground (m)

### ERA5-Land (Copernicus)

**Available meteorological variables:**
- `precipitation`: Daily precipitation (mm) - converted from m
- `temperature`: Average air temperature at 2m (°C) - converted from Kelvin
- `evapotranspiration`: Potential evapotranspiration (mm) - converted from m
- `humidity`: Relative humidity (%) - calculated from temperature + dew point
- `wind`: Wind speed at 10m (m/s)
- `radiation`: Downward solar radiation (MJ/m²) - converted from J/m²

**Note:**
- Weather data is automatically associated with each station using GPS coordinates extracted from Hub'Eau
- ERA5 provides data since 1940 with a spatial resolution of ~9 km
- Values are extracted from the nearest grid point to each station

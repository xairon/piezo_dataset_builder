# ERA5 Configuration Guide

ERA5 is the 5th generation atmospheric reanalysis from ECMWF (European Centre for Medium-Range Weather Forecasts). It is the reference meteorological data source for scientific research and operational applications.

## Why ERA5?

- **Free**: Only requires a Copernicus account (free)
- **Complete history**: Data since **1940** until today (continuously updated)
- **Scientific quality**: Used by BRGM, Météo-France, and many research organizations
- **No restrictive rate limits**: Unlike Open-Meteo and other REST APIs
- **Complete variables**: Temperature, precipitation, evapotranspiration, humidity, wind, radiation, etc.
- **Spatial resolution**: ~9km (ERA5-Land)

## Installation and Configuration

### Step 1: Create a Copernicus CDS Account

1. Go to [https://cds.climate.copernicus.eu/](https://cds.climate.copernicus.eu/)
2. Click "Register" in the top right
3. Fill out the registration form (name, email, password)
4. Validate your email (check spam if needed)
5. Log in and accept the terms and conditions

### Step 2: Accept the ERA5-Land License (REQUIRED ⚠️)

**This step is REQUIRED before you can download data.**

1. Once logged into Copernicus CDS
2. Go to this page: [👉 Accept ERA5-Land License](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download#manage-licences)
3. Click **"Accept Licence"** (free, instant, one click)
4. The license will be accepted immediately

**⛔ Without this step, you will get a 403 Forbidden error when downloading.**

### Step 3: Get Your API Token

1. Click on your name in the top right
2. Go to "Profile" or "User profile"
3. You will see your **API Token** (format: `abcd1234-5678-90ab-cdef-1234567890ab`)
4. Copy this token (you will need it for the application)

**Important note**: The new Copernicus format (2024+) no longer uses a separate UID. There is only one unique token.

### Step 4: Configure Your Credentials (2 options)

You have **2 ways** to provide your credentials to the application:

#### Option A: Via the Streamlit Interface (RECOMMENDED - Simplest)

You will enter your credentials directly in the application during dataset configuration (see "Using in the Application" section below).

**Advantages:**
- No need to create a file
- Easy to use
- No technical manipulation

**Disadvantage:**
- You will need to re-enter your credentials for each new session

#### Option B: Via the `.cdsapirc` File (Optional - For advanced users)

If you frequently use the application or other ERA5 tools, you can configure the `.cdsapirc` file:

**On Windows:**
1. Open the command prompt and type:
   ```cmd
   notepad %USERPROFILE%\.cdsapirc
   ```
2. Paste:
   ```
   url: https://cds.climate.copernicus.eu/api
   key: <YOUR_API_TOKEN>
   ```
   (Replace `<YOUR_API_TOKEN>` with your token, e.g., `abcd1234-5678-90ab-cdef-1234567890ab`)
3. Save

**On Linux/Mac:**
1. In a terminal, type:
   ```bash
   nano ~/.cdsapirc
   ```
2. Paste:
   ```
   url: https://cds.climate.copernicus.eu/api
   key: <YOUR_API_TOKEN>
   ```
   (Replace `<YOUR_API_TOKEN>` with your token)
3. Save (Ctrl+O, Enter, Ctrl+X)
4. Set permissions:
   ```bash
   chmod 600 ~/.cdsapirc
   ```

## Using in the Application

### Steps:

1. **Launch the Streamlit application**:
   ```bash
   streamlit run src/piezo_dataset_builder/app.py
   ```

2. **Step 1 - Load your CSV file** with piezometer station BSS codes

3. **Step 2 - Configuration**

   In the **"Weather (ERA5 - Copernicus)"** section:

   - 🔑 **Enter your Copernicus API Token**:
     - **Copernicus API Token**: Your unique token (e.g., `abcd1234-5678-90ab-cdef-1234567890ab`)
     - Note: The new format no longer uses a separate UID

   - ✅ This field is **required** if you check "Include Weather"
   - 🔒 Your token is **masked** and is **NOT saved** (stored only in the current session)

   - Check **"Include Weather"**
   - Select the desired **weather variables** (precipitation, temperature, etc.)

4. **Launch dataset construction**
   - ERA5 data will be automatically downloaded from Copernicus
   - ⏱️ This can take **several minutes** depending on the request size
   - Follow progress in real-time logs

### Important Notes

- ⚠️ **Your token is NOT saved**: it stays in the Streamlit session only
- 🔒 The token is masked in the interface (password field)
- If you close the tab/browser, you will need to re-enter it
- If you configured the `~/.cdsapirc` file (Option B), you can leave the field empty in the interface

## Available Meteorological Variables

| Variable | Description | Unit | Aggregation |
|----------|-------------|------|-------------|
| **Precipitation** | Total precipitation | mm | Daily sum |
| **Temperature** | Air temperature at 2m | °C | Daily average |
| **Evapotranspiration** | Potential evapotranspiration | mm | Daily sum |
| **Temperature Min** | Minimum daily temperature | °C | Daily minimum |
| **Temperature Max** | Maximum daily temperature | °C | Daily maximum |
| **Humidity** | Relative humidity | % | Daily average |
| **Wind** | Wind speed at 10m | m/s | Daily average |
| **Radiation** | Incident solar radiation | MJ/m² | Daily sum |

## Performance and Limits

### Download Times

Download times depend on:
- **Number of stations**: More stations = longer download
- **Time period**: Long periods (>10 years) take more time
- **Server load**: CDS service can be overloaded during peak hours

**Typical time examples:**
- 5 stations × 1 year: ~2-3 minutes
- 25 stations × 5 years: ~10-15 minutes
- 100 stations × 10 years: ~30-60 minutes

### Optimizations

The application uses several optimizations:
1. **Bounding box**: A single CDS request covers all stations in a region
2. **Point extraction**: Data is extracted for each station from the bbox
3. **Daily aggregation**: 6-hourly data is aggregated into daily averages/sums

### Practical Limits

- **No future data**: ERA5 only provides historical data (no forecasts)
- **Spatial resolution**: ~9km, so no very fine local variations
- **CDS queue**: Requests may be queued if the service is overloaded
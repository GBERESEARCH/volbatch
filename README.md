# Volatility Surface Generator

## Overview

This Python application generates volatility surface data from option prices and outputs the results in JSON format. It's designed to process stock and ETF ticker data, calculate implied volatilities across different strike prices and tenors, and prepare the data for visualization in a React frontend.

## Features

- Extract and process option data for individual or multiple tickers
- Calculate volatility surfaces with or without dividend yields
- Generate skew reports for analyzing volatility smiles across different expirations
- Handle rate discounting for accurate forward pricing
- Flexible timeout handling for large data processing operations
- JSON output optimized for frontend visualization

## Requirements

The application requires the following dependencies:
- Python 3.13+
- pandas
- numpy
- requests
- volvisdata
- voldiscount

## Installation

1. Clone the repository
2. Install required packages:
   ```
   pip install pandas numpy requests
   ```
3. Install the custom volatility packages (refer to their respective documentation)

## Configuration

The application uses configuration parameters stored in `vol_params.py`:

- **General Parameters**:
  - `divs`: Whether to use dividend rates in calculations (boolean)
  - `skew_tenors`: Number of months to display in skew report (integer)
  - `interest_rate`: Fixed interest rate for calculations (float)
  - `timeout_seconds`: Maximum processing time per ticker (integer)
  - `discount_type`: Method for discounting (string, e.g., 'smooth')

- **Ticker Map**:
  - Contains a dictionary of supported tickers with their details
  - Each entry includes ticker symbol, long name, and dividend yield

- **Request Parameters**:
  - User agent strings for web scraping
  - Headers for HTTP requests

## Usage

### Process a Single Ticker

```python
from volbatch import VolBatch

# Initialize with parameters
vol_batch = VolBatch(
    ticker='AAPL',
    start_date='2023-01-01',
    save=True
)

# Process the ticker
vol_batch.process_single_ticker()
```

### Process Multiple Tickers

```python
from volbatch import VolBatch

# Initialize with parameters
vol_batch = VolBatch(
    start_date='2023-01-01',
    save=True
)

# Process all tickers in the tickerMap
vol_batch.process_batch()
```

### Custom Dividend Yields

```python
from volbatch import VolBatch

# Initialize
vol_batch = VolBatch(
    ticker='AAPL',
    start_date='2023-01-01',
    divs=True,
    save=True
)

# Get and use dividend yields
vol_batch.get_div_yields()
vol_batch.process_single_ticker()
```

## Output Format

The application generates JSON files with the following structure:

- `data_dict`: Contains volatility data and parameters
- `skew_dict`: Volatility data organized by tenor and strike price
- `skew_data`: Detailed skew report with various metrics

Example output snippet:
```json
{
  "data_dict": { ... },
  "skew_dict": {
    "1M": {
      "80": 0.32,
      "90": 0.28,
      "100": 0.25,
      "110": 0.27,
      "120": 0.30
    },
    "2M": { ... }
  },
  "skew_data": {
    "skew_dict": { ... },
    "ticker": "AAPL",
    "start_date": "2023-01-01"
  }
}
```

## Technical Details

### Key Components

- **VolBatch**: Main class that coordinates the processing of tickers
- **Volatility**: Handles the calculation of volatility surfaces and skew reports
- **VolDiscount**: Handles discount rates for accurate forward pricing
- **Utility Classes**: 
  - `NumpyDateEncoder`: Handles special JSON encoding of NumPy types
  - `NanConverter`: Converts NaN values to None for valid JSON
  - `UrlOpener`: Manages web requests with proper headers

### Timeout Handling

The application uses a decorator to limit processing time per ticker:
```python
@timeout
def get_vol_data(cls, ticker, start_date, discount_type, skew_tenors):
    # Processing logic
```

This prevents the application from hanging on problematic tickers.

### Data Processing Flow

1. **Initialization**: Set parameters for processing
2. **Data Retrieval**: Fetch option data from Yahoo Finance
3. **Volatility Calculation**: Convert option prices to implied volatilities
4. **Skew Analysis**: Generate volatility curves across strikes
5. **Data Transformation**: Format data for JSON serialization
6. **Output**: Save results to JSON files

## Frontend Integration

The JSON output is designed to be consumed by a React frontend for visualization. Each file contains all necessary data for generating volatility surface charts and skew analysis.
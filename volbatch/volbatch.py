"""
Volatility surface calculation and batch processing module.

This module provides functionality for calculating volatility surfaces
for financial instruments, processing multiple tickers in batch mode,
integrating dividend yields, and generating skew data for analysis.
Results can be saved as structured JSON files for further analysis.
"""

import json
import random
from time import sleep
from typing import Dict, Any, Optional

from volbatch.data import VolBatchData
from volbatch.transform import VolBatchTransform
from volbatch.utils import NanConverter
from volbatch.vol_params import vol_params


class VolBatch(VolBatchData, VolBatchTransform):
    """
    Batch processor for volatility surface calculations across multiple securities.
    """
    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the VolBatch class with parameters for volatility calculation.
        """
        self.params: Dict[str, Any] = vol_params.copy()
        self.params.update(kwargs)
        self.voldata = {}


    def process_batch(self) -> None:
        """
        Process a batch of tickers and save the results to JSON files.
        """
        for key, value in self.params['tickerMap'].items():
            print(f"Processing ticker: {key}")
            try:
                if self.params['divs']:
                    # Use the static method but store the result back to self.params
                    self.params = self.get_div_yields(self.params)
                    vol_surface = self.get_vol_data_with_divs(
                        ticker=value['ticker'],
                        div_yield=self.params['div_map'][key],
                        interest_rate=self.params['interest_rate'],
                        start_date=self.params['start_date'],
                        skew_tenors=self.params['skew_tenors']
                    )
                else:
                    vol_surface = self.get_vol_data(
                        ticker=value['ticker'],
                        start_date=self.params['start_date'],
                        discount_type=self.params['discount_type'],
                        skew_tenors=self.params['skew_tenors']
                    )

                if vol_surface is None:
                    print(f"Processing for {key} timed out or failed, skipping to next ticker")
                    continue

                jsonstring = json.dumps(vol_surface, cls=NanConverter)
                voldata = json.loads(jsonstring)
                filename = key + '.json'

                if self.params['save']:
                    with open(filename, "w") as fp:
                        json.dump(voldata, fp, cls=NanConverter)

                print(f"Successfully processed ticker: {key}")

            except Exception as e:
                print(f"Error processing ticker {key}: {str(e)}")

            # Random pause between tickers to avoid rate limiting
            sleep_time = random.randint(6, 15)
            print(f"Pausing for {sleep_time} seconds before next ticker")
            sleep(sleep_time)


    def process_single_ticker(self) -> None:
        """
        Process a single ticker specified in self.params['ticker'].
        """
        raw_ticker = self.params['ticker']
        clean_ticker = raw_ticker.replace('^', '')
        try:
            if self.params['divs']:
                # Use the static method but store the result back to self.params
                self.params = self.get_div_yields(self.params)
                vol_surface = self.get_vol_data_with_divs(
                    ticker=self.params['ticker'],
                    div_yield=self.params['div_map'][clean_ticker],
                    interest_rate=self.params['interest_rate'],
                    start_date=self.params['start_date'],
                    skew_tenors=self.params['skew_tenors']
                )
            else:
                vol_surface = self.get_vol_data(
                    ticker=self.params['ticker'],
                    start_date=self.params['start_date'],
                    discount_type=self.params['discount_type'],
                    skew_tenors=self.params['skew_tenors']
                )

            if vol_surface is None:
                print(f"Processing for {self.params['ticker']} timed out or failed")
                return

            jsonstring = json.dumps(vol_surface, cls=NanConverter)
            voldata = json.loads(jsonstring)
            self.voldata = voldata

            filename = clean_ticker + '.json'
            if self.params['save']:
                self.save_vol_data(filename)

        except Exception as e:
            print(f"Error processing ticker {self.params['ticker']}: {str(e)}")


    def save_vol_data(self, filename: Optional[str] = None) -> None:
        """
        Save volatility data to a JSON file.
        """
        if filename is None:
            filename = self.params['ticker'] + '.json'

        assert filename is not None  # Type guard for static type checkers    

        if hasattr(self, 'voldata'):
            with open(filename, "w") as fp:
                json.dump(self.voldata, fp, cls=NanConverter)
            print("Data saved as", filename)
        else:
            print("No vol data to save")

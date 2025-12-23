"""
Volatility surface calculation and batch processing module.

This module provides functionality for calculating volatility surfaces
for financial instruments, processing multiple tickers in batch mode,
integrating dividend yields, and generating skew data for analysis.
Results can be saved as structured JSON files for further analysis.
"""

import json
from pathlib import Path
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
        self.failed_tickers = []
        for ticker, ticker_dict in self.params['tickerMap'].items():
            print(f"Processing ticker: {ticker}")
            if self.params['raw_data']:
                try:
                    _ = self.get_raw_data(
                        ticker=ticker_dict['ticker'],
                        start_date=self.params['start_date'],
                        pair_selection_method=self.params['pair_selection_method'],
                        max_trade_age_minutes = self.params['max_trade_age_minutes'],
                        date_folder_path = self.params['folder_path'],
                        save_raw_data = self.params['save_raw_data']
                        )
                    
                except (ValueError, ZeroDivisionError, OverflowError,
                        RuntimeWarning) as e:
                    print(f"Error processing ticker {ticker}: {str(e)}")
                    self.failed_tickers.append(ticker)

            else:
                try:
                    if self.params['divs']:
                        # Use the static method but store the result back to self.params
                        self.params = self.get_div_yields(self.params)
                        vol_surface = self.get_vol_data_with_divs(
                            ticker=ticker_dict['ticker'],
                            div_yield=self.params['div_map'][ticker],
                            interest_rate=self.params['interest_rate'],
                            start_date=self.params['start_date'],
                            skew_tenors=self.params['skew_tenors']
                        )
                    else:
                        vol_surface = self.get_vol_data(
                            ticker=ticker_dict['ticker'],
                            start_date=self.params['start_date'],
                            discount_type=self.params['discount_type'],
                            skew_tenors=self.params['skew_tenors'],
                            pair_selection_method=self.params['pair_selection_method'],
                            max_trade_age_minutes = self.params['max_trade_age_minutes'],
                            date_folder_path = self.params['folder_path'],
                            save_raw_data = self.params['save_raw_data'],
                            use_saved_data = self.params['use_saved_data']
                        )

                    if vol_surface is None:
                        print(f"Processing for {ticker} timed out or failed, skipping to next ticker")
                        continue

                    if self.params['trim_dict']:
                        for surface_type in ['mesh', 'scatter', 'spline', 'svi', 'ssvi', 'svijw', 'trisurf']:
                            if surface_type in vol_surface['data_dict']:
                                del vol_surface['data_dict'][surface_type]

                        del vol_surface['data_dict']['line']['params']

                        keys_to_keep = [
                            'x',
                            'y',
                            'z',
                            'contour_x_size',
                            'contour_x_start',
                            'contour_x_stop',
                            'contour_y_size',
                            'contour_y_start',
                            'contour_y_stop',
                            'contour_z_size',
                            'contour_z_start',
                            'contour_z_stop'
                            ]
                        for surface_type in ['int_svi', 'int_ssvi', 'int_svijw', 'int_mesh', 'int_spline']:
                            if surface_type in vol_surface['data_dict']:
                                keys_to_delete = set(
                                    vol_surface['data_dict'][surface_type][
                                        'params'].keys()) - set(keys_to_keep)
                                for param_key in keys_to_delete:
                                    del vol_surface['data_dict'][surface_type]['params'][param_key]

                    jsonstring = json.dumps(vol_surface, cls=NanConverter)
                    voldata = json.loads(jsonstring)

                    file = ticker + '.json'
                    folder_path = self.params.get('folder_path')
                    filename = folder_path / file if folder_path else file

                    if self.params['save']:
                        with open(filename, "w", encoding="utf-8") as fp:
                            json.dump(voldata, fp, cls=NanConverter)

                    print(f"Successfully processed ticker: {ticker}")

                except (ValueError, ZeroDivisionError, OverflowError,
                        RuntimeWarning) as e:
                    print(f"Error processing ticker {ticker}: {str(e)}")
                    self.failed_tickers.append(ticker)

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
                    skew_tenors=self.params['skew_tenors'],
                    pair_selection_method=self.params['pair_selection_method'],
                    max_trade_age_minutes=self.params['max_trade_age_minutes'],
                    date_folder_path = self.params['folder_path'],
                    save_raw_data = self.params['save_raw_data'],
                    use_saved_data = self.params['use_saved_data']
                )

            if vol_surface is None:
                print(f"Processing for {self.params['ticker']} timed out or failed")
                return

            if self.params['trim_dict']:
                for surface_type in ['mesh', 'scatter', 'spline', 'svi', 'ssvi', 'svijw', 'trisurf']:
                    if surface_type in vol_surface['data_dict']:
                        del vol_surface['data_dict'][surface_type]

                del vol_surface['data_dict']['line']['params']

                keys_to_keep = [
                    'x',
                    'y',
                    'z',
                    'contour_x_size',
                    'contour_x_start',
                    'contour_x_stop',
                    'contour_y_size',
                    'contour_y_start',
                    'contour_y_stop',
                    'contour_z_size',
                    'contour_z_start',
                    'contour_z_stop'
                    ]
                for surface_type in ['int_svi', 'int_ssvi', 'int_svijw', 'int_mesh', 'int_spline']:
                    if surface_type in vol_surface['data_dict']:
                        keys_to_delete = set(
                            vol_surface['data_dict'][surface_type][
                                'params'].keys()) - set(keys_to_keep)
                        for param_key in keys_to_delete:
                            del vol_surface['data_dict'][surface_type]['params'][param_key]

            jsonstring = json.dumps(vol_surface, cls=NanConverter)
            voldata = json.loads(jsonstring)
            self.voldata = voldata

            file = clean_ticker + '.json'
            folder_path = self.params.get('folder_path')
            filename = folder_path / file if folder_path else file

            if self.params['save']:
                self.save_vol_data(filename)

        except (ValueError, ZeroDivisionError, OverflowError,
                RuntimeWarning) as e:
            print(f"Error processing ticker {self.params['ticker']}: {str(e)}")


    def save_vol_data(self, filename: Optional[str] = None) -> None:
        """
        Save volatility data to a JSON file.
        """
        if filename is None:
            file = self.params['ticker'] + '.json'
            folder_path = self.params.get('folder_path')
            filename = folder_path / file if folder_path else file

        assert filename is not None  # Type guard for static type checkers

        if hasattr(self, 'voldata'):
            with open(filename, "w", encoding="utf-8") as fp:
                json.dump(self.voldata, fp, cls=NanConverter)
            print("Data saved as", filename)
        else:
            print("No vol data to save")

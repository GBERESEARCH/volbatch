"""
Data acquisition base class for volatility calculations.
"""

import datetime as dt
import json
import random
from io import StringIO
from time import sleep
from typing import Dict, Any, Optional, Union
from pathlib import Path

import pandas as pd
from scipy.interpolate import interp1d

from volvisdata.volatility import Volatility
from voldiscount.voldiscount import VolDiscount

from volbatch.utils import NumpyDateEncoder, UrlOpener, NanConverter, timeout
from volbatch.transform import VolBatchTransform


class VolBatchData:
    """
    Data acquisition methods for volatility batch processing.
    """
    @staticmethod
    @timeout
    def get_raw_data(
            ticker: str,
            start_date: str,
            pair_selection_method: str,
            max_trade_age_minutes: int,
            date_folder_path: Path,
            save_raw_data: bool,
            yield_curve: interp1d
        ) -> Optional[pd.DataFrame]:
        """
        Get raw volatility data for a ticker.
        """
        print(f"Starting data extraction for {ticker}")

        args = {
            'ticker': ticker,
            'filename': None,
            'underlying_price': None,
            'reference_date': start_date,
            'pair_selection_method': pair_selection_method,
            'max_trade_age_minutes': max_trade_age_minutes,
            'yield_curve': yield_curve
        }
        vol = VolDiscount(**args)
        discount_df = vol.get_data_with_rates()

        clean_ticker = args['ticker'].replace('^', '')
        file = clean_ticker+'.pickle'
        
        if save_raw_data:    
            folder_path = date_folder_path / "raw_data" 
            folder_path.mkdir(parents=True, exist_ok=True)
            filename = folder_path / file
            discount_df.to_pickle(filename)

        return discount_df


    @classmethod
    @timeout
    def get_vol_data(
            cls,
            ticker: str,
            start_date: str,
            discount_type: str,
            skew_tenors: int,
            pair_selection_method: str,
            max_trade_age_minutes: int,
            date_folder_path: Path,
            save_raw_data: bool,
            use_saved_data: bool,
            yield_curve: interp1d
        ) -> Optional[Dict[str, Any]]:
        """
        Get volatility data for a ticker.
        """
        print(f"Starting volatility calculation for {ticker}")

        # args = {
        #     'ticker': ticker,
        #     'filename': None,
        #     'underlying_price': None,
        #     'reference_date': start_date,
        #     'pair_selection_method': pair_selection_method,
        #     'max_trade_age_minutes': max_trade_age_minutes
        # }
        # vol = VolDiscount(**args)
        # discount_df = vol.get_data_with_rates()
        if use_saved_data:
            try:
                clean_ticker = ticker.replace('^', '')
                file = clean_ticker+'.pickle'
                
                folder_path = date_folder_path / "raw_data" 
                filename = folder_path / file
                discount_df = pd.read_pickle(filename)
            except:
                discount_df = cls.get_raw_data(
                    ticker=ticker,
                    start_date=start_date,
                    pair_selection_method=pair_selection_method,
                    max_trade_age_minutes=max_trade_age_minutes,
                    date_folder_path=date_folder_path,
                    save_raw_data=save_raw_data,
                    yield_curve=yield_curve
                    )
        else:
            discount_df = cls.get_raw_data(
            ticker=ticker,
            start_date=start_date,
            pair_selection_method=pair_selection_method,
            max_trade_age_minutes=max_trade_age_minutes,
            date_folder_path=date_folder_path,
            save_raw_data=save_raw_data,
            yield_curve=yield_curve
            )

        inputs = {
            'ticker': ticker,
            'wait': 1,
            'monthlies': True,
            'start_date': start_date,
            'discount_type': discount_type,
            'precomputed_data': discount_df,
            'yield_curve': yield_curve
            }
        imp = Volatility(**inputs)

        imp.data()
        imp.skewreport(skew_tenors)

        vol_dict = VolBatchTransform.create_vol_dict(imp, skew_tenors)
        vol_dict['skew_dict']['ticker'] = imp.params['ticker']
        vol_dict['skew_dict']['start_date'] = imp.params['start_date']

        jsonstring = json.dumps(vol_dict, cls=NumpyDateEncoder)
        voldata = json.loads(jsonstring)

        return voldata

    @staticmethod
    @timeout
    def get_vol_data_with_divs(
            ticker: str,
            div_yield: Union[float, str],
            interest_rate: float,
            start_date: str,
            skew_tenors: int,
            yield_curve: interp1d
        ) -> Optional[Dict[str, Any]]:
        """
        Get volatility data for a ticker incorporating dividend yields.
        """
        div_yield = float(div_yield)

        inputs = {
            'ticker': ticker,
            'start_date': start_date,
            'monthlies': True,
            'q': div_yield,
            'r': interest_rate,
            'yield_curve': yield_curve
            }

        imp = Volatility(**inputs)
        imp.data()
        imp.skewreport(skew_tenors)

        vol_dict = VolBatchTransform.create_vol_dict(imp, skew_tenors)
        vol_dict['skew_dict']['ticker'] = imp.params['ticker']
        vol_dict['skew_dict']['start_date'] = imp.params['start_date']

        jsonstring = json.dumps(vol_dict, cls=NumpyDateEncoder)
        voldata = json.loads(jsonstring)

        return voldata

    @staticmethod
    def get_div_yields(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch dividend yields for all tickers in tickerMap.
        Returns modified params dictionary with div_map added.
        """
        div_map: Dict[str, float] = {}

        for key in params['tickerMap'].keys():
            random.seed(dt.datetime.now().timestamp())
            user_agent = random.choice(params['USER_AGENTS'])
            params['request_headers']["User-Agent"] = user_agent
            urlopener = UrlOpener()
            try:
                url = 'https://stockanalysis.com/stocks/'+key.lower()+'/'
                response = urlopener.open(url, params['request_headers'])
                data_list = pd.read_html(StringIO(response.text))
                div_str = data_list[0].iloc[7, 1]
                print(div_str)
                try:
                    divo = div_str.split(" ", 1)[1].rsplit(" ", 1)[0]  # type: ignore
                    div_yield = divo[1:-2]
                    div_map[key] = float(div_yield) / 100
                    print("Stock div yield for ticker: ", key)
                except (ValueError, ZeroDivisionError, OverflowError,
                    RuntimeWarning):
                    print("No stock div yield for ticker: ", key)
                    div_map[key] = 0.0

            except (ValueError, ZeroDivisionError, OverflowError,
                    RuntimeWarning):
                try:
                    url = 'https://stockanalysis.com/etf/'+key.lower()+'/'
                    response = urlopener.open(url, params['request_headers'])
                    data_list = pd.read_html(StringIO(response.text))
                    div_str = data_list[0].iloc[5, 1]
                    print(div_str)
                    try:
                        div_yield = div_str[0:-2]  # type: ignore
                        div_map[key] = float(div_yield) / 100
                        print("Etf div yield for ticker: ", key)
                    except (ValueError, ZeroDivisionError, OverflowError,
                    RuntimeWarning):
                        print("No etf div yield for ticker: ", key)
                        div_map[key] = 0.0

                except (ValueError, ZeroDivisionError, OverflowError,
                    RuntimeWarning):
                    print("problem with: ", key)
                    div_map[key] = 0.0

            sleep(random.randint(5, 15))

        div_map['SPX'] = div_map['SPY']

        for key in params['tickerMap'].keys():
            params['tickerMap'][key]['divYield'] = div_map[key]

        jsonstring = json.dumps(params['tickerMap'], cls=NanConverter)
        tickerdata = json.loads(jsonstring)
        filename = 'tickerMap.json'

        if params['save']:
            with open(filename, "w", encoding="utf-8") as fp:
                json.dump(tickerdata, fp, cls=NanConverter)

        params['div_map'] = div_map
        return params


    @staticmethod
    def load_div_yields(filename: str = 'tickerMap.json') -> Dict[str, float]:
        """
        Load dividend yields from a previously saved tickerMap JSON file.
        """
        with open(filename, encoding="utf-8") as f:
            ticker_map = json.load(f)

        div_map: Dict[str, float] = {}
        for key, value in ticker_map.items():
            div_map[key] = value['divYield']

        return div_map

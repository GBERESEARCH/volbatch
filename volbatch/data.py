"""
Data acquisition base class for volatility calculations.
"""

import datetime as dt
import json
import random
from io import StringIO
from time import sleep
from typing import Dict, Any, Optional, List, Union

import pandas as pd
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
    def get_vol_data(
            ticker: str,
            start_date: str,
            discount_type: str,
            skew_tenors: int
        ) -> Optional[Dict[str, Any]]:
        """
        Get volatility data for a ticker.
        """
        print(f"Starting volatility calculation for {ticker}")

        args = {
            'ticker': ticker,
            'filename': None,
            'underlying_price': None
        }
        vol = VolDiscount(**args)
        discount_df = vol.get_data_with_rates()

        inputs = {
            'ticker': ticker,
            'wait': 1,
            'monthlies': True,
            'start_date': start_date,
            'discount_type': discount_type,
            'precomputed_data': discount_df
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
            skew_tenors: int
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
        params_copy = params.copy()  # Create a copy to avoid modifying the original
        div_map: Dict[str, float] = {}

        for key in params_copy['tickerMap'].keys():
            random.seed(dt.datetime.now().timestamp())
            user_agent = random.choice(params_copy['USER_AGENTS'])
            params_copy['request_headers']["User-Agent"] = user_agent
            urlopener = UrlOpener()
            key_lower = key.lower()
            try:
                url = 'https://stockanalysis.com/stocks/'+key_lower+'/'
                response = urlopener.open(url, params_copy['request_headers'])
                html_doc = response.text
                data_list = pd.read_html(StringIO(html_doc))
                div_str = data_list[0].iloc[7, 1]
                print(div_str)
                try:
                    divo = div_str.split(" ", 1)[1].rsplit(" ", 1)[0]  # type: ignore
                    div_yield = divo[1:-2]
                    div_map[key] = float(div_yield) / 100
                    print("Stock div yield for ticker: ", key)
                except:
                    print("No stock div yield for ticker: ", key)
                    div_map[key] = 0.0

            except:
                try:
                    url = 'https://stockanalysis.com/etf/'+key_lower+'/'
                    response = urlopener.open(url, params_copy['request_headers'])
                    html_doc = response.text
                    data_list = pd.read_html(StringIO(html_doc))
                    div_str = data_list[0].iloc[5, 1]
                    print(div_str)
                    try:
                        div_yield = div_str[0:-2]  # type: ignore
                        div_map[key] = float(div_yield) / 100
                        print("Etf div yield for ticker: ", key)
                    except:
                        print("No etf div yield for ticker: ", key)
                        div_map[key] = 0.0

                except:
                    print("problem with: ", key)
                    div_map[key] = 0.0

            sleep(random.randint(5, 15))

        div_map['SPX'] = div_map['SPY']

        for key in params_copy['tickerMap'].keys():
            params_copy['tickerMap'][key]['divYield'] = div_map[key]

        jsonstring = json.dumps(params_copy['tickerMap'], cls=NanConverter)
        tickerdata = json.loads(jsonstring)
        filename = 'tickerMap.json'

        if params_copy['save']:
            with open(filename, "w") as fp:
                json.dump(tickerdata, fp, cls=NanConverter)

        params_copy['div_map'] = div_map
        return params_copy

    @staticmethod
    def load_div_yields(filename: str = 'tickerMap.json') -> Dict[str, float]:
        """
        Load dividend yields from a previously saved tickerMap JSON file.
        """
        with open(filename) as f:
            ticker_map = json.load(f)

        div_map: Dict[str, float] = {}
        for key, value in ticker_map.items():
            div_map[key] = value['divYield']

        return div_map
    
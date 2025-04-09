
import datetime as dt
import copy
import json
import pandas as pd
from volvisdata.volatility import Volatility
from voldiscount.voldiscount import VolDiscount
from utils import NumpyDateEncoder, UrlOpener, NanConverter, timeout
from vol_params import vol_params

from io import StringIO
import random
from time import sleep
from typing import Dict, Any


class VolBatch():
    def __init__(self, **kwargs):
        """


        Parameters
        ----------
        ticker : Str
            Ticker of the stock.
        start_date : Str
            Starting date for option trades to include.
        interest_rate : Int
            If using dividend rates, single constant rate to use in calculating forwards.    
        divs : Bool
            Whether to extract dividend rates to use in forward calculation or calibrate using put-call parity. The default is False.
        skew_tenors : Int
            Number of months to display in skew report. The default is 24.        
        tickerMap : Dict
            Dictionary of tickers and their respective annualized dividends. The default is 60 of the most liquid US option tickers.   
    
        Returns
        -------

        """
        self.params: Dict[str, Any] = vol_params.copy()
        self.params.update(kwargs)


    def process_batch(self):
        """Process a batch of tickers and save the results to JSON files."""

        for key, value in self.params['tickerMap'].items():
            print(f"Processing ticker: {key}")
            try:

                if self.params['divs']:
                    self.get_div_yields()
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


    def process_single_ticker(self):
        """Process a single ticker specified in self.params['ticker']."""
        try:
            if self.params['divs']:
                self.get_div_yields()
                vol_surface = self.get_vol_data_with_divs(
                    ticker=self.params['ticker'], 
                    div_yield=self.params['div_map'][self.params['ticker']], 
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

            filename = self.params['ticker'] + '.json'
            if self.params['save']:
                self.save_vol_data(filename)

        except Exception as e:
            print(f"Error processing ticker {self.params['ticker']}: {str(e)}")

    def save_vol_data(self, filename=None):
        """
        Save volatility data to a JSON file.
        
        Parameters:
        -----------
        filename : str, optional
            The name of the file to save to. If None, use the ticker name.
        """
        if filename is None:
            filename = self.params['ticker'] + '.json'

        if hasattr(self, 'voldata'):
            with open(filename, "w") as fp:
                # Use NanConverter for the final JSON dump
                json.dump(self.voldata, fp, cls=NanConverter)
            print("Data saved as", filename)
        else:
            print("No vol data to save")


    @classmethod    
    @timeout
    def get_vol_data(cls, ticker, start_date, discount_type, skew_tenors) -> dict:
        """
        Get volatility data for a ticker.
        
        Parameters:
        -----------
        ticker : str
            The ticker symbol
        start_date : str
            The starting date for option data
        skew_tenors : int
            Number of months to display in skew report
            
        Returns:
        --------
        dict
            Volatility surface data
        """
        print(f"Starting volatility calculation for {ticker}")

        args = {
            'ticker': ticker,
        }
        vol = VolDiscount(**args)
        discount_df = vol.get_data_with_rates()

        kwargs = {
            'ticker':ticker,
            'wait':1,
            'monthlies': True,
            'start_date': start_date,
            'discount_type': discount_type,
            'precomputed_data': discount_df
            }
        imp = Volatility(**kwargs)

        imp.data()
        imp.skewreport(skew_tenors)

        vol_dict = cls.create_vol_dict(imp, skew_tenors)
        vol_dict['skew_dict']['ticker'] = imp.params['ticker']
        vol_dict['skew_dict']['start_date'] = imp.params['start_date']

        jsonstring = json.dumps(vol_dict, cls=NumpyDateEncoder)
        voldata = json.loads(jsonstring)

        return voldata    


    @classmethod
    @timeout
    def get_vol_data_with_divs(cls, ticker, div_yield, interest_rate, start_date, skew_tenors) -> dict:
        """


        Parameters
        ----------
        request : Request
            DESCRIPTION.

        Returns
        -------
        dict
            DESCRIPTION.

        """

        div_yield = float(div_yield)

        inputs = {
            'ticker': ticker,
            'start_date':start_date,
            'monthlies':True,
            'q': div_yield,
            'r': interest_rate,
            }

        imp = Volatility(**inputs)
        imp.data()
        imp.skewreport(skew_tenors)

        vol_dict = cls.create_vol_dict(imp, skew_tenors)
        vol_dict['skew_dict']['ticker'] = imp.params['ticker']
        vol_dict['skew_dict']['start_date'] = imp.params['start_date']

        jsonstring = json.dumps(vol_dict, cls=NumpyDateEncoder)
        voldata = json.loads(jsonstring)

        return voldata


    def get_div_yields(self):
        div_map = {}

        for key in self.params['tickerMap'].keys():
            random.seed(dt.datetime.now().timestamp())
            user_agent = random.choice(self.params['USER_AGENTS'])
            self.params['request_headers']["User-Agent"] = user_agent
            urlopener = UrlOpener()
            key_lower = key.lower()
            try:
                url = 'https://stockanalysis.com/stocks/'+key_lower+'/'
                response = urlopener.open(url, self.params['request_headers'])
                html_doc = response.text
                data_list = pd.read_html(StringIO(html_doc))
                div_str = data_list[0].iloc[7, 1]
                print(div_str)
                try:
                    divo = div_str.split(" ", 1)[1].rsplit(" ", 1)[0] #type:ignore
                    div_yield = divo[1:-2]
                    div_map[key] = float(div_yield) / 100
                    print("Stock div yield for ticker: ", key)
                except:
                    print("No stock div yield for ticker: ", key)
                    div_map[key] = 0.0

            except:
                try:
                    url = 'https://stockanalysis.com/etf/'+key_lower+'/'
                    response = urlopener.open(url, self.params['request_headers'])
                    html_doc = response.text
                    data_list = pd.read_html(StringIO(html_doc))
                    div_str = data_list[0].iloc[5, 1]
                    print(div_str)
                    try:
                        div_yield = div_str[0:-2] #type:ignore
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

        for key in self.params['tickerMap'].keys():
            self.params['tickerMap'][key]['divYield'] = div_map[key]

        jsonstring = json.dumps(self.params['tickerMap'], cls=NanConverter)
        tickerdata = json.loads(jsonstring)
        filename = 'tickerMap.json'

        if self.params['save']:
            with open(filename, "w") as fp:
                json.dump(tickerdata, fp, cls=NanConverter)    

        self.params['div_map'] = div_map    


    @staticmethod    
    def load_div_yields(filename='tickerMap.json'):
        with open(filename) as f:
            tickerMap = json.load(f)

        div_map = {}
        for key, value in tickerMap.items():
            div_map[key] = value['divYield']

        return div_map


    @classmethod
    def create_vol_dict(cls, imp, skew_tenors):
        """


        Parameters
        ----------
        imp : TYPE
            DESCRIPTION.

        Yields
        ------
        vol_dict : TYPE
            DESCRIPTION.

        """
        vol_dict = {}
        vol_dict['data_dict'] = copy.deepcopy(imp.data_dict)
        vol_types = list(vol_dict['data_dict'].keys())
        for vt in vol_types:
            try:
                del vol_dict['data_dict'][vt]['params']['yield_curve']
            except KeyError:
                #print("Problem with yield curve: ", vt)
                pass
            try:
                del vol_dict['data_dict'][vt]['tables']
            except KeyError:
                #print("Problem with tables: ", vt)
                pass
            try:
                del vol_dict['data_dict'][vt]['params']['option_dict']
                del vol_dict['data_dict'][vt]['params']['opt_list']
            except KeyError:
                #print("Problem with opt dict / list: ", vt)
                pass

        raw_skew_dict = copy.deepcopy(imp.vol_dict)

        skew_df = pd.DataFrame()
        skew_df['keys'] = list(raw_skew_dict.keys())
        skew_df['vol'] = list(raw_skew_dict.values())
        skew_df['tenor'] = skew_df['keys'].str[0]
        skew_df['strike'] = skew_df['keys'].str[1]
        skew_df = skew_df.drop(['keys'], axis=1)
        skew_df = skew_df.reindex(['tenor', 'strike', 'vol'], axis=1)
        tenors = list(set(skew_df['tenor']))

        skew_data = {}
        str_tenors = []
        for tenor in tenors:
            str_tenors.append(str(tenor)+'M')

        for tenor in str_tenors:
            skew_data[tenor] = {}

        for index, _ in skew_df.iterrows():
            skew_data[str(skew_df['tenor'].iloc[index])+'M'][str(int( #type:ignore
                skew_df['strike'].iloc[index]))] = float(skew_df['vol'].iloc[index]) #type:ignore

        vol_dict['skew_dict'] = skew_data

        full_skew_dict = cls.create_skew_data(skew_tenors, raw_skew_dict, imp)
        vol_dict['skew_data'] = full_skew_dict

        return vol_dict


    @staticmethod
    def create_skew_data(num_tenors, skew_dict, imp):
        """


        Parameters
        ----------
        num_tenors : TYPE
            DESCRIPTION.
        skew_dict : TYPE
            DESCRIPTION.

        Returns
        -------
        skew_data : TYPE
            DESCRIPTION.

        """
        skew_df = pd.DataFrame(index=range(num_tenors),columns=range(5))
        skew_df.columns = [80, 90, 100, 110, 120]
        tenors = list(range(1, 25))
        skew_df.index = tenors #type:ignore

        for (tenor, strike) in skew_dict.keys():
            skew_df.loc[tenor, strike] = skew_dict[(tenor, strike)]

        skew_df.columns = ['80%', '90%', 'ATM', '110%', '120%']

        skew_df['-20% Skew'] = (skew_df['80%'] - skew_df['ATM']) / 20
        skew_df['-10% Skew'] = (skew_df['90%'] - skew_df['ATM']) / 20
        skew_df['+10% Skew'] = (skew_df['110%'] - skew_df['ATM']) / 20
        skew_df['+20% Skew'] = (skew_df['120%'] - skew_df['ATM']) / 20

        skew_df['label'] = skew_df.index
        skew_df['label'] = skew_df['label'].astype(str)

        shifts = ['-20% Skew', '-10% Skew', '+10% Skew', '+20% Skew']
        for item in shifts:
            skew_df[item] = skew_df[item].apply(lambda x: round(x, 2))

        skew_dict2 = skew_df.to_dict(orient='index')

        skew_data = {}
        skew_data['skew_dict'] = skew_dict2
        skew_data['ticker'] = imp.params['ticker']
        skew_data['start_date'] = imp.params['start_date']

        return skew_data

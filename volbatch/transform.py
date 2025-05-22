"""
Data transformation base class for volatility calculations.
"""

import copy
from typing import Dict, Any, List, Tuple

import pandas as pd
from volvisdata.volatility import Volatility


class VolBatchTransform:
    """
    Data transformation methods for volatility batch processing.
    """
    @staticmethod
    def create_vol_dict(
            imp: Volatility,
            skew_tenors: int
        ) -> Dict[str, Any]:
        """
        Create a volatility dictionary from a Volatility instance.
        """
        vol_dict: Dict[str, Any] = {}
        vol_dict['data_dict'] = copy.deepcopy(imp.data_dict)
        vol_types = list(vol_dict['data_dict'].keys())
        for vt in vol_types:
            try:
                del vol_dict['data_dict'][vt]['params']['yield_curve']
            except KeyError:
                pass
            try:
                del vol_dict['data_dict'][vt]['tables']
            except KeyError:
                pass
            try:
                del vol_dict['data_dict'][vt]['params']['option_dict']
                del vol_dict['data_dict'][vt]['params']['opt_list']
            except KeyError:
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

        skew_data: Dict[str, Dict[str, float]] = {}
        str_tenors: List[str] = []
        for tenor in tenors:
            str_tenors.append(str(tenor)+'M')

        for tenor in str_tenors:
            skew_data[tenor] = {}

        for index, _ in skew_df.iterrows():
            skew_data[str(skew_df['tenor'].iloc[index])+'M'][str(int( #type:ignore
                skew_df['strike'].iloc[index]))] = float(skew_df['vol'].iloc[index]) #type:ignore

        vol_dict['skew_dict'] = skew_data

        full_skew_dict = VolBatchTransform.create_skew_data(skew_tenors, raw_skew_dict, imp)
        vol_dict['skew_data'] = full_skew_dict

        return vol_dict

    @staticmethod
    def create_skew_data(
            num_tenors: int,
            skew_dict: Dict[Tuple[int, int], float],
            imp: Volatility
        ) -> Dict[str, Any]:
        """
        Create a detailed skew data structure from volatility data.
        """
        skew_df = pd.DataFrame(index=range(num_tenors), columns=range(5))
        skew_df.columns = [80, 90, 100, 110, 120]
        tenors = list(range(1, 25))
        skew_df.index = tenors  # type: ignore

        for (tenor, strike) in skew_dict.keys():
            skew_df.loc[tenor, strike] = skew_dict[(tenor, strike)]

        skew_df.columns = ['80%', '90%', 'ATM', '110%', '120%']

        skew_df['-20% Skew'] = (skew_df['80%'] - skew_df['ATM']) / 20
        skew_df['-10% Skew'] = (skew_df['90%'] - skew_df['ATM']) / 10
        skew_df['+10% Skew'] = (skew_df['110%'] - skew_df['ATM']) / 10
        skew_df['+20% Skew'] = (skew_df['120%'] - skew_df['ATM']) / 20

        skew_df['label'] = skew_df.index
        skew_df['label'] = skew_df['label'].astype(str)

        shifts = ['-20% Skew', '-10% Skew', '+10% Skew', '+20% Skew']
        for item in shifts:
            skew_df[item] = skew_df[item].apply(lambda x: round(x, 2))

        skew_dict2 = skew_df.to_dict(orient='index')

        skew_data: Dict[str, Any] = {}
        skew_data['skew_dict'] = skew_dict2
        skew_data['ticker'] = imp.params['ticker']
        skew_data['start_date'] = imp.params['start_date']

        return skew_data

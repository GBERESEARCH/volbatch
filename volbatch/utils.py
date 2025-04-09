from json import JSONEncoder
import numpy as np
import pandas as pd
import datetime as dt
import requests
import math
import threading
import functools
from vol_params import vol_params
from typing import List, Optional, Any


TIMEOUT_SECONDS = vol_params.get('timeout_seconds')


class NumpyDateEncoder(JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        try:
            if isinstance(obj, (np.integer)):
                return int(obj)
            elif isinstance(obj, float):
                return round(obj, 2)
            elif isinstance(obj, (np.floating)):
                float_obj = float(obj)
                return round(float_obj, 2)
            elif isinstance(obj, (np.ndarray, pd.Series)):
                return obj.tolist()
            elif isinstance(obj, (dt.datetime, dt.date)):
                return obj.isoformat()
            elif isinstance(obj, (pd.DatetimeIndex)):
                return obj.date.tolist()
            elif isinstance(obj, (pd.DataFrame)):
                return obj.to_json()

        except TypeError:
            print("Error", obj)

        return JSONEncoder.default(self, obj)
    

class UrlOpener:
    """
    Extract data from Yahoo Finance URL

    """

    def __init__(self):
        self._session = requests

    def open(self, url: str, request_headers: dict) -> requests.models.Response:
        """
        Extract data from Yahoo Finance URL

        Parameters
        ----------
        url : Str
            The URL to extract data from.

        Returns
        -------
        response : Response object
            Response object of requests module.

        """
        print("User Agent: ", request_headers["User-Agent"])
        response = self._session.get(
            url=url, headers=request_headers, timeout=10)

        return response    


def nan2None(obj):
    """
    Recursively convert NaN values to None in nested data structures.
    Handles both Python floats and NumPy floating types.
    
    Parameters:
    -----------
    obj : any
        The object to process
    
    Returns:
    --------
    any
        The processed object with NaN values replaced by None
    """
    # Handle dictionaries recursively
    if isinstance(obj, dict):
        return {k: nan2None(v) for k, v in obj.items()}
    
    # Handle lists recursively
    elif isinstance(obj, list):
        return [nan2None(v) for v in obj]
    
    # Handle Python float NaN
    elif isinstance(obj, float):
        if math.isnan(obj):
            return None
    
    # Handle NumPy floating NaN
    elif isinstance(obj, np.floating):
        if np.isnan(obj):
            return None
    
    # Return unchanged if not a NaN
    return obj


class NanConverter(JSONEncoder):
    """
    Enhanced JSON encoder that handles NaN values in both Python and NumPy types.
    """
    def encode(self, obj, *args, **kwargs):
        """
        Apply nan2None processing before encoding to JSON.
        """
        return super().encode(nan2None(obj), *args, **kwargs)


def round_floats(obj):
    """


    Parameters
    ----------
    obj : TYPE
        DESCRIPTION.

    Returns
    -------
    obj : TYPE
        DESCRIPTION.

    """
    if isinstance(obj, float):
        return round(obj, 2)
    if isinstance(obj, dict):
        return {k: round_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(x) for x in obj]
    return obj


def timeout(func):
    """
    Windows-friendly decorator that applies a timeout to the decorated function.
    Uses TIMEOUT_SECONDS constant from vol_params.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result: List[Any] = [None]
        exception: List[Optional[Exception]] = [None]
        completed: List[bool] = [False]
        
        def worker():
            try:
                result[0] = func(*args, **kwargs)
                completed[0] = True
            except Exception as e:
                exception[0] = e
                
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        
        # Wait until timeout or function completes
        thread.join(TIMEOUT_SECONDS)
        
        # If function raised an exception, re-raise it
        if exception[0] is not None:
            raise exception[0]

        # If thread is still running after timeout
        if not completed[0]:
            print(f"Function {func.__name__} timed out after {TIMEOUT_SECONDS} seconds")
            return None
            
        return result[0]
    return wrapper
"""
Utility functions and classes for financial data processing and volatility calculations.

This module provides specialized JSON encoders for numpy and pandas types,
utilities for HTTP requests to financial data sources, timeout mechanisms,
and other helper functions for handling financial data structures.
"""

import datetime as dt
import functools
from json import JSONEncoder
import math
import threading
from typing import List, Optional, Any, Dict, Callable, TypeVar
import numpy as np
import pandas as pd
import requests
from volbatch.vol_params import vol_params

TIMEOUT_SECONDS = vol_params.get('timeout_seconds')

T = TypeVar('T')
R = TypeVar('R')

class NumpyDateEncoder(JSONEncoder):
    """
    Special JSON encoder for numpy types.

    This encoder handles various numpy and pandas data types and converts them
    to standard Python types that can be serialized to JSON.
    """
    def default(self, obj: Any) -> Any:
        try:
            if isinstance(obj, (np.integer)):
                return int(obj)
            if isinstance(obj, float):
                return round(obj, 2)
            if isinstance(obj, (np.floating)):
                float_obj = float(obj)
                return round(float_obj, 2)
            if isinstance(obj, (np.ndarray, pd.Series)):
                return obj.tolist()
            if isinstance(obj, (dt.datetime, dt.date)):
                return obj.isoformat()
            if isinstance(obj, (pd.DatetimeIndex)):
                return obj.date.tolist()
            if isinstance(obj, (pd.DataFrame)):
                return obj.to_json()

        except TypeError as e:
            print(f"Error converting {type(obj)}: {e}")

        return JSONEncoder.default(self, obj)


class UrlOpener:
    """
    Extract data from Yahoo Finance URL.

    A utility class that wraps the requests module to make HTTP requests
    to Yahoo Finance and other financial data sources.
    """

    def __init__(self) -> None:
        self._session = requests

    def open(self, url: str, request_headers: Dict[str, str]) -> requests.models.Response:
        """
        Extract data from Yahoo Finance URL.

        Parameters
        ----------
        url : str
            The URL to extract data from.
        request_headers : Dict[str, str]
            HTTP headers to include in the request.

        Returns
        -------
        requests.models.Response
            Response object of requests module.

        Raises
        ------
        requests.exceptions.RequestException
            If there is an issue with the HTTP request
        """
        print("User Agent: ", request_headers["User-Agent"])
        response = self._session.get(
            url=url, headers=request_headers, timeout=10)

        return response


def nan_to_none(obj: Any) -> Any:
    """
    Recursively convert NaN values to None in nested data structures.
    Handles both Python floats and NumPy floating types.

    Parameters
    ----------
    obj : Any
        The object to process

    Returns
    -------
    Any
        The processed object with NaN values replaced by None
    """
    # Handle dictionaries recursively
    if isinstance(obj, dict):
        return {k: nan_to_none(v) for k, v in obj.items()}

    # Handle lists recursively
    if isinstance(obj, list):
        return [nan_to_none(v) for v in obj]

    # Handle Python float NaN
    if isinstance(obj, float):
        if math.isnan(obj):
            return None

    # Handle NumPy floating NaN
    if isinstance(obj, np.floating):
        if np.isnan(obj):
            return None

    # Return unchanged if not a NaN
    return obj


class NanConverter(JSONEncoder):
    """
    Enhanced JSON encoder that handles NaN values in both Python and NumPy types.

    This encoder applies the nan_to_none conversion before encoding JSON to
    ensure all NaN values are properly handled.
    """
    def encode(self, obj: Any, *args: Any, **kwargs: Any) -> str:
        """
        Apply nan2None processing before encoding to JSON.

        Parameters
        ----------
        obj : Any
            The object to encode
        *args : Any
            Additional positional arguments for the encoder
        **kwargs : Any
            Additional keyword arguments for the encoder

        Returns
        -------
        str
            JSON-encoded string with NaN values converted to null
        """
        return super().encode(nan_to_none(obj), *args, **kwargs)


def round_floats(obj: Any) -> Any:
    """
    Recursively round floating point values in nested data structures.

    This function traverses complex nested data structures and rounds any
    floating point values to 2 decimal places.

    Parameters
    ----------
    obj : Any
        The object containing floating point values to round

    Returns
    -------
    Any
        The object with all floating point values rounded to 2 decimal places
    """
    if isinstance(obj, float):
        return round(obj, 2)
    if isinstance(obj, dict):
        return {k: round_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(x) for x in obj]
    return obj


class TimeoutError(Exception):
    """Exception raised when a function execution exceeds the time limit."""
    pass


def timeout(func: Callable[..., R]) -> Callable[..., Optional[R]]:
    """
    Windows-friendly decorator that applies a timeout to the decorated function.
    Uses TIMEOUT_SECONDS constant from vol_params.

    Parameters
    ----------
    func : Callable[..., R]
        The function to apply timeout to

    Returns
    -------
    Callable[..., Optional[R]]
        Wrapped function that will return None if the execution exceeds the timeout

    Raises
    ------
    Exception
        Re-raises any exception that occurred in the wrapped function
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Optional[R]:
        result: List[Optional[R]] = [None]
        exception: List[Optional[Exception]] = [None]
        completed: List[bool] = [False]

        def worker() -> None:
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
            if isinstance(exception[0], Exception):
                raise exception[0]
            else:
                # This should never happen, but type checking may flag it
                raise RuntimeError(f"Unknown error in {func.__name__}")

        # If thread is still running after timeout
        if not completed[0]:
            print(f"Function {func.__name__} timed out after {TIMEOUT_SECONDS} seconds")
            return None

        return result[0]
    return wrapper

# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 16:24:14 2015

@author: gjm
"""

import os
os.chdir("/Users/gjm/insight/canisolar/bin/")
import requests
import pandas as pd

#from geopy.geocoders import Nominatim


class EIA_API(object):
    '''
    Rate-limited to 100,000 requests / day.
    '''
    def __init__(self):        
        self.api_key = open("eia_api_key.txt", "r").readline().rstrip()
        self.cat_url = "http://api.eia.gov/category/"
        self.ser_url = "http://api.eia.gov/series/"
        self.ser_cat_url = "http://api.eia.gov/series/categories/"
        self.updates_url = "http://api.eia.gov/updates/"
        self.search_url = "http://api.eia.gov/search/"

        self.retail_sales_resident_cat = 1002
        self.avg_retail_price_resident_cat = 1012
        
        self.retail_sales_resident_series_map = self.make_state_to_series_map(self.retail_sales_resident_cat)
        self.avg_retail_price_resident_series_map = self.make_state_to_series_map(self.avg_retail_price_resident_cat)
    def make_state_to_series_map(self, cat):
        '''
        Return a dictionary mapping state codes to series names for a given category
        '''
        state_to_series_map = {}
        param_dict = {"api_key": self.api_key, "category_id": cat , "out":"json"}
        r = requests.get(self.cat_url, params=param_dict)
        data = r.json()
        for series in data['category']['childseries']:
            # monthly frequency series only
            if series['f'] == 'M':
                # extract state/region codes
                abbr = series['series_id'][11:].split('-')[0]
                # keep only 2 character codes, exclude US country code
                if len(abbr) == 2 and abbr != 'US':
                    state_to_series_map[abbr] = series['series_id']
        return state_to_series_map
    def get_series(self, cat, series_map, state, periods):
        '''
        Return JSON for a specified series, state (two letter code), and number of periods
        '''
        param_dict = {"api_key": self.api_key, "series_id": series_map[state], "num": periods, "out": "json"}
        r = requests.get(self.ser_url, params=param_dict)
        return r.json()    
    def get_consump(self, state, periods):
        '''
        Return a pandas DataFrame with year-month period index and millions of kWh values
        '''
        json = self.get_series(self.retail_sales_resident_cat, self.retail_sales_resident_series_map, state, periods)
        data = json['series'][0]['data']
        timestamps = [i for i in zip(*data)][0]
        values = [i for i in zip(*data)][1]
        periods = pd.to_datetime(pd.Series(timestamps), format="%Y%m").dt.to_period(freq='M')
        consump = pd.DataFrame(list(values), index=periods, columns=["mkWh"])
        return consump
    def get_avg_monthly_consump(self, state, periods=60):
        '''
        Return the monthly average of an arbitrary length series of year-month state consumption data
        '''
        consump = self.get_consump(state, periods)
        # groupby will return index labels as the new index
        avg_monthly_consump = consump.groupby(consump.index.month).mean()
        return(avg_monthly_consump)
    def est_monthly_consump(self, month, cost, state):
        '''
        Estimate an individual's consumption in kWh for a given month, cost in dollars, and state
        Return a floating point value in kWh
        '''
        price = self.get_price(month, state)
        consump = cost / price
        return consump
    def est_annual_consump(self, month, consump, state):
        '''
        Estimate an individual's yearly consumption in kWh by month, based on one given month's consumption and state
        Return a pandas DataFrame with month period index and kWh values; pass month as int, consump as kWh
        '''
        avg_monthly_consump = self.get_avg_monthly_consump(state)
        multiplier = float(consump / avg_monthly_consump.loc[month])
        consump = pd.DataFrame(avg_monthly_consump.values * multiplier, 
                                             index = avg_monthly_consump.index, 
                                             columns = ['kWh'])
        return consump
    def get_prices(self, state, periods=60):
        # Change default period value of 60 to whatever works best for modeling future rates
        '''
        Return a pandas DataFrame with year-month period index and cents per kWh values
        '''
        json = self.get_series(self.avg_retail_price_resident_cat, self.avg_retail_price_resident_series_map, state, periods)
        data = json['series'][0]['data']
        timestamps = [i for i in zip(*data)][0]
        values = [i for i in zip(*data)][1]
        periods = pd.to_datetime(pd.Series(timestamps), format="%Y%m").dt.to_period(freq='M')
        prices = pd.DataFrame(list(values), index=periods, columns=["cpkWh"])
        return prices
    def get_price(self, month, state):
        '''
        Return a floating point value in DOLLARS per kWh for the most recent month argument and state
        '''
        prices = self.get_prices(state, 12)
        # This drops the years from the prices index, leaving only months
        prices.index = prices.index.month
        dpkwh = float(prices.loc[month] / 100)
        return dpkwh

class NREL_Utility_Rates_API(object):
    '''
    Rate-limited to 1,000 requests / hour. Most recent data is from 2012.
    '''
    def __init__(self):
        self.api_key = open("nrel_api_key.txt", "r").readline().rstrip()
        self.url = "http://developer.nrel.gov/api/utility_rates/v3.json"
    def get(self, lat, lon):
        '''
        What should this return, exactly? Can there be multiple providers? (YES)
        '''
        # Introduce bounds checking for latitude/longitude
        param_dict = {"api_key": self.api_key, "lat": lat, "lon": lon}
        r = requests.get(self.url, params=param_dict)
        return r.json()
    def get_resident_rate(self, lat, lon):
        '''
        For now, just return the first rate? Later, add in utility selection feature to client side?
        '''
        json = self.get(lat, lon)
        rate = json['outputs']['residential']
        return rate




# -*- coding: utf-8 -*-
"""
Created on Mon Jun 15 21:31:01 2015

@author: gjm

Stub class for accessing the NREL Utility Rates API.
"""

import requests

class Utility_Rates(object):
    '''
    Rate-limited to 1,000 requests / hour. Most recent data is from 2012.
    '''
    def __init__(self):
        self.api_key = open("nrel_api_key.txt", "r").readline().rstrip()
        self.url = "http://developer.nrel.gov/api/utility_rates/v3.json"
    def get(self, lat, lon):
        '''
        What should this return, exactly? Can there be multiple providers? (Yes)
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

def main():
    pass

if __name__ == "__main__":
    main()
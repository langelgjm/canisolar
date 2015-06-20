# -*- coding: utf-8 -*-
"""
Created on Mon Jun  8 09:25:39 2015

@author: gjm
"""

import os
os.chdir("/Users/gjm/insight/canisolar/bin")
from insolation import Insolation
from eia import EIA_DB
import calendar
import numpy as np
import pandas as pd
from geopy.geocoders import GoogleV3
import json
from r import R
import datetime
import math

###############################################################################
# Global variables
mysql_url = "localhost"
mysql_db = "openpv"
eia_db_url = "localhost"
eia_db_name = "eia"
month_lengths = [calendar.monthrange(2015,i)[1] for i in range(1,13)]
# We load this once at the beginning, because the models are large and take a while to load
myr = R("/Users/gjm/insight/canisolar/bin/models")
###############################################################################

class PredictionBoundError(IndexError):
    '''
    Designed to be raised when predicted breakeven time exceeds 30 years.
    '''
    pass

class GeocodeError(ValueError):
    '''
    Designed to be raised when geocoding fails.
    '''
    pass

def dict_to_dict_pairs(mydict):
    '''
    Helper function that's useful for NVD3: takes a dict with 12 month number indices (1-12), 
    and return a list of dictionaries, each of which has 'x' and 'y' keys, where 
    the 'x' key is also a UNIX timestamp in milliseconds. Since the year is hardcoded, 
    This should only be used when the year doesn't matter in the output.
    '''
    pairs = []
    # Note that we assume the dict's keys are month numbers in the correct order!
    for k in [str(i) for i in list(range(1,13))]:
        pairs.append({'x': datetime.datetime(2015, int(k), 1).timestamp() * 1000, 'y':mydict[k]})
    return pairs

def list_to_dict_pairs_x_dates(mylist):
    '''
    Helper function that's useful for NVD3: takes a list of arbitrary length that should 
    represent some values of months starting in April 2015,
    and return a list of dictionaries, each of which has 'x' and 'y' keys, where 
    the 'x' key is also a UNIX timestamp in milliseconds.
    Using integer division and modulo, it correctly generates future year-month pairs starting 
    in April 2015.
    '''
    pairs = []
    for i, v in enumerate(mylist):
        #TODO: test this with other year and month values
        year = 2015
        month = 4
        if i % 12 <= (12 - month) and not i <= 12 - month + 1:
            months = i % 12 + month
            years = i // 12 + year
        else:
            if i >= 9:
                months = i % 12 + month - 12
                years = i // 12 + year + 1            
            else:
                months = i + month
                years = i // 12 + year
        #print(years,months)
        pairs.append({'x': datetime.datetime(years, months, 1).timestamp() * 1000, 'y': v})
    return pairs

def geocode(address):
    '''
    Google's geocoding service can sometimes timeout. Also, it has limits:
    2500 requests per 24 hour period.
    5 requests per second
    They suggest using client-side geocoding, which I would like to do.
    TODO: convert to client-side geocoding, which would run in the browser in JavaScript and give me the results.
    '''
    geolocator = GoogleV3()
    location = geolocator.geocode(address)
    try:
        lon = location.longitude
        lat = location.latitude
        print('Longitude:', lon)
        print('Latitude:', lat)
        
        # Here we get human-readable location elements for display on the web page. They have default values in case they 
        # don't exist in location.raw. 
        state = 'NA'
        state_name = 'NA'
        zipcode = '0000'
        locality = 'NA'
        for i in location.raw['address_components']:
            if 'administrative_area_level_1' in i['types']:
                state = i['short_name']
                state_name = i['long_name']
            if 'postal_code' in i['types']:
                zipcode = i['short_name']
            if 'locality' in i['types']:
                locality = i['short_name']
    except:
        raise GeocodeError
    loc = {'lon': lon, 'lat': lat, 'locality': locality, 'state': state, 'state_name': state_name, 'zipcode': zipcode}
    print(loc)
    return loc

class SolarUser(object):
    '''
    Currently, a new SolarUser should be instantiated if any of the input values change.
    '''
    def __init__(self, lon, lat, state, cost, month, ann_demand_met=0.5, efficiency=0.15):
        # Set up SolarUser instance variables
        self.lon = lon
        self.lat = lat
        self.state = state
        self.cost = cost
        self.month = month
        self.efficiency = efficiency
        self.ann_demand_met=ann_demand_met
        # This is currently a constant derating factor to account for system losses, e.g. DC to AC conversion, etc.
        # This value is obtained from http://rredc.nrel.gov/solar/calculators/pvwatts/version1/derate.cgi
        self.derate_factor = 0.77
        # We don't need an Insolation instance after getting the insolation once, so don't save it
        myInsolation = Insolation()
        self.insolation = myInsolation.get_insolation(self.lon, self.lat)
        # We don't need an EIA_DB instance after getting price and consumption data, so don't save it
        myEIA_DB = EIA_DB(eia_db_url, eia_db_name)
        self.prices = myEIA_DB.get_prices(self.state, periods=12)
        # Since we don't care about the year of these prices, use just the month as the index
        self.prices.index = self.prices.index.month
        # Sort so that months are in order
        self.prices.sort_index(inplace=True)
        self.consumption =  myEIA_DB.est_monthly_consump(self.month, self.cost, self.state)
        self.annual_consumption = myEIA_DB.est_annual_consump(self.month, self.consumption, self.state)
        self.total_consumption = self.annual_consumption['kWh'].sum()
    def populate(self):
        '''
        Call the appropriate methods in the appropriate order to produce all the usable output of the object.
        '''
        self.req_cap = self.get_req_cap()
        self.req_area_m2 = self.get_req_area_m2()
        self.req_area_sqft = self.get_req_area_sqft()
        self.install_cost = self.get_install_cost(self.req_cap)   
        self.breakeven = {}
        for k in ('fit', 'lwr', 'upr'):
            try:
                self.breakeven[k] = self.est_breakeven_net(self.req_cap, self.install_cost[k])
            except PredictionBoundError:
                # TODO: See if we can avoid using a sentinel value
                self.breakeven[k] = -1
    def get_req_area_m2(self):
        '''
        Return the required area (in m^2) of an installation that would meet the proportion of a SolarUser's 
        annual consumption specified by ann_demand_met.
        '''
        kwh_req_per_year = self.total_consumption * self.ann_demand_met
        print("kWH required per year:", kwh_req_per_year)
        # A 1 m^2 panel would produce this many kWh per year
        kwh_prod_per_year_per_m2 = (self.insolation['kWhpm2'] * self.efficiency * np.array(month_lengths)).sum()
        print("kWh produced by a 1 m^2 panel per year:", kwh_prod_per_year_per_m2)        
        # So we need this many m^2:
        m2 = kwh_req_per_year / kwh_prod_per_year_per_m2
        print("Required array size (m^2):", m2)
        return m2
    def get_req_area_sqft(self):
        '''
        Helper method to convert square meters to square feet.
        '''
        ft2 = self.get_req_area_m2() * 10.7639
        print("Required array size (sqft):", ft2)
        return ft2        
    def get_req_cap(self):
        '''
        Return the required capacity (in peak rated kW) of an installation that would meet the proportion of a SolarUser's 
        annual consumption specified by ann_demand_met.
        '''
        kwh_req_per_year = self.total_consumption * self.ann_demand_met
        print("kWH required per year:", kwh_req_per_year)
        solar_hours_per_year = (self.insolation['kWhpm2'] * np.array(month_lengths)).sum()
        print("Solar hours per year:", solar_hours_per_year)
        actual_kw_req = kwh_req_per_year / solar_hours_per_year
        print("True system size required (kW):", actual_kw_req)
        nominal_kw_req = actual_kw_req / self.derate_factor
        print("Nominal (derated) system size required (kW):", nominal_kw_req)
        return nominal_kw_req
    def get_install_cost(self, cap):
        '''
        Return a dictionary with a cost estimate in dollars, along with a 90% prediction interval, 
        for a system of specified capacity cap using a model.
        '''
        cost = myr.predict_cost(self.state, cap)
        print("Estimated cost of this install:", cost['fit'])
        print("Prediction interval of cost for this install:", cost['lwr'], cost['upr'])
        return cost
    def est_savings(self):
        '''
        Return an estimate of savings (in $) over the course of a year, given a proportion of annual demand met.
        This methode uses forecasted prices.
        '''
        # I only forecast out 30 years.
        prices_forecasted = myr.predict_prices(self.state, 360)
        # Convert the prices to a pandas data frome
        prices_forecasted = pd.DataFrame(list(prices_forecasted), columns=["price"])
        # Repeat this 12-month consumption series 30 times
        future_consump = pd.concat([self.annual_consumption]*30, ignore_index=True)
        # Divide by 100 to turn cpkWh into dollars per kWh; match on index
        future_costs_before = future_consump.mul(prices_forecasted['price'] / 100, axis='index')
        future_costs_before.columns = ['dollars']
        kwh_prod_per_year = self.annual_consumption * self.ann_demand_met
        # Construct an array to simulate declining PV panel performance over time.
        # This uses an exponential decay equation to create a numpy array of derating factors for 30 years (360 months).
        # The targets are about 90% after 10 years, and about 80% after 25 years, capped at 80%. 13 is a constant in the equation below.
        # These targets are currently industry standards, but can be expected to improve over time.
        pv_perf_loss_array = np.array([0.8 + 0.2*math.e**(-((i/12)/13)) if i > 1 else 1.0 for i in range(1,361)])
        # Repeat the 12-month consumption series 30 times, but now multiply by performance loss array
        future_production = pd.concat([kwh_prod_per_year]*30, ignore_index=True).mul(pd.Series(pv_perf_loss_array), axis='index')
        # Since prices are in cents, but we want figures in dollars, divide prices by 100
        future_costs_after = future_costs_before['dollars'] - future_production['kWh'].mul(prices_forecasted['price'] / 100, axis='index')
        savings = future_costs_before['dollars'] - future_costs_after
        return savings        
    def est_breakeven_gross(self, cap, cost):
        '''
        Return break even time, in years, for an install of a given capacity and cost. Uses forecasted prices.
        '''
        remaining_cost = cost
        savings = self.est_savings()        
        savings_list = savings.values.tolist()
        # Iterate through the savings list by month, deducting that month's savings from the total until we break even
        for m, val in enumerate(savings_list):
            remaining_cost = remaining_cost - savings_list[m]
            if remaining_cost <= 0:
                # Add 1 to output because indices begin at 0
                print("Breakeven (years):", (m + 1) / 12)
                return (m + 1) / 12
        if remaining_cost > 0:
            raise PredictionBoundError
    def est_breakeven_net(self, cap, cost):
        '''
        Helper method that calculates breakeven times while including the 30% federal tax credit.
        '''
        net_cost = cost * 0.70
        print("The next line reports the breakeven time while including the 30% federal tax credit.")
        return self.est_breakeven_gross(cap, net_cost)

def make_graphs(user, loc):
    '''
    Return a dict with, inter alia, the JSON for two graphs.
    '''
    # The first graph plots insolation as a line, as well as two bar series representing expected 
    # monthly bills in the first year, one each for the solar and non-solar condition
    bills_before = user.prices['cpkWh'].mul(user.annual_consumption['kWh']).mul(0.01)
    bills_before.name = "bills_before"
    # Important: future costs are 1 minus the proportion of demand met by solar!    
    bills_after = user.prices['cpkWh'].mul(user.annual_consumption['kWh']).mul(1 - user.ann_demand_met).mul(0.01)
    bills_after.name = "bills_after"
    
    graph1_y1_max = round(bills_before.max()) + 1
    graph1_y2_max = round(user.insolation.max()['kWhpm2']) + 1
    
    # Here we create the Python objects that we will JSON serialize for the first graph
    bills_before_list = dict_to_dict_pairs(json.loads(bills_before.to_json()))
    bills_after_list = dict_to_dict_pairs(json.loads(bills_after.to_json()))
    insolation_list = dict_to_dict_pairs(json.loads(user.insolation.to_json())['kWhpm2'])    
    
    dict1 = {'key': 'Bills before solar', 
             'color': '#ccf', 
             'values': bills_before_list}
    dict2 = {'key': 'Bills after solar', 
             'color': '#b2df8a', 
             'values': bills_after_list}             
    dict3 = {'key': ''.join(['Solar hours in ', loc['locality'], 
                             ', ', loc['state']]), 
                             'color': '#333', 
                             'values': insolation_list}    
    graph1_data = [dict1, dict2, dict3]
    # Don't indent the JSON we send: indent=4 causing "unterminated string literal" error in JS
    graph1_json = json.dumps(graph1_data)
    
    # The second graph plots the cumulative money spent over time for both the solar and non-solar condition, as lines.
    future_price_list = list(myr.predict_prices(user.state, 360))
    future_consump = pd.concat([user.annual_consumption['kWh']]*30, ignore_index=True)
    future_costs_before = future_consump.mul(future_price_list).mul(0.01)
    future_costs_before_cum_list = list(future_costs_before.cumsum().values)
    # Important: future costs are 1 minus the proportion of demand met by solar!
    #future_costs_after = future_consump.mul(1 - user.ann_demand_met).mul(future_price_list).mul(0.01)
    future_costs_after = future_costs_before - user.est_savings()
    # Here we add the initial install cost to the initial item
    # Don't forget to reduce the initial cost because of the 30% federal tax credit!
    future_costs_after.loc[0] = future_costs_after.loc[0] + user.install_cost['fit'] * 0.70
    future_costs_after_cum_list = list(future_costs_after.cumsum().values)

    graph2_y1_max = math.ceil(max(future_costs_before_cum_list))
    
    future_costs_before_list = list_to_dict_pairs_x_dates(future_costs_before_cum_list)
    future_costs_after_list = list_to_dict_pairs_x_dates(future_costs_after_cum_list)    
    
    dict1 = {'values': future_costs_before_list,
             'key': 'Cumulative costs without solar',
             'color': '#333'}
    dict2 = {'values': future_costs_after_list,
             'key': 'Cumulative costs with solar',
             'color': '#b2df8a'}
             
    graph2_data = [dict1, dict2]
    graph2_json = json.dumps(graph2_data)
    
    graph_dict = {'graph1_json': graph1_json, 'graph1_y1_max': graph1_y1_max, 
                  'graph1_y2_max': graph1_y2_max, 'graph2_json': graph2_json,
                  'graph2_y1_max': graph2_y1_max}
    return graph_dict

def main():
    pass

if __name__ == "__main__":
    main()

# Standard efficiency panels will produce X amount.
# In order to meet y% of your bill, you would need a system of size Z
# Systems of size Z recently installed in your area cost A (a per m2)
# Given this input, you would break even in W years.

# I'm reimagining the output to contain some sliders that would allow you to adjust y (and thereby Z)
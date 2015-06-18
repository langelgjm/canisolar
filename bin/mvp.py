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
from openpv import OpenPV
from geopy.geocoders import GoogleV3
import json
from r import R
import datetime

month_lengths = [calendar.monthrange(2015,i)[1] for i in range(1,13)]
mysql_url = "localhost"
mysql_db = "openpv"
eia_db_url = "localhost"
eia_db_name = "eia"

# We load this once at the beginning, because the models are large
myr = R("/Users/gjm/insight/canisolar/bin/models")

class SolarUser(object):
    def __init__(self, lon, lat, state, cost, month, efficiency=0.15):
        self.lon = lon
        self.lat = lat
        self.state = state
        self.cost = cost
        self.month = month
        #self.efficiency = efficiency
        self.Insolation = Insolation()
        self.insolation = self.Insolation.get_insolation(self.lon, self.lat)
        #self.EIA = EIA_API()
        self.EIA_DB = EIA_DB(eia_db_url, eia_db_name)
        self.prices = self.EIA_DB.get_prices(self.state, periods=12)
        # get month of index, set as new index
        self.prices.index = self.prices.index.month
        # sort so that we Jan - Dec in order
        self.prices.sort_index(inplace=True)
        self.consumption =  self.EIA_DB.est_monthly_consump(self.month, self.cost, self.state)
        self.annual_consumption = self.EIA_DB.est_annual_consump(self.month, self.consumption, self.state)
        self.total_consumption = self.annual_consumption['kWh'].sum()
        self.OpenPV = OpenPV(mysql_url, mysql_db)
    def get_req_area(self, ann_demand_met=0.50, efficiency=0.15):
        '''
        Return the required area (in m^2) of an installation that would meet the proportion of a SolarUser's 
        annual consumption specified by ann_demand_met.
        '''
        kwh_req_per_year = self.total_consumption * ann_demand_met
        print("kWH required per year:", kwh_req_per_year)
        # A 1 m^2 panel would produce this many kWh per year
        kwh_prod_per_year_per_m2 = (self.insolation['kWhpm2'] * efficiency * np.array(month_lengths)).sum()
        print("kWh produced by a 1 m^2 panel per year:", kwh_prod_per_year_per_m2)        
        # So we need this many m^2:
        m2 = kwh_req_per_year / kwh_prod_per_year_per_m2
        print("Required array size:", m2)
        return m2
    def get_req_cap(self, ann_demand_met=0.50, derate=0.75):
        '''
        Return the required capacity (in peak rated kW) of an installation that would meet the proportion of a SolarUser's 
        annual consumption specified by ann_demand_met.
        '''
        kwh_req_per_year = self.total_consumption * ann_demand_met
        print("kWH required per year:", kwh_req_per_year)
        solar_hours_per_year = (self.insolation['kWhpm2'] * np.array(month_lengths)).sum()
        print("Solar Hours per year:", solar_hours_per_year)
        actual_kw_req = kwh_req_per_year / solar_hours_per_year
        print("True system size required (kW):", actual_kw_req)
        # 
        nominal_kw_req = actual_kw_req / derate
        print("Nominal (derated) system size required (kW):", nominal_kw_req)
        return nominal_kw_req
    def get_cost_modeled(self, cap):
        '''
        Return a cost estimate (in dollars) for a system of specified capacity cap using a model.
        '''
        cost = myr.predict_cost(self.state, cap)
        print("Estimated cost of this install:", cost)
        return cost        
    def est_savings(self, ann_demand_met=0.50):
        '''
        Return an estimate of savings (in $) over the course of a year, given a proportion of annual demand met.
        '''
        cost_before = (self.prices['cpkWh'] / 100) * self.annual_consumption['kWh']
        kwh_prod_per_year = self.annual_consumption * ann_demand_met
        cost_after =  cost_before - ((self.prices['cpkWh'] / 100) * kwh_prod_per_year['kWh'])
        savings = cost_before - cost_after
        print("Total savings per year ($):", savings.sum())
        return savings.sum()
    def est_savings_forecasted(self, ann_demand_met=0.50):
        '''
        Return an estimate of savings (in $) over the course of a year, given a proportion of annual demand met.
        This methode uses forecasted prices.
        '''
        prices_forecasted = self.EIA_DB.get_prices_lin_reg(self.state)
        #print(prices_forecasted)
        # Repeat the 12-month consumption series 30 times
        future_consump = pd.concat([self.annual_consumption]*30, ignore_index=True)
        # Divide by 100 to turn cpkWh into dollars per kWh; match on index
        future_costs_before = future_consump.mul(prices_forecasted['price'] / 100, axis='index')
        #cost_before = (self.prices['cpkWh'] / 100) * self.annual_consumption['kWh']
        kwh_prod_per_year = self.annual_consumption * ann_demand_met
        # Repeat the 12-month consumption series 30 times
        future_production = pd.concat([kwh_prod_per_year]*30, ignore_index=True)        
        future_costs_after = future_costs_before - future_production.mul(prices_forecasted['price'] / 100, axis='index')
        #cost_after =  cost_before - ((self.prices['cpkWh'] / 100) * kwh_prod_per_year['kWh'])
        savings = future_costs_before - future_costs_after
        #return savings.sum()
        return savings
    def est_savings_forecasted_modeled(self, ann_demand_met=0.50):
        '''
        Return an estimate of savings (in $) over the course of a year, given a proportion of annual demand met.
        This methode uses forecasted prices.
        '''
        # We only get 30 years of prices; thus if that's not enough we have to deal with the fact and let the user know
        prices_forecasted = myr.predict_prices(self.state, 360)
        # temporary fix; move this to the R class?
        #prices_forecasted = pd.DataFrame(list(prices_forecasted), index=pd.date_range('2015-04', periods=360, freq='MS'), columns=["price"])
        prices_forecasted = pd.DataFrame(list(prices_forecasted), columns=["price"])
        #print(prices_forecasted)
        # Repeat the 12-month consumption series 30 times
        future_consump = pd.concat([self.annual_consumption]*30, ignore_index=True)
        #future_consump.index = pd.date_range('2015-04', periods=360, freq='MS')
        # Divide by 100 to turn cpkWh into dollars per kWh; match on index
        future_costs_before = future_consump.mul(prices_forecasted['price'] / 100, axis='index')
        #cost_before = (self.prices['cpkWh'] / 100) * self.annual_consumption['kWh']
        kwh_prod_per_year = self.annual_consumption * ann_demand_met
        # Repeat the 12-month consumption series 30 times
        future_production = pd.concat([kwh_prod_per_year]*30, ignore_index=True)        
        future_costs_after = future_costs_before['kWh'] - future_production['kWh'].mul(prices_forecasted['price'] / 100, axis='index')
        #cost_after =  cost_before - ((self.prices['cpkWh'] / 100) * kwh_prod_per_year['kWh'])
        # The column name here is wrong, tofix
        savings = future_costs_before['kWh'] - future_costs_after
        #return savings.sum()
        return savings        
    def est_break_even(self, cap, ann_demand_met=0.50):
        '''
        Return break even time, in years, using constant prices. Obviously needs lots of work.
        '''
        cost = self.get_cost_modeled(cap)
        savings = self.est_savings(ann_demand_met)
        print("Breakeven (constant prices, years):", cost/savings)
        return cost / savings
    def est_break_even_forecasted(self, cap, ann_demand_met=0.50):
        '''
        Return break even time, in years. Uses forecasted prices.
        '''
        cost = self.get_cost_modeled(cap)
        # Temporary, to account for 30% federal tax credit
        net_cost = cost * 0.70
        print("Cost after Federal Tax Credit:", net_cost)
        remaining_cost = net_cost
        #savings = self.est_savings_forecasted(ann_demand_met)
        savings = self.est_savings_forecasted_modeled(ann_demand_met)        
        # The column header is is wrong, fix later
        #savings_list = savings['kWh'].values.tolist()
        savings_list = savings.values.tolist()
        #print(savings_list)
        for m, val in enumerate(savings_list):
            remaining_cost = remaining_cost - savings_list[m]
            if remaining_cost <= 0:
                # Add 1 because indices begin at 0
                print("Breakeven (forecasted prices, years):", (m + 1) / 12)
                return (m + 1) / 12
        if remaining_cost > 0:
            print("WARNING: Breakeven time greater than 30 years; returning sentinel value -1")
            # When break even time is longer than 30 years (i.e., forecasted savings are exhausted), 
            # return a static, linear estimate instead
            return -1
    def remaining_cost_vs_future_prices(self, install_cost, ann_demand_met=0.5):
        '''
        Return a dictionary with two items: a list of remaining cost by month, and a list of future_prices (beginning at April 2015)
        '''
        # Temporary, to account for 30% federal tax credit
        net_cost = install_cost * 0.70        
        future_prices = list(myr.predict_prices(self.state, 360))
        remaining_cost = []
        savings_list = self.est_savings_forecasted_modeled(ann_demand_met).values.tolist()
        for m, val in enumerate(savings_list):
            if net_cost <= 0:
                remaining_cost.append(0)
            else:
                remaining_cost.append(net_cost)
                net_cost = net_cost - savings_list[m]
        result = {'remaining_cost': remaining_cost, 'future_prices': future_prices}
        return result

def geocode(address):
    geolocator = GoogleV3()
    location = geolocator.geocode(address)
    lon = location.longitude
    lat = location.latitude
    print('longitude:', lon)
    print('latitude:', lat)
    
    # Not the best way to get the state, but ok for now
    # Also make sure these are defined up front just in case they don't exist in the location.raw
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
    loc = {'lon': lon, 'lat': lat, 'locality': locality, 'state': state, 'state_name': state_name, 'zipcode': zipcode}
    print('state:', state)
    return loc


def from_web(address, cost, month, slider_val=0.50, efficiency_slider_val=0.15):        
    loc = geocode(address)    
    # Inconsistent behavior here: either pass all args to Solar User or not.
    user = SolarUser(loc['lon'], loc['lat'], loc['state'], cost, month, efficiency_slider_val)
    my_cap = user.get_req_cap(ann_demand_met=slider_val)
    my_area = user.get_req_area(ann_demand_met=slider_val, efficiency=efficiency_slider_val)
    install_cost = user.get_cost_modeled(my_cap)
    breakeven_constant = user.est_break_even(my_cap, ann_demand_met=slider_val)
    breakeven = user.est_break_even_forecasted(my_cap, ann_demand_met=slider_val)
    
    def dict_to_dict_pairs(mydict):
        pairs = []
        for k in [str(i) for i in list(range(1,13))]:
            pairs.append({'x': datetime.datetime(2015, int(k), 1).timestamp() * 1000, 'y':mydict[k]})
        return pairs
    
    def list_to_dict_pairs_dates(mylist):
        pairs = []
        for i, v in enumerate(mylist):
            #pairs.append({'x': i, 'y': v})
            year = 2015
            month = 4
            if i % 12 <= (12 - month) and not i <= 9:
                months = i % 12 + 4
                years = i // 12 + year
            else:
                if i >= 9:
                    months = i % 12 + 4 - 12
                    years = i // 12 + year + 1            
                else:
                    months = i + 4
                    years = i // 12 + year
            #print(years,months)
            pairs.append({'x': datetime.datetime(years, months, 1).timestamp() * 1000, 'y': v})
        return pairs

    # New stuff for second graph)
    cost_vs_price_dict = user.remaining_cost_vs_future_prices(install_cost, ann_demand_met=slider_val)
    graph2_y2_max = round(max(cost_vs_price_dict['future_prices'])) + 1
    graph2_y1_max = round(max(cost_vs_price_dict['remaining_cost']))
    
    cost_vs_price_graph_data = [{'values': list_to_dict_pairs_dates(cost_vs_price_dict['remaining_cost']),
                                 'key': 'Unrecovered installation costs',
                                 'color': '#b2df8a',
                                 'area': True},
                                 {'values': list_to_dict_pairs_dates(cost_vs_price_dict['future_prices']),
                                  'key': 'Electricity cost, cents per kWh',
                                  'color': "#333"}]
    cost_vs_price_graph_json = json.dumps(cost_vs_price_graph_data)
    
    # Extra stuff
    annual_consumption = user.EIA_DB.est_annual_consump(month, cost, loc['state']) 
    graph1_y1_max = round(annual_consumption.max()['kWh']) + 1
    print("Annual consumption:", annual_consumption)
    annual_insolation = user.insolation
    graph1_y2_max = round(annual_insolation.max()['kWhpm2']) + 1
    print("Annual insolation:", annual_insolation)
        
    annual_consumption_list = dict_to_dict_pairs(json.loads(annual_consumption.to_json())['kWh'])
    annual_insolation_list = dict_to_dict_pairs(json.loads(annual_insolation.to_json())['kWhpm2'])    
    
    # Note the default lambda function - this allows us to serialize pandas dataframes with json.dumps
    dict1 = {'key': 'Your electricity consumption', 'color': "#ccf", 'values': annual_consumption_list}
    dict2 = {'key': ''.join(['Solar hours in ', loc['locality'], ', ', loc['state']]), 'color': "#333", 'values': annual_insolation_list}    
    graph_data = [dict1, dict2]
    # Note that the lambda function won't be necessary if we call to_json prior
    # indent=4 causing "unterminated string literal" error in JS
    #graph_json = json.dumps(graph_data, default=lambda df: json.loads(df.to_json()))
    graph_json = json.dumps(graph_data)
    
    if breakeven == -1:
        breakeven_formatted = "More than 30 years"
    else:
        breakeven_formatted = str(int(round(breakeven))) + ' years'
    
    result = {'nominal_capacity': my_cap, 
              'install_cost': install_cost, 
              'install_cost_formatted': "{:,}".format(round(install_cost)),
              'breakeven': breakeven,
              'breakeven_formatted': breakeven_formatted,
              'breakeven_constant': breakeven_constant,
              'area_required': my_area,
              'loc': loc,
              'graph_json': graph_json,
              'graph1_y1_max': graph1_y1_max,
              'graph1_y2_max': graph1_y2_max,
              'graph2_y1_max': graph2_y1_max,
              'graph2_y2_max': graph2_y2_max,
              'graph2_json': cost_vs_price_graph_json
              }
    return result

def main():
    pass

if __name__ == "__main__":
    main()

# Standard efficiency panels will produce X amount.
# In order to meet y% of your bill, you would need a system of size Z
# Systems of size Z recently installed in your area cost A (a per m2)
# Given this input, you would break even in W years.

# I'm reimagining the output to contain some sliders that would allow you to adjust y (and thereby Z)
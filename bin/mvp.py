
# coding: utf-8

# In[48]:


"""
Created on Mon Jun  8 09:25:39 2015

@author: gjm
"""

# Setup
#get_ipython().magic('matplotlib inline')
import os
os.chdir("/Users/gjm/insight/canisolar/bin")
from insolation import Insolation
from eia import EIA_API, EIA_DB
import calendar
import numpy as np
import pandas as pd
from openpv import OpenPV
from geopy.geocoders import GoogleV3
import rpy2.robjects as ro

month_lengths = [calendar.monthrange(2015,i)[1] for i in range(1,13)]
mysql_url = "localhost"
mysql_db = "openpv"

eia_db_url = "localhost"
eia_db_name = "eia"

# Input coordinates, cost, and month of cost figure
#lon = -76.9413576
#lat = 38.9873326
#state = 'MD' # will eventually be derived from coordinates
#cost = 500
#month = 8 # May
efficiency = 0.15
# Should also include a derating constant, maybe 0.75 or something
# FYI EIA prices are nominal, not real, unless stated otherwise

class RPredict(object):
    def __init__(self, model_path):
        self.model_path = model_path
        ro.r.load(self.model_path)
    def predict(self, state, size):
        '''
        Return cost in dollars based on a pre-calculated multilevel model in R
        '''
        # What does it mean to not include random effects here?
        cost = ro.r('''exp(predict(mod_ml_2, newdata=data.frame(state='{state}', size={size}), re.form=NA))'''.format(state=state, size=size))        
        return cost[0]

rpredict = RPredict("/Users/gjm/insight/canisolar/data/openpv_analysis/openpv_model.Robj")

class SolarUser(object):
    def __init__(self, lon, lat, state, cost, month, efficiency=0.15):
        self.lon = lon
        self.lat = lat
        self.state = state
        self.cost = cost
        self.month = month
        self.efficiency = efficiency
        self.Insolation = Insolation()
        self.insolation = self.Insolation.get_insolation(self.lon, self.lat)
        self.EIA = EIA_API()
        self.EIA_DB = EIA_DB(eia_db_url, eia_db_name)
        self.prices = self.EIA.get_prices(self.state, periods=12)
        # get month of index, set as new index
        self.prices.index = self.prices.index.month
        # sort so that we Jan - Dec in order
        self.prices.sort_index(inplace=True)
        self.consumption =  self.EIA.est_monthly_consump(self.month, self.cost, self.state)
        self.annual_consumption = self.EIA.est_annual_consump(self.month, self.consumption, self.state)
        self.total_consumption = self.annual_consumption['kWh'].sum()
        self.OpenPV = OpenPV(mysql_url, mysql_db)
    def get_req_area(self, ann_demand_met=0.50):
        '''
        Return the required area (in m^2) of an installation that would meet the proportion of a SolarUser's 
        annual consumption specified by ann_demand_met.
        '''
        kwh_req_per_year = self.total_consumption * ann_demand_met
        print("kWH required per year:", kwh_req_per_year)
        # A 1 m^2 panel would produce this many kWh per year
        kwh_prod_per_year_per_m2 = (self.insolation['kWhpm2'] * self.efficiency * np.array(month_lengths)).sum()
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
    def get_cost_per_watt(self, cap):
        '''
        Return a cost estimate (in $ per W) for a system of specified capacity cap.
        Right now just taking the mean, should order by date and take most recent.
        Also should deal with lack of data.
        '''
        installs = self.OpenPV.get_similar_installs(self.state, cap)
        # Filter to installs within +/- 1 kW of specified capacity, and that have both size and cost
        #installs = installs[(installs['size'] >= cap - 1) & (installs['size'] <= cap + 1)]
        # Remove any that don't have cost info
        installs = installs[installs['cost'].notnull()]
        print("Number of similar installs:", len(installs))
        cost_per_watt = installs['cost'] / (installs['size'] * 1000)
        cost = cost_per_watt.mean()
        print("Mean cost per watt of similar installs:", cost)
        return cost
    def get_cost(self, cap):
        '''
        Return a cost estimate (in $) for a system of specified capacity cap.
        '''
        cost_per_watt = self.get_cost_per_watt(cap)
        cost = cap * 1000 * cost_per_watt
        print("Estimated cost of this install:", cost)
        return cost
    def get_cost_modeled(self, cap):
        '''
        Return a cost estimate (in $) for a system of specified capacity cap using a model.
        '''
        cost = rpredict.predict(self.state, cap)
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
    def est_break_even(self, cap, ann_demand_met=0.50):
        '''
        Return break even time, in years, using constant prices. Obviously needs lots of work.
        '''
        #cost = self.get_cost(cap)
        cost = self.get_cost_modeled(cap)
        savings = self.est_savings(ann_demand_met)
        print("Breakeven (constant prices, years):", cost/savings)
        return cost / savings
    def est_break_even_forecasted(self, cap, ann_demand_met=0.50):
        '''
        Return break even time, in years. Uses forecasted prices.
        '''
        #cost = self.get_cost(cap)
        cost = self.get_cost_modeled(cap)
        remaining_cost = cost
        savings = self.est_savings_forecasted(ann_demand_met)
        # The column header is is wrong, fix later
        savings_list = savings['kWh'].values.tolist()
        for m, val in enumerate(savings_list):
            remaining_cost = remaining_cost - savings_list[m]
            if remaining_cost <= 0:
                # Add 1 because indices begin at 0
                print("Breakeven (forecasted prices, years):", (m + 1) / 12)            
                return (m + 1) / 12
        if remaining_cost > 0:
            print("Breakeven time greater than 60 years, switching to constant pricing.")
            # When break even time is longer than 30 years (i.e., forecasted savings are exhausted), 
            # return a static, linear estimate instead
            self.est_break_even(cap)

def geocode(address):
    geolocator = GoogleV3()
    location = geolocator.geocode(address)
    lon = location.longitude
    lat = location.latitude
    print('longitude:', lon)
    print('latitude:', lat)
    
    # Not the best way to get the state, but ok for now
    for i in location.raw['address_components']:
        if 'administrative_area_level_1' in i['types']:
            state = i['short_name']
    loc = {'lon': lon, 'lat': lat, 'state': state}
    print('state:', state)
    return loc


def from_web(address, cost, month, slider_val=0.50):        
    loc = geocode(address)    
    user = SolarUser(loc['lon'], loc['lat'], loc['state'], cost, month)
    my_cap = user.get_req_cap(ann_demand_met=slider_val)
    #install_cost = user.get_cost(my_cap)
    install_cost = user.get_cost_modeled(my_cap)
    breakeven_constant = user.est_break_even(my_cap, ann_demand_met=slider_val)
    breakeven = user.est_break_even_forecasted(my_cap, ann_demand_met=slider_val)
    
    # Extra stuff
    annual_consumption = user.EIA.est_annual_consump(month, cost, loc['state'])    
    print("Annual consumption:", annual_consumption)
    annual_insolation = user.insolation
    print("Annual insolation:", annual_insolation)
    
    result = {'nominal_capacity': my_cap, 
              'install_cost': install_cost, 
              'install_cost_formatted': "{:,}".format(round(install_cost)),
              'breakeven': breakeven,
              'breakeven_constant': breakeven_constant,
              'loc': loc,
              'annual_consumption': annual_consumption,
              'annual_consumption_json': annual_consumption.to_json(),
              'annual_insolation': annual_insolation,
              'annual_insolation_json': annual_insolation.to_json()
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
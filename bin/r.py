# -*- coding: utf-8 -*-
"""
Created on Wed Jun 17 11:39:59 2015

@author: gjm

R class that takes care of loading saved objects, and provides prediction functions accessible to Python
"""

import os
import rpy2.robjects as ro

class R(object):
    '''
    We will load all objects in the model_path directory.
    '''
    def __init__(self, model_path):
        self.model_path = model_path
        self.r = ro.r
        for file in os.listdir(model_path):
            if file.endswith("Robj"):
                self.r.load(os.path.join(self.model_path, file))
        self.r('''library(forecast)''')
    def predict(self, state, size):
        '''
        Return cost in dollars based on a pre-calculated multilevel model in R.
        Don't use this method, it's outdated.
        '''
        # What does it mean to not include random effects here?
        cost = ro.r('''exp(predict(mod_ml_varslope_nested_year_state, newdata=data.frame(state='{state}', size={size}), re.form=NA))'''.format(state=state, size=size))        
        return cost[0]
    def predict_cost(self, state, size):
        '''
        Return cost in dollars based on a pre-calculated model in R. Hardcoded year of 2014 right now.
        This particular model returns a cost dict with the point estimate and 90% lower and upper prediction interval bounds.
        '''
        fit, lwr, upr = ro.r('''exp(predict(mod_fe_state_year, newdata=data.frame(state='{state}', size={size}, year_installed="2014"), interval="prediction", level=0.90))'''.format(state=state, size=size))        
        cost = {'fit': fit, 'lwr': lwr, 'upr': upr}
        return cost
    def predict_prices(self, state, periods):
        '''
        Return forecasted prices for a given state and number of periods (after March 2015)
        '''
        prices = ro.r('''mypredict(ts_model_list[['{state}']], {periods})'''.format(state=state, periods=periods))     
        return prices

def main():
    pass
    #myr = R('/Users/gjm/insight/canisolar/bin/models')
    #myr.r.objects()
    #cost = myr.predict_cost('MD', 5)
    #prices = myr.predict_prices('MD', 120)

if __name__ == "__main__":
    main()

from flask import render_template, request
from app import app
import os
os.chdir('/Users/gjm/insight/canisolar/bin/')
from canisolar import SolarUser, geocode, make_graphs

@app.route('/')

@app.route('/index')
def index():
    return render_template("input2.html")

@app.route('/input')
def canisolar_input():
    return render_template("input2.html")

@app.route('/output')
def canisolar_output():
    address = request.args.get('address')
    print(address)
    cost = request.args.get('cost')
    cost = float(cost)
    month = request.args.get('month')
    month = int(month)
    
    if request.args.get('ann_demand_met'):
        ann_demand_met_slider_val = float(request.args.get('ann_demand_met'))
    else:
        ann_demand_met_slider_val = 0.50

    if request.args.get('efficiency'):
        efficiency_slider_val = float(request.args.get('efficiency'))
    else:
        efficiency_slider_val = 0.15
    
    loc = geocode(address)
    user = SolarUser(loc['lon'], loc['lat'], loc['state'], cost, month, 
                     ann_demand_met=ann_demand_met_slider_val, 
                     efficiency=efficiency_slider_val)
    user.populate()
    # Now we can access the following attributes
    #user.req_cap
    #user.req_area_m2
    #user.req_area_sqft
    # The following two items are dicts
    #user.install_cost
    # We need to check to see if any of these dict items are -1
    #user.breakeven

    data = {'address': address,
            'cost': cost, 
            'month': month, 
            'ann_demand_met_slider_val': ann_demand_met_slider_val,
            'efficiency_slider_val': efficiency_slider_val,
            'loc': loc, 'req_cap': user.req_cap, 
            'install_cost': user.install_cost, 
            'breakeven': user.breakeven,
            'req_area_sqft': user.req_area_sqft}    

    graph_data = make_graphs(user, loc)

    return render_template("output2.html", data=data, graph_data=graph_data)
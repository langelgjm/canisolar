from flask import render_template, request
from app import app
from canisolar import SolarUser, make_graphs

with open('google_maps_api_key.txt', 'r') as f:
    google_maps_api_key = f.readline()
    data = {'google_maps_api_key': google_maps_api_key}

@app.route('/')

@app.route('/index')
def index():
    return render_template("input.html", data=data)

@app.route('/input')
def canisolar_input():
    return render_template("input.html", data=data)

@app.route('/output')
def canisolar_output():
    address = request.args.get('address')
    print(address)
    cost = request.args.get('cost')
    cost = float(cost)
    month = request.args.get('month')
    month = int(month)
    lon = float(request.args.get('lng'))
    lat = float(request.args.get('lat'))
    state = request.args.get('state')
    state_name = request.args.get('state_name')
    locality = request.args.get('locality')
    zipcode = request.args.get('zipcode')
    
    if request.args.get('net_metering'):
        net_metering = True
    else:
        net_metering = False
    
    loc = {'lon': lon, 'lat': lat, 'state': state, 'state_name': state_name, 'locality': locality, 'zipcode': zipcode}
    
    if request.args.get('ann_demand_met'):
        ann_demand_met_slider_val = float(request.args.get('ann_demand_met'))
    else:
        ann_demand_met_slider_val = 0.50

    if request.args.get('efficiency'):
        efficiency_slider_val = float(request.args.get('efficiency'))
    else:
        efficiency_slider_val = 0.15
    
    user = SolarUser(loc['lon'], loc['lat'], loc['state'], cost, month, 
                     ann_demand_met=ann_demand_met_slider_val, 
                     efficiency=efficiency_slider_val, net_metering=net_metering)
    user.populate()
    # Now we can access the following attributes
    #user.req_cap
    #user.req_area_m2
    #user.req_area_sqft
    # The following two items are dicts
    #user.install_cost
    # We need to check to see if any of these dict items are -1
    #user.breakeven

    data = {'google_maps_api_key': google_maps_api_key, 
            'address': address,
            'cost': cost, 
            'month': month, 
            'ann_demand_met_slider_val': user.ann_demand_met,
            'efficiency_slider_val': user.efficiency,
            'loc': loc, 'req_cap': user.req_cap, 
            'install_cost': user.install_cost, 
            'breakeven': user.breakeven,
            'req_area_sqft': user.req_area_sqft, 
            'net_metering': 'checked' if net_metering else ''}    

    graph_data = make_graphs(user, loc)

    return render_template("output.html", data=data, graph_data=graph_data)

if __name__ == "__main__":
	app.run(host='0.0.0.0', port=5000)
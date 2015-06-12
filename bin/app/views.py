from flask import render_template, request, Markup
from app import app
import os
os.chdir('/Users/gjm/insight/canisolar/bin/')
import mvp
from nvd3 import lineChart

@app.route('/')

@app.route('/index')
def index():
    return render_template("input.html")

@app.route('/input')
def canisolar_input():
    return render_template("input.html")

@app.route('/output')
def canisolar_output():
    #pull 'ID' from input field and store it
    address = request.args.get('address')
    cost = request.args.get('cost')
    # cast from str to float
    cost = float(cost)
    month = request.args.get('month')
    # cast from str to int
    month = int(month)
    
    # slider
    if request.args.get('ann_demand_met'):
        slider_val = float(request.args.get('ann_demand_met'))
        print("HTML5 Slider Value:", slider_val)
    else:
        slider_val = 0.50

    
    result = mvp.from_web(address, cost, month, slider_val)
    
    chart = lineChart(name="lineChart", x_is_date=False)
    
    xdata = range(1,13)
    # Convert to 10s of kWh for ease of plotting right now on a single axis
    consumption = [i / 10 for i in result['annual_consumption']['kWh'].tolist()]
    insolation = result['annual_insolation']['kWhpm2'].tolist()
    
    #extra_serie = {"tooltip": {"y_start": "There are ", "y_end": " calls"}}
    chart.add_serie(y=consumption, x=xdata, name='Consumption (10s of kWh)')
    #extra_serie = {"tooltip": {"y_start": "", "y_end": " min"}}
    chart.add_serie(y=insolation, x=xdata, name='Insolation (mean kWh / m^2 / day)')
    chart.set_graph_width(1000)
    chart.buildhtml()

    #output_file = open('/Users/gjm/insight/canisolar/bin/app/templates/test-nvd3.html', 'w')
    #output_file.write(chart.htmlcontent)
    print(address)

    return render_template("output.html", address = address,
                           cost = cost,
                           month = month,
                           slider_val = slider_val, 
                           result = result, chart_html = Markup(chart.htmlcontent))
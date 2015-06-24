from flask import render_template, request
from app import app
from canisolar import SolarUser, make_graphs
from insolation import PolyFindError
import us
import smtplib

valid_state_abbr_list = [state.abbr for state in us.states.STATES if state.abbr != 'AK']

with open('google_maps_api_key.txt', 'r') as f:
    google_maps_api_key = f.readline()
    data = {'google_maps_api_key': google_maps_api_key}

with open('gmail_user.txt', 'r') as f:
    gmail_user = f.readline()
with open('gmail_password.txt', 'r') as f:
    gmail_password = f.readline()

def email_admin(query_string):
    '''
    E-mails me the query string when an unknown error occurred.
    '''
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        #Next, log in to the server
        server.ehlo()
        server.starttls()
        server.ehlo()    
        server.login(gmail_user, gmail_password)
        #Send the mail
        msg = "\n" + str(query_string) # The /n separates the message from the headers
        server.sendmail(gmail_user, gmail_user, msg)
    except Exception:
        print("Caught a generic exception in email_admin!")
    finally:
        return None

@app.route('/')
@app.route('/index')
def index():
    data['error_text'] = "Helping you decide if solar power makes sense for you."
    return render_template("input.html", data=data)

@app.route('/input')
def canisolar_input():
    index()

def canisolar_error(error_text):
    data['error_text'] = error_text
    return render_template("input.html", data=data)

@app.route('/output')
def canisolar_output():
    try:
        address = request.args.get('address')
        print(address)
        cost = request.args.get('cost')
        print(cost)
        try:
            # If there are any commas, replace them with nothing
            # Replace dollar sign with nothing
            # Try to convert to float
            cost = float(cost.replace(',', '').replace('$', ''))
            if cost < 0:
                raise ValueError
        except ValueError:
            error_text = "Please enter a valid number for your most recent bill."
            return canisolar_error(error_text)        
        month = request.args.get('month')
        try:
            month = int(month)
            if month > 12 or month < 1:
                raise ValueError
        except ValueError:
            error_text = "Please enter a valid value for the month of your most recent bill."
            return canisolar_error(error_text)
        try:
            lon = float(request.args.get('lng'))
            lat = float(request.args.get('lat'))
        except ValueError:
            error_text = "Please enter valid values for latitude and longitude."
            return canisolar_error(error_text)
        state = request.args.get('state')
        state_name = request.args.get('state_name')
        locality = request.args.get('locality')
        zipcode = request.args.get('zipcode')

        # Construct the DSIRE URL; technology 7 is solar photovoltaics
        if zipcode != '':
            dsire_url = 'http://programs.dsireusa.org/system/program?zipcode={}&technology=7'.format(zipcode)
        # If we don't have the zipcode, just use the state
        else:
            dsire_url = 'http://programs.dsireusa.org/system/program?state={}&technology=7'.format(state)            
        
        #if request.args.get('net_metering'):
        #    net_metering = True
        #else:
        #    net_metering = False
        net_metering = True
        
        loc = {'lon': lon, 'lat': lat, 'state': state, 'state_name': state_name, 'locality': locality, 'zipcode': zipcode}
        
        if loc['state'] not in valid_state_abbr_list:
            error_text = "Sorry, Can I Solar does not yet support that location."
            return canisolar_error(error_text)        
        
        if request.args.get('ann_demand_met'):
            try:
                ann_demand_met_slider_val = float(request.args.get('ann_demand_met'))
                if ann_demand_met_slider_val > 1.0 or ann_demand_met_slider_val < 0.01:
                    raise ValueError
            except ValueError:
                error_text = "Please enter a valid value for consumption supplied by solar."
                return canisolar_error(error_text)            
        else:
            ann_demand_met_slider_val = 0.50
    
        if request.args.get('efficiency'):
            try:
                efficiency_slider_val = float(request.args.get('efficiency'))
                if efficiency_slider_val > 0.20 or efficiency_slider_val < 0.15:
                    raise ValueError
            except ValueError:
                error_text = "Please enter a valid value for panel efficiency."
                return canisolar_error(error_text)                        
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
                'net_metering': 'checked' if net_metering else '',
                'dsire_url': dsire_url}    
    
        graph_data = make_graphs(user, loc)
    
    except PolyFindError:
        error_text = "Sorry, I couldn't find that location."
        return canisolar_error(error_text)
    except Exception as e:
        error_text = "Sorry, an error occurred. The administrator has been notified."
        email_admin(' '.join([request.query_string, str(e)])
        # Here is where it would be nice to e-mail me with the URL that produced this generic error.
        return canisolar_error(error_text)        
    

    return render_template("output.html", data=data, graph_data=graph_data)

if __name__ == "__main__":
	app.run(host='0.0.0.0', port=5000, debug=True)

# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 16:24:14 2015

@author: gjm

This file defines two classes: EIA_DB, and EIA_API.

EIA_DB is used for retrieval of Energy Information Administration 
data, which is stored in MySQL tables.

EIA_API defines a class that was used to retrieve this information from the EIA 
in the first place. It is not used in normal program flow, although it may be used 
at some point in the future if I implement automatic updating of the database 
with new prices.
"""

import requests
import pandas as pd
import pymysql

mysql_url = "localhost"
mysql_db = "eia"

class EIA_DB(object):
    """This class defines methods for interacting with the EIA MySQL tables."""
    def __init__(self, db_url, db_name):
        """Instantiate an EIA_DB object.
        Create a database and tables if necessary.
        """
        self.db_url = db_url
        self.db_name = db_name
        # charset utf8mb4 is the only proper way to handle true UTF-8 in mySQL.
        # First open connection to server without specifying db
        self.connection = pymysql.connect(host=self.db_url,
            user='root',
            passwd='',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor)
        # Create db (if it doesn't already exist)
        self.create_db()
        # Now reconnect using the specified db
        self.connection = pymysql.connect(host=self.db_url,
            user='root',
            passwd='',
            db=self.db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor)
        # Create tables (if they don't already exist)
        self.create_tables()
    def create_db(self):
        """Create a MySQL database if it doesn't already exist."""
        # Can't use parameters with database/table names
        # Technically insecure against the script operator
        sql = ' '.join(['''CREATE DATABASE IF NOT EXISTS ''', self.db_name,  
            '''DEFAULT CHARSET=utf8mb4 DEFAULT COLLATE=utf8mb4_unicode_ci'''])
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
        self.connection.commit()        
    def create_tables(self):     
        """Create MySQL tables if they don't already exist.""" 
        prices = '''CREATE TABLE IF NOT EXISTS retail_residential_prices (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, 
            state CHAR(2),
            date DATE,
            price FLOAT
            )
            ENGINE=MyISAM'''
        consump = '''CREATE TABLE IF NOT EXISTS retail_residential_sales (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, 
            state CHAR(2),
            date DATE,
            sales FLOAT
            )
            ENGINE=MyISAM'''
        with self.connection.cursor() as cursor:
            for sql in (prices, consump):
                cursor.execute(sql)
        self.connection.commit()        
    def insert_price(self, state, date, price):
        """Insert a price for a given state and date into the appropriate MySQL table."""
        # if a variable is missing, it's an empty string; set that to None instead so that it becomes NULL in the db
        state = state if state != '' else None
        # we add the -01 to avoid illegal date strings that have day 00 in MySQL
        date = date + '-01' if date != '' else None
        price = price if price != '' else None
        # note use of STR_TO_DATE to convert the date to the correct format
        # note also that the % for date formatting needs to be escaped
        sql = '''INSERT INTO retail_residential_prices (state, date, price) 
            VALUES (%s, STR_TO_DATE(%s, '%%Y-%%m-%%d'), %s)'''
        #print(sql)
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (state, date, price))
        self.connection.commit()
    def insert_sale(self, state, date, sale):
        """Insert a 'sale' (really, consumption figure) for a given state and date into the 
        appropriate MySQL table.
        """
        # if a variable is missing, it's an empty string; set that to None instead so that it becomes NULL in the db
        state = state if state != '' else None
        # we add the -01 to avoid illegal date strings that have day 00 in MySQL
        date = date + '-01' if date != '' else None
        sale = sale if sale != '' else None
        # note use of STR_TO_DATE to convert the date to the correct format
        # note also that the % for date formatting needs to be escaped
        sql = '''INSERT INTO retail_residential_sales (state, date, sales) 
            VALUES (%s, STR_TO_DATE(%s, '%%Y-%%m-%%d'), %s)'''
        #print(sql)
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (state, date, sale))
        self.connection.commit()
    def get_price(self, month, state):
        '''Return a floating point value in DOLLARS per kWh for the most recent 
        month argument and state.
        '''
        sql = '''SELECT * FROM retail_residential_prices WHERE state = %s ORDER BY date DESC LIMIT 12'''
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (state))
        results = cursor.fetchall()
        prices = pd.DataFrame(list(results), columns=['id', 'state', 'date', 'price'])
        # use month numbers as the new index
        prices.index = prices['date'].apply(lambda i: i.month)
        dpkwh = prices.loc[month]['price'] / 100
        return dpkwh        
    def get_prices(self, state, periods=12):
        '''Return a pandas DataFrame with year-month period index and cents per kWh 
        values.
        '''        
        sql = '''SELECT * FROM retail_residential_prices WHERE state = %s ORDER BY date DESC LIMIT %s'''
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (state, periods))
        results = cursor.fetchall()
        timestamps = [i for i in zip(*results)][2]
        periods = pd.to_datetime(pd.Series(timestamps))
        values = [i for i in zip(*results)][3]
        prices = pd.DataFrame(list(values), index=periods, columns=['cpkWh'])
        return prices
    def get_consump(self, state, periods):
        '''Return a pandas DataFrame with year-month period index and millions of kWh values'''
        sql = '''SELECT * FROM retail_residential_sales WHERE state = %s ORDER BY date DESC LIMIT %s'''
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (state, periods))
        results = cursor.fetchall()
        timestamps = [i for i in zip(*results)][2]
        periods = pd.to_datetime(pd.Series(timestamps))
        values = [i for i in zip(*results)][3]
        sales = pd.DataFrame(list(values), index=periods, columns=['mkWh'])
        return sales
    def get_avg_monthly_consump(self, state, periods=60):
        '''Return the monthly average of an arbitrary length series of year-month state consumption data'''
        consump = self.get_consump(state, periods)
        # groupby will return index labels as the new index
        avg_monthly_consump = consump.groupby(consump.index.month).mean()
        return(avg_monthly_consump)
    def est_monthly_consump(self, month, cost, state):
        '''Estimate an individual's consumption in kWh for a given month, cost in dollars, and state
        Return a floating point value in kWh
        '''
        price = self.get_price(month, state)
        consump = cost / price
        return consump
    def est_annual_consump(self, month, consump, state):
        '''Estimate an individual's yearly consumption in kWh by month, based on one given month's consumption and state
        Return a pandas DataFrame with month period index and kWh values; pass month as int, consump as kWh
        '''
        avg_monthly_consump = self.get_avg_monthly_consump(state)
        multiplier = float(consump / avg_monthly_consump.loc[month])
        consump = pd.DataFrame(avg_monthly_consump.values * multiplier, 
                                             index = avg_monthly_consump.index, 
                                             columns = ['kWh'])
        return consump        
    def close(self):
        """Close the database connection."""
        self.connection.close()

class EIA_API(object):
    """This class defines methods for interacting with the EIA API.
    This API is rate-limited to 100,000 requests per day.
    """
    def __init__(self): 
        """Instantiate an EIA_API object."""       
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
        self.eia_db_url = "localhost"
        self.eia_db_name = "eia"
        self.eia_db = EIA_DB(self.eia_db_url, self.eia_db_name)
    def make_state_to_series_map(self, cat):
        '''Return a dictionary mapping state codes to series names for a given category'''
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
        '''Return JSON for a specified series, state (two letter code), and number of periods'''
        param_dict = {"api_key": self.api_key, "series_id": series_map[state], "num": periods, "out": "json"}
        r = requests.get(self.ser_url, params=param_dict)
        return r.json()    
    def get_consump(self, state, periods):
        '''Return a pandas DataFrame with year-month period index and millions of kWh values'''
        json = self.get_series(self.retail_sales_resident_cat, self.retail_sales_resident_series_map, state, periods)
        data = json['series'][0]['data']
        timestamps = [i for i in zip(*data)][0]
        values = [i for i in zip(*data)][1]
        periods = pd.to_datetime(pd.Series(timestamps), format="%Y%m")
        consump = pd.DataFrame(list(values), index=periods, columns=["mkWh"])
        return consump
    def get_avg_monthly_consump(self, state, periods=60):
        '''Return the monthly average of an arbitrary length series of year-month state consumption data'''
        consump = self.get_consump(state, periods)
        # groupby will return index labels as the new index
        avg_monthly_consump = consump.groupby(consump.index.month).mean()
        return(avg_monthly_consump)
    def est_monthly_consump(self, month, cost, state):
        '''Estimate an individual's consumption in kWh for a given month, cost in dollars, and state
        Return a floating point value in kWh
        '''
        price = self.get_price(month, state)
        consump = cost / price
        return consump
    def est_annual_consump(self, month, consump, state):
        '''Estimate an individual's yearly consumption in kWh by month, based on one 
        given month's consumption and state.
        Return a pandas DataFrame with month period index and kWh values; 
        pass month as int, consump as kWh
        '''
        avg_monthly_consump = self.get_avg_monthly_consump(state)
        multiplier = float(consump / avg_monthly_consump.loc[month])
        consump = pd.DataFrame(avg_monthly_consump.values * multiplier, 
                                             index = avg_monthly_consump.index, 
                                             columns = ['kWh'])
        return consump
    def get_prices(self, state, periods=60):
        '''Return a pandas DataFrame with year-month period index and cents per kWh values'''
        json = self.get_series(self.avg_retail_price_resident_cat, self.avg_retail_price_resident_series_map, state, periods)
        data = json['series'][0]['data']
        timestamps = [i for i in zip(*data)][0]
        values = [i for i in zip(*data)][1]
        periods = pd.to_datetime(pd.Series(timestamps), format="%Y%m")
        prices = pd.DataFrame(list(values), index=periods, columns=["cpkWh"])
        return prices
    def get_price(self, month, state):
        '''Return a floating point value in DOLLARS per kWh for the most recent 
        month argument and state.
        '''
        prices = self.get_prices(state, 12)
        # This drops the years from the prices index, leaving only months
        prices.index = prices.index.month
        dpkwh = float(prices.loc[month] / 100)
        return dpkwh
    def dump_prices(self):
        '''Query API for all states, dump all prices to an SQL database.'''
        eia_db = EIA_DB(mysql_url, mysql_db)
        
        for state in self.avg_retail_price_resident_series_map.keys():
            print(state)
            state_prices = self.get_prices(state, periods=240)
            for row in state_prices.iterrows():
                # The explicit str() cast on the price was necessary, unclear why
                eia_db.insert_price(state, str(row[0]), str(row[1][0]))
            eia_db.connection.commit()
    def dump_sales(self):
        '''Query API for all states, dump all consumption to an SQL database.'''
        eia_db = EIA_DB(mysql_url, mysql_db)
        
        for state in self.retail_sales_resident_series_map.keys():
            print(state)
            state_sales = self.get_consump(state, periods=240)
            for row in state_sales.iterrows():
                # The explicit str() cast on the price was necessary, unclear why
                eia_db.insert_sale(state, str(row[0]), str(row[1][0]))
            eia_db.connection.commit()

def main():
    pass
    # Example of how to dump prices and sales to the MySQL database.
    #eia_db = EIA_DB(mysql_url, mysql_db)
    #eia = EIA_API()
    #eia.dump_prices()
    #eia.dump_sales()

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Created on Fri Jun  5 09:23:38 2015

@author: gjm
"""

import os
os.chdir("/Users/gjm/insight/canisolar/bin/")
import requests
import us
import pymysql.cursors
import csv
from pymysql import DataError
import pandas as pd

mysql_url = "localhost"
mysql_db = "openpv"
openpv_data_path = "/Users/gjm/insight/canisolar/data/openpv/"


class OpenPV(object):
    def __init__(self, db_url, db_name):
        self.api_key = open("openpv_api_key.txt", "r").readline().rstrip()
        self.url = "http://developer.nrel.gov/api/solar/open_pv"
        self.csv_url = "http://developer.nrel.gov/api/solar/open_pv/installs/index"
        self.states = [state.abbr for state in us.states.STATES]
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
        # Can't use parameters with database/table names
        # Technically insecure against the script operator
        sql = ' '.join(['''CREATE DATABASE IF NOT EXISTS ''', self.db_name,  
            '''DEFAULT CHARSET=utf8mb4 DEFAULT COLLATE=utf8mb4_unicode_ci'''])
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
        self.connection.commit()        
    def create_tables(self):       
        item_data = '''CREATE TABLE IF NOT EXISTS installs (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, 
            zipcode CHAR(5), 
            state CHAR(2),
            size FLOAT,
            cost FLOAT,
            date_installed DATE
            )
            ENGINE=MyISAM'''
        with self.connection.cursor() as cursor:
            cursor.execute(item_data)
        self.connection.commit()        
    def get_api_state_data(self, state):
        '''
        Return a link to a CSV file
        '''
        param_dict = {"export": "true", "api_key": self.api_key, "state": state, "pagenum": 1, "nppage": 25}
        r = requests.get(self.csv_url, params=param_dict)
        return r
    def get_api_state_csv(self, state):
        '''
        Save a CSV file export for a given state. Will overwrite without warning.
        '''
        r = self.get_csv_data(state)
        filename = "openpv_" + state + ".csv"
        f = open(filename, 'w')
        f.write(r.text)
        f.close()
    def get_api_all_csv(self):
        '''
        Download CSV files for all states. Will overwrite without warning.
        '''
        for state in self.states:
            self.get_api_state_csv(state)
    def insert_item_data(self, zipcode, state, size, cost, date_installed):
        # if a variable is missing, it's an empty string; set that to None instead so that it becomes NULL in the db
        zipcode = zipcode if zipcode != '' else None
        state = state if state != '' else None
        size = size if size != '' else None
        cost = cost if cost != '' else None
        date_installed = date_installed if date_installed != '' else None
        # note use of STR_TO_DATE to convert the date to the correct format
        # note also that the % for date formatting needs to be escaped
        sql = '''INSERT INTO installs (zipcode, state, size, cost, date_installed) 
            VALUES (%s, %s, %s, %s, STR_TO_DATE(%s, '%%m/%%d/%%Y'))'''
        #print(sql)
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (zipcode, state, size, cost, date_installed))
        self.connection.commit()
    def get_installs(self, state):
        sql = '''SELECT * FROM installs WHERE state = %s'''
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (state))
        results = cursor.fetchall()
        installs = pd.DataFrame(list(results), columns=['id', 'zipcode', 'state', 'size', 'cost', 'date_installed'])
        return installs
    def get_similar_installs(self, state, size):
        '''
        Return 'similar' installs based on state and size. Similar defined to be +/- 10%
        '''
        state = str(state)
        min_size = size * 0.90
        max_size = size * 1.10
        sql = '''SELECT * FROM installs WHERE state = %s AND size >= %s AND size <= %s'''
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (state, str(min_size), str(max_size)))
            results = cursor.fetchall()
        # Need to  handles when there are no results
        installs = pd.DataFrame(list(results), columns=['id', 'zipcode', 'state', 'size', 'cost', 'date_installed'])
        return installs
    def get_similar_installs_cost(self, state, size):
        pass
    def close(self):
        self.connection.close()

def main():
    openpv = OpenPV(mysql_url, mysql_db)
    
    for filename in os.listdir(openpv_data_path):
        if filename.endswith(".csv"):
            with open(os.path.join(openpv_data_path, filename)) as csvfile:
                reader = csv.reader(csvfile)
                # skip the first line, which is a header
                reader.__next__()
                for row in reader:
                    try:
                        # Don't include the last two columns which are blank
                        (zipcode, state, size, cost, date_installed) = row[:-2]
                        openpv.insert_item_data(zipcode, state, size, cost, date_installed)
                    except DataError:
                        print(row)
                        continue

if __name__ == "__main__":
    main()
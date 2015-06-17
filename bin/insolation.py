# -*- coding: utf-8 -*-
"""
Created on Thu Jun  4 11:37:11 2015

@author: gjm

This file contains the Insolation class definition.
The insolation data are obtained from http://www.nrel.gov/gis/data_solar.html
"""

import shapefile
import pymongo
import pandas as pd
import calendar

class Insolation(object):
    '''
    Return an instance of the Insolation class, which provides an interface for storing and accessing insolation (solar hours) data.
    '''
    def __init__(self):
        self.db = pymongo.MongoClient().canisolar
        # A 12-tuple of uppercase month abbreviations, which were keys in the original data
        self.month_abbrs = tuple(calendar.month_abbr[i].upper() for i in range(1,13))
    def __len__(self):
        return self.db.insolation.count()
    def populate(self, file):
        '''
        Populate MongoDB with entries consisting of a location (points comprising a polygon) and attributes (photovoltaic insolation data).
        '''
        sf = shapefile.Reader(file)
        # Records only include 15 entries, but there are 16 fields
        # Thus we exclude the first field, which is a DeletionFlag and unneeded
        keys = sf.fields[1:]
        
        for shape, record in zip(sf.shapes(), sf.records()):
            points = [list(coordinate) for coordinate in shape.points]
            loc = {"type": "Polygon", "coordinates": [points]}
            attributes = {}
            for key, value in zip(keys, record):
                # The first item of the key is the key label
                attributes[key[0]] = value
            data = {"loc": loc, "attributes": attributes}
            self.db.insolation.insert_one(data)
        self.poly_index()
    def poly_index(self):
        '''
        Create a 2dsphere index. This method is broken. Instead, create an index manually in the command line client.
        '''
        self.db.insolation.createIndex( {"loc": "2dsphere" } )
    def poly_find(self, lon, lat):
        '''
        Return a list of documents whose locations (polygons) contain the point, which was passed in as (lon, lat). Note the order of arguments.
        '''
        cursor = self.db.insolation.find( {"loc": 
            {"$geoIntersects": 
                {"$geometry": 
                    {"type": "Point", 
                    "coordinates": 
                        [lon, lat] 
                    } 
                } 
            } 
        })
        polys = [doc for doc in cursor]
        if len(polys) < 1:
            # If no polygons were found, we were probably passed a coordinate for which we don't have any data
            print("ERROR: in Insolation.poly_find(): no matching polygons found; raising ValueError.")
            raise ValueError
        if len(polys) > 1:
            print("WARNING: in Insolation.poly_find(): multiple matching polygons found; using the first.")
        return polys
    def get_insolation(self, lon, lat):
        '''
        Return a pandas DataFrame indexed by integers representing months (1-12), with insolation data in kWh / m2 / day as values
        '''
        # When there are multiple matching polygons, use the first one.
        data = self.poly_find(lon, lat)[0]
        timestamps = []
        values = []
        for key in data['attributes'].keys():
            if key in self.month_abbrs:
                # Get the numeric value of month (that is, the index in the tuple, + 1)
                month = self.month_abbrs.index(key) + 1
                timestamps.append(month)
                values.append(data['attributes'][key])
        # Since there is no year value, we use an integer index instead of a datetime object
        insolation = pd.DataFrame(list(values), index=pd.Series(timestamps), columns=["kWhpm2"])
        # Without sorting, we are not guaranteed numerical order, since the data was pulled from dictionary keys
        insolation.sort_index(inplace=True)
        return insolation

def main():
    pass
    # Uncomment the following lines to populate the database initially
    #insolation_file = "/Users/gjm/insight/canisolar/data/us9809_latilt_updated/us9809_latilt_updated"
    #insolation = Insolation()
    #insolation.populate(insolation_file)

if __name__ == "__main__":
    main()
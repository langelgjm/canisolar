# -*- coding: utf-8 -*-
"""
Created on Thu Jun  4 11:37:11 2015

@author: gjm
"""

import shapefile
import pymongo
import pandas as pd
import calendar

class Insolation(object):
    def __init__(self):
        self.db = pymongo.MongoClient().canisolar
        # A tuple of uppercase month abbreviations
        self.month_abbrs = tuple(calendar.month_abbr[i].upper() for i in range(1,13))
    def __len__(self):
        return self.db.insolation.count()
    def populate(self, file):
        '''
        Populate MongoDB with entries consisting of a location (points comprising polygon) and attributes (PV insolation data)
        '''
        sf = shapefile.Reader(file)
        # Records only include 15 entries, but there are 16 fields
        # Thus we exclude the first field, which is a DeletionFlag
        keys = sf.fields[1:]
        
        for shape, record in zip(sf.shapes(), sf.records()):
            points = [list(coordinate) for coordinate in shape.points]
            loc = {"type": "Polygon", "coordinates": [points]}
            attributes = {}
            for key, value in zip(keys, record):
                # first item of the key is the key label
                attributes[key[0]] = value
            data = {"loc": loc, "attributes": attributes}
            self.db.insolation.insert_one(data)
        self.poly_index()
    def poly_index(self):
        '''
        Not working for some reason; manually indexed in command line client
        '''
        self.db.insolation.createIndex( {"loc": "2dsphere" } )
    def poly_find(self, lon, lat):
        '''
        Return entries whose polygons contain the passed point
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
        return polys
    def get_insolation(self, lon, lat):
        '''
        Return a pandas DataFrame indexed by month, with insolation data in kWh / m2 (are these units correct?) as values
        '''
        # For now take only the first result when there are multiple matching polygons
        data = self.poly_find(lon, lat)[0]
        timestamps = []
        values = []
        for key in data['attributes'].keys():
            if key in self.month_abbrs:
                # Get numeric value of month (index in tuple + 1)
                month = self.month_abbrs.index(key) + 1
                timestamps.append(month)
                values.append(data['attributes'][key])
        #periods = pd.to_datetime(pd.Series(timestamps), format="%m")
        # Since there is no true year value, just using an integer index for now
        insolation = pd.DataFrame(list(values), index=pd.Series(timestamps), columns=["kWhpm2"])
        insolation.sort_index(inplace=True)
        return insolation

#insolation_file = "/Users/gjm/insight/canisolar/data/us9809_latilt_updated/us9809_latilt_updated"
insolation = Insolation()
#insolation.populate(insolation_file)
insolation.poly_find(-72.9211990, 41.3750700)
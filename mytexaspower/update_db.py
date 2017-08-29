import os
import sqlite3
import csv
import urllib.request

class DatabaseManager(object):
  def __init__(self, db):
    self.conn = sqlite3.connect(db)
    self.conn.execute('pragma foreign_keys = on')
    self.conn.commit()
    self.cur = self.conn.cursor()

  def query(self, query, args=''):
    self.cur.execute(query, args)
    self.conn.commit()
    return self.cur

  def querymany(self, arg, arg2):
    self.cur.executemany(arg, arg2)
    self.conn.commit()
    return self.cur

  def __del__(self):
    self.conn.close()

def update_db():
    """Updates database"""
    print("Updating database...")
    #DOWNLOADING CSV FROM POWERTOCHOOSE.ORG AND SAVING FILE
    THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
    csv_location = os.path.join(THIS_FOLDER, 'mypower.csv')

    url = 'http://www.powertochoose.org/en-us/Plan/ExportToCsv'
    urllib.request.urlretrieve(url, csv_location)

    #CONNECTING TO DB
    db_location = os.path.join(THIS_FOLDER, 'mypower.db')
    dbmgr = DatabaseManager(db_location)
    dbmgr.query("DROP TABLE IF EXISTS offers")
    dbmgr.query("DROP TABLE IF EXISTS user")

    #CREATING DB TABLE IF IT DOESN'T EXIST
    dbmgr.query("CREATE TABLE IF NOT EXISTS offers ('idKey' INTEGER, 'TduCompanyName', 'RepCompany', 'Product', 'kwh500' INTEGER, 'kwh1000' INTEGER, 'kwh2000' INTEGER, 'FeesCredits', 'PrePaid', 'TimeOfUse', 'Fixed', 'RateType', 'Renewable' INTEGER, 'TermValue' INTEGER, 'CancelFee', 'Website', 'SpecialTerms', 'TermsURL', 'Promotion', 'PromotionDesc', 'FactsURL', 'EnrollURL', 'PrepaidURL', 'EnrollPhone', 'NewCustomer', 'MinUsageFeesCredits');")

    #OPENING DOWNLOADED CSV TO SAVE IT INTO DB
    with open(csv_location, 'rt') as fin:
        imported_csv = csv.DictReader(fin) # comma is default delimiter
        to_db = [(i['[idKey]'], i['[TduCompanyName]'], i['[RepCompany]'], i['[Product]'], i['[kwh500]'], i['[kwh1000]'], i['[kwh2000]'], i['[Fees/Credits]'], i['[PrePaid]'], i['[TimeOfUse]'], i['[Fixed]'], i['[RateType]'], i['[Renewable]'], i['[TermValue]'], i['[CancelFee]'], i['[Website]'], i['[SpecialTerms]'], i['[TermsURL]'], i['[Promotion]'], i['[PromotionDesc]'], i['[FactsURL]'], i['[EnrollURL]'], i['[PrepaidURL]'], i['[EnrollPhone]'], i['[NewCustomer]'], i['[MinUsageFeesCredits]']) for i in imported_csv]

        #SAVING CSV INTO DB
        dbmgr.querymany("INSERT INTO offers ('idKey', 'TduCompanyName', 'RepCompany', 'Product', 'kwh500', 'kwh1000', 'kwh2000', 'FeesCredits', 'PrePaid', 'TimeOfUse', 'Fixed', 'RateType', 'Renewable', 'TermValue', 'CancelFee', 'Website', 'SpecialTerms', 'TermsURL', 'Promotion', 'PromotionDesc', 'FactsURL', 'EnrollURL', 'PrepaidURL', 'EnrollPhone', 'NewCustomer', 'MinUsageFeesCredits') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", to_db)

      #DELETES LAST ROW
        dbmgr.query('DELETE FROM offers WHERE "idKey"="END OF FILE";')
    #COMMITING CHANGES AND CLOSING CONNECTION
    del dbmgr
    print("Database updated")

update_db()

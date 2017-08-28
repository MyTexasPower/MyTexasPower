import json
import os
import sqlite3
import csv
import urllib.request
import click

from flask import Flask, request, session, g, redirect, make_response, url_for, abort, escape, render_template, flash
app = Flask(__name__) # create application instance
app.config.from_object(__name__) # load confi from this file, app.py

#default config
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'mypower.db'),
    SECRET_KEY= os.urandom(24)
))

app.config.from_envvar('MYPOWER_SETTINGS', silent=True) ##loads settingsi if exist, doesn't complain if they don't

def get_saved_data():
    try:
        data = json.loads(request.cookies.get('user'))
    except TypeError:
        data = {}
    return data

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

@app.route('/update/')
def init_db():
    """Initializes the database."""
    #DOWNLOADING CSV FROM POWERTOCHOOSE.ORG AND SAVING FILE
    url = 'http://www.powertochoose.org/en-us/Plan/ExportToCsv'
    urllib.request.urlretrieve(url, 'mypower.csv')

    db = get_db()
    cur = db.execute("DROP TABLE IF EXISTS offers")

    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

    #OPENING DOWNLOADED CSV TO SAVE IT INTO DB
    with open('mypower.csv', 'rt') as fin:
        imported_csv = csv.DictReader(fin) # comma is default delimiter
        t = [(i['[idKey]'], i['[TduCompanyName]'], i['[RepCompany]'], i['[Product]'], i['[kwh500]'], i['[kwh1000]'], i['[kwh2000]'], i['[Fees/Credits]'], i['[PrePaid]'], i['[TimeOfUse]'], i['[Fixed]'], i['[RateType]'], i['[Renewable]'], i['[TermValue]'], i['[CancelFee]'], i['[Website]'], i['[SpecialTerms]'], i['[TermsURL]'], i['[Promotion]'], i['[PromotionDesc]'], i['[FactsURL]'], i['[EnrollURL]'], i['[PrepaidURL]'], i['[EnrollPhone]'], i['[NewCustomer]'], i['[MinUsageFeesCredits]']) for i in imported_csv]

        #SAVING CSV INTO DB
        db.executemany("INSERT INTO offers ('idKey', 'TduCompanyName', 'RepCompany', 'Product', 'kwh500', 'kwh1000', 'kwh2000', 'FeesCredits', 'PrePaid', 'TimeOfUse', 'Fixed', 'RateType', 'Renewable', 'TermValue', 'CancelFee', 'Website', 'SpecialTerms', 'TermsURL', 'Promotion', 'PromotionDesc', 'FactsURL', 'EnrollURL', 'PrepaidURL', 'EnrollPhone', 'NewCustomer', 'MinUsageFeesCredits') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", t)

      #DELETES LAST ROW
        db.execute('DELETE FROM offers WHERE "idKey"="END OF FILE";')
    #COMMITING CHANGES AND CLOSING CONNECTION
    db.commit()
    response = make_response(redirect(url_for('index')))
    return response

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def avg_price(user_preferences):
    """Estimates monthly electric bill"""
    db = get_db()
    cur = db.execute('SELECT * FROM offers WHERE "kwh500" IS NOT NULL')
    result = cur.fetchall()

    db.execute('DROP TABLE IF EXISTS user')
    db.execute('CREATE TABLE IF NOT EXISTS user (idKey INTEGER, user_id INTEGER, avgPrice INTEGER)')
    ##import pdb; pdb.set_trace() ##added to trace how form data is handled
    usage = int(user_preferences["usage"])
    user_id = escape(session['session_id'])
    print(usage)
    cur.execute('BEGIN TRANSACTION')
    for row in result:
        kwh2000 = row[6]
        kwh1000 = row[5]
        kwh500 = row[4]
        idkey = row[0]

        if usage >= 1000:
            price = round(((usage-1000) * kwh2000) + (500 * kwh1000) + (500 * kwh500), 0)

        elif usage >= 500:
            price = round(((usage-500) * kwh1000) + (500 * kwh500), 0)

        else:
            price = round(usage * kwh500, 0)

        t = (idkey, user_id, price) ##idkey,
        db.execute('INSERT INTO user VALUES (?, ?, ?)', t)
    db.commit()

@app.route('/offers/')
def offers():
    db = get_db()
    saves = get_saved_data()
    t = (saves.get('tdu'), saves.get('contract'), saves.get('renewable'), 'FALSE')
    cur = db.execute('SELECT offers.idKey, offers.RepCompany, user.avgPrice, offers.TermValue, offers.Renewable, offers.RateType FROM offers INNER JOIN user ON offers.idKey = user.idKey WHERE offers.TduCompanyName=? AND offers.TermValue >=? AND offers.Renewable >=? AND offers.MinUsageFeesCredits = ? ORDER BY user.avgPrice ASC LIMIT 10', t)
    offers = cur.fetchall()
    return render_template('offers.html', offers=offers, saves=get_saved_data())

@app.route('/offers/<int:idKey>/')
def view_offer(idKey):
    context={'idKey': idKey}
    t = (context['idKey'], )
    db = get_db()
    cur = db.execute('SELECT offers.idKey, offers.RepCompany, offers.Product, offers.CancelFee, offers.SpecialTerms, offers.NewCustomer, offers.EnrollURL, offers.FactsURL, user.avgPrice, offers.TermValue, offers.Renewable, offers.RateType FROM offers INNER JOIN user ON offers.idKey = user.idKey WHERE offers.idKey = ? LIMIT 1', t)
    offers = cur.fetchall()
    return render_template("offer_details.html", details=offers, **context)

@app.route('/save', methods=['GET', 'POST']) ##method only accesible if your post to it
def save():
    flash("Alright: That looks great!")
    if 'session_id' in session:
        pass
    else:
        session['session_id'] = os.urandom(10)

    if request.method == 'POST':
        data = get_saved_data() #Check if a cookie already exists & retrieve it
        user_input = dict(request.form.items())
        data.update(user_input) ##If the cookie exists, only update the values that have changed
        if user_input['usage']:
            avg_price(user_input)
        response = make_response(redirect(url_for('offers'))) ##generates the response and sets it to response variable
        response.set_cookie('user', json.dumps(data)) ##builds dicts from tuple item pairs
        return response
    else:
        print("DEBUG: save() GET method was called")

@app.route('/')
def index():
    db = get_db()
    cur = db.execute('SELECT DISTINCT TduCompanyName from offers')
    tdus = cur.fetchall()
    return render_template('index.html', saves=get_saved_data(), tdus=tdus)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)

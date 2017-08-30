import csv
import json
import operator
import os
import sqlite3
import urllib.request

from flask import Flask, request, session, g, redirect, make_response, url_for, abort, escape, render_template, flash

app = Flask(__name__) # create application instance
app.config.from_object(__name__) # load confi from this file, app.py

#default config
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'mypower.db'),
    SECRET_KEY= os.urandom(24)
))

app.config.from_envvar('MYPOWER_SETTINGS', silent=True) ##loads settings if exist, doesn't complain if they don't

def get_saved_data():
    try:
        data = json.loads(request.cookies.get('user'))
    except TypeError:
        data = {}
    return data

def get_offers():
    try:
        data = json.loads(request.cookies.get('offers'))
    except TypeError:
        data = {}
    return data

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

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
    t = (user_preferences["tdu"], user_preferences["contract"], user_preferences["renewable"], 'FALSE')
    usage = int(user_preferences["usage"])

    cur = db.execute('SELECT * FROM offers WHERE TduCompanyName=? AND TermValue >=? AND Renewable >=? AND MinUsageFeesCredits = ? AND kwh500 IS NOT NULL', t)
    result = cur.fetchall()

    user_offers = {}
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

        user_offers.update({idkey: price})

    sorted_offer = sorted(user_offers.items(), key=operator.itemgetter(1))
    sorted_offer = sorted_offer[:10]
    sorted_offer = dict(sorted_offer)
    return sorted_offer

@app.route('/offers/')
def offers():
    db = get_db()
    saves = get_saved_data()
    top10 = get_offers()
    t = list(top10.keys())

    if top10:
        cur = db.execute('SELECT idKey, RepCompany, TermValue, Renewable, RateType, NewCustomer FROM offers WHERE idKey IN ({})'.format(', '.join('?' for _ in t)), t)
        offers = cur.fetchall()

        offer_list = []
        for offer in offers:
            offer_data = list(offer) + [top10[str(offer[0])]]
            offer_list.append(offer_data)

        sorted_offers = sorted(offer_list, key=operator.itemgetter(6))
        return render_template('offers.html', offers=sorted_offers, saves=saves)
    else:
        flash("Electric preferences need to be input before viewing offers")
        return redirect("/")

@app.route('/offers/<int:idKey>/')
def view_offer(idKey):
    context={'idKey': idKey}
    top10 = get_offers()

    if top10:
        t = (context['idKey'], )
        db = get_db()
        cur = db.execute('SELECT * FROM offers WHERE idKey = ? LIMIT 1', t)
        #import pdb; pdb.set_trace()
        offer = cur.fetchone()
        offer_data = list(offer) + [top10[str(offer[0])]]
        return render_template("offer_details.html", detail=offer_data, **context)
    else:
        flash("Electric preferences need to be input before viewing offer details")
        return redirect("/")

@app.route('/save', methods=['GET', 'POST']) ##method only accesible if your post to it
def save():
    if 'session_id' in session:
        pass
    else:
        session['session_id'] = os.urandom(10)

    if request.method == 'POST':
        data = get_saved_data() #Check if a cookie already exists & retrieve it
        user_input = dict(request.form.items())
        offers = avg_price(user_input)
        data.update(user_input) ##If the cookie exists, only update the values that have changed
        response = make_response(redirect(url_for('offers'))) ##generates the response and sets it to response variable
        response.set_cookie('user', json.dumps(data)) ##builds dicts from tuple item pairs
        response.set_cookie('offers', json.dumps(offers))
        return response
    else:
        print("DEBUG: save() GET method was called")

@app.route('/about/')
def about():
    return render_template('about.html')

@app.route('/')
def index():
    db = get_db()
    cur = db.execute('SELECT DISTINCT TduCompanyName from offers')
    tdus = cur.fetchall()
    return render_template('index.html', saves=get_saved_data(), tdus=tdus)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)

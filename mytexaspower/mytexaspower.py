import csv
import json
import operator
import os
import sqlite3
import urllib.request
from raven import Client

from flask import Flask, request, session, g, redirect, make_response, url_for, abort, escape, render_template, flash, send_from_directory
from passwords import SENTRY_DSN

client = Client(SENTRY_DSN) #add debugging
app = Flask(__name__, ) # create application instance
app.config.from_object(__name__) # load confi from this file, app.py

#default config
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'mypower.db'),
    SECRET_KEY= os.urandom(24)
))

app.config.from_envvar('MYPOWER_SETTINGS', silent=True) ##loads settings if exist, doesn't complain if they don't

def get_saved_data(arg):
    try:
        data = json.loads(request.cookies.get(arg))
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

def compare_renewable(arg):
    """Compares non-renewable offer to paying for a renewable plan"""
    user_preferences = get_saved_data('user')
    offer_id = arg[0]
    percent_renewable = int(arg[12])
    top_offers = get_saved_data('offers')

    if percent_renewable != 100:
        db = get_db()
        t = (user_preferences["tdu"], user_preferences["contract"], 100, 'FALSE')
        usage = int(user_preferences["usage"])

        cur = db.execute('SELECT * FROM offers WHERE TduCompanyName=? AND TermValue >=? AND Renewable >=? AND MinUsageFeesCredits = ? AND kwh500 IS NOT NULL', t)
        result = cur.fetchall()

        user_offers = {}
        for row in result:
            kwh2000 = row[6]
            kwh1000 = row[5]
            kwh500 = row[4]
            idkey = row[0]

            if usage > 1000:
                price = round(usage * kwh2000, 0)
            elif usage > 500:
                price = round(usage * kwh1000, 0)
            else:
                price = round(usage * kwh500, 0)

            user_offers.update({idkey: price})

        sorted_offer = sorted(user_offers.items(), key=operator.itemgetter(1))
        sorted_offer = sorted_offer[:1]
        sorted_offer = dict(sorted_offer)
        return sorted_offer
    else:
        return {}

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
    usage_upper = usage * 1.25

    cur = db.execute('SELECT * FROM offers WHERE TduCompanyName=? AND TermValue >=? AND Renewable >=? AND MinUsageFeesCredits = ? AND kwh500 IS NOT NULL', t)
    result = cur.fetchall()

    user_offers = {}
    for row in result:
        kwh2000 = row[6]
        kwh1000 = row[5]
        kwh500 = row[4]
        idkey = row[0]

        if usage > 1000:
            price = round(usage * kwh2000, 0)
        elif usage > 500:
            price = round(usage * kwh1000, 0)
        else:
            price = round(usage * kwh500, 0)

        ##compare to an upper price to heelp filter out bad offers
        if usage_upper > 1000:
            price_upper = round(usage_upper * kwh2000, 0)
        elif usage_upper > 500:
            price_upper = round(usage_upper * kwh1000, 0)
        else:
            price_upper = round(usage_upper * kwh500, 0)

        price_ratio = (price_upper - price)/price_upper

        ##if prices jump by 50% with an increase usage of 25% then don't consider them
        if price_ratio >= 0.50:
            pass
        else:
            user_offers.update({idkey: price})

    sorted_offer = sorted(user_offers.items(), key=operator.itemgetter(1))
    sorted_offer = sorted_offer[:10]
    sorted_offer = dict(sorted_offer)
    return sorted_offer

@app.route('/offers/')
def offers():
    db = get_db()
    saves = get_saved_data('user')
    top10 = get_saved_data('offers')
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
        flash("No offers meet your search criteria. Please update your search and try again.")
        return redirect("/")

@app.route('/offers/<int:idKey>/')
def view_offer(idKey):
    context={'idKey': idKey}
    top10 = get_saved_data('offers')
    t = (context['idKey'], )
    db = get_db()
    cur = db.execute('SELECT * FROM offers WHERE idKey = ? LIMIT 1', t)
    offer = cur.fetchone()
    try:
        offer_data = list(offer) + [top10[str(offer[0])]]
    except (TypeError, KeyError):
        flash("Electric preferences need to be input before viewing offer details")
        return redirect("/")
    else:
        r_offer = compare_renewable(offer)
        return render_template("offer_details.html", detail=offer_data, renewable=r_offer, **context)

@app.route('/save', methods=['GET', 'POST']) ##method only accesible if your post to it
def save():
    if request.method == 'POST':
        data = get_saved_data('user') #Check if a cookie already exists & retrieve it
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
    return render_template('index.html', saves=get_saved_data('user'), tdus=tdus)

@app.route('/sitemap/')
def sitemap():
    return render_template('sitemap.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def page_not_found(e):
    return render_template('500.html'), 500

@app.route('/robots.txt')
@app.route('/sitemap.xml')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

if __name__ == '__main__':
    app.run(debug=True)

from yahoo_finance import Share
from progressbar import ProgressBar
from uiautomator import *
import io
import threading
import time
import plotly.plotly as py
from plotly.graph_objs import *
from datetime import datetime
from datetime import date, timedelta

#editable
#dev_ser = '0760b4f313cc9064'   #device serial number (Fuller's nexus)
dev_ser = 'HT478WS01096'        #device serial number (SLG test phone)
price_limit = 1.0               #max price per share to buy
current_money = 1.0             #amount of money you have
max_investment_per_comp = 1.0   #max money to spend on shares for any given company
TESTMODE = True                 #does not buy/sell only report
gather_time_ms = 10             #frequency of the gathering (milliseconds)
sample_time_ms = 30*60*1000     #sample_time = max_samples * gather_time_in_s
graph_density = 100             #higher number is less dense
long_moving = 15                #moving avg (200)
short_moving = 5                #moving avg (15)
#####

def format_date(year, month, day):
    return str(year) + '-' + str(month) + '-' + str(day)

class Company:
    def __init__(self, c, n):
        self.code = c
        self.name = n
        self.prices = []
        self.owned_shares = 0
        self.bought_value = -1.0

    def plot(self):
        x = range(0,max_samples%graph_density)
        y = self.prices[::graph_density]
        trace = Scatter(x=x,y=y)
        data = Data([trace])
        plot_url = py.plot(data, filename=self.code)
        print plot_url
        return

    def how_many_shares_to_buy(self, share_price):
        # buy up to max price limit
        buy_count = int((max_investment_per_comp - self.bought_value) / share_price)
        total_cost = buy_count * share_price
        # do not take more than you can afford
        if total_cost >= current_money:
            original_buy_count = buy_count
            buy_count = int(current_money / share_price)
            print 'WARNING: ('+self.code +') Cannot buy amount wanted (' + original_buy_count + ') because not enough money, getting (' + buy_count + ') instead!'
        print '\t('+self.code +') Calculated buy amount: ' + buy_count + ' @ ' + share_price + '/share.  Total: ' + buy_count * share_price
        return buy_count

    def is_enough_data_to_trade(self):
        return self.get_long_moving_avg() != 0

    def get_high(self):
        return max(self.prices)
    def get_low(self):
        return min(self.prices)

    def get_short_moving_avg(self):
        now = datetime.now()
        '''if TESTMODE:
            e_date = format_date(now.year, now.month, now.day)
            prevnow = now - timedelta(days=short_moving)
            b_date = format_date(prevnow.year, prevnow.month, prevnow.day)
            histories = Share(self.code).get_historical(b_date, e_date)
            avg = 0
            for hist in histories:
                if not 'Close' in hist:
                    print 'Warning: NO CLOSE DEFINED FOR: ' + self.code
                    continue
                avg += float(hist['Close'])
            return avg / short_moving
        else:'''
        shortavg = Share(self.code).get_50day_moving_avg()
        if shortavg is None:
            return None
        return float(shortavg)

    def get_long_moving_avg(self):
        now = datetime.now()
        ''' if TESTMODE:
            e_date = format_date(now.year, now.month, now.day)
            prevnow = now - timedelta(days=long_moving)
            b_date = format_date(prevnow.year, prevnow.month, prevnow.day)
            histories = Share(self.code).get_historical(b_date, e_date)
            avg = 0
            for hist in histories:
                avg += float(hist['Close'])
            return avg / long_moving
        else:'''
        longavg = Share(self.code).get_200day_moving_avg()
        if longavg is None:
            return None
        return float(longavg)

    def fill_historical(self):
        #probs doesn't work
        #map real time space
        day = str(int(datetime.now().second / 2))
        month = str(int(datetime.now().minute / 4))
        if len(month) == 1:
            month = '0' + month
        if len(day) == 1:
            day = '0' + day
        s_date = '2014-' + month + '-' + day
        
        #for testing, get historical
        histories = Share(self.code).get_historical(s_date, s_date)
        return
    
    def gather(self):
        share = Share(self.code)
        price = share.get_price()
        if price is None:
            print 'Company ' + self.code + ' gave no price'
            return
        self.prices.append(float(price))
        return

    # returns the number to buy
    def check_buy(self):
        #one-time buy
        if self.owned_shares != 0:
            return False
        share = Share(self.code)
        avg50 = self.get_short_moving_avg()
        avg200 = self.get_long_moving_avg()
        if avg50 > avg200:
            #trend change, buy
            buy_count = self.how_many_shares_to_buy(share.price)
            if buy_count != 0:
                if buy(self, buy_count) == True:
                    self.owned_shares = buy_count
                    self.bought_value = float(share.get_price() * self.owned_shares)
            return self.owned_shares
        return 0

    def check_sell(self):
        #UNCOMMENT WHEN USING ACTUAL DATA
        #if self.owned_shares == 0:
        #    return False
        share = Share(self.code)
        #UNCOMMENT WHEN USING ACTUAL DATA
        #if self.bought_value < float(share.get_price()):
        #    return False
        avg50 = self.get_short_moving_avg()
        avg200 = self.get_long_moving_avg()
        if avg50 < avg200:
            #trend change, buy
            sell(self, self.owned_shares)
            return True
        return False

#filtered by price limit
companies = []

def LoadPreBake(file_name):
    file = open(file_name, 'r')
    lines = file.readlines()

    for line in lines:
        if line == '':
            return
        tokens = line.split(',', 1)
        comp = Company(tokens[0].strip(), tokens[1].strip())       
        companies.append(comp)
    print 'Loaded in: ' + str(len(companies)) + ' companies'
    
    return

def LoadCSV(file_name):
    file = open(file_name, 'r')
    lines = file.readlines()

    for line in lines:
        if line == '':
            return
        tokens = line.split(',', 1)

        comp = Company(tokens[0].strip(), tokens[1].strip())
        comp_stock = Share(comp.code)
        if comp_stock is None:
            print(comp.name + ' is not in yahoo db')
            continue
        price = comp_stock.get_price()

        if price is None:
            continue
        price = float(price)
      
        if price < price_limit:
            companies.append(comp)
            print(comp.code + ',' + comp.name)
    return

def LoadOwned():
    file = open(file_name, 'r')
    lines = file.readlines()

    for line in lines:
        if line == '':
            return
        tokens = line.split(',', 1)

        code = tokens[0].strip()
        shares = int(tokens[1])
        for comp in companies:
            if comp.code == code:
                print 'Loaded: ' + code + ' with ' + shares + ' shares'
                comp.owned_shares = shares                

    return

def gather_prices():
    for comp in companies:
        comp.gather()
    return

def check_buy_sell():
    for comp in companies:
        comp.check_sell()
        comp.check_buy()
    return

def determine_buy():
    return

def return_menu():
    # for i in range(0,3):
    device.click(40,40)
    time.sleep(1)
    device.click(40,40)
    return

def buy(comp, num_to_buy):
    if comp.is_enough_data_to_trade() == False:
        print 'Purchase of ' + comp.code + ' skipped b/c not enough data to evaluate'
        return
    if search(comp.code) == True:
        if not TESTMODE:
            device(className='android.widget.ScrollView').scroll.to(textContains='BUY')
            device(textContains='BUY').click()
            time.sleep(1)
            device(focused=True).set_text(str(num_to_buy))
            device(resourceIdMatches ="com.robinhood.android:id/review_order_btn").click()
            time.sleep(2)
            #device.swipe(100,200,100,-100, steps=100)
        else:
            print '[TEST MODE]'
        print 'Bought ' + comp.code + ' for ' + Share(comp.code).get_price() + ' ratio: ' + str(comp.get_short_moving_avg() / comp.get_long_moving_avg())
    return_menu()
    return

def sell(comp, num_to_sell):
    if search(comp.code) == True:
        if not TESTMODE:
            device(className='android.widget.ScrollView').scroll.to(textContains='SELL')
            device(textContains='SELL').click()
            time.sleep(1)
            device(focused=True).set_text(str(num_to_sell))
            device(resourceIdMatches ="com.robinhood.android:id/review_order_btn").click()
            time.sleep(2)
            #device.swipe(100,200,100,-100, steps=100)
        else:
            print '[TEST MODE]'
        print 'Sold ' + comp.code + ' for ' + Share(comp.code).get_price()
    return_menu()
    return

def connect():
    #connect
    device = Device(dev_ser)
    if device is None:
        print 'failed to connect to device'
        exit(0)
    print('device connected')
    if 'com.robinhood.android' in device.info[3]:
        print('robinhood not open')
        exit(0)
    return

#do not call directly - use buy/sell
def search(code):
    # click randomly to gain focus
    device.click(100,20)
    #search
    search_for = code.lower()
    search_button = device(descriptionContains = 'search')
    search_button.click()
    
    search_box = device(className='android.widget.EditText')
    search_box.set_text(search_for)
    time.sleep(1)
    print 'search: ' + code
    #device.press.enter()
    search_box.set_text(search_for)
    time.sleep(1)
    result = device(text=search_for.upper())
    try:
        result.click()
    except JsonRPCError:
        print 'Stock not found: ' + code
        return False
    time.sleep(1)
    return True

    
#load nasdaq and nyse, load if under < price_limit
print('Loading...')
#LoadCSV('nasdaq.csv')                
#LoadCSV('nyse.csv')
LoadPreBake('pennies.csv')
print('...Done Loading')

if False:
    #store all stock prices
    print '---Outsider Ready---'
    while True:
        check_buy_sell()
        gather_prices()
        time.sleep(float(gather_time_ms))
        print '.'
else:
    print '---Manual Mode---'



    



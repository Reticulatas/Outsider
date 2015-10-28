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
import simplejson
import os.path

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

#do not edit
money_gained_this_session = 0.0 #do not modify, money made this session
requests_made = 0               # yahoo api limits requests to 2k /hour for public, 20k /hour for oAuth'ed
request_limit = 2000            # yahoo api limit max
stock_refresh_time = 2          # time in seconds from last access that a stock should be refreshed
####


def format_date(year, month, day):
    return str(year) + '-' + str(month) + '-' + str(day)

def add_request():
    global requests_made
    requests_made += 1
    if requests_made > request_limit:
        print('Too many requests to yahoo api, sleeping for an hour...')
        time.sleep(60*60)
        requests_made = 0
        print('...Resumed from sleep.')
    if requests_made % 100:
        print('NOTICE: ' + str(requests_made) + ' requests made (limit ' + str(request_limit) + ')')
    return

class Company:
    def __init__(self, c, n):
        self.code = c               # ticker
        self.name = n               # friendly name
        self.prices = []            # gather data
        self.owned_shares = 0       # quantity of owned shares
        self.bought_value = 0       # invested
        self.share = Share(self.code) # share object
        self.lastAccess = time.time()

    # Every access to self.share must be prefixed with this call
    def verify_share(self):
        global requests_made
        if time.time() - self.lastAccess > 2:
            self.lastAccess = time.time()
            self.share.refresh()
            add_request()
        return

    def log(self, msg):
        print('\t('+self.code+') '+msg)

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
            self.log('WARNING: Cannot buy amount wanted (' + str(original_buy_count) + ') because not enough money, getting (' + str(buy_count) + ') instead!')
        self.log('Calculated buy amount: ' + str(buy_count) + ' @ ' + str(share_price) + '/share.  Total: ' + str(buy_count * share_price))
        return buy_count

    def is_enough_data_to_trade(self):
        return self.get_long_moving_avg() != 0

    def get_high(self):
        return max(self.prices)
    def get_low(self):
        return min(self.prices)

    def get_short_moving_avg(self):
        self.verify_share()
        try:
            shortavg = self.share.get_50day_moving_avg()
        except:
            return -1.0
        if shortavg is None:
            return None
        return float(shortavg)

    def get_long_moving_avg(self):
        self.verify_share()
        try:
            longavg = self.share.get_200day_moving_avg()
        except:
            return -1.0
        if longavg is None:
            return None
        return float(longavg)

    def fill_historical(self):
        self.verify_share()
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
        histories = self.share.get_historical(s_date, s_date)
        return
    
    def gather(self):
        price = self.get_price()
        if price is not None:
            self.prices.append(price)
        return

    def get_price(self):
        self.verify_share()
        try:
           price_u = self.share.get_price()
           if price_u is None:
               self.log('Company gave no price')
               return None
           price = float(price_u)
        except:
            self.log('ERROR: Failed to retrieve price due to internal yahoo API error')
            return None
        return price
    
    # returns the number to buy
    def check_buy(self):
        global current_money
        #one-time buy
        if self.owned_shares != 0:
            return False
        avg50 = self.get_short_moving_avg()
        avg200 = self.get_long_moving_avg()
        if avg50 == -1.0 or avg200 == -1.0:
            self.log('Short or Long moving average cannot be obtained due to yahoo API error')
            return 0
        
        current_price = self.get_price()
        if current_price is None:
            return False;
        
        if avg50 > avg200:
            #trend change, buy
            buy_count = self.how_many_shares_to_buy(current_price)
            if buy_count != 0:
                if buy(self, buy_count, current_price) == True:
                    self.owned_shares += buy_count
                    self.bought_value += float(current_price * self.owned_shares)

                    # reduce our money and re-save the config
                    current_money -= current_price * buy_count;
                    SaveConfig()
                    
            return self.owned_shares
        return 0

    def check_sell(self):
        global money_gained_this_session

        current_price = self.get_price()
        if current_price is None:
            return False;
        
        #UNCOMMENT WHEN USING ACTUAL DATA
        if self.bought_value >= current_price * self.owned_shares:
            return False

        #UNCOMMENT WHEN USING ACTUAL DATA
        if self.owned_shares == 0:
            self.log("Would have sold this stock, but none were owned")
            return False
        
        avg50 = self.get_short_moving_avg()
        avg200 = self.get_long_moving_avg()
        if avg50 < avg200:
            #trend change, buy
            if sell(self, self.owned_shares,current_price) == True:
                money_gained = self.owned_shares * current_price - self.bought_value
                self.log('Pending execution order. Return: ' + str(money_gained))
                money_gained_this_session += money_gained
                print('--Money Gained This Session: ' + str(money_gained_this_session) + ' --')
                self.owned_shares = 0
                self.bought_value = 0
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

def TryAddCompany(code, name):
    comp = Company(code, name)
    comp_stock = Share(comp.code)
    if comp_stock is None:
        print(comp.name + ' is not in yahoo db')
        return False
    price = comp_stock.get_price()

    if price is None:
        return False
    price = float(price)
      
    if price < price_limit:
        companies.append(comp)
        print(comp.code + ',' + comp.name)
        return True
    return False

def LoadCSV(file_name):
    file = open(file_name, 'r')
    lines = file.readlines()

    for line in lines:
        if line == '':
            return
        tokens = line.split(',', 1)

        TryAddCompany(tokens[0].strip(), tokens[1].strip())
    return

def LoadOwned(file_name='owned_stocks.ini'):
    file = open(file_name, 'r')
    lines = file.readlines()

    for line in lines:
        if line == '':
            return
        if '#' in line:
            continue
        tokens = line.split(',', 2)

        code = tokens[0].strip()
        shares = int(tokens[1].strip())
        invested = float(tokens[2].strip())
        found = False
        for comp in companies:
            if comp.code == code:
                print 'Loaded: ' + code + ' with ' + str(shares) + ' shares'
                comp.owned_shares = shares
                comp.bought_value = invested
                found = True

        if found == False:
            print('Company owned but not in db: ' + code + ' with ' + str(shares) + ' shares')
    return

# put owned shares in file to load back later
def DumpOwned(file_name='owned_stocks.ini'):
    file = open(file_name, 'w')

    print('Dumping owned shares to ' + file_name)

    file.write('#CODE,SHARES')

    dumped = 0
    for comp in companies:
        if comp.owned_shares != 0:
            file.write(comp.code + ',' + comp.owned_shares + '\n')
            dumped += 1

    file.write(' ')
    print('\tDumped: ' + str(dumped) + ' shares')
    return

def LoadConfig(file_name='config.ini'):
    global price_limit, current_money, max_investment_per_comp, TESTMODE
    if not os.path.isfile(file_name):
        SaveConfig(file_name)
    
    file = open(file_name, 'r')
    json = file.read()
    
    configStruct = simplejson.loads(json)

    price_limit = configStruct["price limit"];
    current_money = configStruct["current money"];
    max_investment_per_comp = configStruct["max investment per comp"];
    TESTMODE = configStruct["TEST MODE"];

    print 'Config Loaded.'
    print '\tPrice Limit:\t ' + str(price_limit)
    print '\tCurrent Money:\t ' + str(current_money)
    print '\tMax Investment Per Comp: ' + str(max_investment_per_comp)
    print '\tTest Mode:\t ' + str(TESTMODE)
    return

def SaveConfig(file_name='config.ini'):
    configStruct = { "price limit" : price_limit,\
                     "current money" : current_money,\
                     "max investment per comp" : max_investment_per_comp,\
                     "TEST MODE" : TESTMODE,\
                }
    json = simplejson.dumps(configStruct, indent=4)
    file = open(file_name, 'w')
    file.write(json)

    print 'Config Saved'    
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

def return_menu():
    while not device(resourceIdMatches="com.robinhood.android:id/notification_header_btn").exists:
        device.click(40,40)
        time.sleep(1)
    print 'UI returned to main menu'
    return

def buy(comp, num_to_buy, price):
    if comp.is_enough_data_to_trade() == False:
        print 'Purchase of ' + comp.code + ' skipped b/c not enough data to evaluate'
        return False
    if search(comp.code) == True:
        if not TESTMODE:
            device(className='android.widget.ScrollView').scroll.to(textContains='BUY')
            device(textContains='BUY').click()
            time.sleep(1)
            device(focused=True).set_text(str(num_to_buy))
            device(resourceIdMatches ="com.robinhood.android:id/review_order_btn").click()
            time.sleep(2)
            device.swipe(100,200,100,-100, steps=100)
        else:
            print '[TEST MODE]'

        # output result
        print 'Bought ' + str(num_to_buy) + 'x' + comp.code + ' for ' + str(price) + ' ratio: ' + str(comp.get_short_moving_avg() / comp.get_long_moving_avg()) + ' Total: ' + str(price * num_to_buy)
        return_menu()
        return True
    return_menu()
    return False

def sell(comp, num_to_sell, price):
    if search(comp.code) == True:
        if not TESTMODE:
            device(className='android.widget.ScrollView').scroll.to(textContains='SELL')
            device(textContains='SELL').click()
            time.sleep(1)
            device(focused=True).set_text(str(num_to_sell))
            device(resourceIdMatches ="com.robinhood.android:id/review_order_btn").click()
            time.sleep(2)
            device.swipe(100,200,100,-100, steps=100)
        else:
            print '[TEST MODE]'
        print 'Sold ' + str(num_to_sell) + 'x' + comp.code + ' for ' + str(price * num_to_sell)
        return_menu()
        return True
    return_menu()
    return False

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
LoadOwned()
LoadConfig()
print('...Done Loading')

if True:
    #store all stock prices
    print '---Outsider Ready---'
    while True:
        check_buy_sell()
        gather_prices()
        time.sleep(float(gather_time_ms))
        print '.'
else:
    print '---Manual Mode---'



    



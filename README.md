# Outsider
Robinhood automated trader

[![Build Status](https://travis-ci.org/Reticulatas/Outsider.svg?branch=master)](https://travis-ci.org/Reticulatas/Outsider)

## Dependencies:

See Requirements.txt for pip-installable dependencies.  

    pip install -r requirements.txt

You also need android sdk for adb and the appropriate drivers for your phone.  Phone must be in developer mode.

## Config.ini - Set Money Settings:

    {
        "current money": 0.12,
        "TEST MODE": true,
        "price limit": 1.0,
        "max investment per comp": 1.0
    }
    
    CORRELATE TO:
    
    price_limit = 1.0               #max price per share to buy
    current_money = 1.0             #amount of money you have
    max_investment_per_comp = 1.0   #max money to spend on shares for any given company
    TESTMODE = True                 #does not buy/sell only report
    
## Setup your Device

Figure out your serial # for your phone and set it in the script at:

    dev_ser = 'HT473WS01096'        #device serial number

## Setup Owned Stocks (Optional)

If you'd like to append stocks you currently own, add them to owned_stocks.ini in the format  

*CODE,# OF SHARES*  

One per line.

## Saving after use

When running in shell, press Ctrl-C to stop execution when done. Then type:  

SaveConfig()  

*and*  

DumpOwned()  


## Adding Stocks

Only the stocks in pennies.csv are loaded as they are 'safe' small stocks.


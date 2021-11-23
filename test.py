from numpy import NaN
import pandas as pd
from pandas.io.parsers import read_csv
from requests.api import get
import  yfinance as yf 
import alpaca_trade_api as tradeapi
from yfinance.utils import auto_adjust
from result import Result
import os
import datetime
from urllib.parse import urlparse, parse_qs
import pandas_datareader as pdr

def undone():
    filePath = "data/VP50%last4year.csv"
    df = pd.read_csv(filePath)
    df["done"]=False
    df.to_csv(filePath,index=False)
    print(df)


def checkdatayf(date,ticker):
    print("this is for YF")
    company = yf.Ticker(ticker) 
    hist = company.history(period="4y",interval="1wk",start = date,back_adjust=True)  
    print(hist)
    return hist

def checkdataAlpaca(trade_Date,ticker):
    print("this is for alpaca")
    key = getApiKey()
    alpaca_api = tradeapi.REST(key["PUBLIC_KEY"],key["SECRET_KEY"],key["END_POINT"])
    twoweeksago=(datetime.date.today()-datetime.timedelta(days=14)).strftime('%Y-%m-%d') 
    barset = alpaca_api.get_bars([ticker], "5Day", start =trade_Date, end= twoweeksago, adjustment="all",limit=53).df
    barset.index = pd.to_datetime(barset.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
    print(barset)
    return barset
def checkdata(trade_Date,ticker):
    checkdatayf(trade_Date,ticker)
    checkdataAlpaca(trade_Date,ticker)
def getApiKey():
        key_file = "key/alpaca_keys.txt"
        with open(key_file,"r") as f:
                line= f.read().strip().split(" ")
                API_KEY,SECRET_KEY,END_POINT=line 
        return {"PUBLIC_KEY":API_KEY,"SECRET_KEY":SECRET_KEY,"END_POINT":END_POINT}

def checkcompanyinAlpaca(companyName):
    key = getApiKey()
    alpaca_api = tradeapi.REST(key["PUBLIC_KEY"],key["SECRET_KEY"],key["END_POINT"])
    assets = alpaca_api.list_assets()
    specificCompany = [x for x in assets if x.name == companyName]
    print(specificCompany)

def checksymbolinAlpaca(symbol):
    key = getApiKey()
    alpaca_api = tradeapi.REST(key["PUBLIC_KEY"],key["SECRET_KEY"],key["END_POINT"])
    assets = alpaca_api.list_assets()
    specificCompany = [x for x in assets if x.symbol == symbol]
    print(specificCompany)

def dropcolumn(path,col):
    df=read_csv(path)
    del df[col]
    df.to_csv(path,index=False)

def cleanup(df):
        #drop those without price or no 2week data
        df=df.dropna(axis=0,subset=["Ticker"])
        df = df[df["Price"]!=0]
        df = df.loc[df["2w"]!=0]
        print("----------------------------------------------------------------------------------------")
        return df
def getApiKey():
        try:
            key_file = "key/alpaca_keys.txt"
            with open(key_file,"r") as f:
                    line= f.read().strip().split(" ")
                    API_KEY,SECRET_KEY,END_POINT=line 
            return {"PUBLIC_KEY":API_KEY,"SECRET_KEY":SECRET_KEY,"END_POINT":END_POINT}
        except:
            return {}
def isgrouped(url)->bool:
        o = urlparse(url)
        query = parse_qs(o.query)
        return query["grp"][0]=="2"


def getinsider(df,file):
    df = read_csv(file)
    df =df.sort_values(by=["Ticker","4m%"],ascending=False)
    onecompany = df.drop_duplicates(subset=["Ticker"],keep="first")
    onecompany = onecompany[onecompany["6m%"]!=0]
    tickers = onecompany["Ticker"].tolist()
    amount_of_insiders = {ticker: 0 for ticker in tickers}
    for ticker in tickers:
        amount_of_insiders[ticker] = df.loc[df["Ticker"]==ticker]["done"].sum()
    amount_of_insiders = {k: v for k, v in sorted(amount_of_insiders.items(), key=lambda item: item[1],reverse=True)}

    returns =[]
    for ticker, num in amount_of_insiders.items():
        bestreturn = onecompany[onecompany["Ticker"]==ticker].iloc[0]["4m%"]
        print(f"for Ticker {ticker},number of insider is {num}, the best return after 4m is: {bestreturn}%")
        returns.append(bestreturn)
import warnings
# warnings.filterwarnings("ignore")

import threading
def getsomedata():
    tickers = ["CBL","AAPL"]
    df = pdr.yahoo.daily.YahooDailyReader(tickers, start='2021-10-10', end='2021-11-22',interval="d",adjust_price=True).read()
    df.index = pd.to_datetime(df.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
    print(df)
    for i in tickers:
        indivisualdf = df[("Open",i)].dropna()
        if(indivisualdf.empty):
            continue
    print("DONE!")
    print(df)
def getsomedata2():
    tickers =['AAPL',"MSFT","FB","TSLA","OSN","GOOG"]
    df = pdr.yahoo.daily.YahooDailyReader(tickers, start='2017-01-01', end='2021-09-28',interval="w",adjust_price=True).read()
    df.index = pd.to_datetime(df.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
    print(df)
    for i in tickers:
        indivisualdf = df[("Open",i)].dropna()
        if(indivisualdf.empty):
            print("data not found")
            continue
        # print(indivisualdf.index.values[0], indivisualdf.iloc[0])
    print("DONE! with r2")

import time

class a:
    value = 10
    def __init__(self) -> None:
        pass   

    def count(self):
        while True:
            print(self.value)
            time.sleep(1)
    def startthread(self):
        t1 = threading.Thread(target=self.count)
        t1.start()
def validateAlapcaDF(df):
        if len(df)==0:
            return False
        consecutive =0
        #sometimes the stock have off days with 0 volume, but if its not consequtive them its fine
        last_date = df.index.values[0]
        print(last_date)
        for i,row in df.iterrows():
            print(i)
            if(not within10days(i,last_date)):
                return False
            if row.volume==0:
                consecutive+=1
                if(consecutive==2):
                    print(df.loc[df.volume==0])
                    return False
            last_date = i
            consecutive-=1
        return True

def within10days(givendate,tradeDate):
        givendate = str(givendate).split("T")[0]
        #modify it so taht alpaca df can use it too
        givendate = str(givendate).split(" ")[0]
        if(givendate==tradeDate):
            return True
        year,month,day = map(int,givendate.split("-"))
        givendate = datetime.date(year,month,day)
        year,month,day = map(int,tradeDate.split("-"))
        tradeDate = datetime.date(year,month,day)
        margin = datetime.timedelta(days = 10)
        return givendate - margin <= tradeDate <= givendate + margin
a= "adbcsdf"
print(a[-5:])
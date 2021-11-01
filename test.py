from numpy import NaN
import pandas as pd
from pandas.io.parsers import read_csv
from requests.api import get
from DataGetter import DataGetter
from scrapper import Scrapper
import  yfinance as yf 
import alpaca_trade_api as tradeapi
from result import Result
def undone():
    filePath = "data/VP50%last4year.csv"
    df = pd.read_csv(filePath)
    df["done"]=False
    df.to_csv(filePath,index=False)
    print(df)
def checkdata(ticker,date):
    company = yf.Ticker(ticker) 
    hist = company.history(period="4y",interval="1wk",start = date)  
    print(hist)
    return hist


def cleanup(df):
        #drop those without price or no 2week data
        df=df.dropna(axis=0,subset=["Price"])
        df = df[df["Price"]!=0]
        df = df.loc[df["2w"]!=0]
        print("----------------------------------------------------------------------------------------")
        return df




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



# r = Result()
# r.getPositive(ticker)
# r.getAVG(df)
# print(df)
# print(round(12.76523,2))

# step = {"Price":0,"2w":2,"1m":4,"4m":16,"6m":24,"1yr":48,"2yr":96}


# getter = DataGetter()

# getter = DataGetter()
# keys = getter.getApiKeys()
# api = tradeapi.REST(keys[0]["apikey"],keys[0]["secretkey"],keys[0]["endpoint"])
# barset = api.get_barset('OCN', '1D', limit=507,after="{}T09:30:00-04:00".format("2020-08-01"))["OCN"]
# print(barset)
















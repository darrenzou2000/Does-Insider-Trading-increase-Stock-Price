import datetime
from sys import platform
#this allows me to query multiple tickers at once rather than rely on yf which only gives me one
import pandas_datareader as pdr
import os
import alpaca_trade_api as tradeapi
import pandas as pd
import scrapper as Scrapper
import time
import warnings
import threading
import re
warnings.filterwarnings("ignore")
class DataGetter():
    def __init__(self) -> None:
        self.timeframe = Scrapper.TimeFrame()
        self.key = self.getApiKey()
        self.api= tradeapi.REST(self.key["PUBLIC_KEY"],self.key["SECRET_KEY"],self.key["END_POINT"])
        #since I can query multiple data from YF, I need to keep a list just for YF
        self.yfList = []
        self.Threads = []
        self.yfLimitHit = False
        self.count =0
        self.regex = re.compile('[^a-z]')
        return

    def update(self,scrapper):
        self.scrapper = scrapper
        self.data = scrapper.get_data()
        dfSize = len(self.data)
        self.getCorrectStockTicker()
        #save the correct sticker progress
        self.to_csv()
        rowGroup = []
        for _,row in self.data.iterrows():
            self.count+=1
            #this if statment is here so that in case the update is inturrupted, this doesnt start from beginning
            if(bool(row["done"])):
                continue
            rowGroup.append(row)
            #alapca allows multiple tickers be queried at once so I will do one api call every 10 rows
            if(len(rowGroup)<20 and (dfSize-self.count)>19): 
                continue
            tickers= self.getTickersFromGroup(rowGroup)
            # print(f"currently doing {tickers}, on {count} out of {self.scrapper.size()}")
            self.getPriceAtTimeBrought(rowGroup,tickers) 
            self.getWeeklyDataFromRowGroup(rowGroup,tickers)
            rowGroup.clear() 
            self.to_csv()
        print("WAITING FOR YF TO FINISH")
        for i in self.Threads:
            i.join()
        #do the rest
        if(len(self.yfList)>0):
            self.queueStockForYF(doTheRest=True)
        self.updatepercentChange(self.data)  
        self.cleanup()
        self.to_csv()
        print("done, all data is updated to",scrapper.csvFilePath)
        return scrapper


    def to_csv(self):
        self.scrapper.data = self.data
        self.scrapper.to_csv()

    def getWeeklyDataFromRowGroup(self,rowGroup,tickers):
        lastrow = rowGroup[-1]
        startDate=lastrow.Trade_Date
        twoweeksago=(datetime.date.today()-datetime.timedelta(days=14)).strftime('%Y-%m-%d')
        if(startDate>twoweeksago):
            twoweeksago=startDate 
        #this is now weekly data, the timeframe is 5day
        alpacaDF = self.api.get_bars(tickers,timeframe="5Day",start=startDate, end=twoweeksago,adjustment="all").df
        for row in rowGroup:
            idx = row.idx
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"]==row.Ticker]
                self.getWeeklyDataFromAlpacaDF(indivisualDF,row)
            except IndexError:
                continue
            except KeyError:
                continue
            except Exception as e:
                errorType = type(e)
                print(f"Error {e} at index {idx} FOR getWeeklyDataFromRowGroup type {errorType}")
                self.data.loc[self.data.idx==idx,"skip"]=True

    def getWeeklyDataFromAlpacaDF(self,alpacaDF,row):
        idx = row.idx
        trade_date = row.Trade_Date
        offset = 0
        self.data.loc[self.data.idx==idx,"done"]=True
        #this means that YF already checked it
        twoweekdata =self.data.loc[self.data.idx==idx,"2w"]
        if(float(twoweekdata)!=0.0):
            return
        #getting offset because the start date is based on the earlist stock's trade date in the row group, that might be serveral weeks before this 
        for timestamp, row in alpacaDF.iterrows():
            timestamp=str(timestamp).split(" ")[0]
            if(trade_date>timestamp):
                offset+=1
            else:
                break
            #this returns {"2w":2, "1m":4}etc
        lableAndweeknum = self.timeframe.getWeekDict()
        try:
            for timeframe,numofweek in lableAndweeknum.items():
                priceAtTimeFrame = alpacaDF.iloc[int(numofweek)+offset].open
                self.putDataIntoDF(priceAtTimeFrame,idx,timeframe)
        except IndexError:
            return
        except Exception as e:
            print("error:",e , "at index",idx,"For getWeeklyDataFromAlpacaDF")   
    #this function takes the list of rows and their tickers, then trys to get data from the time brought
    def getPriceAtTimeBrought(self,rowGroup,tickers):
        lastrow = rowGroup[-1]
        startDate,endDate=self.getStartAndEndDate(lastrow.Trade_Date)
        alpacaDF = self.api.get_bars(tickers,timeframe="1Day",start=startDate, end=endDate,adjustment="all").df
        for row in rowGroup:
            ticker = row.Ticker
            trade_date = row.Trade_Date
            idx = row.idx
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"]==ticker]
            except:
                self.queueStockForYF(row)
                continue
            #if symbol doesnt exist on alpaca, check yahoo finance
            if(indivisualDF.empty):
                #yahoo finance already gets all the 2week/months data, so no need to query data about it again
                self.queueStockForYF(row)
                continue
            else:
                priceWhenBrought = self.getTradePriceWhenBrought(trade_date,indivisualDF,row)
                if(priceWhenBrought==None):
                    self.queueStockForYF(row)
                    continue
                print(f"Price of {ticker} when brought is {priceWhenBrought}, Currently {self.count} out of {len(self.data)}")
                self.data.loc[self.data.idx==idx,"Price"]=priceWhenBrought
    
                # print(f"for {ticker} the price brought at was {priceWhenBrought} at {trade_date}")

    #this puts the tickers in a list for YF to query all at once
    def queueStockForYF(self,row=pd.Series([]),doTheRest = False):
        if(not row.empty):
            self.yfList.append(row)
            idx = row.idx
            #skip those that are done, or are marked as skip(marked as skip means no stock data is found
            if(self.data.loc[self.data.idx==idx].iloc[0].done or self.data.loc[self.data.idx==idx].iloc[0].skip ):
                return
        #start quering at 20 stock, or do the rest at the end,
        if(self.yfLimitHit):
            print("Sorry but the data limit on yahoo finance is hit (about 2000 entires), please reselect the entry after about 20 minutes")
            quit()
        if(len(self.yfList)==20 or doTheRest):
            #use threading to get yf data cus it takes FOREVER
            tickers = self.getTickersFromGroup(self.yfList,False)
            print(tickers, "is put into threading")
            thread = threading.Thread(target=self.getweeklyDataFromYF) 
            thread.start()
            self.Threads.append(thread)
    
    #apprently "Perma-fix" and "Perma fix" are not the same thing!
    def stripNonAlpabet(self,string):
        #regex is only lowercase a-z
        return self.regex.sub("",string)
    def getweeklyDataFromYF(self) -> None:

            if(self.yfLimitHit):
                return
        #start date is the trade date of the last row in this group because that is the earliest
            lastrow = self.yfList[-1]
            startDate=lastrow.Trade_Date
            twoweeksago=(datetime.date.today()-datetime.timedelta(days=14)).strftime('%Y-%m-%d')
            if(startDate>twoweeksago):
                twoweeksago=startDate  
            tickers = self.getTickersFromGroup(self.yfList,asOneString=False)
            rowGroup= self.yfList
            self.yfList.clear()
            try:
                weeklystockDataForAllStockInList = pdr.yahoo.daily.YahooDailyReader(tickers, start=startDate, end=twoweeksago,interval="w",adjust_price=True).read()
            except:
                print("Sorry, but this query takes too much searches and Yahoo has blocked furthur searches, please wait like 10 minutes to try again")
                self.yfLimitHit = True
            weeklystockDataForAllStockInList.index = pd.to_datetime(weeklystockDataForAllStockInList.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
            for row in rowGroup:
                ticker = row.Ticker
                #this will filter the DF into just the column of the Open price of each company
                try:
                    indivisualdf = weeklystockDataForAllStockInList[("Open",ticker)].dropna()
                except:
                    indivisualdf = pd.DataFrame()
                self.inputYFDataIntoDF(indivisualdf,row)
            
    def inputYFDataIntoDF(self,indivisualDF,row):
        idx = row.idx
        #yahoo finance have a data limit so if that limit is hit then all the incomming df would be empty. so if the limit is hit
        # then the program should not mark that row as done 
        if self.yfLimitHit:
            return
        self.data.loc[self.data.idx==idx,"done"] = True
        #if df is empty, no stock data is found, no need to continue
        if indivisualDF.empty:
            self.data.loc[self.data.idx==idx,"skip"]=True
            return
        ticker = str(row.Ticker)
        trade_Date = row.Trade_Date
        step = self.timeframe.getWeekDict()
        #first get Price at the brought date, adjusted for stock split
        try:
            #if the last seen data on stock is more than a week out of original trade date, then this trade happens before stock went public, so it is unusable
            if(not self.within7days(indivisualDF.index.values[0],trade_Date)):
                print(f"{ticker} was traded outside of it's public traded time idx:{idx}")
                return
            priceWhenBrought =round(indivisualDF.iloc[0],3)
            self.data.loc[self.data.idx==idx,"Price"]=priceWhenBrought
            print(f"Opening price for {ticker} is {priceWhenBrought} found on YF,idx {idx}")
            for timeframe, i in step.items():
                    priceAtThatTime = round(indivisualDF.iloc[i],3)
                    self.putDataIntoDF(priceAtThatTime,idx,timeframe)
        except IndexError:
            return
        except Exception as e:
            print("error:",e , "at index",idx,"FOR queueStockForYF")   
    
    def getTradePriceWhenBrought(self,trade_date,dailyDF,row):
        idx = row.idx
        ticker = row.Ticker
        #checks if the stock had undergone a period of 0 volume, which will disqualfy a stock
        if(not self.validateAlapcaDF(dailyDF)):
            self.data.loc[self.data.idx==idx,"skip"]=True
            print("failed because of invalidate for ticker", row.Ticker)
            return 
        for timestamp,entry in dailyDF.iterrows():
            if trade_date in str(timestamp):
                return entry.open
        #if the trade date is not in the df, then this stock's trade date is outside of two month period, so I will mark it for indivisual search.
        self.queueStockForYF(row)

    def updateConsole(self,message):
        self.clearConsole()
        print("found:",len(self.data), "results")
        print("Expected wait time: ", round(len(self.data)/3/60,2), "Minutes\n")
        print(message)

    def getTickersFromGroup(self,group,asOneString=True)->list:
        if(asOneString):
            result= ""
            for i in group:
                result+= str(i["Ticker"])+','
            return [result[0:-1]]
        else:
            result =[]
            for i in group:
                result.append(str(i.Ticker))
            return result

    def clearConsole(self):
        if platform == "linux" or platform == "linux2":
            os.system("clear")
        elif platform == "darwin":
            os.system("clear")
        elif platform == "win32":
            os.system("cls")

    #yahoo finanace doesnt give exact date so I have to check if it is within a range of at least 5 days. if yes then the info is good to use
    def within7days(self,givendate,tradeDate):
        givendate = str(givendate).split("T")[0]
        if(givendate==tradeDate):
            return True
        year,month,day = map(int,givendate.split("-"))
        givendate = datetime.date(year,month,day)
        year,month,day = map(int,tradeDate.split("-"))
        tradeDate = datetime.date(year,month,day)
        margin = datetime.timedelta(days = 7)
        return givendate - margin <= tradeDate <= givendate + margin

    #can be refactored to be shorter but this is more readable
    def putDataIntoDF(self,value,idx,timeframe):
        idx = int(idx)
        value = round(value,2)
        #this updates the price at that time frame, ie: $65 two weeks later
        self.data.loc[self.data.idx==idx,timeframe] = value

    def percentChange(self,oldprice,newprice):
        result =0
        if oldprice == newprice:
            return 0
        if oldprice < newprice:
            result= (newprice-oldprice)/oldprice
        else:
            result = -(oldprice-newprice)/oldprice
        return round(result*100,2)

    def updatepercentChange(self,df):
        for i, row in df.iterrows():
            oldprice = df.at[i,"Price"]
            #time frame is ["2w","1m"...]
            for time in self.timeframe.timeframe:
                newprice = row[time]
                if(newprice!=0):
                    df.at[i,f"{time}%"] = self.percentChange(oldprice,newprice)
        print("done updating percent change")       
        return df
    
    #fixing annoying bugs for alpaca api, such as having a stock data before stock even ipos, but its always followed by volumn=0 for a few weeks
    #so I can filter that out
    def validateAlapcaDF(self,df):
        if len(df)==0:
            return False
        consecutive =0
        #sometimes the stock have off days with 0 volume, but if its not consequtive them its fine
        for i,row in df.iterrows():
            if row.volume==0:
                consecutive+=1
                if(consecutive==2):
                    print(df.loc[df.volume==0])
                    return False
            consecutive-=1
        return True
    #to adjust for some ticker changes, I will look through all assets in NYSE and Nasdaq and see if the company have a different ticker 
    def getCorrectStockTicker(self):
        #if the first row is done then it means that all the companies already have the correct stock ticker
        if self.data.iloc[0].done==True:
            return
        print("Checking if any company changed their ticker...")
        key = self.getApiKey()
        alpaca_api = tradeapi.REST(key["PUBLIC_KEY"],key["SECRET_KEY"],key["END_POINT"])
        assets = alpaca_api.list_assets(status="active")
        #limit exchange to only nyse and nasdaq

        #get symbol and its corresponding company name as a dict for that CONSTANT LOOK UP TIME
        symbolandcompany = self.getsymbolandcomany(assets)
        #get company and corresponding symbol
        companyandsymbol = self.getCompanyandSymbol(assets)
        for _,row in self.data.iterrows():
                ticker = row.Ticker
                idx = row.idx
                companyname = self.stripNonAlpabet(row.Company_Name.lower()) 
                if(companyname[0:10] in companyandsymbol):
                    newticker = self.findClosestMatch(companyandsymbol[companyname[0:10]],companyname)
                    if(ticker != newticker and newticker!=None):
                        print(f"Company {row.Company_Name}'s symbol is {newticker},instead of {ticker}")
                        self.data.loc[self.data.idx==idx,"Ticker"]=newticker   
                        self.scrapper.changeTickerCount+=1  
        self.to_csv()
        time.sleep(3)     
    def getStartAndEndDate(self,tradeDate):
        y,m,d = map(int,tradeDate.split("-"))
        startTradeDate = datetime.date(y,m,d)-datetime.timedelta(days=4) 
        fivemonths = datetime.timedelta(days=152)
        endTradeDate=startTradeDate+fivemonths
        yesterday = datetime.date.today()-datetime.timedelta(days=1)
        if(endTradeDate>=yesterday):
            return  [str(startTradeDate),str(yesterday)]
        return [str(startTradeDate),str(endTradeDate)]

    #this gives me all the symbol and it's comany name in a dictionary
    def getsymbolandcomany(self,assets)->dict:
        result = {}
        for i in assets:
            companyname = self.stripNonAlpabet(i.name.lower())
            result[i.symbol]=companyname
        return result
    def getCompanyandSymbol(self,assets)->dict:
        result = {}
        for i in assets:
            #convert it all to lowercase because sometimes things like "New Therapical" and "NEW Therapical" can appear
            companyname =  self.stripNonAlpabet(i.name.lower())
            #some company have some off shore 1/40th owhershup stock or something that have very long names 
            # if the names too long, its out
            if(len(companyname)>100):
                continue
            partialName = companyname[0:10]
            indivisual_company = {companyname:i.symbol}
            if(partialName not in result):
                result[partialName]=[]
            result[partialName].append(indivisual_company)
        return result

    #some companies have the same first 10 letters so they are divided into sub groups, 
    #this function takes the subgroup (companies), and try to match the closest one to the companyname
    #like consolidated Edison(NYSE:ED) would return instead of consolidated Water(CWCO)
    def findClosestMatch(self,companies,companyname):
        if len(companies)==1:
            return list(companies[0].values())[0]
        #converts list of dicts into a single dictionary
        companydict = {}
        for company in companies:
            companydict.update(company)
        companyNames = list(companydict.keys())
        #if the exact name is already in, no need to loop at all
        if(companyname in companydict):
            return companydict[companyname]
        #I loop through each character of the original name, look at each character of all companies with that starting 10 characters
        # filter them out and get the correct one. I do this for that constnat look up time about 99% of the stocks
        #exmaple:   company name: consolidatededison (consolidated Edison(NYSE:ED))
        #            companies: consolidatededison (consolidated Edison(NYSE:ED)) <-what we want
        #                       consolidatedwater  (Consolidated Water Co NASDAQ: CWCO) <- what we want to filter out
        #      since both have the same leading 10 characters, this will loop through and filter out the unwanted one.
        for i,char in enumerate(companyname):
            if len(companyNames) ==1:
                return companydict[companyNames[0]]
            #both dont match, return None
            if  len(companyNames)==0:
                return None

            for x in companyNames:
                if(x[i]!=char):

                    companyNames.remove(x)
                
        

    #this function removes all the Companys where data cannot be attained from, or two weeks has not passed
    def cleanup(self):
        #drop those without price or no 2week data
        self.data = self.data[self.data["skip"]==False]
        self.data = self.data.dropna(axis=0,subset=["Price"])
        self.data = self.data[self.data["Price"]!=0]
        self.data = self.data.loc[self.data["2w"]!=0]
        self.removedDataAmount = self.scrapper.originalSize - len(self.data) 
        self.scrapper.updateScrapped()
        print("----------------------------------------------------------------------------------------")
        print(f"\ndone,removed {self.removedDataAmount} entries because no stock data can be found by them, or they are overlapps" )
        print("NO stock data can mean multiple things: ticker change, merger, acqusition, going private, or bankruptcy")
        print(f"Had to update the tickers of {self.scrapper.changeTickerCount} companies")
        print("----------------------------------------------------------------------------------------")
        
        

    def getApiKey(self):
        try:
            key_file = "key/alpaca_keys.txt"
            with open(key_file,"r") as f:
                    line= f.read().strip().split(" ")
                    API_KEY,SECRET_KEY,END_POINT=line 
            return {"PUBLIC_KEY":API_KEY,"SECRET_KEY":SECRET_KEY,"END_POINT":END_POINT}
        except:
            return {}
import datetime
from sys import platform
#this allows me to query multiple tickers at once rather than rely on yf which only gives me one
import pandas_datareader as pdr
import os
import alpaca_trade_api as tradeapi
import pandas as pd
import scrapper as Scrapper
import time
import yfinance as yf 
import warnings
import threading
import re
from dotenv import load_dotenv
load_dotenv()

warnings.filterwarnings("ignore")
class DataGetter():
    def __init__(self) -> None:
        self.timeframe = Scrapper.TimeFrame()
        self.key = self.getApiKey()
        self.api= tradeapi.REST(self.key["PUBLIC_KEY"],self.key["SECRET_KEY"],self.key["END_POINT"])
        #since I can query multiple data from YF, I need to keep a list just for YF
        self.yfList = []
        self.yfcount=0
        self.Threads = []
        self.count =0
        self.regex = re.compile('[^a-z]')
        return

    def update(self,scrapper):
        self.scrapper = scrapper
        self.data = scrapper.get_data()
        dfSize = len(self.data)
        #if every ticker is done, then no need to loop
        if(self.data[self.data.done==False].empty):
            self.print_summary()
            return scrapper
        self.getCorrectStockTicker()
        self.to_csv()
        self.notdone = self.data[self.data.done==False]
        self.count = len(self.data)-len(self.notdone)
        #grouping the rows into a list so I can query them all at once with one api call
        rowGroup = []
        for _,row in self.notdone.iterrows():
            self.count+=1
            #this if statment is here so that in case the update is inturrupted, this doesnt start from beginning
            if(bool(row["done"])):
                continue
            rowGroup.append(row)
            #alapca allows multiple tickers be queried at once so I will do one api call every 10 rows
            if(len(rowGroup)<20 and (dfSize-self.count)>19): 
                continue
            
            tickers= self.getTickersFromGroup(rowGroup)
            self.getPriceAtTimeBrought(rowGroup,tickers) 
            self.getWeeklyDataFromRowGroup(rowGroup,tickers)
            rowGroup.clear() 
            self.to_csv()
        #do the rest
        if(len(self.yfList)>0):
            self.queueStockForYF(doTheRest=True)
        for i in self.Threads:
            i.join()
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
        startDate=lastrow.Filing_Date
        twoweeksago=(datetime.date.today()-datetime.timedelta(days=14)).strftime('%Y-%m-%d')
        if(startDate>twoweeksago):
            twoweeksago=startDate 
        #this is now weekly data, the timeframe is 5day
        alpacaDF = self.api.get_bars(tickers,timeframe="5Day",start=startDate, end=twoweeksago,adjustment="all").df
        for row in rowGroup:
            idx = row.idx
            if(self.isrowDone(idx)):
                continue
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"]==row.Ticker]
                indivisualDF.index = pd.to_datetime(indivisualDF.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
                self.getWeeklyDataFromAlpacaDF(indivisualDF,row)
            except IndexError:
                continue
            except KeyError:
                continue
            except Exception as e:
                print(f"Error {e} at index {idx} FOR getWeeklyDataFromRowGroup type { type(e)}")
                self.data.loc[self.data.idx==idx,"skip"]=True

    def testOneRow(self,df):
        row = df.iloc[0]
        tickers = [row.Ticker]
        self.data = df
        self.getPriceAtTimeBrought([row],tickers) 
        self.getWeeklyDataFromRowGroup([row],tickers)
        self.queueStockForYF(doTheRest=True)
        self.data.to_csv("test.csv")

    def getWeeklyDataFromAlpacaDF(self,weeklyDF,row):
        idx = row.idx
        filing_date = row.Filing_Date
        offset = 0
        self.data.loc[self.data.idx==idx,"done"]=True
        self.data.loc[self.data.idx==idx,"source"] = "ALPACA"
        #getting offset because the start date is based on the earlist stock's trade date in the row group, that might be serveral weeks before this 
        for timestamp, row in weeklyDF.iterrows():
            if(filing_date>timestamp):
                offset+=1
            else:
                break
        starttime = weeklyDF.iloc[0+offset].name
        if(not self.within14days(starttime,filing_date)):
            self.queueStockForYF(row)
            return
        #this returns {"2w":2, "1m":4}etc
        timeframeAndweeknum = self.timeframe.getWeekDict()
        try:
            for timeframe,numofweek in timeframeAndweeknum.items():
                priceAtTimeFrame = weeklyDF.iloc[int(numofweek)+offset].open
                self.putDataIntoDF(priceAtTimeFrame,idx,timeframe)
        except IndexError:
            return
        except Exception as e:
            print("error:",e , "at index",idx,"For getWeeklyDataFromAlpacaDF")   
    #this function takes the list of rows and their tickers, then trys to get data from the time brought
    def getPriceAtTimeBrought(self,rowGroup,tickers):
        lastrow = rowGroup[-1]
        startDate,endDate=self.getStartAndEndDate(lastrow.Filing_Date)
        alpacaDF = self.api.get_bars(tickers,timeframe="1Day",start=startDate, end=endDate,adjustment="all").df
        for row in rowGroup:
            ticker = row.Ticker
            filing_date = row.Filing_Date
            idx = row.idx
            indivisualDF = pd.DataFrame()
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"]==ticker]
                #change the time date format to just y-m-d 
                indivisualDF.index = pd.to_datetime(indivisualDF.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
            except Exception as e:
                self.queueStockForYF(row)
                continue
            #if symbol doesnt exist on alpaca or the dates dont match, check yahoo finance
            if(indivisualDF.empty):
                #yahoo finance already gets all the 2week/months data, so no need to query data about it again
                self.queueStockForYF(row)
                continue
            else:
                indivisualDF = indivisualDF[indivisualDF["volume"]!=0]
                priceWhenBrought = self.getTradePriceWhenBrought(filing_date,indivisualDF,row)
                if(priceWhenBrought==None):
                    print(f"send {ticker} to YF price brougth cant be found on alpaca")
                    self.queueStockForYF(row)
                    continue
                print(f"Price of {ticker} when brought is {priceWhenBrought}, Currently {self.count} out of {len(self.data)}")
                self.data.loc[self.data.idx==idx,"Price"]=priceWhenBrought

    #this puts the tickers in a list for YF to query all at once
    def queueStockForYF(self,row=pd.Series([]),doTheRest = False):
        if(not row.empty):
            self.yfcount+=1
            self.yfList.append(row)
            idx = row.idx
            #mark it as skip so alpaca dont look for it
            self.data.loc[self.data.idx==idx,"skip"]=True
        if(len(self.yfList)==20 or doTheRest):
            #use threading to get yf data cus it takes FOREVER
            thread = threading.Thread(target=self.getweeklyDataFromYF) 
            thread.start()
            self.Threads.append(thread)

    #apprently "Perma-fix" and "Perma fix" are not the same thing!
    def stripNonAlpabet(self,string):
        #regex the string to only lowercase a-z
        return self.regex.sub("",string)

    def getweeklyDataFromYF(self) -> None:
        #start date is the trade date of the last row in this group because that is the earliest
            rowGroup= self.yfList.copy()
            self.yfList.clear() 
            # weeklystockDataForAllStockInList.index = pd.to_datetime(weeklystockDataForAllStockInList.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
            for row in rowGroup:
                company = yf.Ticker(str(row.Ticker)) 
                filingDate = row.Filing_Date
                hist = company.history(period="3y",interval="1wk",start = filingDate,back_adjust=True)
                self.inputYFDataIntoDF(hist,row)
            
    
    def isrowDone(self,idx):
        return self.data.loc[self.data.idx==idx].iloc[0].done or self.data.loc[self.data.idx==idx].iloc[0].skip 

    def inputYFDataIntoDF(self,indivisualDF,row):
        idx = row.idx
        #yahoo finance have a data limit so if that limit is hit then all the incomming df would be empty. so if the limit is hit
        # then the program should not mark that row as done 
        self.data.loc[self.data.idx==idx,"done"] = True
        self.data.loc[self.data.idx==idx,"source"] = "YF"
        #if df is empty, no stock data is found, no need to continue
        #if theres a GIANT spike in price, like 10x from lastweeks's high and a week later, then its SUS, safer to just filter it out
        if indivisualDF.empty or not self.validateYFdf(indivisualDF):
            self.scrapper.removecount +=1
            return
        step = self.timeframe.getWeekDict()
        #first get Price at the brought date, adjusted for stock split
        try:
            priceWhenBrought =round(indivisualDF.iloc[0].Open,3)
            self.data.loc[self.data.idx==idx,"Price"]=priceWhenBrought
            print(f"Opening price for {row.Ticker} is {priceWhenBrought} found on YF,count {self.count}/{len(self.data)}")
            for timeframe, i in step.items():
                    priceAtThatTime = round(indivisualDF.iloc[i].Open,3)
                    self.putDataIntoDF(priceAtThatTime,idx,timeframe)
        except IndexError:
            return
        except Exception as e:
            print("error:",e , "at index",idx,"FOR queueStockForYF")   
    
    #sometimes a pre ipo price was given like for ENCR on 2015-05-08, where the price went from 0.15 to 6 overnight, but its not even publicly tradable yet
    #this will filter that out
    def validateYFdf(self,df):
        lastprice = df.iloc[0].High
        for time, row in df.iterrows():
            currentprice = row.High
            if(currentprice/lastprice >10):
                return False
            lastprice = currentprice
        return True
    def getTradePriceWhenBrought(self,filing_date,dailyDF,row) ->float:
        idx = row.idx
        ticker = row.Ticker
        #checks if the stock had undergone a period of 0 volume, which will disqualfy a stock
        if(not self.validateAlapcaDF(dailyDF)):
            self.queueStockForYF(row)
            return None
        for timestamp,entry in dailyDF.iterrows():
            if filing_date == timestamp:
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
    def within14days(self,givendate,tradeDate):
        givendate = str(givendate).split("T")[0]
        #modify it so taht alpaca df can use it too
        givendate = str(givendate).split(" ")[0]
        if(givendate==tradeDate):
            return True
        year,month,day = map(int,givendate.split("-"))
        givendate = datetime.date(year,month,day)
        year,month,day = map(int,tradeDate.split("-"))
        tradeDate = datetime.date(year,month,day)
        margin = datetime.timedelta(days = 14)
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
    #also when ticker changes companies, there will be gaps between 
    def validateAlapcaDF(self,df):
        if len(df)==0:
            return False
        consecutive =0
        #sometimes the stock have off days with 0 volume, but if its not consequtive them its fine
        last_date = df.index.values[0]
        for trade_date,row in df.iterrows():
            if(not self.within14days(trade_date,last_date)):
                return False
            if row.volume==0:
                consecutive+=1
                if(consecutive==2):
                    print(df.loc[df.volume==0])
                    return False
            else:
               consecutive-=1
            last_date = trade_date
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
        #get company and corresponding symbol
        companyandsymbol = self.getCompanyandSymbol(assets)
        for _,row in self.data.iterrows():
                ticker = row.Ticker
                idx = row.idx
                companyname = self.stripNonAlpabet(row.Company_Name.lower()) 
                if(companyname[0:10] in companyandsymbol):
                    self.data.loc[self.data.idx==idx,"active"]=True
                    newticker,exchange = self.findClosestMatch(companyandsymbol[companyname[0:10]],companyname)
                    self.data.loc[self.data.idx==idx,"exchange"]=exchange  
                    if(ticker != newticker and newticker!=None):
                        print(f"Company {row.Company_Name}'s symbol is {newticker},instead of {ticker}")
                        self.data.loc[self.data.idx==idx,"Ticker"]=newticker   
                        self.scrapper.changeTickerCount+=1  
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
            indivisual_company = {companyname:i.symbol,"exhange":i.exchange}
            if(partialName not in result):
                result[partialName]=[]
            result[partialName].append(indivisual_company)
        return result

    """explaination: some companies have the same first 10 letters so they are divided into sub groups, 
    this function takes the subgroup (companies), and try to match the closest one to the companyname
    like consolidated Edison(NYSE:ED) would return instead of consolidated Water(CWCO)
    @params 
    companies: list of dicts with companyname and ticker   example:  [{"consolidatededison": ED,"exchange":NYSE},{"consolidatedwater":COHW,"exhcange":"NYSE"}]
    companyname: str, stripped company name lowercase, example: consolidatededison
    given the companyname, this should return (ED,NYSE)
    :"""

    def findClosestMatch(self,companies:list,companyname) -> tuple:
        if len(companies)==1:
            if companyname[-5:] not in list(companies[0].keys())[0]:
                return (None,None)
            return companies[0].values()
        longestsimilar = 0
        index = 0
        for i,company in enumerate(companies):
            name =list(company.keys())[0]
            if(longestsimilar<self.getLongestSimilarInitial(companyname,name)):
                longestsimilar=self.getLongestSimilarInitial(companyname,name)
                index = i
        result = companies[index].values()
        resultname = list(companies[index].keys())[0]
        if("blackdiamond" in companyname):
            print(companies)
        #last 5 character usally diffienciates between companies. So if its not in there, then this is a different company
        if companyname[-5:] not in resultname:
            return (None,None)
        return result
            
    def getLongestSimilarInitial(self,originalstr,comparestr):
        count =0
        for i,char in enumerate(comparestr):
            try:
                if originalstr[i]!=char:
                    break
            except:
                break
            count+=1 
        return count  

    #this function removes all the Companys where data cannot be attained from, or two weeks has not passed
    def cleanup(self):
        #drop those without price or no 2week data
        # self.data = self.data[self.data["skip"]==False]
        # self.data = self.data.dropna(axis=0,subset=["Price"])
        # self.data = self.data[self.data["Price"]!=0]
        # self.data = self.data.loc[self.data["2w"]!=0]
        self.scrapper.updateScrapped()
        self.print_summary()

    def print_summary(self):
        print("----------------------------------------------------------------------------------------")
        print(f"\ndone,removed {self.scrapper.removecount} entries because no stock data can be found by them, or they are overlapps" )
        print("NO stock data can mean multiple things: ticker change, merger, acqusition, going private, or bankruptcy")
        print(f"Had to update the tickers of {self.scrapper.changeTickerCount} companies")
        print("----------------------------------------------------------------------------------------")   
        

    def getApiKey(self):
        PUBLIC_KEY=os.getenv("ALPACA_PUBLIC_KEY")
        SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
        ENDPOINT=os.getenv("ALPACA_ENDPOINT")
        if(len(PUBLIC_KEY)==0):
            print("you need to set up the ALPACA keys in .env file, please follow the .env.example file for more guidence")
            quit()
        return {"PUBLIC_KEY":PUBLIC_KEY,"SECRET_KEY":SECRET_KEY,"END_POINT":ENDPOINT}
    
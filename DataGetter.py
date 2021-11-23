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
        #if every ticker is done, then no need to loop
        self.notdone = self.data[self.data.done==False]
        if(self.notdone.empty):
            self.print_summary()
            return scrapper
        self.getCorrectStockTicker()
        self.to_csv()
        self.notdone = self.data
        #save the correct sticker progress
        
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
        if(self.yfLimitHit):
            print("Yahoo finance limit it, unable to complete some of the data, try again in like 20 minutes")
            quit()
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
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"]==row.Ticker]
                indivisualDF.index = pd.to_datetime(indivisualDF.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
                self.getWeeklyDataFromAlpacaDF(indivisualDF,row)
            except IndexError:
                continue
            except KeyError:
                continue
            except Exception as e:
                errorType = type(e)
                print(f"Error {e} at index {idx} FOR getWeeklyDataFromRowGroup type {errorType}")
                self.data.loc[self.data.idx==idx,"skip"]=True

    def getWeeklyDataFromAlpacaDF(self,weeklyDF,row):
        idx = row.idx
        filing_date = row.Filing_Date
        offset = 0
        self.data.loc[self.data.idx==idx,"done"]=True
        self.data.loc[self.data.idx==idx,"source"] = "ALPACA"
        #getting offset because the start date is based on the earlist stock's trade date in the row group, that might be serveral weeks before this 
        for timestamp, row in weeklyDF.iterrows():
            timestamp=str(timestamp).split(" ")[0]
            if(filing_date>timestamp):
                offset+=1
            else:
                break
        priceAtFilingDate = weeklyDF.iloc[offset].open
        self.putDataIntoDF(priceAtFilingDate,idx,"Price")
        #this returns {"2w":2, "1m":4}etc
        lableAndweeknum = self.timeframe.getWeekDict()
        try:
            for timeframe,numofweek in lableAndweeknum.items():
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
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"]==ticker]
                #change the time date format to just y-m-d 
                indivisualDF.index = pd.to_datetime(indivisualDF.index, format = '%Y-%m-%d').strftime('%Y-%m-%d')
            except:
                self.queueStockForYF(row)
                continue
            #if symbol doesnt exist on alpaca, check yahoo finance
            if(indivisualDF.empty):
                #yahoo finance already gets all the 2week/months data, so no need to query data about it again
                self.queueStockForYF(row)
                continue
            else:
                priceWhenBrought = self.getTradePriceWhenBrought(filing_date,indivisualDF,row)
                if(priceWhenBrought==None):
                    self.queueStockForYF(row)
                    continue
                print(f"Price of {ticker} when brought is {priceWhenBrought}, Currently {self.count} out of {len(self.data)}")
                self.data.loc[self.data.idx==idx,"Price"]=priceWhenBrought
    
                # print(f"for {ticker} the price brought at was {priceWhenBrought} at {filing_date}")

    #this puts the tickers in a list for YF to query all at once
    def queueStockForYF(self,row=pd.Series([]),doTheRest = False):
        if(not row.empty):
            self.yfList.append(row)
            idx = row.idx
            #skip those that are done, or are marked as skip(marked as skip means no stock data is found)
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
            startDate=lastrow.Filing_Date
            twoweeksago=(datetime.date.today()-datetime.timedelta(days=14)).strftime('%Y-%m-%d')
            if(startDate>twoweeksago):
                twoweeksago=startDate  
            tickers = self.getTickersFromGroup(self.yfList,asOneString=False)
            rowGroup= self.yfList
            self.yfList.clear()
            try:
                weeklystockDataForAllStockInList = pdr.yahoo.daily.YahooDailyReader(tickers, start=startDate, end=twoweeksago,interval="w",adjust_price=True).read()
            except:
                print("Sorry, the yahoo finance hourly limit of 2000 is hit, please wait 20 minutes to try again")
                self.yfLimitHit = True
            #change the date format to (y-m-d)
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
        self.data.loc[self.data.idx==idx,"source"] = "YF"
        #if df is empty, no stock data is found, no need to continue
        if indivisualDF.empty:
            self.data.loc[self.data.idx==idx,"skip"]=True
            return
        ticker = str(row.Ticker)
        step = self.timeframe.getWeekDict()
        #first get Price at the brought date, adjusted for stock split
        try:
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
    
    def getTradePriceWhenBrought(self,filing_date,dailyDF,row):
        idx = row.idx
        ticker = row.Ticker
        #checks if the stock had undergone a period of 0 volume, which will disqualfy a stock
        if(not self.validateAlapcaDF(dailyDF)):
            self.data.loc[self.data.idx==idx,"skip"]=True
            print("failed because of invalidate for ticker", row.Ticker)
            return 
        for timestamp,entry in dailyDF.iterrows():
            if filing_date in str(timestamp):
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
            last_date = trade_date
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
        self.data = self.data[self.data["skip"]==False]
        self.data = self.data.dropna(axis=0,subset=["Price"])
        self.data = self.data[self.data["Price"]!=0]
        self.data = self.data.loc[self.data["2w"]!=0]
        self.scrapper.updateScrapped()
        self.print_summary()

    def print_summary(self):
        self.removedDataAmount = self.scrapper.originalSize - len(self.data) 
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
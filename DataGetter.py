import time
import yfinance as yf
import os
class DataGetter():
    def __init__(self) -> None:
        self.timeframe = ["2w","1m","4m","6m","1yr","2yr"]
        return

    def update(self,scrapper):
        self.scrapper = scrapper
        self.data = scrapper.data
        # keys = self.getApiKeys()
        # api = tradeapi.REST(keys[0]["apikey"],keys[0]["secretkey"],keys[0]["endpoint"])
        count =0
        for idx,row in self.data.iterrows():
            count+=1
            #this if statment is here so that in case the update is inturrupted, this doesnt scan from beginning
            if(bool(row["done"])==False):
                ticker = row["Ticker"]
                if not ticker:
                    continue
                if(count>150):
                    time.sleep(0.2)
                    if(count%100==0):
                        print("pause for 10 second so YF doesnt throttle my speed")
                        time.sleep(10)
                trade_Date = row["Trade_Date"]
                self.updateConsole(f"gotten historical data for {ticker} current count is {count} out of {len(self.data)}")
                try: 
                    self.getstockdataFromYF(idx,row)
                except Exception as e:
                    continue
                if(idx%20==0):
                    scrapper.to_csv()   
        self.updatepercentChange(self.data)  
        self.cleanup()
        scrapper.data = self.data
        scrapper.to_csv()
        print("done, all data is updated to",scrapper.csvFilePath)
        return scrapper
    
    def updateConsole(self,message):
        self.clearConsole()
        print("found:",len(self.data), "results")
        print("Expected wait time: ", round(len(self.data)/4)/60, "Minutes\n")
        print(message)


    def clearConsole(self):
        os.system("clear")
    def getstockdataFromYF(self,idx,row):
        ticker = row["Ticker"]
        trade_Date = row["Trade_Date"]
        company = yf.Ticker(ticker) 
        hist = company.history(period="4y",interval="1wk",start = trade_Date)  
        #yahoo finance allows weekly pulls, hist[1] is two weeks after start date
        step = {"Price":0,"2w":2,"1m":4,"4m":16,"6m":24,"1yr":48,"2yr":96}
        if len(hist)>0:
            try:
                self.data.at[idx,"done"]= True
                for timeframe, i in step.items():
                    self.putDataIntoDF(hist.iloc[i].Close,idx,timeframe)
            except IndexError:
                return
            except Exception as e:
                print("error:",e , "at index",idx)

    #can be refactored to be shorter but this is more readable
    def putDataIntoDF(self,value,idx,timeframe):
        value = round(value,2)
        #this updates the price at that time frame, ie: $65 two weeks later
        self.data.at[idx,timeframe] = value

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
            for time in self.timeframe:
                newprice = row[time]
                if(newprice!=0):
                    df.at[i,f"{time}%"] = self.percentChange(oldprice,newprice)
        print("done updating percent change")       
        return df

    #this function removes all the Companys where data cannot be attained from, or two weeks has not passed
    def cleanup(self):
        #drop those without price or no 2week data
        self.data=self.data.dropna(axis=0,subset=["Price"])
        self.data = self.data[self.data["Price"]!=0]
        self.data = self.data.loc[self.data["2w"]!=0]
        self.removedDataAmount = self.scrapper.originalSize - len(self.data) 
        print("----------------------------------------------------------------------------------------")
        print(f"\ndone,removed {self.removedDataAmount} entries because no stock data can be found by them, or they are overlapps" )
        print("----------------------------------------------------------------------------------------")
        
        

    def getApiKeys(self):
        path = "/home/darren/api-keys/alpaca.txt"
        f= open(path,'r')
        keys = []
        for line in f:
            line = line.replace("\n","")
            apiKey,secretkey,endpoint = line.split(" ")
            keys.append({"apikey":apiKey,"secretkey":secretkey,"endpoint":endpoint})
        return keys

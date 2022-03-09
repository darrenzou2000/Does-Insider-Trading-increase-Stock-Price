import datetime
from sys import platform
# this allows me to query multiple tickers at once rather than rely on yf which only gives me one
import os
import alpaca_trade_api as tradeapi
import pandas as pd
import Scrapper as Scrapper
import time
import yfinance as yf
import warnings
import threading
import re
from dotenv import load_dotenv

load_dotenv()

# A lot of annoying warnings from YahooFianace, TODO: think of a better way to handle warnings
warnings.filterwarnings("ignore")

"""
After scrapping, this class takes the data and then use primarily alpaca API and yahoo finance API for backup.
It will populate the prices columns of the data for the timesframes between 2week and 2 yr.
"""
class DataGetter():

    def __init__(self) -> None:
        # the timeframes needed for the stock such as ["1m","2m","3m" etc]
        self.timeframe = Scrapper.TimeFrame()

        # api keys for alpaca
        self.key = self.getApiKey()
        self.api = tradeapi.REST(self.key["PUBLIC_KEY"],
                                 self.key["SECRET_KEY"], self.key["END_POINT"])
        # since I can't query multiple data from YF, I need to keep a list just for YF
        self.yfList = []

        # the treads used to speed up data gathering from Yahoo finance
        self.Threads = []

        # number of rows processed- for the user to see
        self.count = 0

        # used to standardize company names
        self.regex = re.compile('[^a-z]')
        return

    def update(self, scrapper: Scrapper) -> Scrapper:
        """
            This function might be overwelming but it does a lot of things:
            1: check if the data is already done(i.e no data need to be updated and the
               result can be displayed immediately)
            2: check with current active companies and see if any of them have a ticker change
            3: groups rows togather to get stock data from Alpaca api 
            4: after all the data is collected, update percent change
            5: clean up data and get rid of empty rows, then save to csv file
        Args:
            scrapper (Scrapper): The scrapper from Scrapper.py that contains all the 
                                 insider trading from OpenInsider.com
        """
        self.scrapper = scrapper
        self.data = scrapper.getData()
        dfSize = len(self.data)
        # if every ticker is done, then no need to loop,
        #  also note: using "is False" causes a error because numpy bool is not the same as regular python bool
        if (self.data[self.data.done == False].empty):
            self.print_summary()
            return scrapper
        self.getCorrectStockTicker()
        self.to_csv()
        self.notdone = self.data[self.data.done == False]
        self.count = len(self.data) - len(self.notdone)
        # grouping the rows into a list so I can query them all at once with one api call
        rowGroup = []
        for _, row in self.notdone.iterrows():
            self.count += 1
            # this if statment is here so that in case the update is inturrupted, this doesnt start from beginning
            if (bool(row["done"])):
                continue
            rowGroup.append(row)
            # alpaca allows multiple tickers be queried at once so I will do one api call every 10 rows
            if (len(rowGroup) < 20 and (dfSize - self.count) > 19):
                continue

            tickers = self.getTickersFromRowGroup(rowGroup)
            self.getBroughtPriceForGroup(rowGroup, tickers)
            self.getWeeklyDataFromRowGroup(rowGroup, tickers)
            rowGroup.clear()
            self.to_csv()
        # do the rest
        if (len(self.yfList) > 0):
            self.queueStockForYF(doTheRest=True)
        for i in self.Threads:
            i.join()
        self.updatepercentChange()
        self.cleanUp()
        self.to_csv()
        print("done, all data is updated to", scrapper.csvFilePath)
        return scrapper

    def to_csv(self):
        """Save data to the csv file that was assigned to the scrapper 
        """
        self.scrapper.data = self.data
        self.scrapper.to_csv()

    def getCorrectStockTicker(self) -> None:
        """to adjust for some ticker changes, I will look through all stocks in NYSE and Nasdaq 
        and see if the company have a different ticker

        TODO: This function can still be massivly improved, such as including more exchanges
        """

        # if the first row is done then it means that all the companies already have the correct stock ticker
        if self.data.iloc[0].done:
            return
        print("Checking if any company changed their ticker...")
        assets = self.api.list_assets(status="active")
        # get company and corresponding symbol in a dict
        companyAndTicker = self.getCompanyandSymbol(assets)
        for _, row in self.data.iterrows():
            ticker = row.Ticker
            idx = row.idx
            companyName = self.stripNonAlpabet(row.Company_Name.lower())
            # Im applying a library like system to query for stock names 
            # because sometimes the companyName given are not the same as the offcial name
            # so this would give the most accurate result (hopefully)
            # TODO: rethink this entire process.
            if (companyName[0:10] in companyAndTicker):
                self.data.loc[self.data.idx == idx, "active"] = True
                newticker, exchange = self.findClosestMatch(
                    companyAndTicker[companyName[0:10]], companyName)
                self.data.loc[self.data.idx == idx, "exchange"] = exchange
                if (ticker != newticker and newticker is not None):
                    print(
                        f"Company {row.Company_Name}'s symbol is {newticker},instead of {ticker}"
                    )
                    self.data.loc[self.data.idx == idx, "Ticker"] = newticker
                    self.scrapper.changeTickerCount += 1
        # I spent a painful weeks on this, you better look at what companies changed their tickers.
        time.sleep(3)

    def getWeeklyDataFromRowGroup(self, rowGroup: pd.DataFrame, tickers: list): 
        # TODO: refactor this function
        """ Takes in the rowGroup of companies and Gather data from Alpaca API for all of them 
            at once, then loop through the row group and separate out each company
            and extract the datas in getWeeklyDataFromAlpacaDF function

        Args:
            rowGroup (pd.DataFrame): A subset of self.data that contains about 20 companies .
            tickers (list[str]): list of tickers for the rowGroup
        """
        lastRow = rowGroup[-1]
        startDate = lastRow.Filing_Date
        twoWeeksAgo = (datetime.date.today() -
                       datetime.timedelta(days=14)).strftime('%Y-%m-%d')
        if (startDate > twoWeeksAgo):
            twoWeeksAgo = startDate
        # this is now weekly data for all 20 companies(assuming there are data for those companies)
        alpacaDF = self.api.get_bars(tickers,
                                     timeframe="1Week",
                                     start=startDate,
                                     end=twoWeeksAgo,
                                     adjustment="all").df
        for row in rowGroup:
            idx = row.idx
            if (self.isrowDone(idx)):
                continue
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"] == row.Ticker]
                indivisualDF.index = pd.to_datetime(
                    indivisualDF.index, format='%Y-%m-%d').strftime('%Y-%m-%d')
                self.getWeeklyDataFromAlpacaDF(indivisualDF, row)
            # TODO: refactor this to get rid of the excepts 
            except IndexError:
                continue
            except KeyError:
                continue
            except Exception as e:
                print(
                    f"Error {e} at index {idx} FOR getWeeklyDataFromRowGroup type { type(e)}"
                )
                self.data.loc[self.data.idx == idx, "skip"] = True

    # outputs the data fro a single row. For testing purposes
    def testOneRow(self, df):
        row = df.iloc[0]
        tickers = [row.Ticker]
        self.data = df
        self.getBroughtPriceForGroup([row], tickers)
        self.getWeeklyDataFromRowGroup([row], tickers)
        self.queueStockForYF(doTheRest=True)
        self.data.to_csv("test.csv")

    def getWeeklyDataFromAlpacaDF(self, weeklyDF: pd.DataFrame,
                                  row: pd.Series):
        """The alpaca DF have stock data from 20 companies, the row is one of the company. 
        This function extracts data from the DF and puts it into the row. 

        Args:
            weeklyDF (pd.DataFrame): dataframe containing stock data for the company in row
            row (pd.Series): A row from self.data that the data from weeklyDF is extracted to
        """
        idx = row.idx
        filingDate = row.Filing_Date
        offset = 0
        self.data.loc[self.data.idx == idx, "done"] = True
        self.data.loc[self.data.idx == idx, "source"] = "ALPACA"
        # getting offset because the start date is based on the earlist stock's trade date in the rowGroup, 
        # that might be serveral weeks before this
        for timestamp, row in weeklyDF.iterrows():
            if (filingDate > timestamp):
                offset += 1
            else:
                break
        startTime = weeklyDF.iloc[0 + offset].name
        if (not self.within14days(startTime, filingDate)):
            self.queueStockForYF(row)
            return
        # this returns {"2w":2, "1m":4}etc
        timeframeAndWeekNum = self.timeframe.getWeekDict()
        try:
            for timeframe, numofweek in timeframeAndWeekNum.items():
                priceAtTimeFrame = weeklyDF.iloc[int(numofweek) + offset].open
                self.putDataIntoDF(priceAtTimeFrame, idx, timeframe)
        # index error means that theres no data at the given timeframe, E.G. the 1 year data is not avaliable
        except IndexError:
            return
        except Exception as e:
            print("error:", e, "at index", idx,
                  "For getWeeklyDataFromAlpacaDF")

    def getBroughtPriceForGroup(self, rowGroup: pd.DataFrame, tickers: list):
        """I need to figure out the price when the stock is traded by the insider because multiple things can happen to a stock
          for example: stock splits, options, etc
          So I will extract the price when brought first. 
          The reason why I cant do it togather is because the weekly datas always start on mondays. 

        Args:
            rowGroup (pd.DataFrame): A group of about 20 companies because alpaca api allows group queries
            tickers (list[str]): the list of tickers for those 20 companies
        """
        lastRow = rowGroup[-1]
        startDate, endDate = self.getStartAndEndDate(lastRow.Filing_Date)
        alpacaDF = self.api.get_bars(tickers,
                                     timeframe="1Day",
                                     start=startDate,
                                     end=endDate,
                                     adjustment="all").df
        for row in rowGroup:
            ticker = row.Ticker
            filingDate = row.Filing_Date
            indivisualDF = pd.DataFrame()
            try:
                indivisualDF = alpacaDF[alpacaDF["symbol"] == ticker]
                # change the time date format to just y-m-d
                indivisualDF.index = pd.to_datetime(
                    indivisualDF.index, format='%Y-%m-%d').strftime('%Y-%m-%d')
            # any error at all will pass this row to YF
            except:
                self.queueStockForYF(row)
                continue
            # if symbol doesnt exist on alpaca or the dates dont match, check yahoo finance
            if (indivisualDF.empty):
                # yahoo finance already gets all the 2week/months data, so no need to query data about it again
                self.queueStockForYF(row)
                continue
            else:
                indivisualDF = indivisualDF[indivisualDF["volume"] != 0]
                self.setBroughtPrice(filingDate, indivisualDF, row)

    # this puts the tickers in a list for YF to query all at once
    def queueStockForYF(self, row=pd.Series([]), doTheRest=False):
        """Alpaca often dont have data for a specific ticker, so Yahoo fianace is my backup since it have way more data,
        YahooFinance doesnt allow group queries so using it as the sole source is really slow. 
        I use threading to bypass the speed limit, but still cap the threading to 20 so I dont get blacklisted from yahoo servers.

        Args:
            row (pd.Series([]), optional): The row that alpaca dont have data on. Defaults to pd.Series([]).
            doTheRest (bool, optional): At the end of the program, do the rest that are queued. Defaults to False.
        """
        if (not row.empty):
            self.yfList.append(row)
            idx = row.idx
            # mark it as skip so alpaca dont look for it
            self.data.loc[self.data.idx == idx, "skip"] = True
        if (len(self.yfList) == 20 or doTheRest):
            rowGroup = self.yfList.copy()
            # clear out yfList after copying it over so that more data can be queued
            self.yfList.clear()
            # use threading to get yf data cus it takes FOREVER
            thread = threading.Thread(target=self.getweeklyDataFromYF,
                                      args=[rowGroup])
            thread.start()
            self.Threads.append(thread)

    def getweeklyDataFromYF(self, rowGroup: list) -> None:
        """Takes all the queued companies from yfList and get data from each of them, then parse them
            Args:
            rowGroup (list[pd.Series]): List of rows of companies that are queued to get data from YF
        """

        for row in rowGroup:
            company = yf.Ticker(str(row.Ticker))
            filingDate = row.Filing_Date
            hist = company.history(period="3y",
                                   interval="1wk",
                                   start=filingDate,
                                   back_adjust=True)
            self.inputYFDataIntoDF(hist, row)

    def isrowDone(self, idx: int) -> bool:
        return self.data.loc[self.data.idx == idx].iloc[
            0].done or self.data.loc[self.data.idx == idx].iloc[0].skip

    def inputYFDataIntoDF(self, indivisualDF: pd.DataFrame,
                          row: pd.Series) -> None:
        """Take the stock data from YF's dataframe and puts it into the row

        Args:
            indivisualDF (pd.DataFrame): stock data for a single company 
            row (pd.Series): the row that needs the data
        """

        idx = row.idx
        # yahoo finance have a data limit so if that limit is hit then all the incomming df would be empty. so if the limit is hit
        # then the program should not mark that row as done
        self.data.loc[self.data.idx == idx, "done"] = True
        self.data.loc[self.data.idx == idx, "source"] = "YF"
        # if df is empty, no stock data is found, no need to continue
        # if theres a GIANT spike in price, like 10x from lastweeks's high and a week later, then its SUS, safer to just filter it out
        if indivisualDF.empty or not self.validateYFdf(indivisualDF):
            self.scrapper.removecount += 1
            return
        step = self.timeframe.getWeekDict()
        # first get Price at the brought date, adjusted for stock split
        try:
            priceWhenBrought = round(indivisualDF.iloc[0].Open, 3)
            self.data.loc[self.data.idx == idx, "Price"] = priceWhenBrought
            print(
                f"Opening price for {row.Ticker} is {priceWhenBrought} found on YF,count {self.count}/{len(self.data)}"
            )
            for timeframe, i in step.items():
                priceAtThatTime = round(indivisualDF.iloc[i].Open, 3)
                self.putDataIntoDF(priceAtThatTime, idx, timeframe)
        except IndexError:
            return
        except Exception as e:
            print("error:", e, "at index", idx, "FOR queueStockForYF")

    # sometimes a pre ipo price was given like for ENCR on 2015-05-08, where the price went from 0.15 to 6 overnight, but its not even publicly tradable yet
    # this will filter that out
    def validateYFdf(self, df: pd.DataFrame) -> bool:
        """Sometimes incorrect data can be given, or data from a company that the ticker previously belonged to is given
        To filter those out, it would be safer to throw out data that is suspicious.

        This function needs further exploring and is currently a bandaid solution. 

        Args:
            df (pd.DataFrame): stock data of a single company 

        Returns:
            bool: Whether or not there is a HUGE(10x) jump in price from the week to week of a stock
        """
        lastprice = df.iloc[0].High
        for i, row in df.iterrows():
            currentprice = row.High
            if ((currentprice / lastprice)> 10):
                return False
            lastprice = currentprice
        return True

    # TODO: account of stocks that filed on weekends
    def setBroughtPrice(self, filingDate: str, dailyDF: pd.DataFrame,
                        row: pd.Series) -> None:
        """Sets the price when traded by insider

        This function finds the date that the filing was announced and fill the price when filed for that row

        Args:
            filingDate (str): the date that the insider trading was made public
            dailyDF (pd.DataFrame): daily stock price of a single company
            row (pd.Series): the company's data 


        """
        idx = row.idx
        # checks if the stock had undergone a period of 0 volume, which will disqualfy a stock
        if (not self.validateAlpacaDF(dailyDF)):
            self.queueStockForYF(row)
        for timestamp, entry in dailyDF.iterrows():
            if filingDate == timestamp:
                self.data.loc[self.data.idx == idx, "Price"] = entry["open"]
                return
        # if the trade date is not in the df, then this stock's trade date is outside of two month period, 
        # so I will mark it for indivisual search.
        self.queueStockForYF(row)

    def updateConsole(self, message):
        self.clearConsole()
        print("found:", len(self.data), "results")
        print("Expected wait time: ", round(len(self.data) / 3 / 60, 2),
              "Minutes\n")
        print(message)

    def getTickersFromRowGroup(self,
                               group: pd.DataFrame,
                               asOneString: bool = True) -> list:
        """Alpaca accepts the tickers in ["AAPL,MSFT,FB"] instead of the regular way, but this function can return both
            with the asOneString param

        Args:
            group (pd.DataFrame): a group of companies from self.data
            asOneString (bool, optional): whether to return tickers as one string inisde a array or as separate elements. Defaults to True.

        Returns:
            list: returns either ["MSFT,AAPL"] or ["MSFT","AAPL"] base on asOneString
        """
        if (asOneString):
            result = ""
            for i in group:
                result += str(i["Ticker"]) + ','
            return [result[0:-1]]
        else:
            result = []
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

    def within14days(self, givendate: str, tradeDate: str) -> bool:
        """On a dataset, when a company transfers its ticekr to another company, there is a minimum two weeks window 
        where there is no activity, this function detects if any of the last avaliable data and current data have a 14 day skip.

        Args:
            givendate (str): the start date
            tradeDate (str): the other date

        Returns:
            bool: true if the two dates are within 14 days inclusive, else false 
        """
        givendate = str(givendate).split("T")[0]
        # modify it so taht alpaca df can use it too
        givendate = str(givendate).split(" ")[0]
        if (givendate == tradeDate):
            return True
        year, month, day = map(int, givendate.split("-"))
        givendate = datetime.date(year, month, day)
        year, month, day = map(int, tradeDate.split("-"))
        tradeDate = datetime.date(year, month, day)
        margin = datetime.timedelta(days=14)
        return givendate - margin <= tradeDate <= givendate + margin

    def putDataIntoDF(self, value: float, idx: str, timeframe: str):
        """ puts a price value into the result DF,
        Args:
            value (float): the price of the stock at that time
            idx (str): the idx of the row that this value belong to
            timeframe (str): this is a column in the Dataframe, eg: 6m, 4m, etc
        """
        idx = int(idx)
        value = round(value, 2)
        # this updates the price at that time frame, ie: $65 two weeks later
        self.data.loc[self.data.idx == idx, timeframe] = value

    def percentChange(self, oldprice: float, newprice: float):
        """calculates percent change

        Args:
            oldprice (_type_): the original price
            newprice (_type_): the new price

        Returns:
            _type_: percent change, eg 10 -> 20 is 100% change
        """
        result = 0
        if oldprice == newprice:
            return 0
        if oldprice < newprice:
            result = (newprice - oldprice) / oldprice
        else:
            result = -(oldprice - newprice) / oldprice
        return round(result * 100, 2)

    def updatepercentChange(self):
        """after getting all the stock data, the percent changes are filled in from the original
        """
        for i, row in self.data.iterrows():
            oldprice = self.data.at[i, "Price"]
            # t is ["2w","1m"...]
            for t in self.timeframe.timeframe:
                newprice = row[t]
                if (newprice != 0):
                    self.data.at[i, f"{t}%"] = self.percentChange(oldprice, newprice)
        print("done updating percent change")

    def validateAlpacaDF(self, df: pd.DataFrame) -> bool:
        """
        fixing annoying bugs for alpaca api, such as having a stock data before stock even ipos, but its always followed by volumn=0 for a few weeks
        also when ticker changes companies, there will be gaps between
        Args:
            df (pd.DataFrame): the stock data for a single comany
        Returns:
            bool: true if the data is valid, false if not
        """
        if len(df) == 0:
            return False
        consecutive = 0
        last_date = df.index.values[0]
        for trade_date, row in df.iterrows():
            if (not self.within14days(trade_date, last_date)):
                return False
            if row.volume == 0:
                consecutive += 1
                if (consecutive == 2):
                    print(df.loc[df.volume == 0])
                    return False
            else:
                consecutive = 0
            last_date = trade_date
        return True

    def getStartAndEndDate(self, tradeDate):
        y, m, d = map(int, tradeDate.split("-"))
        startTradeDate = datetime.date(y, m, d) - datetime.timedelta(days=4)
        fivemonths = datetime.timedelta(days=152)
        endTradeDate = startTradeDate + fivemonths
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        if (endTradeDate >= yesterday):
            return [str(startTradeDate), str(yesterday)]
        return [str(startTradeDate), str(endTradeDate)]

    def getCompanyandSymbol(self, assets) -> dict:
        result = {}
        for i in assets:
            # convert it all to lowercase because sometimes things like "New Therapical" and "NEW Therapical" can appear
            companyName = self.stripNonAlpabet(i.name.lower())
            # some company have some off shore 1/40th owhershup stock or something that have very long names
            # if the names too long, its out
            if (len(companyName) > 100):
                continue
            partialName = companyName[0:10]
            indivisual_company = {companyName: i.symbol, "exhange": i.exchange}
            if (partialName not in result):
                result[partialName] = []
            result[partialName].append(indivisual_company)
        return result


    def findClosestMatch(self, companies: list, companyName: str) -> tuple:
        """some companies have the same first 10 letters so they are divided into sub groups, 
            this function takes the subgroup (companies), and try to match the closest one to the companyName
            like consolidated Edison(NYSE:ED) would return instead of consolidated Water(CWCO)
        
        Args: companies(list(str)): list of dicts with companyName and ticker   
                                    e.g.[{"consolidatededison": ED,"exchange":NYSE},{"consolidatedwater":COHW,"exhcange":"NYSE"}]
              companyName(str): str, stripped company name lowercase, example: consolidatededison
        Returns:
            _type_: given the companyName, this should return (ED,NYSE)
        """
        if len(companies) == 1:
            if companyName[-5:] not in list(companies[0].keys())[0]:
                return (None, None)
            return companies[0].values()
        longestsimilar = 0
        index = 0
        for i, company in enumerate(companies):
            name = list(company.keys())[0]
            if (longestsimilar < self.getLongestSimilarInitial(
                    companyName, name)):
                longestsimilar = self.getLongestSimilarInitial(
                    companyName, name)
                index = i
        result = companies[index].values()
        resultname = list(companies[index].keys())[0]
        if ("blackdiamond" in companyName):
            print(companies)
        # last 5 character usally diffienciates between companies. So if its not in there, then this is a different company
        if companyName[-5:] not in resultname:
            return (None, None)
        return result

    # apprently "Perma-fix" and "Perma fix" are not the same thing!
    def stripNonAlpabet(self, string):
        # regex the string to only lowercase a-z
        return self.regex.sub("", string)

    def getLongestSimilarInitial(self, originalstr, comparestr):
        """
            Given "abcdef" and "abc123"
            return 3
        """
        count = 0
        for i, char in enumerate(comparestr):
            try:
                if originalstr[i] != char:
                    break
            except IndexError:
                break
            count += 1
        return count

    # this function removes all the Companys where data cannot be attained from, or two weeks has not passed
    def cleanUp(self):
        # TODO think of a better way to approach this function.
        # drop those without price or no 2week data
        # self.data = self.data[self.data["skip"]==False]
        # self.data = self.data.dropna(axis=0,subset=["Price"])
        # self.data = self.data[self.data["Price"]!=0]
        # self.data = self.data.loc[self.data["2w"]!=0]
        self.scrapper.updateScrapped()
        self.print_summary()

    def print_summary(self):
        print(
            "----------------------------------------------------------------------------------------"
        )
        print(
            f"\ndone,removed {self.scrapper.removecount} entries because no stock data can be found by them, or they are overlapps"
        )
        print(
            "NO stock data can mean multiple things: ticker change, merger, acqusition, going private, or bankruptcy"
        )
        print(
            f"Had to update the tickers of {self.scrapper.changeTickerCount} companies"
        )
        print(
            "----------------------------------------------------------------------------------------"
        )

    # gets api keys if they exist, set them up if they dont
    def getApiKey(self):
        PUBLIC_KEY = os.getenv("ALPACA_PUBLIC_KEY")
        SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
        ENDPOINT = os.getenv("ALPACA_ENDPOINT")
        if (not PUBLIC_KEY):
            ENDPOINT = "https://paper-api.alpaca.markets"
            print(
                """Looks like you dont have an alpaca api key yet, its ok, just follow this doc: 
                https://docs.google.com/document/d/1wdcO4dxtI0B5Ki6PVoLiNI4UsVR7oe1t_AtQOdYHV0A/edit?usp=sharing  
               this process probably only takes a minute"""
            )
            with open(".env", 'w') as f:
                f.write(f"ALPACA_ENDPOINT= {ENDPOINT} \n")
                PUBLIC_KEY = input("the API Key ID: ")
                SECRET_KEY = input("the Secret Key: ")
                f.write(f"ALPACA_SECRET_KEY= {SECRET_KEY} \n")
                f.write(f"ALPACA_PUBLIC_KEY= {PUBLIC_KEY}")
                f.close()
        return {
            "PUBLIC_KEY": PUBLIC_KEY,
            "SECRET_KEY": SECRET_KEY,
            "END_POINT": ENDPOINT
        }

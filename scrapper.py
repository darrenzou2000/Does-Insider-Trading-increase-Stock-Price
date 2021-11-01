#import requests to get website source data
import requests
import pandas as pd
from bs4 import BeautifulSoup
import numpy as np
import json
from DataGetter import DataGetter
#NOTE: this scrapper is built only for opensider.com


#functions: init: takes the url of the open insider page that u are tyring to scrape from, outputs a csv file of the table shown.
# example: url: http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=365&tdr=&fdlyl=&fdlyh=&daysago=14&xp=1&vl=&vh=&ocl=5&och=&sic1=-1&sicl=100&sich=9999&isceo=1&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1
#          csvFilePath: CEO.csv 
#          description: "this tracks the purchases of CEOS of a company that have a % change in ownership of 5% or more in the last year 
#                        and more than 14 days ago puts the output into a csv file named CEO.csv"

class Scrapper():
    data = pd.DataFrame()
    def __init__(self,url:str,csvFilePath:str,description:str) -> None:
        print("Scrapping Openinsider.com... please wait a few seconds")
        self.url = url
        self.csvFilePath = csvFilePath
        self.description = description
        #if the site is scrapped already, no need to waste time doing it again
        if(self.alreadyscrapped()):
            self.data = pd.read_csv(csvFilePath)
            self.originalSize = len(self.data)
            getter = DataGetter()
            getter.update(self)
            return
        #insider data contains all the major fields, this will be converted into dataframe and eventurally csv
        insiderData = {'Filing_Date':[], 'Trade_Date':[], 'Ticker':[], 'Company_Name':[], 'Insider_Name':[], 'Title':[], 'Trade_Type':[], 'Price':[], 'Qty':[], 'Owned':[], 'ΔOwn':[], 'Value':[]}
        #takes the html data of requests and puts it into insider data
        insiderData = self.turnDataintodict(insiderData,url)
        self.data= pd.DataFrame(data = insiderData)
        self.originalSize = len(self.data)
        #this is added so stocks after the time period can be filled in.
        self.data[['2w', '1m', '4m', '6m', '1yr', '2yr']]= 0.0
        #this is change in % since brought
        self.data[['2w%', '1m%', '4m%', '6m%', '1yr%', '2yr%', 'done']] = 0.0
        self.data["done"]=False
        #remove trades that happens on the same day same time
        self.data = self.data.drop_duplicates(['Ticker','Trade_Date'],keep= 'last')
        self.data.to_csv(csvFilePath)   
        self.addToScrapped()
        
        #after scrapping data, fill in the stock price after time Frame
        getter = DataGetter()
        getter.update(self)
    def turnDataintodict(self,insiderData,url) ->dict:
        result = requests.get(url)
        src = result.content
        soup = BeautifulSoup(src,"lxml")
        body = soup.find_all("tbody")[1]
        rows = body.find_all("tr")
        #parsing table data from open insider
        for items in rows:
            column = items.find_all("td")
            Filing_Date = self.getchildData(column[1],"div a") 
            insiderData["Filing_Date"].append(Filing_Date)
            Trade_Date = self.getchildData(column[2],"div") 
            insiderData["Trade_Date"].append(Trade_Date)
            Ticker = self.getchildData(column[3],"b a") 
            insiderData['Ticker'].append(Ticker)
            Company_Name = self.getchildData(column[4],"a") 
            insiderData['Company_Name'].append(Company_Name)
            Insider_Name = self.getchildData(column[5],"a") 
            insiderData['Insider_Name'].append(Insider_Name)
            Title = column[6].get_text()
            insiderData['Title'].append(Title)
            Trade_Type =column[7].get_text()
            insiderData['Trade_Type'].append(Trade_Type)
            Price =self.toFloat(column[8].get_text()) 
            insiderData['Price'].append(Price)
            Qty = self.toFloat(column[9].get_text())
            insiderData['Qty'].append(Qty)
            Owned =self.toFloat(column[10].get_text()) 
            insiderData['Owned'].append(Owned)
            ΔOwn =self.toFloat(column[11].get_text())
            insiderData['ΔOwn'].append(ΔOwn)
            Value = self.toFloat(column[12].get_text())
            insiderData['Value'].append(Value)
        #if the number if rows is 1000, then there might be more data on the next page, so we go to the next page
        if(len(rows)==1000):
            #pagenumber is found at the end of the url
            page = int(url[-2:].replace("=","")) 
            #99 is the page limit
            if(page<100):
                url = url.split("page=")[0] + "page=" + str(page+1)
                print("currently scanning page:",page, "entries gotten so far:",(page)*1000)
                #recursion until all the 
                insiderData = self.turnDataintodict(insiderData,url)
        return insiderData

    def __repr__(self):
        return "-------------------------------------------------------\nDESCRIPTION: "+ self.description+ "\n found: "+ str(len(self.data))+ " entries"+"\n Located at:"+self.csvFilePath+"\n-------------------------------------------------"
    def get_data(self)->pd.DataFrame:
        return self.data
    #this is so that running the code multiple times with the same url wont take so long.
    def alreadyscrapped(self)->bool:
        f = open("alreadyscrapped.json")
        scrapped = json.load(f)["Scrapped"]
        f.close()
        for entry in scrapped:
            if self.description == entry["description"]:
                return True
        return False

    #stripes unnessary symbols  
    def toFloat(self,input):
        if input == "New":
            return "New"
        removelist = ["+","%",",", "$",">"]
        for i in removelist:
            input = input.replace(i,"")
        return float(input)
    def to_csv(self):
        self.data.to_csv(self.csvFilePath,index=False)

    def addToScrapped(self)->None:
        f = open("alreadyscrapped.json")
        scrapped = json.load(f)
        data = {"url":self.url,"description":self.description,"filePath":self.csvFilePath,"count":self.originalSize}
        scrapped["Scrapped"].append(data)
        with open("alreadyscrapped.json","w") as f:
            json.dump(scrapped,f)
        f.close()


    #sometimes the data in a table is enwrapped in a div or h3 or a tag or multiple layers, this function will traverse through it all to get the data
    def getchildData(self,data,path)->str:
        path = path.split(" ")   
        childNode = None
        for child in path:
            childNode= data.find(child)
        return childNode.get_text()
    



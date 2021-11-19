
from bs4 import BeautifulSoup

import requests 

import pandas as pd

def toFloat(input):
        if input == "New":
            return "New"
        removelist = ["+","%",",", "$",">"]
        for i in removelist:
            input = input.replace(i,"")
        return float(input)

def getchildData(data,path)->str:
        path = path.split(" ")   
        childNode = None
        for child in path:
            childNode= data.find(child)
        return childNode.get_text()
    
def extractDataFromWebsite(insiderData,url) ->dict:
        result = requests.get(url)
        src = result.content
        soup = BeautifulSoup(src,"lxml")

        #find the table
        body = soup.find_all("tbody")[1]

        #find all the rows inside the body
        rows = body.find_all("tr")
        #parsing table data from open insider
        for entry in rows:
            #gets all the indivisual data slots
            column = entry.find_all("td")
            Filing_Date = getchildData(column[1],"div a") 
            insiderData["Filing_Date"].append(Filing_Date)
            Trade_Date = getchildData(column[2],"div") 
            insiderData["Trade_Date"].append(Trade_Date)
            Ticker = getchildData(column[3],"b a") 
            insiderData['Ticker'].append(Ticker)
            Company_Name = getchildData(column[4],"a") 
            insiderData['Company_Name'].append(Company_Name)
            Insider_Name = getchildData(column[5],"a") 
            insiderData['Insider_Name'].append(Insider_Name)
            Title = column[6].get_text()
            insiderData['Title'].append(Title)
            Trade_Type =column[7].get_text()
            insiderData['Trade_Type'].append(Trade_Type)
            Price =toFloat(column[8].get_text()) 
            insiderData['Price'].append(Price)
            Qty = toFloat(column[9].get_text())
            insiderData['Qty'].append(Qty)
            Owned =toFloat(column[10].get_text()) 
            insiderData['Owned'].append(Owned)
            OwnChange =toFloat(column[11].get_text())
            insiderData['ΔOwn'].append(OwnChange)
            Value = toFloat(column[12].get_text())
            insiderData['Value'].append(Value)
        #if the number if rows is 1000, then there might be more data on the next page, so we go to the next page
        if(len(rows)==1000):
            #pagenumber is found at the end of the url
            page = int(url[-2:].replace("=","")) 
            #9 is the page limit or 9000 entries
            if(page>=10):
                return insiderData
            url = url.split("page=")[0] + "page=" + str(page+1)
            print("currently scanning page:",page, "entries gotten so far:",(page)*1000)
            #recursion until all the pages are done
            insiderData = extractDataFromWebsite(insiderData,url)
        return insiderData


if(__name__=="__main__"):
    url = ""
    filename = "data.csv"
    print("extracting data!")
    insiderData = {'Filing_Date':[], 'Trade_Date':[], 'Ticker':[], 'Company_Name':[], 'Insider_Name':[], 'Title':[], 'Trade_Type':[], 'Price':[], 'Qty':[], 'Owned':[], 'ΔOwn':[], 'Value':[]}
    insiderData = extractDataFromWebsite(insiderData,url)
    df = pd.DataFrame(data=insiderData)
    print(f"success! Found {len(df)} entries!")
    df.to_csv("data.csv",index=False)
    print(f"Stored result to {filename}")
    
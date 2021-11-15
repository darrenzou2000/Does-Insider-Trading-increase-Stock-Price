
from scrapper import Scrapper
from DataGetter import DataGetter
from result import Result
import json
import os
import pandas as pd
from pathlib import Path
class App():
    def __init__(self) -> None:
        self.printScrapped()
        self.generalData()

    def printScrapped(self):
        f=open("alreadyscrapped.json")
        self.scrapped = json.load(f)
        f.close()
        print("Found the following:")
        count = 1
        for entry in self.scrapped["Scrapped"]:
            print(count,":",entry["description"], "// Located at", entry["filePath"], "// count", entry["count"])
            count+=1
        if(len(self.scrapped["Scrapped"])==0):
            print("(No data is found, please enter new)")
        self.getScrapper()

    def generalData(self):
        df = self.scrapper.get_data()
        result = Result(self.scrapper)
        result.getPositive(df)
        result.getAVG(df)
        result.getactive(df)

    def getScrapper(self)-> Scrapper:
        action = input("\ntype the number of the data you want to check or 'new' if you want to add another one (or 'remove' and 'redo'):\n")
        try:
            index = int(action)-1
            while(index>=len(self.scrapped["Scrapped"])):
                index = int(input("out of range, please enter the number of the index you want to see: "))-1
            obj = self.scrapped["Scrapped"][index]
            url = obj["url"]
            desc = obj["description"]
            filePath = obj["filePath"]
        except Exception as e:
            if(action.strip() =="remove"):
                self.removefile()
                self.printScrapped()
                return
            if(action.strip().lower()=="new"):
                self.check_alpaca_api_keys()
                url = input("enter Openinsider Url:\n --------------------\n example: http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=-1&fdr=11%2F08%2F2011+-+11%2F18%2F2021&td=0&tdr=&fdlyl=&fdlyh=&daysago=70&xp=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=2&nfl=&nfh=&nil=2&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1\n---------------------\n")
                desc = input("Enter the description for this: \n --------------------\nexample: CEO purchase last 4 years with own change >5%\n---------------------\n")
                filename = input("enter file name, \n---------------------\n example: CEO BUYS from 2014 to 2020\n---------------------\n ").replace(" ","_").strip()
                filePath = self.createFile(filename)
            if(action.strip().lower()=="redo"):
               url,desc,filePath=self.redo()
            else:
                print("Not an option please enter: new, remove,  or redo")   
        scrapper = Scrapper(url,filePath,desc)
        self.scrapper = scrapper

    def getDataframe(self,filename):
        df = pd.read_csv(f"data/{filename}.csv")
        return df

    def createFile(self,filename):
        path = "data/"
        dir_list = os.listdir(path) 
        if (filename in dir_list):
            while(filename in dir_list):
                print("filename", filename, "taken")
                filename = input("enter a new one: ")
        with open(f'data/{filename}.csv', 'w') as fp:
            pass
        print(f"file created: {filename}.csv")
        return f"data/{filename}.csv"
    def removefile(self):
        idx = int(input("enter index of the data you want to remove: "))-1
        print(idx+1,":",self.scrapped["Scrapped"][idx]["description"], "// Located at", self.scrapped["Scrapped"][idx]["filePath"])
        confirm =input("are you sure you want to delete the above? (y or n): ")
        obj = self.scrapped["Scrapped"][idx]
        filePath = obj["filePath"]
        if confirm == "y" or confirm =="1":  
            print("\n\nREMOVED:")
            print(idx+1,":",self.scrapped["Scrapped"][idx]["description"], "// Located at", self.scrapped["Scrapped"][idx]["filePath"],"\n\n")
            del self.scrapped["Scrapped"][idx]
            with open("alreadyscrapped.json","w") as f:
                json.dump(self.scrapped,f)
            os.remove(filePath)
    def redo(self):
        index = int(input("enter index of data you want to redo: "))-1
        obj = self.scrapped["Scrapped"][index]
        url = obj["url"]
        desc = obj["description"]
        filePath = obj["filePath"]
        os.remove(filePath)
        with open(filePath, 'w') as fp:
            pass
        del self.scrapped["Scrapped"][index]
        with open("alreadyscrapped.json","w") as f:
            json.dump(self.scrapped,f)
        return [url,desc,filePath]
    def check_alpaca_api_keys(self):
        key_file = Path("key/alpaca_keys.txt")
        if not key_file.is_file():
            print("You might want to get the API keys for alpaca to drastically speed up the data gathering process(im talking over 70% speed up")
            print("completely free, about a minute and you dont need to give ANY personal data to anyone")
            print("follow this tutorial: (yt video link here")
            option = input("do you want to enter your api keys now? (y or n)")
            if(option == "y" or option == "yes"):
                API_KEY = input("PUBLIC API KEY: \n")
                SECRET_KEY = input("SECRET KEY: \n")
                END_POINT = input("END_POINT:\n ")
                self.createAPIKEYSfile(API_KEY,SECRET_KEY,END_POINT)
                return {"PUBLIC_KEY":API_KEY,"SECRET_KEY":SECRET_KEY,"END_POINT":END_POINT}
            else:
                print("alright, if this query have over 9000 results, then it will take about 5 hours")
                return
        else:
            with open(key_file,"r") as f:
                line= f.read().strip().split(" ")
                API_KEY,SECRET_KEY,END_POINT=line 
            return {"PUBLIC_KEY":API_KEY,"SECRET_KEY":SECRET_KEY,"END_POINT":END_POINT}
    
    def createAPIKEYSfile(self,public_key,secret_key,endpoint):
        key_file = Path("key/alpaca_keys.txt")
        if not key_file.is_file():
            with open("key/alpaca_keys.txt",'w') as f:
                f.write(f"{public_key} {secret_key} {endpoint}")
            f.close


#drops the 5 from both ends so the avg is more representative

if __name__ == "__main__":
    a = App()



    #dont worry aobut this,its just there so I can leave data gathering over night
    # url = ["http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=-1&fdr=11%2F08%2F2011+-+11%2F18%2F2021&td=-1&tdr=11%2F08%2F2011+-+11%2F18%2F2021&fdlyl=&fdlyh=&daysago=70&xp=1&vl=&vh=&ocl=5&och=&sic1=-1&sicl=100&sich=9999&isceo=1&grp=0&nfl=&nfh=&nil=2&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1","http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=-1&fdr=11%2F08%2F2011+-+11%2F18%2F2021&td=-1&tdr=11%2F08%2F2011+-+11%2F18%2F2021&fdlyl=&fdlyh=&daysago=70&xp=1&vl=&vh=&ocl=5&och=&sic1=-1&sicl=100&sich=9999&ispres=1&grp=0&nfl=&nfh=&nil=2&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1","http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=-1&fdr=11%2F08%2F2011+-+11%2F18%2F2021&td=-1&tdr=11%2F08%2F2011+-+11%2F18%2F2021&fdlyl=&fdlyh=&daysago=70&xp=1&vl=&vh=&ocl=5&och=&sic1=-1&sicl=100&sich=9999&iscfo=1&grp=0&nfl=&nfh=&nil=2&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1","http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=-1&fdr=11%2F08%2F2011+-+11%2F18%2F2021&td=-1&tdr=11%2F08%2F2011+-+11%2F18%2F2021&fdlyl=&fdlyh=&daysago=70&xp=1&vl=&vh=&ocl=5&och=&sic1=-1&sicl=100&sich=9999&isdirector=1&grp=0&nfl=&nfh=&nil=2&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1"]
    # desc = ["CEO purchases 5% or up from 2011 to 2021","Pres purchases 5% or up from 2011 to 2021","CFO purchases 5% or up from 2011 to 2021","DIrector purchases 5% or up from 2011 to 2021"]
    # filepath=["data/CEO_PURCHASE_2011_2021.csv","data/Pres_PURCHASE_2011_2021.csv","data/CFO_PURCHASE_2011_2021.csv","data/Director_PURCHASE_2011_2021.csv"]

    # for i in range(3):
    #     scrapper = Scrapper(url[i],filepath[i],desc[i])

from scrapper import Scrapper
from DataGetter import DataGetter
from result import Result
import json
import os
import pandas as pd

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
        self.scrapper= self.getScrapper()

    def generalData(self):
        df = self.scrapper.data
        result = Result()
        result.getPositive(df)
        result.getAVG(df)
        print(self.scrapper)
    def getScrapper(self)-> Scrapper:
        action = input("\ntype the number of the data you want to check or 'new' if you want to add another one (or 'remove'):\n")
        try:
            index = int(action)-1
            while(index>=len(self.scrapped["Scrapped"])):
                index = int(input("out of range, please enter the number of the index you want to see: "))-1
            obj = self.scrapped["Scrapped"][index]
            url = obj["url"]
            desc = obj["description"]
            filePath = obj["filePath"]
        except Exception as e:
            if(action =="remove"):
                obj = self.scrapped["Scrapped"][index]
                filePath = obj["filePath"]
                self.removefile(filePath)
                self.printScrapped()
                return
            url = input("enter Url: ")
            desc = input("Enter the description for this: example: CEO purchase last 4 years with own change >5%\n  ")
            filename = input("enter file name,  example: CEOPurchaseOnly\n  ").replace(" ","_")
            filePath = self.createFile(filename)
        return Scrapper(url,filePath,desc)

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
    def removefile(self,filepath):
        idx = int(input("enter index of the data you want to remove: "))-1
        print(print(idx+1,":",self.scrapped["Scrapped"][idx]["description"], "// Located at", self.scrapped["Scrapped"][idx]["filePath"]))
        confirm =input("are you sure you want to delete the above? (y or n): ")
        if confirm == "y":
            del self.scrapped["Scrapped"][idx]
            with open("alreadyscrapped.json","w") as f:
                json.dump(self.scrapped,f)
            os.remove(filepath)
        



#drops the 5 from both ends so the avg is more representative

if __name__ == "__main__":
    a = App()
    backupurl = ["http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=-1&tdr=01%2F01%2F2011+-+07%2F13%2F2021&fdlyl=&fdlyh=&daysago=&xp=1&vl=&vh=&ocl=4&och=&sic1=-1&sicl=100&sich=9999&iscfo=1&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1","http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=-1&tdr=01%2F01%2F2011+-+07%2F13%2F2021&fdlyl=&fdlyh=&daysago=&xp=1&vl=&vh=&ocl=4&och=&sic1=-1&sicl=100&sich=9999&iscoo=1&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1","http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=-1&tdr=01%2F01%2F2011+-+07%2F13%2F2021&fdlyl=&fdlyh=&daysago=&xp=1&vl=&vh=&ocl=20&och=&sic1=-1&sicl=100&sich=9999&isdirector=1&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1"]
    backupDESC = ["CFO Buys 2011 to 2021 own change >4%","COO Buys 2011 to 2021 own change >4%","Director buys 2011 to 2011 OC>20%"]
    backupFileName = ["CFO Buys 2011 to 2021","COO Buys 2011 to 2021 ","Director buys 2011 to 2011"]
    for i in range(3):
        a.createFile(backupFileName[i])
        Scrapper(backupurl[i],backupFileName[i],backupDESC[i])



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
            if(action.strip() =="remove"):
                self.removefile()
                self.printScrapped()
                return
            url = input("enter Url: ")
            desc = input("Enter the description for this: example: CEO purchase last 4 years with own change >5%\n  ")
            filename = input("enter file name,  example: CEOPurchaseOnly\n  ").replace(" ","_").strip()
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
    def removefile(self):
        idx = int(input("enter index of the data you want to remove: "))-1
        print(idx+1,":",self.scrapped["Scrapped"][idx]["description"], "// Located at", self.scrapped["Scrapped"][idx]["filePath"])
        confirm =input("are you sure you want to delete the above? (y or n): ")
        obj = self.scrapped["Scrapped"][idx]
        filePath = obj["filePath"]
        if confirm == "y":  
            print("\n\nREMOVED:")
            print(idx+1,":",self.scrapped["Scrapped"][idx]["description"], "// Located at", self.scrapped["Scrapped"][idx]["filePath"],"\n\n")
            del self.scrapped["Scrapped"][idx]
            with open("alreadyscrapped.json","w") as f:
                json.dump(self.scrapped,f)
            os.remove(filePath)
        



#drops the 5 from both ends so the avg is more representative

if __name__ == "__main__":
    a = App()

from scrapper import Scrapper
from DataGetter import DataGetter
from result import Result
import json
import os
import pandas as pd
from pathlib import Path
import os

#this class is the interface to easily access previously gathered data, The acutal scrapper is in scrapper.py and the data gathering from apis is in DataGetter.py
class App():
    def __init__(self) -> None:
        self.removeEmptyDataFiles()
        self.printScrapped()
        self.generalData()

    #prints the previously scanned filters 
    def printScrapped(self) -> None:
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
        self.setScrapper()

    #after a dataframe is selected or genereated, print out the normal data that people want to see like average, % that returns positive, and stocks taht are still tradeable today. 
    def generalData(self) ->None:
        df = self.scrapper.get_data()
        result = Result(self.scrapper.get_data())
        result.getPositive()
        result.getAVG()
        result.getactive()

    #This gets the input of the user based on what they want, like view past data or make a new entry from the website
    def setScrapper(self)-> None:
        action = input("\ntype the number of the data you want to check or 'new' if you want to add another one (or 'remove' and 'redo'):\n")

        #if action is a number then they want to view past data base on an index
        if(action.isnumeric()):
            index = int(action)-1
            while(index>=len(self.scrapped["Scrapped"])):
                index = int(input("out of range, please enter the number of the index you want to see: "))-1
            obj = self.scrapped["Scrapped"][index]
            url = obj["url"]
            desc = obj["description"]
            filePath = obj["filePath"]

        else:
            action = action.strip().lower()
            if(action == "remove"):
                self.removefile()
                self.printScrapped()
                return

            elif(action == "new"):
                url = input("enter Openinsider Url:\n --------------------\n example: http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=-1&fdr=11%2F08%2F2011+-+11%2F18%2F2021&td=0&tdr=&fdlyl=&fdlyh=&daysago=70&xp=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=2&nfl=&nfh=&nil=2&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1\n---------------------\n")
                desc = input("Enter the description for this: \n --------------------\nexample: CEO purchase last 4 years with own change >5%\n---------------------\n")
                filename = input("enter file name, \n---------------------\n example: CEO BUYS from 2014 to 2020\n---------------------\n ").replace(" ","_").strip()
                filePath = self.createFile(filename)

            elif(action == "redo"):
                url,desc,filePath=self.redo()
            else:
                print("action not found, please enter one of the following: remove, new, redo")
                self.setScrapper()
        
        # this is the acutal scrapper that goes to openinsider.com and gets the data
        scrapper = Scrapper(url,filePath,desc)
        self.scrapper = scrapper

    #makes the file that user want to create under the "./data" folder
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

    #removes the data entry from already scrapped 
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

    #rescrapes the openinsider website and the data gathering process, this is basicly remove then remake 
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
    
        
    
    def removeEmptyDataFiles(self):
        dir_path ="data/"
        for root, dirnames, files in os.walk(dir_path):
            for f in files:
                full_name = os.path.join(root, f)
                if os.path.getsize(full_name) == 0:
                    print("removed",full_name, "because it is empty")
                    os.remove(full_name)

#drops the 5 from both ends so the avg is more representative

if __name__ == "__main__":
    a = App()
import pandas as pd

class Result():
    def __init__(self) -> None:
        self.timeframe = ["2w","1m","4m","6m","1yr","2yr"]
        return

    #gets average of every column 
    def getAVG(self,df):
        result = {f"{x}":None for x in self.timeframe}
        for time in self.timeframe:
            try:
                # gets all entry thats not empty for that time (eg: 6 dollars after 4 month)
                drop0 = df.loc[df[time]>0].drop_duplicates(subset='Ticker', keep="first")
                drop0=drop0.sort_values(by=[f'{time}%'],ascending=False)
                average = drop0.mean(axis=0,numeric_only=True)
                result[f"{time}"]= round(average[f'{time}%'],2)
            except:
                continue
        print("\n-----------------------------------------------\nTHIS IS AVERAGE  ")
        for time,data in result.items():
            print(f"For {time}, the average return is {data}%")
        return result

    def getPositive(self,df):
        print("\n-----------------------------------------------\nTHIS IS NUMBER OF POSITIVE RETURNS")
        for time in self.timeframe:
            try:
                havereturn = df.loc[df[time]>0].drop_duplicates(subset='Ticker', keep="first")
                positive = havereturn.loc[df[f"{time}%"]>0]
                median = round(positive.median(axis=0,numeric_only=True)[time],2)
                print(f"out of {len(havereturn)}, {len(positive)} returned a profit after {time}, about {round(len(positive)/len(havereturn)*100,2)}% mode: {median}% return") 
            except:
                continue
        print("\n-----------------------------------------------")

        top = df.sort_values(by=["1yr%"],ascending=False).drop_duplicates(subset='Ticker', keep="first").head(5)
        top = top.loc[df["1yr"]!=0]
        if(top.empty):
            return
        print("Here are the top 5 returns after 1 year")
        for i,row in top.iterrows():
            ticker = row["Ticker"]
            yearReturn = row["1yr%"]
            broughton = row["Trade_Date"]
            deltaOwnership = row["ΔOwn"]
            print(f"{yearReturn}% for {ticker} brought on {broughton}, %change in ownership {deltaOwnership}%")
    
            

    
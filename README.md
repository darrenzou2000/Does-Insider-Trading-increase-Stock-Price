Project dev: Darren Zou 
Started at 10/18/2021

What is this project?

I built a webscrapping bot to scrape insider trading from openinsider.com and then get price changes up to two years after they are traded and then display relavent data

Technologies used:
Language: Python 3.8
Beautiful soup (for webscrapping)
Pandas Dataframe (for everything)
API with Alpaca and Yahoo finance

Results:
I scrapped over 10k entries and find that in most cases, the insider made a return! 
Here are some examples:
```
-----------------------------------------------
THIS IS NUMBER OF POSITIVE RETURNS
out of 1448, 756 returned a profit after 2w, about 52.21% mode: 10.62% return
out of 1455, 814 returned a profit after 1m, about 55.95% mode: 11.38% return
out of 1441, 860 returned a profit after 4m, about 59.68% mode: 12.7% return
out of 1450, 881 returned a profit after 6m, about 60.76% mode: 13.75% return
out of 1382, 843 returned a profit after 1yr, about 61.0% mode: 17.53% return
out of 1129, 665 returned a profit after 2yr, about 58.9% mode: 18.82% return

-----------------------------------------------
Here are the top 5 returns after 1 year
5455.0% for FNGR brought on 2020-05-01, %change in ownership 180.0%
4275.0% for IGSC brought on 2018-03-29, %change in ownership 23.0%
3846.43% for FTLF brought on 2018-08-15, %change in ownership 7.0%
2591.49% for OSTK brought on 2020-03-18, %change in ownership 55.0%
2483.33% for TOGL brought on 2016-12-02, %change in ownership 999.0%

-----------------------------------------------
THIS IS AVERAGE  
For 2w, the average return is 2.05%
For 1m, the average return is 4.9%
For 4m, the average return is 20.54%
For 6m, the average return is 30.1%
For 1yr, the average return is 56.18%
For 2yr, the average return is 54.35%
-------------------------------------------------------
DESCRIPTION: CEO purchase from 2011 ownchange>5%
 found: 3509 entries
 Located at:data/CEO2011to2021.csv
-------------------------------------------------
```

PYTHON VERSION USED: 3.8.10

TO USE IT:

1: Install anaconda, https://www.anaconda.com/

2: open a powershell if you are on windows or just terminal if you are on mac/linux

3: verify that conda is install by typing "conda" in terminal

4: type this command 
```
conda create --name insider python=3.8.10
```

5: then activate the enviornment you just created:
```
conda activate insider
```

6: install all dependencies
```
pip install -r requirements.txt 
```

7: run the program: 
```
python main.py
```


After running it, head to 

http://openinsider.com/

enter in any filter you want 

![image](https://user-images.githubusercontent.com/89553844/157266948-6cf8b55d-0cc7-4adb-9e9b-04cb2055ecb0.png)

NOTE: DO NOT enter a ticker or insider name

Note: This bot is currently only built to look at purchases only. 

*Also remember to set the Max results to 1000*

8: 
Copy the url and follow the program instructions.


Future plans: Add a web interface to make this project more people friendly













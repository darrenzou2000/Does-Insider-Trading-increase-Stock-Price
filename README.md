First of all watch this video, it tells you everything:
(video link for when I acutally does it)


What is this project?

Im sick and tired of losing money on Robinhood like an absolute idiot, so I wanted to see whether or not Insider trading will yeild me better results
I scrape data from OpenInsider.com and using Yahoo Finance, find the results of insider trading and it mostly been positive. 

Technologies used:
Language: Python 3.8
Beautiful soup (for webscrapping)
Pandas Dataframe (for storing data)

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

import requests
from bs4 import BeautifulSoup
import pandas as pd

standings_url = "https://fbref.com/en/comps/9/premier-league-stats"

# download the page, will make req to server and download html of the page
data = requests.get(standings_url)

# get BeautifulSoup object for HTML parsing
soup = BeautifulSoup(data.text, features="html.parser")

# need to select table which has the epl standings. From here can go to each teams website and get match logs
standings_table = soup.select('table.stats_table')[0]

# get all of the anchor (a) tags, these are all the teams
links = standings_table.find_all('a')

# go through a elements, and finds value of href property
links = [l.get("href") for l in links]

# filter links to make sure we get squad (team) links
links = [l for l in links if '/squad' in l]

# create proper links for all teams
team_urls = [f"https://fbref.com{l}" for l in links]

team_url = team_urls[0]
data = requests.get(team_url)

# turn match table into dataframe. Match will look for string in table. Scanning all table tags on page and looking for scores and fixtures
matches = pd.read_html(data.text, match="Scores & Fixtures")
print(matches)
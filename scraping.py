import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

standings_url = "https://fbref.com/en/comps/9/premier-league-stats"

# download the page, will make req to server and download html of the page
data = requests.get(standings_url)

if data.status_code == 429:
    print(f"Too many requests. Try again after {data.headers.get('Retry-After', 'a while')} seconds.")

# check if request went through, possible that there are too many requests
if data.status_code != 200:
    print(f"Error: Received status code {data.status_code}")
    exit()

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
matches = pd.read_html(data.text, match="Scores & Fixtures")[0]

# now want to get shooting stats, similar approach as above
soup = BeautifulSoup(data.text, features="html.parser")
links = soup.find_all('a')
links = [l.get("href") for l in links]

# looking for elements with shooting links
links = [l for l in links if l and 'all_comps/shooting/' in l]

# download html of shooting stats page
data = requests.get(f"https://fbref.com{links[0]}")

shooting = pd.read_html(data.text, match="Shooting")[0]

# get rid of top row, useless information
shooting.columns = shooting.columns.droplevel()

# At this point, matches and shooting dataframe rows will have information on the same matches, so they can be merged

team_data = matches.merge(shooting[["Date", "Sh", "SoT", "Dist", "FK", "PK", "PKatt"]], on="Date")

# UPSCALING
# we will use a loop to get data for previous seasons
years = list(range(2025, 2023, -1))

# this list will contain dataframes, each dataframe will contain match logs for 1 team in 1 season
all_matches = []

standings_url = "https://fbref.com/en/comps/9/premier-league-stats"

counter = 1

for year in years:
    data = requests.get(standings_url)

    if data.status_code != 200:
        print(f"Error: Received status code {data.status_code}")
        exit()

    soup = BeautifulSoup(data.text, features="html.parser")
    standings_table = soup.select('table.stats_table')[0]

    links = standings_table.find_all('a')
    links = [l.get("href") for l in links]
    links = [l for l in links if '/squad' in l]
    team_urls = [f"https://fbref.com{l}" for l in links]

    # need to get the url of the previous season
    previous_season = soup.select("a.prev")[0].get("href")
    standings_url = f"https://fbref.com{previous_season}"

    # scraping match logs for each team
    for i, team_url in enumerate(team_urls):
        team_name = team_url.split("/")[-1].replace("-Stats", "").replace("-", " ")

        data = requests.get(team_url)

        print(f"Counter: {counter}, Status code: {data.status_code}")


        if data.status_code != 200:
            print(f"Error: Received status code {data.status_code}")
            exit()

        matches = pd.read_html(data.text, match="Scores & Fixtures")[0]

        soup = BeautifulSoup(data.text, features="html.parser")
        links = soup.find_all('a')
        links = [l.get("href") for l in links]
        links = [l for l in links if l and 'all_comps/shooting/' in l]
        # data = requests.get(f"https://fbref.com{links[0]}")

        shooting_url = f"https://fbref.com{links[0]}"
        data = requests.get(shooting_url)

        if data.status_code != 200:
            print(f"Error: Received status code {data.status_code}")
            exit()

        try:
            shooting = pd.read_html(data.text, match="Shooting")[0]
            shooting.columns = shooting.columns.droplevel()
        except ValueError:
            print(f"No 'Shooting' table found on {shooting_url}")
            continue

        # sometimes shooting stats are unavailable, so skip teams where shooting stats are unavailable
        try:
            team_data = matches.merge(shooting[["Date", "Sh", "SoT", "Dist", "FK", "PK", "PKatt"]], on="Date")
        except ValueError:
            continue

        # filter out other comps (UCL, UEL, etc.), and add a season and team element
        team_data = team_data[team_data["Comp"] == "Premier League"]
        team_data["Season"] = year
        team_data["Team"] = team_name
        all_matches.append(team_data)
        counter += 1
        time.sleep(random.randint(10,15))

        if (i + 1) % 5 == 0:
            print("5 minute pause to avoid request overload")
            time.sleep(300)
    

# combine all individual dataframes into 1 dataframe
match_df = pd.concat(all_matches)

# set column names to lowercase
match_df.columns = [c.lower() for c in match_df.columns]

# write to csv
match_df.to_csv("matches.csv")
print("Complete!")
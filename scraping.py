import requests

standings_url = "https://fbref.com/en/comps/9/premier-league-stats"

# download the page, will make req to server and download html of the page
data = requests.get(standings_url)

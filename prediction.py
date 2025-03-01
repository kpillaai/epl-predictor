import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.metrics import precision_score

# read csv into matches dataframe
matches = pd.read_csv("matches.csv", index_col=0)

# replace data types of date column with datetime data type
matches["date"] = pd.to_datetime(matches["date"])

# convert home/away column into numeric column, will convert to categorical datatype in pandas. String to categories, categories to numbers
matches["venue_code"] = matches["venue"].astype("category").cat.codes

# convert opponents into numeric values. Each team will have a unique number
matches["opp_code"] = matches["opponent"].astype("category").cat.codes

# replace colon in time column with nothing, then convert hour to integer
matches["hour"] = matches["time"].str.replace(":.+", "", regex=True).astype("int")

# get numbers for the day of the week
matches["day_code"] = matches["date"].dt.dayofweek

# boolean for wins or not wins (losses and draws are 0, wins are 1. option to do 0 for loss, 1 for win, 2 for draw in future)
matches["target"] = (matches["result"] == "W").astype("int")

# Random Forest Classifier: Type of ML model that can pick up non linearities in data. Opp code doesn't have linear relationship with difficulty, opp code is just values for different opponents. 

# n_estimators = no. of decision trees we want to train. Bigger this number, longer algo will take but potentially more accurate
# min_samples_split = no of samples we want to have in a leaf of a decision tree before we split the node. Higher this is, less likely to overfit but lower the accuracy on the training data
# random_state = if we set a random_state and run the random forest multiple times, we'll get the same results 
rf = RandomForestClassifier(n_estimators=50, min_samples_split=10, random_state=1)

# training data is matches before 2025
train = matches[matches["date"] < '2025-01-01']

# testing on matches in 2025
test = matches[matches["date"] > '2025-01-01']

# predictors that we created
predictors = ["venue_code", "opp_code", "hour", "day_code"]

# fit random forest model using predictors to predict target
rf.fit(train[predictors], train["target"])

# generate predictions passing in test data
preds = rf.predict(test[predictors])

# can check accuracy of predictions, with first run through accuracy is 0.5853658536585366, or 58.5%
acc = accuracy_score(test["target"], preds)

# trying to look for situations for where accuracy was high vs low
# dataframe of actual values combined with predicted values
combined = pd.DataFrame(dict(actual=test["target"], prediction=preds))

# two way table that will show when we predicted 0 or 1, what actually happened
# Currently when predicting a loss/draw, we were correct 76 times and wrong 47 times. When predicting a win we were wrong 21 times and right 20 times
pd.crosstab(index=combined["actual"], columns=combined["prediction"])
# print(pd.crosstab(index=combined["actual"], columns=combined["prediction"]))

# will tell us when we predicted a win, what percentage of the time did the team actually win. Currently at 0.4878048780487805, or 48.8%
precision_score(test["target"], preds)
# print(precision_score(test["target"], preds))

# More predictors to improve accuracy
# create a dataframe per team
grouped_matches = matches.groupby("team")

group = grouped_matches.get_group("Manchester City")
# print(group)

"""
    This function will be used to improve predictions based on a teams form over their past few games
    group: Team
    cols: Set of columns that we want to compute rolling averages for
    new_cols: Set of new columns that we want to assign the rolling averages to
"""
def rolling_averages(group, cols, new_cols):
    # sort grouup by date to be able to look at last 3 matches a team played
    group = group.sort_values("date")

    # compute rolling averages of the columns passed in. Closed=left is important because without it, it will update past data. Eg, weeks 1-3 data, week 3 would be updated without it
    rolling_stats = group[cols].rolling(3, closed='left').mean()

    # assign rolling stats back to original dataframe
    group[new_cols] = rolling_stats

    # drop missing values (trying to compuute week 2, but only 1 previouus week to work with)
    group = group.dropna(subset=new_cols)

    return group

# defining columns we want rolling averages for
cols = ["gf", "ga", "sh", "sot", "dist", "fk", "pk", "pkatt"]

# creating new columns list, adding rolling onto the end of the column names
new_cols = [f"{c}_rolling" for c in cols]

# print(rolling_averages(group, cols, new_cols))

# apply to all of the matches
matches_rolling = matches.groupby("team").apply(lambda x: rolling_averages(x, cols, new_cols))

# drop extra team index level
matches_rolling = matches_rolling.droplevel('team')

#want unique values for index, will assign values from 0 - matches_rolling
matches_rolling.index = range(matches_rolling.shape[0])

# print(matches_rolling)

"""
    This function will be used to iterate on the algorithm to train the model
    data:
    predictors:
"""
def make_predictions(data, predictors):
    train = data[data["date"] < '2025-01-01']
    test = data[data["date"] > '2025-01-01']
    rf.fit(train[predictors], train["target"])
    preds = rf.predict(test[predictors])
    combined = pd.DataFrame(dict(actual=test["target"], predicted=preds), index=test.index)
    precision = precision_score(test["target"], preds)
    return combined, precision

# with rolling averages, the new precision is at 0.5862068965517241, or 58.6%, compared to the previous 48.8%
# currently combined will not show us what team played in which match, despite it showing the results of correct or incorrect predictions
combined, precision = make_predictions(matches_rolling, predictors + new_cols)
# print(f"Precision: {precision}")
# print(combined)

# adding team information to combined. It will look at the combined dataframe, take the index and look at the corresponding index in matches rolling, and merge the row based on that
combined = combined.merge(matches_rolling[["date", "team", "opponent", "result"]], left_index=True, right_index=True)
# print(combined)

# combining home and away predictions
# some names are different when comparing the team name to the opponent (Wolverhampton Wanderers and Wolves)

# create a dictionary and use the pandas map function with that dict. Inherits from dict class. By default pandas map method will not handle missing keys
class MissingDict(dict):
    __missing__ = lambda self, key: key

map_values = {
    "Brighton and Hove Albion": "Brighton",
    "Manchester United": "Manchester Utd",
    "Newcastle United": "Newcastle Utd",
    "Tottenham Hotspur": "Tottenham",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves"
}
mapping = MissingDict(**map_values)

# if we had used a regular dictionary and passed map_values instead of mapping, it would have returned missing values for Arsenal etc because they do not exist in the dictionary
combined["new_team"] = combined["team"].map(mapping)

# merge dataframe with itself using the new column of standardized team names
# This is checking that the predictions match on both sides. Eg, Arsenal vs Burnley and Burnley vs Arsenal should have the same prediction (not talking about Home and Away games here, this is for the same game)
merged = combined.merge(combined, left_on=["date", "new_team"], right_on=["date", "opponent"])

# can look at just the rows and see where one team was predicted to win and the other was predicted to lose. This indicates where the algorithm has confidence
#merged[(merged["predicted_x"] == 1) & (merged["predicted_y"] == 0)]["actual_x"].value_counts()
print(merged[(merged["predicted_x"] == 1) & (merged["predicted_y"] == 0)]["actual_x"].value_counts())

# 1/3/25 - 17/27 correct predictions, approx 63% success

# OPTIONS TO IMPROVE ACCURACY
# Use more data, scrape more years
# Use more columns

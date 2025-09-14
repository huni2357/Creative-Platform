from feature_validation import quick_validate
import pandas as pd

df = pd.read_csv(r"C:\Users\leehu\OneDrive\Desktop\창플\code\Demo_1.csv", encoding="utf-8")
quick_validate(df)

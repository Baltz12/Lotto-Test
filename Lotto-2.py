import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
import random
from datetime import datetime

# -----------------------------------
# Scraper from manalotto.com history
# -----------------------------------
def fetch_manalotto_history():
    url = "https://manalotto.com/6-58-lotto-result/history"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the history table
        table = soup.find("table")
        rows = table.find_all("tr")[1:]  # skip header row

        results = []
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            # Expect format: Draw Date | Winning Combination | Winners | Jackpot Prize
            if len(cols) >= 2:
                date_str = cols[0]
                nums_str = cols[1]
                # Parse date: e.g., "Sep 2, 2025"
                draw_date = datetime.strptime(date_str, "%b %d, %Y")
                numbers = [int(n) for n in nums_str.split("-") if n.isdigit()]
                results.append({"date": draw_date, "numbers": numbers})
        return results

    except Exception as e:
        st.error(f"Failed to fetch data from manalotto.com: {e}")
        return []

# -----------------------------
# Analysis functions
# -----------------------------
def number_frequencies(results):
    cnt = Counter()
    for entry in results:
        cnt.update(entry["numbers"])
    return cnt

def co_occurrence(results):
    co = defaultdict(Counter)
    for entry in results:
        nums = entry["numbers"]
        for a in nums:
            for b in nums:
                if a != b:
                    co[a][b] += 1
    return co

def predict_next_numbers(results, top_n=6, n_predictions=3):
    freq = number_frequencies(results)
    co = co_occurrence(results)
    top_nums = [n for n, _ in freq.most_common(20)]  # top 20 frequent numbers

    predictions = []
    for _ in range(n_predictions):
        prediction = set()

        # Step 1: choose 1–2 seeds from top frequent numbers
        seeds = random.sample(top_nums, k=min(2, len(top_nums)))
        prediction.update(seeds)

        # Step 2: add their top co-occurring partners
        for seed in seeds:
            if seed in co:
                sorted_partners = sorted(co[seed].items(), key=lambda x: x[1], reverse=True)
                for partner, _ in sorted_partners[:2]:  # take up to 2 partners per seed
                    if len(prediction) < top_n:
                        prediction.add(partner)

        # Step 3: fill the rest with frequent numbers
        while len(prediction) < top_n:
            prediction.add(random.choice(top_nums))

        predictions.append(sorted(prediction))

    return predictions

# -----------------------------
# Streamlit Application
# -----------------------------
st.set_page_config(page_title="Ultra Lotto 6/58 Explorer", layout="wide")

st.title("Ultra Lotto 6/58 — History & Predictor")

# Fetch data
with st.spinner("Fetching draw history from manalotto.com..."):
    data = fetch_manalotto_history()
    df = pd.DataFrame(data)

if df.empty:
    st.error("No draw history available.")
    st.stop()

# Ensure df["date"] is Timestamp
df["date"] = pd.to_datetime(df["date"])

# Date range filter
default_start = df["date"].min().date()
default_end = df["date"].max().date()
start_date, end_date = st.date_input("Select date range", [default_start, default_end])

# Convert both to Timestamp
start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

# Apply filter
df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

st.subheader("Draw History")
df_display = df.copy()
df_display["numbers_str"] = df_display["numbers"].apply(lambda nums: " - ".join(f"{n:02d}" for n in nums))
st.dataframe(df_display[["date", "numbers_str"]].sort_values("date", ascending=False))

# Frequency chart
st.subheader("Number Frequencies")
freq = number_frequencies(df.to_dict("records"))
freq_df = pd.DataFrame(sorted(freq.items()), columns=["Number", "Frequency"]).set_index("Number")
st.bar_chart(freq_df)

# Co-occurrence analysis
st.subheader("Numbers that co-occur with each other")
co = co_occurrence(df.to_dict("records"))
selected = st.number_input("Select a number (1–58)", min_value=1, max_value=58, value=43)
if selected in co:
    co_df = pd.DataFrame(co[selected].items(), columns=["Partner", "Times"]).sort_values("Times", ascending=False)
    st.table(co_df)
else:
    st.write("No data for that number in selected range.")

# Prediction
st.subheader("Next Draw (Heuristic Predictions)")

predictions = predict_next_numbers(df.to_dict("records"), top_n=6, n_predictions=3)
for i, p in enumerate(predictions, 1):
    st.success(f"Prediction {i}: {p}")

# Export CSV
st.subheader("Export Data")
csv_data = df_display[["date", "numbers_str"]].to_csv(index=False)
st.download_button("Download CSV", data=csv_data, file_name="ultra6_58_draw_history.csv", mime="text/csv")

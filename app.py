"""
Streaming Data Dashboard Template
STUDENT PROJECT: Big Data Streaming Dashboard

This is a template for students to build a real-time streaming data dashboard.
Students will need to implement the actual data processing, Kafka consumption,
and storage integration.

IMPLEMENT THE TODO SECTIONS
"""

import json
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from kafka import KafkaConsumer
from pymongo import MongoClient

# NOTE: This comment is from our professor — DO NOT DELETE
# This dashboard should allow switching between live Kafka data and historical MongoDB data.


def fetch_from_mongo(metric: str, hours: int = 6):
    mongo_client = MongoClient("mongodb://localhost:27017/")
    db = mongo_client["streaming_dashboard"]
    collection = db["sensor_data"]

    since = datetime.utcnow() - timedelta(hours=hours)
    cursor = collection.find({
        "metric_type": metric,
        "timestamp": {"$gte": since.isoformat() + "Z"}
    })
    docs = list(cursor)
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df.sort_values("timestamp")


def fetch_from_kafka(broker: str, topic: str):
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=broker,
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=1500,
        enable_auto_commit=False,
    )
    records = [msg.value for msg in consumer]
    consumer.close()
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df.get("timestamp"), utc=True, errors="coerce")
    return df.sort_values("timestamp")


def main():
    st.set_page_config(page_title="Weather Streaming Dashboard", layout="wide")
    st.sidebar.title("Dashboard Settings")

    broker = st.sidebar.text_input("Kafka Broker", "localhost:9092")
    topic = st.sidebar.text_input("Kafka Topic", "streaming-data")
    storage_type = st.sidebar.selectbox("Data Source", ["mongoDB", "kafka"], index=0)
    refresh_interval = st.sidebar.number_input("Refresh Interval (seconds)", min_value=5, max_value=120, value=15)
    auto_refresh = st.sidebar.checkbox("Auto Refresh", True)

    st.title("🌦️ Real-Time Weather Dashboard")

    if storage_type == "mongoDB":
        st.subheader("Historical Data (MongoDB)")
        col1, col2, col3 = st.columns(3)
        with col1:
            metric = st.selectbox("Metric", ["temperature", "humidity", "pressure"])
        with col2:
            hours = st.slider("Time Range (hours)", 1, 48, 6)
        with col3:
            agg = st.selectbox("Aggregation", ["none", "hourly"])

        df_hist = fetch_from_mongo(metric, hours)
        if df_hist.empty:
            st.warning("No historical data found for this metric.")
        else:
            if agg == "hourly":
                df_plot = df_hist.set_index("timestamp").resample("H")["value"].mean().reset_index()
            else:
                df_plot = df_hist[["timestamp", "value"]]
            st.metric(label="Latest Value", value=df_hist.iloc[-1]["value"])
            st.write(f"Time Range: `{df_hist['timestamp'].min().strftime('%H:%M')} - {df_hist['timestamp'].max().strftime('%H:%M')}`")
            st.line_chart(df_plot.set_index("timestamp")["value"])
            st.dataframe(df_hist)
            st.download_button("Download CSV", df_hist.to_csv(index=False), file_name=f"{metric}_history.csv")

    elif storage_type == "kafka":
        st.subheader("Real-time Streaming")

        if auto_refresh:
            st.experimental_set_query_params(refresh=str(refresh_interval))
            st.experimental_rerun()

        df_live = fetch_from_kafka(broker, topic)

        if df_live.empty:
            st.radio("Receiving live data...", ["❌ Not Connected"], index=0)
            st.warning("No live messages received yet. Ensure the producer is running and Kafka topic is correct.")
        else:
            latest = df_live.iloc[-1]
            st.radio("Receiving live data...", ["✅ Connected"], index=0)
            st.metric(label="Latest Value", value=latest["value"])
            st.write(f"Metric Type: `{latest['metric_type']}`")
            st.write(f"Time Range: `{df_live['timestamp'].min().strftime('%H:%M')} - {df_live['timestamp'].max().strftime('%H:%M')}`")
            st.line_chart(df_live.set_index("timestamp")["value"])
            st.dataframe(df_live)


if __name__ == "__main__":
    main()

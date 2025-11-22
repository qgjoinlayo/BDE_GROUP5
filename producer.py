"""
Kafka Producer Template for Streaming Data Dashboard
STUDENT PROJECT: Big Data Streaming Data Producer

This is a template for students to build a Kafka producer that generates and sends
streaming data to Kafka for consumption by the dashboard.

DO NOT MODIFY THE TEMPLATE STRUCTURE - IMPLEMENT THE TODO SECTIONS
"""

import requests
import json
import time
from datetime import datetime
from kafka import KafkaProducer
from pymongo import MongoClient
import argparse


def fetch_weather_data(api_key, location):
    url = f"https://api.weatherapi.com/v1/current.json?key={api_key}&q={location}&aqi=no"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        timestamp = datetime.utcnow().isoformat() + "Z"

        records = []

        if "temp_c" in current:
            records.append({
                "timestamp": timestamp,
                "value": float(current["temp_c"]),
                "metric_type": "temperature",
                "sensor_id": "weatherapi_temp_qc",
                "location": location,
                "unit": "celsius"
            })

        if "humidity" in current:
            records.append({
                "timestamp": timestamp,
                "value": float(current["humidity"]),
                "metric_type": "humidity",
                "sensor_id": "weatherapi_humidity_qc",
                "location": location,
                "unit": "percent"
            })

        if "pressure_mb" in current:
            records.append({
                "timestamp": timestamp,
                "value": float(current["pressure_mb"]),
                "metric_type": "pressure",
                "sensor_id": "weatherapi_pressure_qc",
                "location": location,
                "unit": "mb"
            })

        return records

    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", type=str, default="localhost:9092")
    parser.add_argument("--topic", type=str, default="streaming-data")
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--duration", type=int, default=None)
    args = parser.parse_args()

    # Kafka setup
    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )

    # MongoDB setup
    mongo_client = MongoClient("mongodb://localhost:27017/")
    db = mongo_client["streaming_dashboard"]
    collection = db["sensor_data"]

    # WeatherAPI config
    api_key = "3708e5cce5614fb09bf193731252211"
    location = "Quezon City"

    print("Starting producer...")
    start_time = time.time()
    sent = 0

    try:
        while True:
            if args.duration and (time.time() - start_time) >= args.duration:
                print("Duration reached. Stopping producer.")
                break

            records = fetch_weather_data(api_key, location)

            for record in records:
                try:
                    producer.send(args.topic, value=record)
                    print(f"Sent to Kafka: {record}")
                    collection.insert_one(record)
                    print("Inserted into MongoDB.")
                    sent += 1
                except Exception as e:
                    print(f"Error sending/inserting record: {e}")

            time.sleep(1.0 / max(args.rate, 0.1))

    except KeyboardInterrupt:
        print("Producer interrupted by user.")

    finally:
        producer.close()
        print(f"Producer stopped. Total messages sent: {sent}")


if __name__ == "__main__":
    main()

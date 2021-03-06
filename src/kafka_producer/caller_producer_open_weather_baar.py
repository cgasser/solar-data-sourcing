#!/usr/bin/env python3
#
# Open weather api caller and Kafka message producer
#
# Run the file directly on SourceHost01 with python3
# To see if data correctly can be consumed use following confluent cli:
# $ kafka_producer-console-consumer --bootstrap-server localhost:9092 --topic open_weather --from-beginning
#
# Thanks goes to the example from https://docs.confluent.io/4.0.0/clients/producer.html


import http.client
import json
import csv
import time
import requests
import logging
from confluent_kafka import Producer
import socket
from hdfs import InsecureClient
import collections
import pandas as pd


def open_weather_call(app_id, zip_id):
    conn = http.client.HTTPConnection("")
    r = requests.get("http://api.openweathermap.org/data/2.5/weather?zip=" + str(zip_id) + ",ch" + "&appid=" + app_id + "&units=metric")
    logging.info("Response: " + str(r.status_code) + " " + r.reason)

    data = r.json()  # This will return entire content.
    # Remove key's in order to clean data from complex JSON structure and wrong syntax
    sorted_data = collections.OrderedDict(sorted(data.items()))
    # sorted_data = pd.io.json.json_normalize(sorted_data)
    logging.debug(sorted_data)
    conn.close()
    return sorted_data


def kafka_produce(data):
    topic = 'open_weather'
    conf = {'bootstrap.servers': "localhost",
            'client.id': socket.gethostname(),
            'default.topic.config': {'acks': '1'}}

    logging.info("Confluent Message config client.id: " + socket.gethostname())
    producer = Producer(conf)

    logging.info("Send message to topic : " + str(topic))
    logging.debug("Write message json" + str(data))
    producer.produce(topic, str(data), callback=acked)

    # Wait up to 1 second for events. Callbacks will be invoked during
    # this method call if the message is acknowledged.
    producer.poll(1)


def acked(err, msg):
    if err is not None:
        print("Failed to deliver message: %s: %s" % (str(msg), str(err)))
    else:
        print("Message produced: %s" % (str(msg)))


if __name__ == "__main__":
    logging.basicConfig(filename='/var/log/open_weather.log',
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)
    epoch_time_now = str(round(time.time()))
    logging.info("Start API call Open Weather Map at Time: " + epoch_time_now)

    # Call open Weather api to get Data
    apiKey = "01638bd216e99ac31b6b81973d2adc08"
    zip = 6340
    weather_data = open_weather_call(apiKey, zip)

    # Write to local store
    path = '/home/bda/data'
    logging.info("Write json and csv to : " + path)

    with open(path + '/open_weather_'+ str(zip) +'_' + epoch_time_now + '.json', 'w', encoding='utf-8') as outfile:
        json.dump(weather_data, outfile, indent=4, ensure_ascii=False)

    #write the same data as .csv since it is more easy to handel with hdfs..
    with open(path + '/open_weather_'+ str(zip) +'_' + epoch_time_now + '.csv', 'w') as f:
        w = csv.DictWriter(f, weather_data.keys(), dialect=csv.excel_tab)
        w.writeheader()
        w.writerow(weather_data)

    # write data to hdfs
    logging.info("Write csv to hdfs : /data/open_weather/")
    client = InsecureClient('http://nh-01.ip-plus.net:50070', user='hdfs')
    with client.write('/data/open_weather/open_weather_'+ str(zip) +'_' + epoch_time_now + '.csv', encoding='utf-8') as writer:
        w = csv.DictWriter(writer, weather_data.keys(), dialect=csv.excel_tab)
        w.writeheader()
        w.writerow(weather_data)

    # Write to KAFKA
    kafka_produce(weather_data)

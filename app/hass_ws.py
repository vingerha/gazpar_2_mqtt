import json
import logging
import ssl
from datetime import datetime, timedelta

import websocket

class HomeAssistantWs:
    def __init__(self, action, pce, url, ssl, ssl_data, token, sensor, data):
        self.ws = None
        self.pce = pce
        self.url = url
        self.ssl = ssl    
        self.ssl_data = ssl_data
        self.token = token
        self.sensor_name = sensor
        self.data = data
        self.action = action
        self.id = 1
        self.current_stats = []
        if self.load_config():
            if self.connect() and self.action == "import":
                                  
                                   
                self.import_data()
            elif self.connect() and self.action == "delete":
                self.list_data()
                logging.debug("Deleting current statistics: %s", self.current_stats)
                self.clear_data()
            else:
                logging.critical("The configuration of the Websocket Home Assistant WebSocket is erroneous")
        else:
            logging.critical("The configuration of the Websocket Home Assistant WebSocket is erroneous")
        if self.ws.connected:
            self.ws.close()

    def load_config(self):
        if self.ssl:
            url_prefix = "wss"
        else:
            url_prefix = "ws"
        self.url = f"{url_prefix}://{self.url}/api/websocket"
        return True

    def connect(self):
        try:
            check_ssl = self.ssl_data
            sslopt = None
            if self.ssl and "gateway" in check_ssl:
                sslopt = {"cert_reqs": ssl.CERT_NONE}
            self.ws = websocket.WebSocket(sslopt=sslopt)
            logging.info(f"Connection to WebSocket Home Assistant {self.url}")
            self.ws.connect(
                self.url,
                timeout=5,
            )
            output = json.loads(self.ws.recv())
            if "type" in output and output["type"] == "auth_required":
                logging.info("Authentication needed")
                return self.authentificate()
            return True
        except Exception as e:
            self.ws.close()
            logging.error(e)
            logging.critical("Connection to Websocket Home Assistant failed")
            logging.warning(
                f" => WARNING, the WebSocket will be banned after multiple unsuccesful login attempts."
            )
            logging.warning(f" => ex: 403: Forbidden")

    def authentificate(self):
        data = {"type": "auth", "access_token": self.token}
        auth_output = self.send(data)
        if auth_output["type"] == "auth_ok":
            logging.info(" => OK")
            return True
        else:
            logging.error(" => Authentication impossible, please verify url & token.")
            return False

    def send(self, data):
        self.ws.send(json.dumps(data))
        self.id = self.id + 1
        output = json.loads(self.ws.recv())
        if "type" in output and output["type"] == "result":
            if not output["success"]:
                logging.error(f"Error when sending : {data}")
                logging.error(output)
        return output

    def list_data(self):
        logging.info("Collecting LTS data already in Home Assistant.")
        import_statistics = {
            "id": self.id,
            "type": "recorder/list_statistic_ids",
            "statistic_type": "sum",
        }
        current_lts = self.send(import_statistics)
        for stats in current_lts["result"]:
            if stats["statistic_id"] == self.sensor_name:
                self.current_stats.append(stats["statistic_id"])
        return self.current_stats

    def clear_data(self):
        logging.info("Deleting Long Terms Statistics for gazpar.")
        clear_statistics = {
            "id": self.id,
            "type": "recorder/clear_statistics",
            "statistic_ids": self.current_stats,
        }
        logging.info("Cleaning :")
        for data in self.current_stats:
            logging.info(f" - {data}")
        clear_stat = self.send(clear_statistics)
        return clear_stat

    def get_data(self, statistic_ids, begin, end):
        statistics_during_period = {
            "id": self.id,
            "type": "recorder/statistics_during_period",
            "start_time": begin.isoformat(),
            "end_time": end.isoformat(),
            "statistic_ids": [statistic_ids],
            "period": "hour",
        }
        stat_period = self.send(statistics_during_period)
        return stat_period

    def import_data(self):
        logging.info(f"Exporting to HA Long Term Statistics : {self.pce}")
        metadata = {
            "has_mean": False,
            "has_sum": True,
            "name": "gazpar m3",
            "statistic_id": (
                self.sensor_name
                    ),
            "unit_of_measurement": "m³",
            "source": "recorder",
            
            }
        statistics = {
                "id": self.id,
                "type": "recorder/import_statistics",
                "metadata": metadata,
                "stats": self.data,
            } 

        self.send(statistics)
            

import requests
import json
from websocket import create_connection
import uuid
from bs4 import BeautifulSoup
from typing import List, Optional

GBPUSD = 3440
EURUSD = 3438
USDJPY = 3427
EURGBP = 3419
USDCAD = 3433
USDCHF = 3390
AUDUSD = 3411
NZDUSD = 3398
EURJPY = 3392
AUDCHF = 3395
XAUUSD = 3406
US30 = 3351
ETHUSD = 3443
BTCUSD = 3425
csrf = ""
BUY = 0
SELL = 1
MARKET = 0

class Identity:
    def __init__(self, username, password, server):
        self.csrf = None
        self.account_id = None
        self.username = username
        self.password = password
        self.server = server
        self.cookies = {}
        self.s = requests.Session()

    def login(self):
        url = "https://dxtrade.ftmo.com/api/auth/login"
        payload = json.dumps({
            "username": "1210003069",
            "password": "2K2=WJ3^6rj5",
            "vendor": "ftmo"
        })
        headers = {
            'content-type': 'application/json',
        }
        response = self.s.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            for cookie in response.cookies:
                self.cookies[cookie.name] = cookie.value
            self.fetch_csrf()
            self.get_positions()
        else:
            print("Login failed with status code:", response.status_code)

    def get_positions(self):
        try:
            json_str = self.establish_handshake("POSITIONS")
            json_str = json_str.split("|")[1]
            data = json.loads(json_str)
            account_id = data["accountId"]
            positions = data["body"]
            print(f"Account ID: {account_id}")
            self.account_id = account_id
            return positions
        except json.JSONDecodeError as e:  # if json doesnt work for some reason
            print("Error decoding JSON:", str(e))
            return None

    def establish_handshake(self, kill_msg=None):
        cookie_string = "; ".join([f"{name}={value}" for name, value in self.cookies.items()])
        headers = {
            "Cookie": cookie_string
        }
        # DXTFID="4a5c1792438ca392"; JSESSIONID=D158AB6886F36A59CEFB4FE770D215EF.jvmroute
        # DXTFID="82eb6bec36023478"; JSESSIONID=E2A9049F02A933B4E505BBA07F9D06CF.jvmroute
        ws_url = "wss://dxtrade." + self.server + ".com/client/connector?X-Atmosphere-tracking-id=0&X-Atmosphere-Framework=2.3.2-javascript&X-Atmosphere-Transport=websocket&X-Atmosphere-TrackMessageSize=true&Content-Type=text/x-gwt-rpc;%20charset=UTF-8&X-atmo-protocol=true&sessionState=dx-new&guest-mode=false"
        ws = create_connection(ws_url, header=headers)
        try:
            ws.connect(ws_url, header=headers)
            while True:
                message = ws.recv()
                print(message)
                if kill_msg and kill_msg in message:
                    return message
        except Exception as e:
            print("WebSocket Error:", str(e))
        finally:
            ws.close()

    def fetch_csrf(self):
        try:
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'cookie': '; '.join([f"{key}={value}" for key, value in self.cookies.items()]),
            }
            # only use JSessionid in request
            cookies_in_req = {key: value for key, value in self.cookies.items() if "JSESSIONID" in key}
            response = self.s.get("https://dxtrade.ftmo.com/", headers=headers, cookies=cookies_in_req)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_meta_tag = soup.find('meta', attrs={'name': 'csrf'})
            if csrf_meta_tag and 'content' in csrf_meta_tag.attrs:
                self.csrf = csrf_meta_tag['content']
                return csrf_meta_tag['content']
            else:
                print("CSRF token not found.")
                return None

        except requests.RequestException as e:
            print(f"{e}")
            return None

    def open_trade(self, order_side, quantity, tp, sl, limit_price, symbol, instrument_id):
        url = "https://dxtrade.ftmo.com/api/orders/single"
        headers = {
            'content-type': 'application/json; charset=UTF-8',
            'cookie': '; '.join([f"{key}={value}" for key, value in self.cookies.items()]),
            'x-csrf-token': self.csrf,
            'x-requested-with': 'XMLHttpRequest'
        }
        payload = {
            "directExchange": False,
            "legs": [{
                "instrumentId": instrument_id,
                "positionEffect": "OPENING",
                "ratioQuantity": 1,
                "symbol": symbol
            }],
            "limitPrice": limit_price,
            "orderSide": "BUY" if order_side == BUY else "SELL",
            "orderType": "MARKET" if limit_price == 0 else "LIMIT",
            "quantity": quantity,
            "requestId": "gwt-uid-931-" + str(uuid.uuid4()),
            "timeInForce": "GTC"  # Good till cancelled or do EOD for end of day
        }
        if sl != 0:
            payload["stopLoss"] = {
                "fixedOffset": 5,
                "fixedPrice": sl,
                "orderType": "STOP",
                "priceFixed": True,
                "quantityForProtection": quantity,
                "removed": False
            }
        if tp != 0:
            payload["takeProfit"] = {
                "fixedOffset": 5,
                "fixedPrice": tp,
                "orderType": "LIMIT",
                "priceFixed": True,
                "quantityForProtection": quantity,
                "removed": False
            }
        print("PAYLOAD", payload)
        response = self.s.post(url, headers=headers, data=json.dumps(payload).replace(" ", ""))
        if response.status_code != 200:
            print("market order", response.status_code, csrf)
        else:
            print("Order executed successfully!")

    def buy(self, quantity, tp, sl, price, symbol, instrument_id):
        self.open_trade(BUY, quantity, tp,sl, price, symbol, instrument_id)

    def sell(self, quantity, tp,sl,price, symbol, instrument_id):
        self.open_trade(SELL, -quantity, tp,sl, price, symbol, instrument_id)

    def close_trade(self, position_id, quantity, price, symbol, instrument_id):
        url = "https://dxtrade.ftmo.com/api/positions/close"
        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'Cookie': '; '.join([f"{key}={value}" for key, value in self.cookies.items()]),
            'X-CSRF-Token': self.csrf,
            'X-Requested-With': 'XMLHttpRequest',
        }

        # Constructing the payload based on the provided Go code structure
        payload = {
            "legs": [{
                "instrumentId": instrument_id,
                "positionCode": position_id,
                "positionEffect": "CLOSING",
                "ratioQuantity": 1,
                "symbol": symbol
            }],
            "limitPrice": price,
            "orderType": "MARKET" if price == 0 else "LIMIT",
            "quantity": -quantity,
            "timeInForce": "GTC"
        }
        response = self.s.post(url, headers=headers, data=json.dumps(payload))

    def close_all(self):
        for position in self.get_positions():
            identity.close_trade(position["positionKey"]["positionCode"], position["quantity"], 0,
                                    position["positionKey"]["positionCode"], position["positionKey"]["instrumentId"])
if __name__ == "__main__":
    identity = Identity("1210003069", "2K2=WJ3^6rj5", "ftmo")
    identity.login()
    identity.buy(0.50, 0, 0, MARKET, "BTCUSD", BTCUSD)

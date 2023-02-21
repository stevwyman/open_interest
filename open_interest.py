import urllib3
import pymongo
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from datetime import datetime, timedelta
import time

DATE_FORMAT = "%Y%m%d"


class OnlineReader:
    def __init__(self):
        # open a connection to a URL using urllib3
        self._http = urllib3.PoolManager()

    def request_data(self, parameters: dict) -> dict:
        # url = generate_url_(product, type, expiry_date, bus_date)
        url = generate_url(**parameters)

        response = self._http.request("GET", url)
        # print(response.geturl())

        eurex_data = response.data.decode("utf-8")
        parsed_html = BeautifulSoup(eurex_data, features="lxml")
        data_table = parsed_html.body.find("table", attrs={"class": "dataTable"})

        table = etree.HTML(str(data_table))

        # headers
        headers = [th.text.strip() for th in table.findall(".//th")]
        columns = len(headers)

        data = list()

        for tr in table.findall(".//tbody/tr"):
            row = []

            for entry in range(columns):
                row.append(tr[entry].text)

            data.append(row)

        # print(tabulate(data,headers = headers,tablefmt='fancy_grid'))

        data_dict = {}
        for row in data:
            try:
                strike = str(row[headers.index("Strike price")]).replace(",", "")
                strike_int = int(
                    str(row[headers.index("Strike price")]).replace(",", "")
                )
                open_interest = int(
                    str(row[headers.index("Open interest")]).replace(",", "")
                )
                open_interest_adj = int(
                    str(row[headers.index("Open interest (adj.)")]).replace(",", "")
                )
                data_dict[strike] = (strike_int, open_interest, open_interest_adj)
            except ValueError:
                pass

        return {"parameter": parameters, "data": data_dict}


class LocaleDAO:
    def __init__(self):
        self._myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        self._db = self._myclient.python_test
        self._collection = self._db.open_interest

    def write(self, open_interest_data: dict) -> None:
        
        try:
            if (
                len(
                    list(
                        self._collection.find(
                            generate_unique_filter(open_interest_data["parameter"])
                        )
                    )
                )
                > 0
            ):
                print(f"Entry exists already.")
            else:
                print(f"Adding new entry: {open_interest_data['parameter']['type']['bus_date']}")
                self._collection.insert_one(open_interest_data)
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not write data to locale storrage: ", e)

    def read_all_byexpiry_date(self, parameter: dict) -> list[dict]:
        # print(f"Using Parameter: {parameter}")
        try:
            return self._collection.find(generate_filter_expiry_date(parameter))
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not read data from locale storrage: ", e)
            return None
    
    def read_entry(self, parameter:dict) -> dict:
        # print(f"Using Parameter: {parameter}")
        try:
            return self._collection.find_one(generate_unique_filter(parameter))
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not read data from locale storrage: ", e)
            return None

    def close(self):
        self._myclient.close


def update_data(parameter: dict) -> None:
    online_reader = OnlineReader()
    locale_dao = LocaleDAO()

    expiry_date = datetime.strptime(parameter["expiry_date"]["date"], DATE_FORMAT)
    today = datetime.now()

    for n in range(60):
        days_ago = timedelta(days = n)
        a = expiry_date - days_ago
        if a >= today:
            continue

        bus_date = a.strftime(DATE_FORMAT)
        parameter["bus_date"] = bus_date

        parameter["type"] = "Call"
        result = locale_dao.read_entry(parameter)
        # if data not in local storage, request online 
        if result is None:
            online_data: dict = online_reader.request_data(parameter)
            if not online_data["data"]:
                continue
            locale_dao.write(online_data)
            time.sleep(5)
        else:
            print(f"Entry already in local storage: {parameter['type']}, {parameter['bus_date']}")

        parameter["type"] = "Put"
        result = locale_dao.read_entry(parameter)
        # if data not in local storage, request online 
        if result is None:
            online_data: dict = online_reader.request_data(parameter)
            if not online_data["data"]:
                continue
            locale_dao.write(online_data)
            time.sleep(5)
        else:
            print(f"Entry already in local storage: {parameter['type']}, {parameter['bus_date']}")
    
    locale_dao.close


def generate_max_pain_chart(parameter: dict) -> None:
    
    max_pain_over_time = list()

    locale_dao = LocaleDAO()

    parameter["type"] = "Call"
    # print(f"requesting: {parameter}")
    calls = list(locale_dao.read_all_byexpiry_date(parameter))
    # print(f"{len(calls)} entries found")

    parameter["type"] = "Put"
    # print(f"requesting: {parameter}")
    puts = list(locale_dao.read_all_byexpiry_date(parameter))
    # print(f"{len(puts)} entries found")

    # using a set as we want unique strike values
    strikes = set()

    # empty list to create a list of available business dates
    bus_dates = list()

    # add all the strikes form the list of puts
    for put in puts:
        for key in put["data"].keys():
            strikes.add(int(key))

    # add all the strikes form the list of call     
    for call in calls:
        # get a list of available business dates
        bus_dates.append(call["parameter"]["bus_date"])
        for key in call["data"].keys():
            strikes.add(int(key))

    # for each business day, create the max_pain entry
    for bus_date in bus_dates:

        # max pain is a dict holding strike - value data, where value is a sum of put and call
        max_pain = {}

        parameter["type"] = "Call"
        parameter["bus_date"] = bus_date
        call = locale_dao.read_entry(parameter)

        parameter["type"] = "Put"
        parameter["bus_date"] = bus_date
        put = locale_dao.read_entry(parameter)

        for strike in strikes:

            data = call["data"]
            wert = 0
            for key, value in data.items():
                if value[0] < strike:
                    delta = strike - value[0]
                    wert += delta * value[1] 

            if strike not in max_pain:
                max_pain[strike] = 0
            max_pain[strike] += wert

            data = put["data"]
            wert = 0
            for key, value in data.items():
                if value[0] > strike:
                    delta =  value[0] - strike
                    wert += delta * value[1]

            if strike not in max_pain:
                max_pain[strike] = 0
            max_pain[strike] += wert           

        max_pain = dict(sorted(max_pain.items(), key=lambda item: item[1]))
        minimum_strike = list(max_pain)[0]
        # print(f"{bus_date} {minimum_strike}: {max_pain[minimum_strike]} ")

        max_pain_over_time.append([bus_date, minimum_strike, max_pain[minimum_strike]])

        # max_pain = dict(sorted(max_pain.items(), key=lambda item: item[0]))
        # names = list(max_pain.keys())
        # values = list(max_pain.values())

        # plt.bar(range(len(max_pain)), values, tick_label=names)
        # plt.show()

    locale_dao.close

    header = ["Date", "Strike", "Value"]
    print(tabulate(max_pain_over_time, headers=header, tablefmt='fancy_grid'))


def generate_max_pain_history(parameter: dict) -> None:
    
    max_pain_over_time = list()

    locale_dao = LocaleDAO()

    parameter["type"] = "Call"
    # print(f"requesting: {parameter}")
    calls = list(locale_dao.read_all_byexpiry_date(parameter))
    # print(f"{len(calls)} entries found")

    parameter["type"] = "Put"
    # print(f"requesting: {parameter}")
    puts = list(locale_dao.read_all_byexpiry_date(parameter))
    # print(f"{len(puts)} entries found")

    # using a set as we want unique strike values
    strikes = set()

    # empty list to create a list of available business dates
    bus_dates = list()

    # add all the strikes form the list of puts
    for put in puts:
        for key in put["data"].keys():
            strikes.add(int(key))

    # add all the strikes form the list of call     
    for call in calls:
        # get a list of available business dates
        bus_dates.append(call["parameter"]["bus_date"])
        for key in call["data"].keys():
            strikes.add(int(key))

    # for each business day, create the max_pain entry
    for bus_date in bus_dates:

        # max pain is a dict holding strike - value data, where value is a sum of put and call
        max_pain = {}

        parameter["type"] = "Call"
        parameter["bus_date"] = bus_date
        call = locale_dao.read_entry(parameter)

        parameter["type"] = "Put"
        parameter["bus_date"] = bus_date
        put = locale_dao.read_entry(parameter)

        for strike in strikes:

            data = call["data"]
            wert = 0
            for key, value in data.items():
                if value[0] < strike:
                    delta = strike - value[0]
                    wert += delta * value[1] 

            if strike not in max_pain:
                max_pain[strike] = 0
            max_pain[strike] += wert

            data = put["data"]
            wert = 0
            for key, value in data.items():
                if value[0] > strike:
                    delta =  value[0] - strike
                    wert += delta * value[1]

            if strike not in max_pain:
                max_pain[strike] = 0
            max_pain[strike] += wert           

        max_pain = dict(sorted(max_pain.items(), key=lambda item: item[1]))
        minimum_strike = list(max_pain)[0]
        # print(f"{bus_date} {minimum_strike}: {max_pain[minimum_strike]} ")

        max_pain_over_time.append([bus_date, minimum_strike, max_pain[minimum_strike]])

    locale_dao.close

    max_pain_over_time = sorted(max_pain_over_time, key=lambda x: x[0], reverse=True)

    header = ["Date", "Strike", "Value"]
    print(tabulate(max_pain_over_time, headers=header, tablefmt='fancy_grid'))


def generate_unique_filter(parameter: dict) -> dict:
    return {
        "$and": [
            {"parameter.type": parameter["type"]},
            {"parameter.bus_date": parameter["bus_date"]},
            {"parameter.product.productId": parameter["product"]["productId"]},
            {
                "parameter.product.productGroupId": parameter["product"][
                    "productGroupId"
                ]
            },
            {"parameter.expiry_date.month": parameter["expiry_date"]["month"]},
            {"parameter.expiry_date.year": parameter["expiry_date"]["year"]},
        ]
    }


def generate_filter_expiry_date(parameter: dict) -> dict:
    return {
        "$and": [
            {"parameter.type": parameter["type"]},
            {"parameter.product.productId": parameter["product"]["productId"]},
            {
                "parameter.product.productGroupId": parameter["product"][
                    "productGroupId"
                ]
            },
            {"parameter.expiry_date.month": parameter["expiry_date"]["month"]},
            {"parameter.expiry_date.year": parameter["expiry_date"]["year"]},
        ]
    }


def generate_url(
    product: dict[str, int], type: str, expiry_date: dict[str, int], bus_date: str
):
    return f"https://www.eurex.com/ex-en/data/statistics/market-statistics-online/100!onlineStats?productGroupId={product['productGroupId']}&productId={product['productId']}&viewType=3&cp={type}&month={expiry_date['month']}&year={expiry_date['year']}&busDate={bus_date}"

import urllib3
import pymongo
import configparser
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from datetime import date, datetime, timedelta
from sys import exit
import time
import calendar
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATE_FORMAT = "%Y%m%d"


class OnlineReader:
    def __init__(self):
        # open a connection to a URL using urllib3
        self._http = urllib3.PoolManager()

    def request_data(self, parameters: dict) -> dict:
        # url = generate_url_(product, type, expiry_date, bus_date)
        url = generate_url(**parameters)

        response = self._http.request("GET", url)
        print(f"Response for {response.geturl()}: {response.status} ... ")

        eurex_data = response.data.decode("utf-8")
        parsed_html = BeautifulSoup(eurex_data, features="lxml")
        if parsed_html.body is None:
            raise ValueError("no body found in server answer")
        else:
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

        entries = len(data_dict)
        if entries == 0:
            print("... no data available")
        else:
            print(f"... received {entries} entries")
        return {"parameter": parameters, "data": data_dict}


class LocaleDAO:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read("config.ini")
        self._client = pymongo.MongoClient(config.get("DB","url"))
        try:
            self._client.server_info()
        except pymongo.errors.ServerSelectionTimeoutError:
            exit("Mongo instance not reachable.")

        self._db = self._client[config.get("DB","db")]
        self._collection = self._db[config.get("DB","collection")]

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
                print(
                    f"Adding new entry for {open_interest_data['parameter']['product']['name']} {open_interest_data['parameter']['type']} {open_interest_data['parameter']['bus_date']}"
                )
                self._collection.insert_one(open_interest_data)
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not write data to locale storage: ", e)
        except KeyError:
            pass

    def read_all_by_expiry_date(self, parameter: dict) -> list[dict]:
        # print(f"Using Parameter: {parameter}")
        try:
            return list(self._collection.find(generate_filter_expiry_date(parameter)))
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not read data from locale storage: ", e)
            return list()
        except KeyError as ke:
            return list()

    def read_entry(self, parameter: dict) -> dict:
        # print(f"Using Parameter: {parameter}")
        try:
            return self._collection.find_one(generate_unique_filter(parameter))
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print("Could not read data from locale storage: ", e)
            return {}
        except KeyError:
            return {}

    def close(self):
        self._client.close


def update_data(parameter: dict) -> None:
    online_reader = OnlineReader()
    locale_dao = LocaleDAO()

    expiry_date = datetime.strptime(parameter["expiry_date"]["date"], DATE_FORMAT)
    today = datetime.now()

    for n in range(60):
        days_ago = timedelta(days=n)
        a = expiry_date - days_ago

        # if date is in the future or today
        if a >= today:
            continue

        # if the requested date is not a weekday (Mon - Fri)
        if a.isoweekday() not in range(1, 6):
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
            print(
                f"Entry already in local storage: {parameter['type']}, {parameter['bus_date']}"
            )

        parameter["type"] = "Put"
        result = locale_dao.read_entry(parameter)
        # if data not in local storage, request online
        if result is None:
            online_data = online_reader.request_data(parameter)
            if not online_data["data"]:
                continue
            locale_dao.write(online_data)
            time.sleep(5)
        else:
            print(
                f"Entry already in local storage: {parameter['type']}, {parameter['bus_date']}"
            )

    locale_dao.close


def generate_max_pain_chart(parameter: dict) -> None:
    max_pain_over_time = sorted(
        get_max_pain_history(parameter), key=lambda x: x[0], reverse=True
    )

    values = [max_pain[1] for max_pain in max_pain_over_time]
    names = [max_pain[0] for max_pain in max_pain_over_time]

    plt.title(
        f'{parameter["product"]["name"]} {parameter["expiry_date"]["month"]}.{parameter["expiry_date"]["year"]} {max_pain_over_time[0][1]}'
    )
    plt.ylabel("Strike")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    plt.step(names, values)
    plt.gcf().autofmt_xdate()
    plt.show()


def generate_max_pain_history(parameter: dict) -> None:
    max_pain_over_time = sorted(
        get_max_pain_history(parameter), key=lambda x: x[0], reverse=True
    )

    header = ["Date", "Strike", "Value"]
    print(tabulate(max_pain_over_time, headers=header, tablefmt="fancy_grid"))


def get_max_pain_history(parameter: dict) -> list:
    """
    generates a list of max pain entries
    """

    max_pain_over_time = list()

    locale_dao = LocaleDAO()

    parameter["type"] = "Call"
    calls = list(locale_dao.read_all_by_expiry_date(parameter))

    parameter["type"] = "Put"
    puts = list(locale_dao.read_all_by_expiry_date(parameter))

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
                    delta = value[0] - strike
                    wert += delta * value[1]

            if strike not in max_pain:
                max_pain[strike] = 0
            max_pain[strike] += wert

        max_pain = dict(sorted(max_pain.items(), key=lambda item: item[1]))
        minimum_strike = list(max_pain)[0]

        max_pain_over_time.append(
            [
                datetime.strptime(bus_date, DATE_FORMAT),
                minimum_strike,
                max_pain[minimum_strike],
            ]
        )

    locale_dao.close

    return max_pain_over_time


def get_most_recent_distribution(parameter: dict) -> None:
    max_pain_over_time = sorted(
        get_max_pain_history(parameter), key=lambda x: x[0], reverse=True
    )

    current_max_pain = max_pain_over_time[0]
    min_level = current_max_pain[1] * 0.925
    max_level = current_max_pain[1] * 1.075

    locale_dao = LocaleDAO()

    parameter["type"] = "Call"
    calls = list(locale_dao.read_all_by_expiry_date(parameter))

    parameter["type"] = "Put"
    puts = list(locale_dao.read_all_by_expiry_date(parameter))

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

    bus_date = sorted(bus_dates, reverse=True)[0]

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
                delta = value[0] - strike
                wert += delta * value[1]

        if strike not in max_pain:
            max_pain[strike] = 0
        max_pain[strike] += wert

    locale_dao.close

    max_pain = dict(sorted(max_pain.items(), key=lambda item: item[0]))

    max_pain_filtered = dict()
    print(f"filtering for {min_level} and {max_level}")
    for mp in max_pain:
        if mp < max_level and mp > min_level:
            max_pain_filtered[mp] = max_pain[mp]

    plt.title(
        f'{parameter["product"]["name"]} {parameter["expiry_date"]["month"]}.{parameter["expiry_date"]["year"]} {max_pain_over_time[0][1]}'
    )
    plt.ylabel("Value")
    # plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    plt.step(max_pain_filtered.keys(), max_pain_filtered.values())
    plt.gcf().autofmt_xdate()
    plt.show()


def generate_most_distribution(parameter: dict) -> None:
    """
    generate a chart showing for the specified business date the distribution of calls and puts
    """
    local_dao = LocaleDAO()
    parameter["type"] = "Call"
    calls = local_dao.read_entry(parameter)
    if not calls:
        raise ValueError("No data found for the provided parameter")

    call_labels = list()
    call_values = list()
    for call in calls["data"].values():
        call_labels.append(call[0])
        call_values.append(call[2])

    parameter["type"] = "Put"
    puts = local_dao.read_entry(parameter)

    put_labels = list()
    put_values = list()
    for put in puts["data"].values():
        put_labels.append(put[0])
        put_values.append(put[2])

    plt.barh(call_labels, call_values, height=20)
    plt.barh(put_labels, put_values, height=20)
    plt.show()


def generate_unique_filter(parameter: dict) -> dict:
    try:
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
    except KeyError as ke:
        print(f"Provided parameters are invalid: {parameter}")
        raise KeyError(ke)


def generate_filter_expiry_date(parameter: dict) -> dict:
    try:
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
    except KeyError as ke:
        print(f"Provided parameters are invalid: {parameter}")
        raise KeyError(ke)


def generate_url(
    product: dict[str, int], type: str, expiry_date: dict[str, int], bus_date: str
):
    return f"https://www.eurex.com/ex-en/data/statistics/market-statistics-online/100!onlineStats?productGroupId={product['productGroupId']}&productId={product['productId']}&viewType=3&cp={type}&month={expiry_date['month']}&year={expiry_date['year']}&busDate={bus_date}"


def next_expiry_date() -> dict:
    """
    using the current date, we want to know the next expiry date
    """
    now = date.today()
    current_year = now.year
    current_month = now.month

    c = calendar.Calendar(firstweekday=calendar.SATURDAY)
    expiry_date = c.monthdatescalendar(current_year, current_month)[2][6]

    if now > expiry_date:
        print(f" we are already past expiry, using next month")
        current_month += 1
        if current_month == 12:
            current_year += 1
            current_month = 1
        print(f"using month: {current_month} and year: {current_year}")
        expiry_date = c.monthdatescalendar(current_year, current_month)[2][6]

    expiry_month = expiry_date.month
    expiry_year = expiry_date.year
    expiry_day = datetime.strftime(expiry_date, DATE_FORMAT)
    expiry_date_entry = {
        "month": expiry_month,
        "year": expiry_year,
        "date": expiry_day,
    }

    return expiry_date_entry

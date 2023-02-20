
from open_interest import OnlineReader, LocaleDAO
from datetime import datetime, timedelta
from tabulate import tabulate
import matplotlib.pyplot as plt
import time
import underlying

expiry_date = {"month": 2, "year": 2023}
product = underlying.ALLIANZ

parameter = {"product": product, "expiry_date": expiry_date}
    

def main():

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

        max_pain = dict(sorted(max_pain.items(), key=lambda item: item[0]))
        names = list(max_pain.keys())
        values = list(max_pain.values())

        plt.bar(range(len(max_pain)), values, tick_label=names)
        plt.show()

    locale_dao.close

if __name__ == "__main__":
  main()
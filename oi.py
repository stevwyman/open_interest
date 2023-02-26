from open_interest import update_data, generate_most_distribution, generate_max_pain_chart, generate_max_pain_history, get_most_recent_distribution
import underlying
import expiry
import argparse


def main():
    parser = argparse.ArgumentParser(description="Manage open interest data from www.eurex.de")
    parser.add_argument(
        "-t",
        type=str,
        default="update",
        help="the task to perform, i.e. update"
    )
    parser.add_argument(
        "-u",
        type=str,
        default="DAX",
        help="the underlying, i.e. DAX",
    )
    parser.add_argument(
        "-e",
        type=str,
        default="March_2023",
        help="the expiry, i.e. March_2023",
    )
    parser.add_argument(
        "-b",
        type=str,
        help="the date for which the date is requested, i.e. 20230222 (Feb 22nd, 2023)",
    )
    args = parser.parse_args()

    
    if args.u in underlying.UNDERLYINGS:
        product = underlying.UNDERLYINGS[args.u]
    else:
        exit("Invalid underlying name provided, use i.e. DAX or ADIDAS")

    if args.e in expiry.EXPIRIES:
        expiry_date = expiry.EXPIRIES[args.e]
    else:
        exit("Invalid expiry date provided, use i.e. March_2023")

    if args.t == "update":
        print(f"Updating {product['name']} for {expiry_date['month']} {expiry_date['year']} ...")
        update_data({"product": product, "expiry_date": expiry_date})
    elif args.t == "list":
        print(f"Showing history of max pain list for {product['name']} for {expiry_date['month']} {expiry_date['year']} ...")
        generate_max_pain_history({"product": product, "expiry_date": expiry_date})
    elif args.t == "chart":
        print(f"Showing history of max pain chart for {product['name']} for {expiry_date['month']} {expiry_date['year']} ...")
        generate_max_pain_chart({"product": product, "expiry_date": expiry_date})
    elif args.t == "distribution":
        print(f"Showing distribution of max pain for {product['name']} for {expiry_date['month']} {expiry_date['year']} ...")
        get_most_recent_distribution({"product": product, "expiry_date": expiry_date})
    elif args.t == "distribution_by_date":
        if args.b:
            print(f"Showing distribution of max pain for {product['name']} for {expiry_date['month']} {expiry_date['year']} on {args.b}...")
            try:
                generate_most_distribution({"product": product, "expiry_date": expiry_date, "bus_date": args.b})
            except ValueError as ve:
                exit(ve)
        else:
            exit("No business date provided, use the -b option")

if __name__ == "__main__":
    main()
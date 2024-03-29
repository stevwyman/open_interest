from open_interest import (
    update_data,
    generate_most_distribution,
    generate_max_pain_chart,
    generate_max_pain_history,
    get_most_recent_distribution,
    next_expiry_date,
)
import underlying
import expiry
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Manage open interest data from www.eurex.de"
    )
    parser.add_argument(
        "-t",
        type=str,
        default="update",
        help="the task to perform, default update, others: list, chart, distribution, distribution_by_date",
    )
    parser.add_argument(
        "-u",
        type=str,
        default="DAX",
        help="the underlying, default DAX, others ES50, see underlying.py",
    )
    parser.add_argument(
        "-e",
        type=str,
        help="the expiry, i.e. March_2023 from the list expiry.py, or leave empty, then the next valid expiry date is chosen by default",
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
        expiry_date = next_expiry_date()
        print(f"Using the following expiry date: {expiry_date}")

    if args.t == "update":
        print(
            f"Updating {product['name']} for {expiry_date['month']} {expiry_date['year']} ..."
        )
        update_data({"product": product, "expiry_date": expiry_date})
    elif args.t == "list":
        print(
            f"Showing history of max pain list for {product['name']} for {expiry_date['month']} {expiry_date['year']} ..."
        )
        generate_max_pain_history({"product": product, "expiry_date": expiry_date})
    elif args.t == "chart":
        print(
            f"Showing history of max pain chart for {product['name']} for {expiry_date['month']} {expiry_date['year']} ..."
        )
        generate_max_pain_chart({"product": product, "expiry_date": expiry_date})
    elif args.t == "distribution":
        print(
            f"Showing distribution of max pain for {product['name']} for {expiry_date['month']} {expiry_date['year']} ..."
        )
        get_most_recent_distribution({"product": product, "expiry_date": expiry_date})
    elif args.t == "distribution_by_date":
        if args.b:
            print(
                f"Showing distribution of max pain for {product['name']} for {expiry_date['month']} {expiry_date['year']} on {args.b}..."
            )
            try:
                generate_most_distribution(
                    {"product": product, "expiry_date": expiry_date, "bus_date": args.b}
                )
            except ValueError as ve:
                exit(ve)
        else:
            exit("No business date provided, use the -b option")
    else:
        exit("Invalid task requested")


if __name__ == "__main__":
    main()

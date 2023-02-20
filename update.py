from open_interest import update_data
import underlying


expiry_date = {"month": 3, "year": 2023}
product = underlying.ALLIANZ

update_data({"product": product, "expiry_date": expiry_date})

from open_interest import update_data
import underlying
import expiry


expiry_date = expiry.February_2023
product = underlying.DAX

update_data({"product": product, "expiry_date": expiry_date})

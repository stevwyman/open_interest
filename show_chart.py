from open_interest import generate_max_pain_chart
import underlying
import expiry


expiry_date = expiry.March_2023
product = underlying.DAX

generate_max_pain_chart({"product": product, "expiry_date": expiry_date})

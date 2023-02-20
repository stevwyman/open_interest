from open_interest import generate_max_pain_history
import underlying


expiry_date = {"month": 3, "year": 2023}
product = underlying.DAX

generate_max_pain_history({"product": product, "expiry_date": expiry_date})

from open_interest import LocaleDAO

product = {"productGroupId": 13394, "productId": 70044}
expiry_date = {"month": 2, "year": 2023}


def test_read():
    parameter = {"product": product, "type": "Call", "expiry_date": expiry_date, "bus_date": "20230217"}
    local_dao = LocaleDAO()
    assert local_dao != None

    results = local_dao.read(parameter)
    assert len(list(results)) > 0
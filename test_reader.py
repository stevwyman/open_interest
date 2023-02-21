from open_interest import LocaleDAO, OnlineReader
import expiry
import underlying

invalid_product = {"name": "something", "productGroupId": "7", "productId": "b"}
invalid_expiry = {"month": "d", "year": "a", "date": "20230317"}


def test_read_all_byexpiry_date():
    parameter = {"product": invalid_product, "type": "muhh", "expiry_date": invalid_expiry, "bus_date": "20230217"}
    
    local_dao = LocaleDAO()
    assert local_dao != None

    results = local_dao.read_all_byexpiry_date(parameter)
    assert len(list(results))  == 0

    parameter = {}
    results = local_dao.read_all_byexpiry_date(parameter)
    assert len(list(results))  == 0

def test_online_reader():
    online_reader = OnlineReader()
    assert online_reader != None

    parameter = {"product": invalid_product, "type": "muhh", "expiry_date": invalid_expiry, "bus_date": "20230217"}
    online_reader.request_data(parameter) == None

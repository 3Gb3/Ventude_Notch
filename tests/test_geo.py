from ventude.services.geo import _place_from_ip_payload
from ventude.services.weather import Place


def test_place_from_ip_api_payload():
    place = _place_from_ip_payload(
        {
            "status": "success",
            "city": "Porto Alegre",
            "regionName": "Rio Grande do Sul",
            "country": "Brazil",
            "lat": -30.03,
            "lon": -51.23,
        }
    )
    assert place == Place(
        name="Porto Alegre",
        country="Brazil",
        lat=-30.03,
        lon=-51.23,
        admin1="Rio Grande do Sul",
    )


def test_place_from_ipapi_co_payload():
    place = _place_from_ip_payload(
        {
            "city": "Lisbon",
            "region": "Lisbon",
            "country_name": "Portugal",
            "latitude": 38.72,
            "longitude": -9.14,
        }
    )
    assert place is not None
    assert place.name == "Lisbon"
    assert place.lat == 38.72


def test_place_from_failed_status():
    assert _place_from_ip_payload({"status": "fail", "message": "reserved"}) is None

from app.services.whatsapp.code_parser import extract_pairing_code


def test_extract_pairing_code_accepts_case_insensitive_and_separators():
    assert extract_pairing_code("CODE 2F4U4J7A") == "2F4U4J7A"
    assert extract_pairing_code("code 2f4u4j7a") == "2F4U4J7A"
    assert extract_pairing_code("CoDe 2f4u-4j7a") == "2F4U4J7A"
    assert extract_pairing_code("cOdE : 2 f 4 u - 4 j 7 a") == "2F4U4J7A"


def test_extract_pairing_code_accepts_plain_wrapped_code():
    assert extract_pairing_code("@@@2f4u-4j7a###") == "2F4U4J7A"


def test_extract_pairing_code_rejects_invalid_lengths_or_missing():
    assert extract_pairing_code("CODE 2F4U4J7") is None
    assert extract_pairing_code("CODE 2F4U4J7A99") is None
    assert extract_pairing_code("hello there") is None
    assert extract_pairing_code("") is None


from app.services.media_intelligence import build_task_type, extract_receipt_fields, normalize_text


def test_task_type_routing():
    assert build_task_type('audio', 'audio/ogg') == 'transcription'
    assert build_task_type('document', 'application/pdf') == 'document'
    assert build_task_type('image', 'image/jpeg') == 'vision'
    assert build_task_type('image', 'image/jpeg', 'receipt') == 'receipt'


def test_receipt_extraction_is_conservative():
    text = 'SHOP ABC\nTOTAL: LSL 1,250.50\nDate 2026-09-07\n+266 5000 1234'
    result = extract_receipt_fields(text)
    assert result['total'] == '1250.50'
    assert result['currency'] == 'LSL'
    assert '+266 5000 1234' in result['phones']


def test_text_normalization_removes_nul_and_caps_output():
    assert normalize_text(' a\x00   b ') == 'a b'
    assert len(normalize_text('x' * 20, 5)) == 5

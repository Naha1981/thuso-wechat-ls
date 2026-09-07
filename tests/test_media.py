from app.services.media import content_key, hash_bytes, sanitize_filename, sniff_mime


def test_media_hash_and_content_key_are_deterministic():
    digest = hash_bytes(b'hello')
    assert len(digest) == 64
    assert content_key(digest, 'image/jpeg').endswith(f'/{digest}.jpg')


def test_filename_is_path_safe():
    assert sanitize_filename('../../secret.pdf') == 'secret.pdf'
    assert sanitize_filename('a/b\\c?.pdf') == 'a_b_c_.pdf'


def test_magic_bytes_win_over_mime_spoofing():
    assert sniff_mime(b'%PDF-1.7\n', 'image/jpeg') == 'application/pdf'
    assert sniff_mime(b'\x89PNG\r\n\x1a\n', 'application/pdf') == 'image/png'


def test_mp4_requires_ftyp():
    assert sniff_mime(b'not-an-mp4', 'video/mp4') is None
    assert sniff_mime(b'\x00\x00\x00\x18ftypisom', 'video/mp4') == 'video/mp4'

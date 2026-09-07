from app.payments.registry import get_payment_registry

def test_lesotho_registry_contains_all_current_issuers_and_aggregators():
    names={x['name'] for x in get_payment_registry().list()}
    assert {'mopay_ls','paylesotho','mpesa_ls','ecocash_ls','khetsi_ls','cpay_ls','smartel_money_ls','chaperone_ls'} <= names

def test_lesotho_channels():
    rows={x['name']:x['channels'] for x in get_payment_registry().list()}
    assert 'mpesa' in rows['mopay_ls'] and 'ecocash' in rows['mopay_ls']
    assert 'khetsi' in rows['khetsi_ls']
    assert 'smartel_money' in rows['smartel_money_ls']

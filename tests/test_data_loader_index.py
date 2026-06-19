import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.data_loader import INDEX_STANDARD_COLUMNS


def test_index_standard_columns_includes_amount():
    assert 'amount' in INDEX_STANDARD_COLUMNS
    assert 'date' in INDEX_STANDARD_COLUMNS
    assert 'open' in INDEX_STANDARD_COLUMNS
    assert 'close' in INDEX_STANDARD_COLUMNS
    assert 'volume' in INDEX_STANDARD_COLUMNS
    assert len(INDEX_STANDARD_COLUMNS) == 7

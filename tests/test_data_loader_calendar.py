"""default_trading_calendar 测试 —— 走 DataHub(已有 FakeHub 模式参考 test_backtest_service.py)。"""
import os
import pytest

from backtest.data_loader import default_trading_calendar


def test_returns_sorted_dates_from_fake_hub(monkeypatch):
    """注入 fake datahub,验证返回的日期列表按 YYYYMMDD 升序。"""

    class FakeFrame:
        def __init__(self, dates):
            import pandas as pd
            self._df = pd.DataFrame({'date': pd.to_datetime(dates)})

        @property
        def empty(self):
            return self._df.empty

        def __getitem__(self, key):
            return self._df[key]

        @property
        def columns(self):
            return self._df.columns

    class FakeHub:
        def __init__(self, dates):
            self._frame = FakeFrame(dates)

        def get_dataset(self, request):
            class Result:
                pass
            r = Result()
            r.frame = self._frame
            return r

    # 用 datahub.service.DataHub 作为注入点:monkeypatch 替换构造函数
    import datahub.service
    monkeypatch.setattr(
        datahub.service, 'DataHub',
        lambda **kwargs: FakeHub(['2020-01-02', '2020-01-01', '2020-01-03']),
    )

    dates = default_trading_calendar('000001', '20200101', '20200131')
    assert dates == ['20200101', '20200102', '20200103'], f'应排序后输出,实际 {dates}'


def test_returns_empty_when_no_data(monkeypatch):
    class FakeFrame:
        empty = True
        def __getitem__(self, key): return None

    class FakeHub:
        def get_dataset(self, request):
            class Result: pass
            r = Result()
            r.frame = FakeFrame()
            return r

    import datahub.service
    monkeypatch.setattr(datahub.service, 'DataHub', lambda **kwargs: FakeHub())

    assert default_trading_calendar('000001', '20200101', '20200131') == []

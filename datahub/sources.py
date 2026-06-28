from __future__ import annotations

import time

import akshare as ak
import pandas as pd

from datahub.models import DataHubError, DatasetRequest


_AKSHARE_COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}


def _is_empty_data_error(exc: Exception) -> bool:
    """Deterministic empty-data error from AkShare: retrying is pointless."""
    return "Length mismatch" in str(exc)


def _retry_akshare(fetch, what: str, attempts: int = 3):
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch()
        except Exception as exc:
            last_err = exc
            if _is_empty_data_error(exc):
                raise
            print(f"{what} 请求失败(第{attempt}次): {exc}")
            if attempt < attempts:
                time.sleep(2)
    raise last_err


class AkshareSource:
    name = "akshare"

    def fetch(self, request: DatasetRequest) -> pd.DataFrame:
        if request.dataset_type == "stock_daily":
            return self.fetch_stock_daily(request)
        if request.dataset_type == "index_daily":
            return self.fetch_index_daily(request)
        if request.dataset_type == "etf_daily":
            return self.fetch_etf_daily(request)
        if request.dataset_type == "market_turnover":
            return self.fetch_market_turnover(request)
        if request.dataset_type == "stock_profile":
            return self.fetch_stock_profile(request)
        if request.dataset_type == "index_constituents":
            return self.fetch_index_constituents(request)
        raise DataHubError("unsupported_dataset", f"Unsupported dataset type: {request.dataset_type}")

    def fetch_stock_daily(self, request: DatasetRequest) -> pd.DataFrame:
        last_err = None
        for attempt in range(1, 4):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=request.symbol,
                    period="daily",
                    start_date=request.start,
                    end_date=request.end,
                )
                df = df[list(_AKSHARE_COLUMN_MAP.keys())]
                df.columns = list(_AKSHARE_COLUMN_MAP.values())
                return df
            except Exception as exc:
                last_err = exc
                if attempt < 3:
                    time.sleep(2)

        prefix = "sh" if str(request.symbol).startswith("6") else "sz"
        for attempt in range(1, 3):
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=f"{prefix}{request.symbol}",
                    start_date=request.start,
                    end_date=request.end,
                )
                tx_df = pd.DataFrame({
                    "date": df["date"],
                    "open": df["open"],
                    "high": df["high"],
                    "low": df["low"],
                    "close": df["close"],
                    "volume": df["volume"],
                    "amount": df["amount"],
                })
                return tx_df
            except Exception:
                if attempt < 2:
                    time.sleep(1)
        raise DataHubError("source_unavailable", f"All stock sources failed for {request.symbol}") from last_err

    def fetch_stock_profile(self, request: DatasetRequest) -> pd.DataFrame:
        """Snapshot of A-share static info: code, name, is_st (name prefix).

        Snapshot dataset — call with start=end=fetch date. list_date is not
        exposed by akshare's bulk APIs; callers should derive it from the
        earliest cached stock_daily date per symbol.
        """
        last_err = None
        for attempt in range(1, 3):
            try:
                df = ak.stock_info_a_code_name()
                df["is_st"] = df["name"].astype(str).str.startswith(("ST", "*ST"))
                snapshot_date = pd.to_datetime(request.start).normalize()
                df["date"] = snapshot_date
                return df[["date", "code", "name", "is_st"]].copy()
            except Exception as exc:
                last_err = exc
                if attempt < 2:
                    time.sleep(2)

        try:
            df = ak.stock_zh_a_spot_em()
            df["is_st"] = df["名称"].astype(str).str.startswith(("ST", "*ST"))
            snapshot_date = pd.to_datetime(request.start).normalize()
            df["date"] = snapshot_date
            return df[["date", "代码", "名称", "is_st"]].rename(
                columns={"代码": "code", "名称": "name"}
            ).copy()
        except Exception as exc:
            raise DataHubError(
                "source_unavailable", f"All profile sources failed: {exc}"
            ) from last_err

    def fetch_index_constituents(self, request: DatasetRequest) -> pd.DataFrame:
        """Snapshot of an index's current constituents (csindex).

        Symbol format: '000300' (CSI 300), '000905' (CSI 500). akshare returns
        the current snapshot only — historical constituent changes are not
        available through this source.
        """
        try:
            df = ak.index_stock_cons_weight_csindex(symbol=request.symbol)
        except Exception as exc:
            raise DataHubError(
                "source_unavailable", f"Index constituents failed for {request.symbol}"
            ) from exc

        snapshot_date = pd.to_datetime(df["日期"].iloc[0]).normalize()
        out = pd.DataFrame({
            "date": [snapshot_date] * len(df),
            "code": df["成分券代码"].astype(str).str.zfill(6).values,
            "weight": df["权重"].astype(float).values,
        })
        return out[["date", "code", "weight"]].copy()

    def fetch_index_daily(self, request: DatasetRequest) -> pd.DataFrame:
        try:
            full_df = ak.stock_zh_index_daily(symbol=request.symbol)
        except Exception as exc:
            raise DataHubError("source_unavailable", f"Index source failed for {request.symbol}") from exc
        full_df["date"] = pd.to_datetime(full_df["date"])
        mask = (full_df["date"] >= pd.to_datetime(request.start)) & (full_df["date"] <= pd.to_datetime(request.end))
        df = full_df.loc[mask].copy()
        if "amount" not in df.columns:
            df["amount"] = df["close"] * df["volume"] * 100
        return df[["date", "open", "high", "low", "close", "volume", "amount"]]

    def fetch_etf_daily(self, request: DatasetRequest) -> pd.DataFrame:
        try:
            df = ak.fund_etf_hist_sina(symbol=request.symbol).copy()
        except Exception as exc:
            raise DataHubError("source_unavailable", f"ETF source failed for {request.symbol}") from exc
        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"] >= pd.to_datetime(request.start)) & (df["date"] <= pd.to_datetime(request.end))
        df = df.loc[mask, ["date", "open", "high", "low", "close", "volume"]].copy()
        df["amount"] = 0.0
        return df[["date", "open", "high", "low", "close", "volume", "amount"]]

    def fetch_market_turnover(self, request: DatasetRequest) -> pd.DataFrame:
        index_df = self.fetch_index_daily(
            DatasetRequest("index_daily", symbol="sh000001", start=request.start, end=request.end)
        )
        rows = []
        for current in pd.to_datetime(index_df["date"]).drop_duplicates().sort_values():
            date_text = current.strftime("%Y%m%d")
            sse = _fetch_sse_turnover(date_text)
            szse = _fetch_szse_turnover(date_text)
            if sse is None or szse is None:
                continue  # 该交易日两市成交额数据不完整，跳过
            total = float(sse) + float(szse)
            rows.append(
                {
                    "date": current,
                    "open": total,
                    "high": total,
                    "low": total,
                    "close": total,
                    "volume": 0.0,
                }
            )
        if not rows:
            raise DataHubError("empty_data", f"No turnover rows for {request.start}-{request.end}")
        return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])


def _fetch_sse_turnover(date_text: str) -> float | None:
    """SSE stock turnover for one day. Returns None (skip day) when no data, like the legacy loader."""
    try:
        df = _retry_akshare(lambda: ak.stock_sse_deal_daily(date=date_text), f"SSE成交额 {date_text}")
    except Exception as e:
        print(f"SSE成交额 {date_text} 无可用数据，跳过: {e}")
        return None
    row = df.loc[df["单日情况"] == "成交金额"]
    if row.empty:
        return None
    if "股票" in row.columns and pd.notna(row["股票"].iloc[0]):
        return float(row["股票"].iloc[0])
    columns = [col for col in ["主板A", "主板B", "科创板"] if col in row.columns]
    return float(row[columns].fillna(0).sum(axis=1).iloc[0])


def _fetch_szse_turnover(date_text: str) -> float | None:
    """SZSE stock turnover for one day. Returns None (skip day) when no data, like the legacy loader."""
    try:
        df = _retry_akshare(lambda: ak.stock_szse_summary(date=date_text), f"SZSE成交额 {date_text}")
    except Exception as e:
        print(f"SZSE成交额 {date_text} 无可用数据，跳过: {e}")
        return None
    exact_row = df.loc[df["证券类别"] == "股票"]
    if not exact_row.empty:
        return float(exact_row["成交金额"].iloc[0])
    stock_rows = df[df["证券类别"].astype(str).str.contains("股票|A股|B股", na=False)]
    if stock_rows.empty:
        return None
    return float(stock_rows["成交金额"].sum())

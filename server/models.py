from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    start: str
    end: str
    cash: float = 100000.0
    use_market_filter: bool = True
    risk_percent: float = 0.95
    fast_ma: int = 10
    slow_ma: int = 20
    force: bool = False


class JobResponse(BaseModel):
    id: int
    run_key: str
    status: str
    symbol: str
    start_date: str
    end_date: str
    cash: float
    use_market_filter: bool
    risk_percent: float
    fast_ma: int
    slow_ma: int
    code_version: str
    cache_hit: bool
    error: str | None = None
    created_at: str
    updated_at: str

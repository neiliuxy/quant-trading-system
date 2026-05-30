# Web Backtest Dashboard

## Local Development

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the API:

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Install frontend dependencies:

```powershell
Set-Location web
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Data Files

- SQLite task database: `data/quantx.sqlite`
- Result artifacts: `data/results/{job_id}.json`
- Market and stock CSV caches: `data/*.csv`

## Deployment Notes

The first version has no login. For server deployment, bind the API behind a reverse proxy or a private network. Use:

```powershell
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Build the frontend with:

```powershell
Set-Location web
npm run build
```

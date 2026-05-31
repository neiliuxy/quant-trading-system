# Backtest History Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add single-item and bulk deletion capabilities to the backtest history, allowing users to remove individual backtest results or clear all history from the web UI and API.

**Architecture:** 
- Backend: Add two new API endpoints (`DELETE /api/jobs/{job_id}` for single deletion, `DELETE /api/jobs` for bulk deletion) with database cascade cleanup
- Database: Leverage existing foreign key constraints to automatically clean up job_results when jobs are deleted
- Frontend: Add delete buttons to the job list UI with confirmation dialogs, and a "Clear All" button with safety confirmation

**Tech Stack:** FastAPI (backend), SQLite with foreign keys (database), React/TypeScript (frontend)

---

## File Structure

**Backend changes:**
- `server/jobs.py` — Add `delete_job()` and `delete_all_jobs()` functions
- `server/api.py` — Add two new DELETE endpoints

**Frontend changes:**
- `web/src/api.ts` — Add `deleteJob()` and `deleteAllJobs()` API client functions
- `web/src/App.tsx` — Add delete buttons and confirmation dialogs to the job list UI

**Tests:**
- `tests/test_server_api.py` — Add tests for both delete endpoints
- `tests/test_server_jobs.py` — Add tests for delete functions

---

## Task 1: Add delete functions to server/jobs.py

**Files:**
- Modify: `server/jobs.py`
- Test: `tests/test_server_jobs.py`

- [ ] **Step 1: Read the current jobs.py to understand the structure**

Run: `cat server/jobs.py`

Expected: See the current job management functions and database interaction patterns.

- [ ] **Step 2: Write the failing test for delete_job()**

Add to `tests/test_server_jobs.py`:

```python
def test_delete_job_removes_job_and_result(conn):
    """Test that deleting a job also deletes its result via CASCADE."""
    from server.jobs import create_or_reuse_job, delete_job, get_job, get_job_result
    from backtest.service import BacktestRequest
    
    # Create a job
    req = BacktestRequest(symbol='000001', start='20240101', end='20240630')
    job = create_or_reuse_job(conn, req)
    job_id = job['id']
    
    # Verify job exists
    assert get_job(conn, job_id) is not None
    
    # Delete the job
    delete_job(conn, job_id)
    
    # Verify job is gone
    assert get_job(conn, job_id) is None
    
    # Verify result is also gone (CASCADE delete)
    assert get_job_result(conn, job_id) is None


def test_delete_job_with_nonexistent_id_does_not_raise(conn):
    """Test that deleting a nonexistent job doesn't raise an error."""
    from server.jobs import delete_job
    
    # Should not raise
    delete_job(conn, 99999)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/test_server_jobs.py::test_delete_job_removes_job_and_result -v`

Expected: FAIL with "delete_job not defined"

- [ ] **Step 4: Implement delete_job() in server/jobs.py**

Add to `server/jobs.py` after the `get_job_result()` function:

```python
def delete_job(conn: sqlite3.Connection, job_id: int) -> None:
    """Delete a job and its associated result (CASCADE via foreign key)."""
    conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
    conn.commit()


def delete_all_jobs(conn: sqlite3.Connection) -> int:
    """Delete all jobs and their results. Returns the count of deleted jobs."""
    cursor = conn.execute('SELECT COUNT(*) FROM jobs')
    count = cursor.fetchone()[0]
    conn.execute('DELETE FROM jobs')
    conn.commit()
    return count
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_server_jobs.py::test_delete_job_removes_job_and_result tests/test_server_jobs.py::test_delete_job_with_nonexistent_id_does_not_raise -v`

Expected: PASS

- [ ] **Step 6: Write and run test for delete_all_jobs()**

Add to `tests/test_server_jobs.py`:

```python
def test_delete_all_jobs_removes_all_jobs(conn):
    """Test that delete_all_jobs removes all jobs and returns count."""
    from server.jobs import create_or_reuse_job, delete_all_jobs, list_jobs
    from backtest.service import BacktestRequest
    
    # Create multiple jobs
    for i in range(3):
        req = BacktestRequest(symbol=f'{i:06d}', start='20240101', end='20240630')
        create_or_reuse_job(conn, req)
    
    # Verify jobs exist
    assert len(list_jobs(conn, limit=100)) == 3
    
    # Delete all
    count = delete_all_jobs(conn)
    
    # Verify count and empty list
    assert count == 3
    assert len(list_jobs(conn, limit=100)) == 0
```

Run: `pytest tests/test_server_jobs.py::test_delete_all_jobs_removes_all_jobs -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add server/jobs.py tests/test_server_jobs.py
git commit -m "feat: add delete_job and delete_all_jobs functions"
```

---

## Task 2: Add DELETE API endpoints to server/api.py

**Files:**
- Modify: `server/api.py`
- Test: `tests/test_server_api.py`

- [ ] **Step 1: Write the failing test for DELETE /api/jobs/{job_id}**

Add to `tests/test_server_api.py`:

```python
def test_delete_job_endpoint(client, conn):
    """Test DELETE /api/jobs/{job_id} removes the job."""
    from server.jobs import create_or_reuse_job, get_job
    from backtest.service import BacktestRequest
    
    # Create a job
    req = BacktestRequest(symbol='000001', start='20240101', end='20240630')
    job = create_or_reuse_job(conn, req)
    job_id = job['id']
    
    # Delete via API
    response = client.delete(f'/api/jobs/{job_id}')
    assert response.status_code == 200
    
    # Verify job is gone
    assert get_job(conn, job_id) is None


def test_delete_job_endpoint_nonexistent_returns_404(client):
    """Test DELETE /api/jobs/{job_id} returns 404 for nonexistent job."""
    response = client.delete('/api/jobs/99999')
    assert response.status_code == 404


def test_delete_all_jobs_endpoint(client, conn):
    """Test DELETE /api/jobs removes all jobs."""
    from server.jobs import create_or_reuse_job, list_jobs
    from backtest.service import BacktestRequest
    
    # Create multiple jobs
    for i in range(2):
        req = BacktestRequest(symbol=f'{i:06d}', start='20240101', end='20240630')
        create_or_reuse_job(conn, req)
    
    # Delete all via API
    response = client.delete('/api/jobs')
    assert response.status_code == 200
    data = response.json()
    assert data['deleted_count'] == 2
    
    # Verify all jobs are gone
    assert len(list_jobs(conn, limit=100)) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_server_api.py::test_delete_job_endpoint tests/test_server_api.py::test_delete_all_jobs_endpoint -v`

Expected: FAIL with "404 Not Found" or similar (endpoints don't exist yet)

- [ ] **Step 3: Add imports to server/api.py**

At the top of `server/api.py`, update the imports from `server.jobs`:

```python
from server.jobs import create_or_reuse_job, get_job, get_job_result, list_jobs, request_from_job, delete_job, delete_all_jobs
```

- [ ] **Step 4: Implement DELETE /api/jobs/{job_id} endpoint**

Add to `server/api.py` after the `job_result()` endpoint (around line 1130):

```python
    @app.delete('/api/jobs/{job_id}')
    def delete_job_endpoint(job_id: int):
        """Delete a single backtest job."""
        job = get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail='job not found')
        delete_job(conn, job_id)
        return {'status': 'deleted', 'job_id': job_id}
```

- [ ] **Step 5: Implement DELETE /api/jobs endpoint**

Add to `server/api.py` after the single delete endpoint:

```python
    @app.delete('/api/jobs')
    def delete_all_jobs_endpoint():
        """Delete all backtest jobs."""
        deleted_count = delete_all_jobs(conn)
        return {'status': 'deleted', 'deleted_count': deleted_count}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_server_api.py::test_delete_job_endpoint tests/test_server_api.py::test_delete_job_endpoint_nonexistent_returns_404 tests/test_server_api.py::test_delete_all_jobs_endpoint -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add server/api.py tests/test_server_api.py
git commit -m "feat: add DELETE endpoints for single and bulk job deletion"
```

---

## Task 3: Add API client functions to web/src/api.ts

**Files:**
- Modify: `web/src/api.ts`

- [ ] **Step 1: Add deleteJob() function**

Add to `web/src/api.ts` after the `getResult()` function:

```typescript
export function deleteJob(jobId: number): Promise<{ status: string; job_id: number }> {
  return request<{ status: string; job_id: number }>(`/api/jobs/${jobId}`, {
    method: 'DELETE',
  });
}
```

- [ ] **Step 2: Add deleteAllJobs() function**

Add to `web/src/api.ts` after `deleteJob()`:

```typescript
export function deleteAllJobs(): Promise<{ status: string; deleted_count: number }> {
  return request<{ status: string; deleted_count: number }>('/api/jobs', {
    method: 'DELETE',
  });
}
```

- [ ] **Step 3: Verify the file compiles**

Run: `cd web && npm run build`

Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add web/src/api.ts
git commit -m "feat: add deleteJob and deleteAllJobs API client functions"
```

---

## Task 4: Add delete UI to web/src/App.tsx

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Read the current App.tsx to understand the job list rendering**

Run: `cat web/src/App.tsx | head -100`

Expected: See the current component structure and job list rendering.

- [ ] **Step 2: Import the new API functions**

Update the import statement at the top of `web/src/App.tsx`:

```typescript
import { listJobs, createJob, listStrategies, getResult, deleteJob, deleteAllJobs } from './api';
```

- [ ] **Step 3: Add state for delete confirmation dialog**

In the App component, add state variables after the existing useState calls:

```typescript
const [deleteConfirmJobId, setDeleteConfirmJobId] = useState<number | null>(null);
const [deleteAllConfirm, setDeleteAllConfirm] = useState(false);
const [isDeleting, setIsDeleting] = useState(false);
```

- [ ] **Step 4: Add handleDeleteJob function**

Add this function in the App component before the return statement:

```typescript
const handleDeleteJob = async (jobId: number) => {
  setIsDeleting(true);
  try {
    await deleteJob(jobId);
    setDeleteConfirmJobId(null);
    // Refresh the job list
    const jobs = await listJobs();
    setJobs(jobs);
  } catch (error) {
    alert(`Failed to delete job: ${error}`);
  } finally {
    setIsDeleting(false);
  }
};
```

- [ ] **Step 5: Add handleDeleteAllJobs function**

Add this function after `handleDeleteJob`:

```typescript
const handleDeleteAllJobs = async () => {
  setIsDeleting(true);
  try {
    await deleteAllJobs();
    setDeleteAllConfirm(false);
    // Refresh the job list
    const jobs = await listJobs();
    setJobs(jobs);
  } catch (error) {
    alert(`Failed to delete all jobs: ${error}`);
  } finally {
    setIsDeleting(false);
  }
};
```

- [ ] **Step 6: Add delete button to each job row in the job list**

Find the job list rendering section (the map over `jobs`) and add a delete button. Locate the line that renders each job and add this button before the closing `</div>`:

```typescript
<button
  onClick={() => setDeleteConfirmJobId(job.id)}
  disabled={isDeleting}
  style={{ marginLeft: '8px', padding: '4px 8px', backgroundColor: '#ff6b6b', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
>
  Delete
</button>
```

- [ ] **Step 7: Add delete confirmation dialog for single job**

Add this JSX before the closing `</div>` of the App component (before the final return's closing tag):

```typescript
{deleteConfirmJobId !== null && (
  <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
    <div style={{ backgroundColor: 'white', padding: '20px', borderRadius: '8px', maxWidth: '400px' }}>
      <h3>Delete Job?</h3>
      <p>Are you sure you want to delete this backtest job? This action cannot be undone.</p>
      <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
        <button onClick={() => setDeleteConfirmJobId(null)} disabled={isDeleting}>
          Cancel
        </button>
        <button
          onClick={() => handleDeleteJob(deleteConfirmJobId)}
          disabled={isDeleting}
          style={{ backgroundColor: '#ff6b6b', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer' }}
        >
          {isDeleting ? 'Deleting...' : 'Delete'}
        </button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 8: Add "Clear All" button and confirmation dialog**

Add this button in the header area (near where other action buttons are):

```typescript
<button
  onClick={() => setDeleteAllConfirm(true)}
  disabled={isDeleting || jobs.length === 0}
  style={{ padding: '8px 16px', backgroundColor: '#ff8c42', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
>
  Clear All History
</button>
```

Add the confirmation dialog for "Clear All" before the single-job confirmation dialog:

```typescript
{deleteAllConfirm && (
  <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
    <div style={{ backgroundColor: 'white', padding: '20px', borderRadius: '8px', maxWidth: '400px' }}>
      <h3>Clear All History?</h3>
      <p>Are you sure you want to delete ALL backtest jobs ({jobs.length} total)? This action cannot be undone.</p>
      <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
        <button onClick={() => setDeleteAllConfirm(false)} disabled={isDeleting}>
          Cancel
        </button>
        <button
          onClick={handleDeleteAllJobs}
          disabled={isDeleting}
          style={{ backgroundColor: '#ff6b6b', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer' }}
        >
          {isDeleting ? 'Deleting...' : 'Delete All'}
        </button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 9: Verify the app compiles**

Run: `cd web && npm run build`

Expected: Build succeeds with no errors

- [ ] **Step 10: Commit**

```bash
git add web/src/App.tsx
git commit -m "feat: add delete buttons and confirmation dialogs to job list UI"
```

---

## Task 5: Manual testing and verification

**Files:**
- None (testing only)

- [ ] **Step 1: Start the backend server**

Run: `python server/main.py`

Expected: Server starts on http://127.0.0.1:8000

- [ ] **Step 2: Start the frontend dev server**

In a new terminal, run: `cd web && npm run dev`

Expected: Frontend starts on http://localhost:5173

- [ ] **Step 3: Create a few test jobs**

In the web UI:
1. Create 3 backtest jobs with different symbols (e.g., 000001, 000002, 000003)
2. Wait for them to complete

Expected: Jobs appear in the job list

- [ ] **Step 4: Test single job deletion**

1. Click the "Delete" button on one of the jobs
2. Confirm the deletion in the dialog
3. Verify the job disappears from the list

Expected: Job is removed from the UI and database

- [ ] **Step 5: Test "Clear All" deletion**

1. Click the "Clear All History" button
2. Confirm the deletion in the dialog
3. Verify all jobs disappear

Expected: All jobs are removed, job list is empty

- [ ] **Step 6: Test API directly with curl**

Create a job, then delete it via API:

```bash
# Create a job
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"symbol":"000001","start":"20240101","end":"20240630","cash":100000,"use_market_filter":true,"risk_percent":0.95,"fast_ma":10,"slow_ma":20,"strategy_id":"swing_ma_boll","strategy_params":{}}'

# Note the job_id from the response, then delete it
curl -X DELETE http://127.0.0.1:8000/api/jobs/{job_id}

# Verify it's gone
curl http://127.0.0.1:8000/api/jobs
```

Expected: Job is deleted and no longer appears in the list

- [ ] **Step 7: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass, including the new delete tests

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "test: verify delete functionality works end-to-end"
```

---

## Summary

This plan adds complete delete functionality to the backtest history system:

1. **Backend database layer** — Two functions (`delete_job`, `delete_all_jobs`) that leverage SQLite CASCADE constraints
2. **API layer** — Two endpoints (`DELETE /api/jobs/{job_id}`, `DELETE /api/jobs`) with proper error handling
3. **Frontend API client** — Two functions to call the delete endpoints
4. **UI** — Delete buttons on each job with confirmation dialogs, plus a "Clear All" button with safety confirmation

All changes are minimal, focused, and follow the existing code patterns. The implementation uses the existing database schema without modifications (CASCADE delete already configured).

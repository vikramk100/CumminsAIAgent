# Frontend–Backend Connection & Debugging

## How they’re connected

| Layer    | URL / role |
|----------|------------|
| **Frontend** | `http://localhost:8080/index.html` (UI5 app) |
| **Backend**  | `http://localhost:8000` (FastAPI) |

On load, the frontend:

1. Reads **API base** from (in order):
   - Query: `?apiBase=http://localhost:8000`
   - LocalStorage key `API_BASE`
   - Default: `http://localhost:8000`
2. Reads **order ID** from:
   - Query: `?orderId=WO-10000`
   - Hash: `#/WO-10000`
   - Default: `WO-10000`
3. Calls: **`GET {apiBase}/api/v1/dispatch-brief/{orderId}`**
4. Renders Equipment, Insights, Preparation, Documentation from the JSON response.

When you check a tool, it calls: **`POST {apiBase}/api/v1/audit-trail`**.

So **yes, the backend is wired to the frontend** via these two endpoints. If you see no data, the request is failing, slow, or returning something the UI doesn’t understand.

---

## What to check in the app

After the recent changes you should see:

- A **blue info bar** at the top: `API: WO-10000 → http://localhost:8000` (or whatever order/base is used).
- **“Loading dispatch brief...”** while the request is in progress.
- If the request fails, a **red error bar** with the message (e.g. `Failed to fetch` or `API error 404: ...`).

If the blue bar shows a different URL than where your backend runs, the frontend is not talking to your backend.

---

## Details that help debug

When things don’t work, please capture:

### 1. Browser Network tab

- Open DevTools (F12) → **Network**.
- Reload the page (or trigger the action again).
- Find the request to **`dispatch-brief`** (or `audit-trail` if the issue is on check).
- For that request, note:
  - **Request URL** (full URL).
  - **Status** (e.g. 200, 404, 500, or “(failed)” / CORS error).
  - **Response** body (or the error text) if you can copy it.

### 2. Browser Console tab

- Any **red errors** (especially about `fetch`, CORS, or “Failed to load”).
- Whether you see **“Failed to load dispatch brief.”** toast (that means the controller caught an error).

### 3. Backend

- Confirm the API is running: open **http://localhost:8000/docs** and try **GET /api/v1/dispatch-brief/WO-10000**.
- If you run the backend in a terminal, paste any **error or traceback** that appears when you load the page or trigger the action.

### 4. What you see in the UI

- Do you see the blue **“API: … → …”** bar?
- Do you see **“Loading dispatch brief...”** and then it never goes away?
- Do you see a **red error bar**? If yes, the exact text.
- Are sections (Equipment, Insights, Preparation, Documentation) empty even with no error?

With the **request URL**, **status**, **response/error**, and **console/backend errors**, we can pinpoint whether the problem is backend down, wrong URL, CORS, or response format.

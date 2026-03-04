# AI Agent (Gemini 2.5 Flash)

Simple chat frontend and Python backend using the Gemini 2.5 Flash API.
Note: I had it working on Python 3.11 but failing on Python 3.14
## Setup

1. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure `.env` contains your Gemini API key:
   ```
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```

## Run

From the `CumminsAIAgent` folder:

```bash
python server.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser to use the chat.

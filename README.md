# 60-Day Dopamine Sprint

## Run locally
    python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    python app.py        # open http://127.0.0.1:5000
First login creates your account; no one else can sign up after that.

## Deploy on PythonAnywhere (free)
1. Upload this folder to `/home/<you>/dopamine-sprint` (Files tab, or `git clone`).
2. Web tab > Add a new web app > Manual configuration > pick your Python version.
3. In the Bash console: `pip install --user Flask` (skip if the default Flask is new enough).
4. Edit the WSGI file (link on Web tab) and replace its contents with:

       import sys, os
       sys.path.insert(0, '/home/<you>/dopamine-sprint')
       os.environ['SECRET_KEY'] = 'put-a-long-random-string-here'
       from app import app as application

5. Hit Reload. Visit `<you>.pythonanywhere.com`.
6. Free accounts need a click on "Run until 3 months from today" on the Web tab every 3 months.

Day rollover uses IST. Change with the `TZ_OFFSET_MIN` env var (e.g. 0 for UTC).

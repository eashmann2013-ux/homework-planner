# Homework Planner

A small website that checks your three teacher pages and shows you what's
due, sorted into Math, Science, and Language Arts.

- **Language Arts (Mr. Greene)** — reads the dated homework list directly.
- **Science (Dalvand)** — reads the dated homework list and finds "Due:" dates.
- **Math (Larcher)** — follows the link to the homework Google Doc and reads
  it for dated entries. This one is the least predictable, since it depends
  on your teacher's doc formatting — see "About the Math parser" below.

It re-checks all three sites automatically every time you open the page
(and caches for 5 minutes so refreshing repeatedly doesn't hammer the
sites). There's also a manual **Refresh** button.

## Try it on your computer first

You don't need to deploy it to check that it works.

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser. Do this before
deploying — it's much faster to fix anything here than on the live site.

## Putting it on a real, live URL (free)

This uses [Render](https://render.com), which has a free tier for exactly
this kind of small app — no credit card needed. The app will be reachable
from any device once it's up, including your phone.

**1. Put the code on GitHub**
- Create a free account at [github.com](https://github.com) if you don't
  have one.
- Create a new repository (call it `homework-planner`).
- Upload every file in this folder to that repository. (On the repo page,
  "Add file" → "Upload files" works fine — drag the whole folder in.)

**2. Create a Render account**
- Go to [render.com](https://render.com) and sign up (you can use your
  GitHub account to sign in, which also makes step 3 easier).

**3. Create the web service**
- In the Render dashboard, click **New** → **Web Service**.
- Connect your GitHub account if prompted, then select your
  `homework-planner` repository.
- Render should auto-detect it's a Python app. Confirm these settings:
  - **Build Command:** `pip install -r requirements.txt`
  - **Start Command:** `gunicorn app:app`
  - **Instance Type:** Free
- Click **Create Web Service**.

**4. Wait for the deploy**
- Render will install everything and start the app — takes a couple of
  minutes. You'll see a live log on screen.
- When it says **Live**, you'll get a URL like
  `https://homework-planner-xxxx.onrender.com` — that's your real website.

**One thing to know:** on the free tier, the site "falls asleep" after 15
minutes with no visitors, so the very first visit after a while takes about
a minute to wake back up. After that it's instant. This doesn't cost
anything or lose any data — it's just Render's free-tier behavior.

## About the Math parser

Your Geometry teacher's page links out to a Google Doc rather than listing
homework on the page itself. The app follows that link and tries to find
dated entries inside the doc. Google Docs formatting varies a lot from
teacher to teacher, so:

- If it finds clear date patterns, it'll split the doc into dated entries
  like the other two subjects.
- If it can't confidently find dates, it falls back to showing the raw
  text of the document so nothing gets hidden — just less neatly organized.

If Math entries look off once it's live, tell me what the doc actually
looks like and I can tune `scraper.py`'s `scrape_math()` function to match.

## Project files

```
app.py              Flask server — routes and caching
scraper.py           Fetches and parses the three teacher sites
templates/index.html  Page layout
static/style.css      Styling
static/script.js      Tab switching, today/upcoming sorting
test_parsers.py       Checks the Language Arts / Science parsing logic
requirements.txt      Python dependencies
Procfile              Tells Render how to start the app
```

## If a site changes format

Teachers sometimes restructure their pages mid-year. If a subject stops
showing homework, the app won't crash — it shows a message explaining it
couldn't read that site rather than showing nothing. Send me the new page
and I'll update the parser for it.

# Close Encounters of a Python Kind

This repository contains the code for a simple web application built using Python and Flask, which provides a platform to display a terminal based game I built with my team during a course ran by Code Nation in 2023. The resulting web app can be reached at [https://alien.njtd.xyz](https://alien.njtd.xyz).

## pyxterm.js

To build this website containing a terminal able to run the python code, I first started by looking at [pyxtermjs](https://github.com/cs01/pyxtermjs) - A fully functional terminal in your browser - and adapted it to suit my needs.

## From this...

![screenshot](https://github.com/cs01/pyxterm.js/raw/master/pyxtermjs.gif)

## To this...

![screenshot](./images/screenshot.png)

## Installation

### Clone & Run Locally

This code is able to be run locally if you want to use it to host your own web app featuring python code that you want to be displayed in a 'terminal'.
Simply follow the steps below and edit the appropriate files to include your own code.

Clone this repository, enter the newly created directory.

```bash
> git clone https://github.com/NathanJohnNJ/closeEncountersOfAPythonKind.git
> cd closeEncountersOfAPythonKind
```

Create and activate a new virtual environment.

```bash
> python3 -m venv .env
> source .env/bin/activate
```

From within the virtual environment, run the following:

```bash
> python3 -m pip install -r requirements.txt
> python3 main.py
```

## Deploying to Render

This project requires a persistent backend (Flask + Flask-SocketIO) that maintains WebSocket connections and spawns a PTY for each browser session. Static hosts (GitHub Pages, Vercel static sites) cannot run the long-lived process this app needs — use a full hosting service such as Render, Railway, Fly.io, or Heroku.

I prepared a simple `render.yaml` and a `Procfile` so you can deploy to Render with automatic builds.

### Quick Render UI steps

1. Push your repository to GitHub (if not already).
2. Go to [https://dashboard.render.com](https://dashboard.render.com) and create a new Web Service.
3. Connect your GitHub repo, choose the `main` branch (or the branch you pushed), and Render will read `render.yaml` if present.
4. Build command: `pip install -r requirements.txt` (this is set in `render.yaml`).
5. Start command: `python main.py --host 0.0.0.0 --port $PORT` (also in `render.yaml` / `Procfile`).
6. Deploy and watch the build logs; once live the service URL will host the app and the web terminal will connect to the backend.

### Notes & troubleshooting

- Ensure `requirements.txt` contains `eventlet` so Flask-SocketIO can use WebSockets on Render.
- If you see Socket.IO connection errors, check the Render service logs for errors and confirm the service is listening on the `$PORT` environment variable.

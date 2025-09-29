Django on Vercel (serverless shim)
=================================

This folder contains a minimal serverless shim to run the Django WSGI app on Vercel.

Files added:
- `api/django.py` - Vercel Python function that bootstraps Django and uses `awsgi` to forward requests to the WSGI app.
- `vercel.json` - Routes `/api/*` to the serverless function (project root is this `kissanmart` folder).

Quick steps
-----------
1. Add `awsgi` to `kissanmart/requirements.txt` (already added).
2. Set environment variables in Vercel (DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS, DATABASE_URL, etc.).
3. Deploy the project to Vercel. API requests under `/api/` will be handled by Django.

Note: When creating the Vercel project, set the "Project Root" to the `kissanmart` folder so Vercel builds the backend correctly.

Limitations & caveats
---------------------
- Cold starts: serverless functions may be slower on the first request.
- Filesystem is ephemeral: use external storage (S3) for media/uploads.
- Database connections should be suitable for serverless workloads (use a managed database with connection pooling).
- Large dependency bundles may hit Vercel size limits; if so, consider hosting Django on a container-friendly platform and keep frontend on Vercel.

Function timeout
----------------
`vercel.json` includes a `functions` entry that sets `maxDuration` to 30 seconds for `api/django.py`. Increase this if you expect longer-running requests, but avoid very long sync requests in serverless functions.

If you prefer a long-running process with Gunicorn and WhiteNoise (simpler for Django), deploy using Docker/Heroku/Render instead.

Quick local test (recommended):

```powershell
# from repo root
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r kissanmart/requirements.txt
cd kissanmart
python manage.py migrate
python manage.py runserver
```

Note: The backend now allows CORS from https://kissanmart-frontend.vercel.app (see `kissanmart/settings.py`).


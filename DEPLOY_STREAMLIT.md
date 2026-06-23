# Deploying to Streamlit Cloud (GitHub)

This repository can be deployed to Streamlit Cloud directly from GitHub. Follow these steps:

1. Commit & push this repository to GitHub (create a new repo and push all files).

2. On Streamlit Cloud (https://streamlit.io/cloud):
   - Sign in with your GitHub account.
   - Click "New app" → select the GitHub repo and branch.
   - Set the `Main file` to `src/app.py`.
   - Optionally set advanced settings (port, secrets). Streamlit Cloud will use the `requirements.txt` to install packages.

3. Environment / RDKit note:
   - RDKit is not reliably installable via `pip` in Streamlit Cloud. If you need full RDKit support, deploy using Docker (see below) or a custom VM with Conda.
   - This app includes a runtime fallback when RDKit is not available (the features calculator returns a zero-filled vector), so the UI and basic functionality will still work on Streamlit Cloud without RDKit.

4. Secrets and credentials:
   - To secure the app, set `LOGIN_USERNAME` and `LOGIN_PASSWORD_HASH` as secrets in Streamlit Cloud (App settings → Secrets):
     - `LOGIN_USERNAME`: your admin username
     - `LOGIN_PASSWORD_HASH`: the salted PBKDF2 hash (format `salthex:hashhex`).
   - You can generate a hash locally using `scripts/generate_login_hash.py` and paste it into Streamlit Cloud secrets.

5. Troubleshooting:
   - If dependencies fail to install, check the build logs in Streamlit Cloud. For large binary packages (RDKit), use Docker.

Optional: Docker deployment (recommended for RDKit)
- Use the provided `Dockerfile` (not included) to create a container with Miniconda + RDKit from conda-forge. If you want this, request `docker` and I'll add a tested `Dockerfile` + `docker-compose.yml`.


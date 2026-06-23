# Push repository to GitHub and enable CI to publish Docker image

1) Create a new GitHub repository (on github.com) and follow the instructions to push your local repo. Example commands:

```bash
# from repo root
git init
git add .
git commit -m "Initial commit: ToxPredict"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

2) The workflow `.github/workflows/docker-publish.yml` will run on pushes to `main` and build/publish a Docker image to GitHub Container Registry at:

```
ghcr.io/<your-username>/toxpredict:latest
```

3) Notes and secrets
- The workflow uses the automatically provided `GITHUB_TOKEN` to authenticate with GHCR; no additional secrets are required for GHCR publishing.
- If you prefer Docker Hub instead, create a Docker Hub access token and add the following repository secrets in GitHub Settings → Secrets → Actions:
  - `DOCKERHUB_USERNAME` — your Docker Hub username
  - `DOCKERHUB_TOKEN` — your Docker Hub access token

4) Verify
- After pushing to `main`, open the Actions tab on GitHub to watch the build.
- Check Packages → Container registry on GitHub to see pushed images.

5) Streamlit Cloud
- If you want to deploy the app via Streamlit Cloud from GitHub, follow the steps in `DEPLOY_STREAMLIT.md`.


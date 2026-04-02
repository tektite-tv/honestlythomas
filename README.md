# Honestly Thomas Blog Template

A static black-and-white Courier New blog starter for GitHub Pages.

## What it does

- Loads generated post data from `/data/posts.json`
- Supports source posts in `/posts` as `.md`, `.txt`, and `.html`
- Provides URL-based search using `?q=`
- Provides post pages using `?post=`
- Provides basic pagination using `?page=`
- Uses a GitHub Actions workflow to rebuild the manifest when files in `/posts` change

## Setup

1. Put these files in your GitHub Pages repository.
2. Make sure GitHub Actions are enabled for the repo.
3. Push to the `main` branch.
4. Wait for the workflow to generate `data/posts.json`.
5. Open your GitHub Pages URL.

## Notes

GitHub Pages cannot list folder contents on its own in the browser. That is why the workflow generates `/data/posts.json`.

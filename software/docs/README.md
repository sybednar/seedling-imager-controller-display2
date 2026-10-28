# Site setup

This folder is a ready-to-deploy Jekyll site for GitHub Pages — no build
step needed on your end, GitHub builds it automatically.

## 1. Add it to your repo

Copy everything in this folder into a `docs/` directory at the root of
`ArabidopsisAnalysisV2`:

```
ArabidopsisAnalysisV2/
  docs/
    _config.yml
    _layouts/
    index.html
    changelog.html
    docs/
      install.html
      training.html
      architecture.html
    assets/
```

(Yes, there's a `docs/docs/` nesting — the inner `docs/` holds the doc
pages, the outer one is the Pages source root. Rename either if it bothers
you, just update the links in `index.html`/`_layouts/default.html` to match.)

## 2. Turn on Pages

In the repo: **Settings → Pages → Build and deployment → Source**, choose
**Deploy from a branch**, then branch `main` (or whichever), folder `/docs`.

Save. The site goes live at:

```
https://calvinyong1.github.io/ArabidopsisAnalysisV2/
```

usually within a minute or two.

## 3. Swap in your real docs

The three doc pages (`install.html`, `training.html`, `architecture.html`)
and `changelog.html` currently hold **hand-written summaries**, not the full
text of `WSL_INSTALL.md` / `TRAINING.md` / `CHANGES.md`. Two ways to fix
that:

- **Simplest:** paste the real markdown content into each page, below the
  front matter (the `---` block at the top). Jekyll renders GitHub-flavored
  markdown automatically.
- **Stay in sync automatically:** copy `WSL_INSTALL.md`, `TRAINING.md`, and
  `CHANGES.md` into `docs/` (the inner one) and replace each stub page's
  body with:

  ```liquid
  {% include_relative WSL_INSTALL.md %}
  ```

  (swap the filename per page). Now editing the root-level `.md` files and
  re-copying them is the only sync step.

## 4. Update the repo link

`_config.yml` has `repository: calvinyong1/ArabidopsisAnalysisV2` — update
if the repo ever moves or is renamed.

## Local preview (optional)

If you want to preview before pushing:

```bash
gem install bundler jekyll
bundle init
bundle add jekyll
bundle exec jekyll serve --source docs --destination docs/_site
```

Then open `http://localhost:4000/ArabidopsisAnalysisV2/`.

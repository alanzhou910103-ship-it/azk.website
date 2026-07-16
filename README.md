# int-rock website

Hugo static website for [int-rock.com](https://int-rock.com). The `main` branch deploys to GitHub Pages through GitHub Actions.

## Day-to-day updates

- Product content: `content/products/<sku>.md`
- Homepage content: `content/_index.md`
- Images: `static/images/<sku>/`
- Theme templates: `themes/azk/layouts/`
- Theme styling: `assets/css/style.css`
- Site-wide SEO and integrations: `config/_default/params.toml`

## Local preview

The deployment workflow uses Hugo Extended `0.162.1`. Install the same version locally before editing, then run:

```powershell
hugo server --disableFastRender
```

For a production-equivalent check, run:

```powershell
hugo --minify
```

Hugo writes the generated site to `public/`. Do not edit files in that folder manually.

## Release checklist

1. Confirm each new product page has a title, description, tagline, card image, hero image, specifications, and source-approved claims.
2. Run `hugo --minify` without errors and review the affected page locally.
3. Confirm image paths, metadata, and enquiry routing.
4. Commit source changes and push `main`; GitHub Actions publishes the result.

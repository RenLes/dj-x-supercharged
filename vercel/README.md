# Vercel OAuth fallback

A tiny static page that shows the OAuth `code` after Spotify or X redirects back. Use this when you can't run the loopback server (SSH session, container, Codespace, mobile).

## Deploy in 30 seconds

```bash
cd vercel
npx vercel deploy --prod
```

Vercel will give you a URL like `https://djx-callback-username.vercel.app`. Put that in your `.env`:

```
DJX_VERCEL_FALLBACK_URL=https://djx-callback-username.vercel.app
```

Then add the same URL **with `/callback` appended** as a redirect URI in:
- [Spotify Dashboard](https://developer.spotify.com/dashboard) → your app → Settings → Redirect URIs
- [X Developer Portal](https://developer.x.com/portal/dashboard) → your app → User authentication settings → Callback URI

Set:
```
SPOTIFY_REDIRECT_URI=https://djx-callback-username.vercel.app/callback
X_REDIRECT_URI=https://djx-callback-username.vercel.app/callback
```

When `djx auth …` runs, the page will display the `code`. Copy it and paste back into the terminal.

## Alternatives

Any static host works — Netlify, GitHub Pages, Cloudflare Pages. The page is one file with no build step.

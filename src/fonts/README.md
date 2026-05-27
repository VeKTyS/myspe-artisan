# MySpresso Artisan — bundled fonts

These TTFs are registered at app startup via `QFontDatabase.addApplicationFont()`
so the QSS family references resolve without OS-wide installation.

| File | Family name | Used for |
|---|---|---|
| `JetBrainsMono-Regular.ttf` | JetBrains Mono | Tabular numbers (timer, temperatures, weights) |
| `JetBrainsMono-Medium.ttf` | JetBrains Mono | Tabular numbers |
| `JetBrainsMono-Bold.ttf` | JetBrains Mono | Hero timer |

## Montserrat

Not currently bundled. The QSS uses the fallback chain:

```css
font-family: "Montserrat", -apple-system, "Segoe UI", sans-serif;
```

So:
- macOS → San Francisco (-apple-system)
- Windows → Segoe UI
- Linux → system default sans-serif

To bundle Montserrat properly, download the static TTFs from
<https://fonts.google.com/specimen/Montserrat> (download family, extract the
`static/` folder), then copy:

- `Montserrat-Regular.ttf`
- `Montserrat-Medium.ttf`
- `Montserrat-SemiBold.ttf`
- `Montserrat-Bold.ttf`

into this directory. The loader in `artisanlib/styles/__init__.py:_FONT_FILES`
already lists them — they'll register automatically once present.

Licensing : Montserrat is SIL Open Font License 1.1, JetBrains Mono is also OFL —
both can be bundled with GPL software.

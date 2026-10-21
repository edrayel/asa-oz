# Static JavaScript

## `altcha.min.js` — the ALTCHA widget

The proof-of-work captcha on the public forms. It is **vendored, not loaded
from a CDN**: the widget runs on this site, the challenge is issued by this
site, and the answer is checked by this site — so a visitor's data never
leaves the server and no third-party script is loaded.

- **Upstream:** <https://github.com/altcha-org/altcha> — MIT licensed
- **Version:** the `main` branch build fetched on 21 October 2026
- **Refresh it** with:

  ```bash
  curl -sL -o static/js/altcha.min.js \
    https://cdn.jsdelivr.net/gh/altcha-org/altcha/dist/main/altcha.min.js
  ```

  Check the diff before committing — the bundle is generated.

The server side lives in `captcha.py`: it issues the challenge
(`/captcha/challenge`) and verifies the answer with the `altcha` Python
package (see `requirements.txt`). The signing key is `CAPTCHA_HMAC_KEY`, or
a key derived from `SECRET_KEY` when that is not set — so a fresh
installation has nothing to configure.

The captcha is switched on with the `captcha_enabled` setting (Settings →
Spam protection) and applies to the public forms only: the contact form, the
feedback form, the story submission, the waitlist, the newsletter signup,
the member sign-up and the admin sign-in. Signed-in members are exempt —
they have already proved they are a person.

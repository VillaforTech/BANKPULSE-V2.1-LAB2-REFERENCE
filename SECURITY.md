# Security policy

This BankPulse Social Split development environment is built with synthetic data and local demo credentials. Do not reuse those credentials or expose the default stack to the public Internet.

- Never commit `.env`, access tokens, institutional credentials, certificates or real customer data.
- Report a suspected vulnerability privately to the repository owner instead of opening an issue with exploit details.
- Keep databases private; product traffic enters through the isolated Nginx edge.
- Store registry credentials in GitHub Actions Secrets.
- Treat the HMAC flow in `travel-benefits-api` as a demo credential mechanism, not production identity.
- Before a public deployment, add managed secrets, OIDC or mTLS where appropriate, image signing, dependency and container scanning, rate limits, audit retention and data-protection review.

Security improvements should include the threat, mitigation and a reproducible verification method.

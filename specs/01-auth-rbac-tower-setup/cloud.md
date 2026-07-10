# Module 1 — Auth, RBAC & Tower/Complex Setup: Cloud/DevOps Notes

> Companion files: [`overview.md`](./overview.md) · [`frontend.md`](./frontend.md) · [`backend.md`](./backend.md)

Everything in `../06-cloud-devops.md` applies as-is (Secrets Manager for credentials, ECS
Fargate hosting, CloudWatch logging). Two things are specific to this module and not
covered in `06`:

- **JWT signing secret**: stored in Secrets Manager at `aavaas/{env}/jwt-signing-key`
  (HS256; a single FastAPI service verifies its own tokens, so no asymmetric keypair is
  needed for v1.0), injected into the ECS task definition exactly like the DB URL per `06`
  §3. Access tokens: 15-minute expiry. Rotation: quarterly, dual-key verification for a
  24-hour grace window (accept tokens signed by either the outgoing or incoming secret)
  so in-flight sessions don't get logged out mid-rotation.
- **Refresh token storage**: refresh tokens are opaque random 256-bit values (not JWTs),
  stored **hashed** (SHA-256) in the `refresh_tokens` table so a DB read alone can't be
  replayed as a valid token. 30-day expiry, single-use with rotation on every
  `/auth/refresh` call (reuse of an already-rotated token revokes the entire token family
  for that user — theft-detection pattern). Password reset and explicit logout revoke all
  of a user's refresh tokens; a role/permission change does **not** force revocation —
  the 15-minute access-token TTL is the accepted bound on how stale a permission set can be.

Everything else (RDS, ECS, CI/CD, observability) is shared — see `../06-cloud-devops.md`.

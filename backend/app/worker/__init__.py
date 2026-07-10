"""Background-worker entrypoints — one process per `06-cloud-devops.md` §4 (a second ECS
Fargate service / Celery worker container sharing the API's DB and S3 access). Nothing in
`app.api`/`app.main` imports this package; it is only ever invoked as `python -m app.worker.*`.
"""

# Aavaas — Infrastructure (Terraform)

All-AWS infrastructure for Aavaas, implementing `specs/06-cloud-devops.md` (shared
cloud/devops plan) and the module-1-specific notes in
`specs/01-auth-rbac-tower-setup/cloud.md` (JWT signing secret path/rotation).

## Assumptions

- **IaC tool: Terraform.** No IaC tool is mandated by the specs; Terraform is used
  here because it's cloud-portable and doesn't force a CDK-language choice on the
  backend/frontend teams working in parallel.
- **Local state, for now.** Every environment's `main.tf` has a `# TODO: replace with
  S3+DynamoDB remote state backend before first real deploy` marker with a
  commented-out example `backend "s3" {}` block. No remote-state bucket has been
  provisioned — do that (once, by hand or via a small bootstrap stack) before any
  team member runs a real `apply`, then uncomment/fill in the backend block and run
  `terraform init -migrate-state`.
- **No AWS credentials in this sandbox.** This repo was built and validated with
  *no* AWS credentials configured. Every command below is safe to run
  (`init -backend=false`, `fmt`, `validate`); **never run `terraform plan` or
  `terraform apply` without first configuring real AWS credentials and a real
  remote-state backend** — `plan`/`apply` need live AWS API access this sandbox
  does not have.
- **Frontend hosting = AWS Amplify** (per `06-cloud-devops.md` §6), not Terraform-
  managed here. Connecting the Amplify app to the frontend repo/branch is a small
  one-time console (or `aws_amplify_app`/`aws_amplify_branch`) step, deliberately
  left out of this module list (the task's Step 2 module list is `vpc, rds,
  ecs-service, alb, s3, secrets, sqs, cloudwatch, waf` — no `amplify` module). The
  alternate "Next.js as its own ECS/Fargate service + CloudFront" path from §6 is
  captured only as a commented-out example inside
  `modules/ecs-service/main.tf` for future use, not built out.
- **RDS master password is manually seeded, not Terraform-generated.** See
  "Secrets that must be manually seeded" below.

## Layout

```
infra/
  modules/
    vpc/           public + private subnets, NAT, routing per env
    rds/           Postgres 16 instance, subnet group, security group, parameter group
    secrets/       Terraform-managed secrets (DB URL, S3 bucket name, SQS queue URLs)
    ecs-service/   generic Fargate service (used for both the API and the worker)
    alb/           ALB + HTTPS listener + API target group
    s3/            aavaas-{env}-files bucket
    sqs/           billing-cycle-jobs / report-export-jobs / special-collection-jobs queues (+ DLQs)
    cloudwatch/    log groups + alarms
    waf/           WAFv2 web ACL (rate limit + AWS managed rule sets) on the ALB
  environments/
    dev/           terraform.tfvars sized per 06-cloud-devops.md §1 (db.t4g.micro, 1 task)
    staging/       db.t4g.small, single-AZ default (Multi-AZ parameterized), 1 task
    prod/          db.r6g.large, Multi-AZ REQUIRED (enforced via variable validation),
                   35-day backups, deletion protection on, 2+ tasks
```

Each environment directory wires the modules together with sizing specific to that
environment; `prod/variables.tf` additionally enforces the "required, not optional"
settings (Multi-AZ, deletion protection, 35-day backups, slow-query logging, min 2
ECS tasks, 100/200 min/max healthy percent) via Terraform variable `validation`
blocks, so a misconfigured prod `terraform.tfvars` fails fast.

## Running Terraform

Per environment (`dev`, `staging`, or `prod`):

```sh
cd "infra/environments/<env>"
terraform init -backend=false   # -backend=false: no remote state configured yet (see TODO above)
terraform fmt -recursive ..     # run from infra/ to format every module + environment at once
terraform validate
```

`terraform plan` / `terraform apply` are **not runnable in this sandbox** (no AWS
credentials configured) and were not attempted — only `fmt`/`validate` (syntax and
internal-consistency checks, no AWS API calls) were run during this build-out, and
all three environments passed cleanly.

## Secrets that must be manually seeded before first apply

These are **never committed** and are **not created by Terraform** — an operator
must create them in Secrets Manager out-of-band, before the first real `apply` for
a given environment, because `rds` and `ecs-service` reference them via
`data "aws_secretsmanager_secret_version"` (a read-only lookup):

```sh
# 1. RDS master password (used as the literal RDS master password at DB creation time)
aws secretsmanager create-secret \
  --name "aavaas/<env>/rds-master-password" \
  --secret-string "$(openssl rand -base64 32)"

# 2. Initial JWT signing key (HS256, per specs/01-auth-rbac-tower-setup/cloud.md).
#    JSON shape supports the dual-key 24h grace window used during quarterly rotation:
#    { "current": "<key>", "previous": "", "rotated_at": "<iso8601>" }.
#    "previous" starts empty; it's populated by the rotation runbook (not built here —
#    Module 1's backend/ops owns the actual rotation procedure) so tokens signed by
#    the outgoing key still verify for 24h after a rotation.
aws secretsmanager create-secret \
  --name "aavaas/<env>/jwt-signing-key" \
  --secret-string '{"current":"<generate-a-256-bit-random-value>","previous":"","rotated_at":""}'
```

All other Secrets Manager entries (`aavaas/{env}/db-url`, `aavaas/{env}/s3-bucket-name`,
`aavaas/{env}/sqs-queue-urls`) are created and populated **by Terraform itself** from
other modules' outputs (RDS endpoint, S3 bucket name, SQS queue URLs) — no manual
seeding needed for those.

## Shared infra that later modules will consume, not built here

- **SQS queues** (`billing-cycle-jobs`, `report-export-jobs`, `special-collection-jobs`)
  are provisioned now per `06-cloud-devops.md` §4 and
  `specs/04-special-collections-expenditure/cloud.md` ("SQS / async jobs"), but
  **no backend consumes any of them yet** — they sit idle until Module 3
  (Maintenance Billing), Module 4 (Special Collections/Expenditure), and Module 5
  (Reporting) land their respective worker application code, at which point each
  can start sending/receiving without any infra change. `special-collection-jobs`
  specifically backs Module 4's async due-generation path for special
  collections on towers with >300 active flats (same sync/async threshold logic
  as billing cycles) — that async path is explicitly deferred by Module 4's
  backend this round (it depends on Module 3), so this queue is provisioned but
  has no producer/consumer yet, same idle status as the other two.
- **Frontend CloudWatch log group** (`/aavaas/{env}/frontend`) is created as a
  placeholder/aggregation target only — Amplify Hosting manages its own build/SSR
  logs natively; this group only becomes useful if custom log forwarding from
  Amplify is added later.
- **ALB p95 latency alarm** is a single ALB-wide alarm at the "dashboard aggregate"
  budget (500ms, the common case) from `00-architecture-and-standards.md` §4 — a
  single ALB/target-group metric can't be split per route class (auth 300ms vs. CRUD
  200ms vs. report export up to 10s). Splitting alarms per route class would require
  separate target groups per route class, which is a deliberate follow-up, not done
  here.
- **ECS+CloudFront frontend path** (the alternative to Amplify from §6) is captured
  only as a commented-out example in `modules/ecs-service/main.tf`.
- **Module 4's S3 prefixes** (`expenditure-attachments/{tower_id}/{expenditure_id}/{filename}`
  and the reused `receipts/{tower_id}/{receipt_id}.pdf` prefix, per
  `specs/04-special-collections-expenditure/cloud.md` §S3) require **zero**
  changes to the `s3` module — same `aavaas-{env}-files` bucket, same
  encryption/versioning/lifecycle rules, no per-prefix Terraform resources.
  There's no existing per-module/per-prefix bucket-policy or scoped-IAM pattern
  in this codebase to extend; bucket access is granted per ECS service (api,
  worker), not per prefix — see the comment block at the top of
  `modules/s3/main.tf` for the full rationale.

## CI/CD

See `.github/workflows/backend-ci.yml` and `.github/workflows/frontend-ci.yml` at the
repo root. Gating per `06-cloud-devops.md` §7:

- PRs require passing lint/typecheck/tests (configure these as required status checks
  in GitHub branch protection settings — not expressible purely in the workflow YAML).
- `staging` auto-deploys on merge to `main`.
- `prod` deploy is a manual/tag-based promotion (`workflow_dispatch` or a `v*` tag)
  gated by a GitHub **Environment** named `production` with required reviewers —
  create that Environment and add reviewers once in the repo's Settings → Environments
  (also not expressible purely in YAML).
- Both workflows expect an OIDC deploy role per environment
  (`AWS_DEPLOY_ROLE_ARN_STAGING` / `AWS_DEPLOY_ROLE_ARN_PROD` repo/environment
  secrets) rather than long-lived AWS access keys.

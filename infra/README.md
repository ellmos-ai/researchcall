# Deploying the public dry-run demo

`deploy_demo_lambda.py` packages, deploys, and tears down `calle-demo-researchcall` --
an AWS Lambda Function URL running the same web interface `researchcall-web`
(`python -m researchcall.web.app`) runs locally, behind the `demo/lambda_entry.py`
Mangum adapter. See that script's own module docstring for the full detail
(live-path hardening, cost guard) -- this file is only the quickstart.

## What it is, and is not

It is a read-mostly showcase: a Lambda cold start turns on the workbench's own
built-in fixture tour -- "Test mode", the same one a visitor reaches with one
click of the on-page banner button (`researchcall/web/test_mode.py`) -- with a
fictional local-bus-service study already filled in, in English, across all
eight stations, so a judge sees an operable example the moment the page loads.

It is **not** capable of placing a real call. `DEMO_MODE=1` is set in the
Lambda's own environment and no `CALLE_API_KEY` is ever configured there --
the code-level guard in `researchcall/calls.py::LiveCallClient.__init__`
checks `DEMO_MODE` before its own api-key check and refuses unconditionally.
Proven in `tests/test_live_guard.py`. The web app this Lambda serves also has
no route that reaches `LiveCallClient` at all -- the only place it is built in
this codebase is `cli.py`'s `run-day --live`, which this Lambda never runs.

It is **ephemeral**: state resets whenever AWS recycles the execution
environment. This is a demo link, not a hosted product.

## Prerequisites

* An AWS profile with the permissions in
  `.../.HACKATHONS/2026-call-e/AWS-DEMO-SETUP.md`'s policy JSON (Lambda + IAM,
  scoped to `calle-demo-*` resources only), configured as `[calle-demo-deploy]`
  in `~/.aws/credentials` (or export `AWS_PROFILE=calle-demo-deploy` before
  running these commands).
* `pip install boto3` in whatever environment runs this script (not a runtime
  dependency of the deployed function itself -- see `PACKAGE_DEPENDENCIES` in
  the script).

## Quickstart

```bash
export AWS_PROFILE=calle-demo-deploy   # or via AWS_PROFILE in your shell config

python infra/deploy_demo_lambda.py package
python infra/deploy_demo_lambda.py create-role
python infra/deploy_demo_lambda.py deploy
python infra/deploy_demo_lambda.py enable-url
```

`enable-url` prints the public Function URL -- that is what goes into the
README's "Live demo" line and the DevPost submission.

## Tearing it down

```bash
python infra/deploy_demo_lambda.py teardown
```

Best-effort, not a transactional stack deletion (matches the roshambo/
ringedingeding precedent this script follows) -- verify in the AWS console
afterward that nothing `calle-demo-*` is still billable.

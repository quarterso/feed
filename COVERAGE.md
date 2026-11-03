# What the Quarter rulebook covers

Feed version 3, issued 2026-11-03. 121 rules for HTTP APIs across 40 services, and 35 rules for shell commands. The ratings of MCP server tools are in `RATINGS.md`.

Each rule asks a person before the call runs. No rule refuses a call, and your own rules always come first. Each rule names the public API documentation it is drawn from (`source` in `body.json`), and has a test with one call it must catch and one close call it must let through (`cases.json`).

HTTP rules apply in a Quarter gateway, to agents that reach APIs through it. Shell rules apply there too, and in `guard.py` for Claude Code and Cursor.

`guard.py` also applies the HTTP rules to API calls an agent makes itself:

- From the shell, with `curl`, `wget`, HTTPie (`http`, `https`, `xh`) or `gh api`. It reads the method, URL, query and body the way each tool sends them, including GraphQL queries sent with `gh api graphql`.
- Through an MCP tool whose input names a full URL and an HTTP method, such as a generic fetch tool.

It does not see calls made from inside a program, such as a Python script or a Node app. It does not see a URL or body held in a shell variable. When a call goes to a GraphQL endpoint that a rule covers and the guard cannot read the query, it asks, as `FORMAT.md` says.

## HTTP APIs

### Algolia

- A call that deletes an Algolia index.
- A call that empties an Algolia index, or deletes records by query.

### Auth0

- A call that deletes an Auth0 user, application or connection.

### AWS

- A call that terminates instances or deletes databases, volumes, snapshots, stacks or IAM identities.
- A call that deletes an S3 bucket.
- A call that deletes many S3 objects at once.

### Azure

- A call that deletes an Azure resource group and everything in it.
- A call that deletes an Azure resource.

### Cloudflare

- A call that deletes a Cloudflare zone or DNS record.
- A call that deletes a Worker, R2 bucket, D1 database or KV namespace.
- A call that runs SQL on D1 that drops or empties a table or deletes every row.
- A call that purges a zone's whole cache.

### Confluence

- A call that deletes a Confluence space.
- A call that deletes a Confluence page for good.

### Datadog

- A call that deletes a monitor, dashboard or key.
- A call that mutes alerts.

### DigitalOcean

- A call that deletes DigitalOcean droplets, databases, volumes, apps, clusters, snapshots or domains.

### Elasticsearch

- A call that deletes an index.
- A call that deletes documents by query, a snapshot or a data stream.

### Fly.io

- A call that deletes a Fly app, machine or volume.

### GitHub

- A call that deletes a GitHub repository or organization.
- A call that force-moves a branch or tag, which can drop commits.
- A call that deletes a branch or tag.
- A call that removes branch protection or a ruleset.
- A call that deletes a GitHub secret.
- A call that deletes a deploy key or SSH key.
- A call that removes a person from an organization, team or repository.
- A call that transfers a repository to another owner.
- A call that makes a repository public.
- A call that deletes a deployment environment and its secrets.
- A call that deletes a branch, branch protection, ruleset or environment, or archives a repository.

### GitLab

- A call that deletes a GitLab project or group.
- A call that deletes a branch or removes branch protection.
- A call that deletes a CI/CD variable.
- A call that removes a member, or deletes a user.
- A call that makes a project public.

### Google Cloud

- A call that deletes a Google Cloud project.
- A call that deletes a Cloud SQL instance, database or backup.
- A call that deletes a Cloud Storage bucket.
- A call that deletes a Compute Engine instance, disk, snapshot, image or network.
- A call that deletes a GKE cluster.
- A call that deletes a Firestore database or bulk-deletes its documents.
- A call that deletes a BigQuery dataset or table.
- A call that runs SQL that drops or empties a table or deletes every row.

### Google Workspace

- A call that deletes a Drive file for good, skipping the trash, or empties the trash.
- A call that shares a Drive file with anyone who has the link.
- A call that deletes email for good, skipping the trash.
- A call that deletes many emails for good, skipping the trash.
- A call that forwards a mailbox to another address.
- A call that adds a Gmail filter that forwards mail.
- A call that deletes a Workspace user or group, or makes someone an admin.

### Heroku

- A call that deletes a Heroku app, add-on (such as its database), space, pipeline or team.

### HubSpot

- A call that deletes a CRM record.
- A call that deletes CRM records in bulk, or erases a contact for good.

### Jira

- A call that deletes a Jira project.
- A call that deletes a Jira issue.
- A call that deletes up to 1,000 Jira issues at once.
- A call that deletes a Jira user.

### Kubernetes

- A call that deletes a Kubernetes namespace or persistent volume (and its data).
- A call that deletes a Kubernetes workload, or every pod, service, secret or config map in a namespace.
- A call that deletes a custom resource definition and every resource of that kind.

### Linear

- A call that deletes a Linear issue, project, team, document, initiative or file.
- A call that suspends a user, removes an integration or webhook, or deletes the organization.

### MongoDB Atlas

- A call that deletes an Atlas cluster, project or organization.
- A call that deletes an Atlas backup snapshot or backup schedule.

### Neon

- A call that deletes a Neon project, branch, database or snapshot.
- A call that restores a Neon branch over its current data.

### Netlify

- A call that deletes a Netlify site, deploy, database or DNS zone.
- A call that deletes a Netlify environment variable.

### Notion

- A call that moves a Notion page or database to the trash.

### Okta

- A call that deactivates or deletes an Okta user, or deletes a group or app.
- A call that deactivates an Okta user.

### PagerDuty

- A call that deletes a service, escalation policy, schedule or user.
- A call that changes many incidents at once, such as resolving them all.
- A call that starts a maintenance window, which silences alerts.

### Pinecone

- A call that deletes a Pinecone index or collection.
- A call that deletes every vector in a namespace.

### PlanetScale

- A call that deletes a PlanetScale database, branch or backup.

### Railway

- A call that deletes a Railway volume or its backups, or changes or restores backups.
- A call that deletes a Railway service, environment or deployment.
- A call that deletes a Railway project or workspace.
- A call that deletes a Railway domain, variable or plugin.
- A call that replaces every Railway variable in a service.
- A call that commits a Railway environment change that deletes a service, volume or bucket.

### Render

- A call that deletes a Render service, database, key value store, disk or environment group.
- A call that suspends a Render service or database.

### Salesforce

- A call that deletes Salesforce records.
- A call that starts a bulk job that deletes records.

### SendGrid

- A call that deletes every contact.
- A call that deletes an API key or contact list, or lets mail reach someone who unsubscribed.
- A call that schedules a marketing email to a whole list.

### Sentry

- A call that deletes a Sentry project or organization.

### Shopify

- A call that deletes a product, customer, order, collection or theme.
- A call that refunds or cancels an order.
- A call that runs a bulk operation that deletes, refunds or cancels.
- A call that deletes a product, customer, order, collection or theme, or refunds or cancels an order.

### Slack

- A call that archives or deletes a Slack channel.
- A call that removes a person from a channel or the workspace.
- A call that deletes a Slack file.

### Snowflake

- A call that runs SQL that drops or empties a table, schema, database or warehouse.

### Stripe

- A call that refunds a payment.
- A call that sends a payout or a transfer.
- A call that deletes a Stripe customer, product, connected account, coupon or webhook.
- A call that cancels a subscription.
- A call that voids an invoice or issues a credit note.

### Supabase

- A call that deletes a Supabase project or branch, or turns branching off.
- A call that pauses a Supabase project, resets a branch or restores a backup over the database.
- A call that runs SQL that drops or empties a table or deletes every row.
- A call that deletes or empties a Supabase storage bucket.

### Terraform Cloud

- A call that starts a destroy run.
- A call that deletes a Terraform Cloud workspace or organization.
- A call that deletes a Terraform Cloud workspace that manages no resources.

### Twilio

- A call that releases a phone number, or deletes an API key or recording.
- A call that closes a Twilio account.

### Vercel

- A call that deletes a Vercel project.
- A call that deletes a Vercel deployment.
- A call that removes a Vercel domain or environment variable.

## Shell commands

In any tool that runs a command, with any agent.

### Cloud CLIs

- A command that tears down cloud resources.

### Cloud storage CLIs

- A command that deletes files in cloud storage in bulk.

### Cloudflare

- A command that deletes a Worker, R2 bucket, D1 database, KV namespace or queue.

### DigitalOcean

- A command that deletes a DigitalOcean resource.

### Django

- A command that deletes every row in the database.

### Docker

- A command that deletes Docker volumes or every unused image.

### Firebase

- A command that deletes Firestore or Realtime Database data, functions or hosting.

### Fly.io

- A command that destroys a Fly app, volume or machine.

### Git

- A command that rewrites or deletes git history, or throws away uncommitted work.
- A command that rewrites history, deletes a remote branch or drops stashed work.

### GitHub CLI

- A command that deletes a secret, release or repository, or makes a repository public.

### HashiCorp Vault

- A command that destroys secrets in Vault for good.

### Heroku

- A command that destroys a Heroku app or add-on, or resets its database.

### Kubernetes

- A command that deletes OpenShift resources, drains a node or scales a workload to zero.

### Laravel

- A command that drops every table and rebuilds the database.

### Migration tools

- A command that rolls back every migration or drops the database.

### MongoDB

- A command that drops a MongoDB database or collection, or deletes an Atlas cluster.

### Neon and PlanetScale

- A command that deletes a Neon or PlanetScale database, branch or backup.

### Package registries

- A command that publishes a package, image or release, or deletes a repository.

### PostgreSQL and MySQL

- A command that drops a database or a user from the command line.

### Prisma

- A command that resets the database, deleting its data.

### Rails

- A command that drops or reloads the database, deleting its data.

### Railway

- A command that deletes a Railway project, service, volume or deployment.

### Redis

- A command that deletes every key in Redis.

### Shell

- A command that deletes a root, home or working directory.
- A command that formats or overwrites a disk.
- A command that runs a downloaded script straight in a shell.
- A command that deletes files across a whole disk or home directory, or wipes a disk.

### SQL

- A command that drops or empties a database table, or deletes every row.
- A command that empties a table, or changes every row of one.
- A command that drops a column, a user or a role.

### Stripe

- A command that moves money or deletes Stripe customers, products or subscriptions.

### Supabase

- A command that resets a remote Supabase database or deletes a project or branch.

### Terraform, OpenTofu and Pulumi

- A command that destroys infrastructure or deletes its state.

### Vercel and Netlify

- A command that deletes a Vercel project, deployment, domain or variable, or a Netlify site.

## Not covered yet

- AWS APIs that name the action in a header (DynamoDB and other JSON APIs, through `X-Amz-Target`). Rules match the host, path, query and body, not headers. The AWS command line rules cover them.
- Rolling a Stripe secret key. Stripe has no public API for it; it is done in the Dashboard.
- Resetting a Heroku Postgres database over HTTP. It goes through a separate Postgres API that is not publicly documented. `heroku pg:reset` is covered.
- Deleting one Notion block, one file, one object in a bucket, or one row through a REST API. Agents do these all the time, so a rule would ask too often to help.
- GitLab and Jira on your own servers. The rules name gitlab.com and atlassian.net; add your host to your own rules.

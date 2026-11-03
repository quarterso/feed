#!/usr/bin/env python3
"""Quarter guard: asks you before a coding agent runs a destructive command or API call.

A hook for Claude Code (PreToolUse) and Cursor (beforeShellExecution, beforeMCPExecution). It checks
each shell command and MCP tool call against the Quarter feed's rules and, on a match, makes the
agent ask you first. It never refuses anything on its own. Shell rules match the command text.
HTTP rules match the web calls a command makes with curl, wget, HTTPie or gh api, and MCP tools
that name a URL and a method. The rules are built in, so it works offline; a newer signed feed
replaces them once a day. Standard library only. Print the settings to add with:
python3 guard.py --settings [--host claude|cursor]
"""

import hashlib
import json
import os
import re
import shlex
import sys
import time
import urllib.parse
import urllib.request
from fnmatch import fnmatchcase
from pathlib import Path

FEED = os.environ.get("QUARTER_FEED", "https://quarterso.github.io/feed/feed.json")
FEED_KEY = os.environ.get("QUARTER_FEED_KEY", "ed25519-pub:37115bdfec3099c6a0391470c618d5a12466d10a7148b97451ea87d624183b20")  # Quarter's public feed key
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "quarter-guard" / "feed.json"
DAY = 86_400

BUILT_IN = {"version": 2, "rules": [
    {"tool": "*", "why": "deletes a root, home or working directory",
     "command": r"\brm\s+-\w*(rf|fr)\w*\s+(/\*?|~/?|\$HOME/?|\*|\.\.?/?)(\s|;|&|$)"},
    {"tool": "*", "why": "formats or overwrites a disk",
     "command": r"\bmkfs(\.\w+)?\s|\bdd\s[^;&|]*\bof=/dev/"},
    {"tool": "*", "why": "drops or empties a database table, or deletes every row",
     "command": r"\b(drop\s+(database|schema|table)|truncate\s+table)\s|\bdelete\s+from\s+[\w.]+\s*(;|$)"},
    {"tool": "*", "why": "rewrites or deletes git history, or throws away uncommitted work",
     "command": r"\bgit\s+push\b[^;&|]*(--force\b|\s-f\b|--mirror\b|--delete\b)|\bgit\s+reset\s+--hard\b"
                r"|\bgit\s+clean\s+-\w*f"},
    {"tool": "*", "why": "tears down cloud resources",
     "command": r"\b(terraform|pulumi|cdk)\s+destroy\b|\bkubectl\s+delete\b|\bhelm\s+(uninstall|delete)\b"
                r"|\baws\s+\S+\s+(delete|terminate)-|\baws\s+s3\s+(rm|rb)\b|\b(gcloud|az)\s[^;&|]*\sdelete\b"},
    {"tool": "*", "why": "publishes a package, image or release, or deletes a repository",
     "command": r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bdocker\s+push\b"
                r"|\bgh\s+(release\s+create|repo\s+delete)\b"},
    {"tool": "*", "why": "runs a downloaded script straight in a shell",
     "command": r"\b(curl|wget)\s[^|;&]*\|\s*(sudo\s+)?(ba|z)?sh\b"},
    {"tool": "*", "why": "empties a table, or changes every row of one",
     "command": r"\btruncate\s+(?!table\b)[\w.\x22]+\s*(;|$|'|\x22)"
                r"|\bupdate\s+[\w.\x22]+\s+set\b(?![^;]*\bwhere\b)[^;]*;"},
    {"tool": "*", "why": "drops a column, a user or a role",
     "command": r"\balter\s+table\s+[\w.\x22]+\s+drop\s+(column\s+)?(?!(constraint|index|default|not)\b)[\w\x22]+"
                r"|\bdrop\s+(user|role|owned\s+by)\s"},
    {"tool": "*", "why": "drops a database or a user from the command line",
     "command": r"\b(dropdb|dropuser)\s|\bmysqladmin\s[^;&|]*\bdrop\s|\bpg_dropcluster\s"},
    {"tool": "*", "why": "resets the database, deleting its data",
     "command": r"\bprisma\s+(migrate\s+reset\b|db\s+push\b[^;&|]*--(force-reset|accept-data-loss)\b)"},
    {"tool": "*", "why": "drops or reloads the database, deleting its data",
     "command": r"\b(rails|rake)\s+db:(drop|reset|purge|schema:load|structure:load|migrate:reset)\b"},
    {"tool": "*", "why": "deletes every row in the database",
     "command": r"\bmanage\.py\s+(flush|reset_db)\b"},
    {"tool": "*", "why": "drops every table and rebuilds the database",
     "command": r"\bartisan\s+(migrate:(fresh|reset|refresh)|db:wipe)\b"},
    {"tool": "*", "why": "rolls back every migration or drops the database",
     "command": r"\balembic\s+downgrade\s+base\b|\bknex\s+migrate:rollback\b[^;&|]*--all\b"
                r"|\bsequelize(-cli)?\s+db:drop\b"},
    {"tool": "*", "why": "deletes every key in Redis",
     "command": r"\b(redis|valkey)-cli\b[^;&|]*\bflush(all|db)\b"},
    {"tool": "*", "why": "drops a MongoDB database or collection, or deletes an Atlas cluster",
     "command": r"\bmongosh?\b[^|;&]*(\.dropDatabase\(|\.drop\(\)|\.deleteMany\(\s*\{\s*\}\s*\))"
                r"|\batlas\s+(clusters|projects)\s+delete\b"},
    {"tool": "*", "why": "deletes Firestore or Realtime Database data, functions or hosting",
     "command": r"\bfirebase\s+(firestore:delete|database:remove|functions:delete|hosting:disable)\b"},
    {"tool": "*", "why": "resets a remote Supabase database or deletes a project or branch",
     "command": r"\bsupabase\s+(db\s+reset\b[^;&|]*--(linked|db-url)\b|projects\s+delete\b|branches\s+delete\b)"},
    {"tool": "*", "why": "deletes Docker volumes or every unused image",
     "command": r"\bdocker\s+(system\s+prune\b[^;&|]*(\s-\w*a\w*|\s--all|\s--volumes)\b|volume\s+(rm|prune)\b)"
                r"|\bdocker[\s-]compose\s[^;&|]*\bdown\b[^;&|]*(\s-v\b|--volumes\b)"},
    {"tool": "*", "why": "deletes a Railway project, service, volume or deployment",
     "command": r"\brailway\s+(delete|down|(volume|service|bucket|environment|variables?)\s+(delete|rm|remove))\b"},
    {"tool": "*", "why": "deletes a Vercel project, deployment, domain or variable, or a Netlify site",
     "command": r"\bvercel\s+(remove|rm|(project|domains|env)\s+(rm|remove))\b"
                r"|\bnetlify\s+sites:delete\b"},
    {"tool": "*", "why": "destroys a Heroku app or add-on, or resets its database",
     "command": r"\bheroku\s+(apps:destroy|destroy|pg:reset|addons:destroy)\b"},
    {"tool": "*", "why": "destroys a Fly app, volume or machine",
     "command": r"\bfly(ctl)?\s+(apps\s+destroy|destroy|volumes?\s+(destroy|delete|rm)|machines?\s+(destroy|rm))\b"},
    {"tool": "*", "why": "deletes a Neon or PlanetScale database, branch or backup",
     "command": r"\bneonctl\s+(projects|branches|databases)\s+delete\b"
                r"|\bpscale\s+(database|branch|backup)\s+delete\b"},
    {"tool": "*", "why": "deletes a Worker, R2 bucket, D1 database, KV namespace or queue",
     "command": r"\bwrangler\s+(delete|r2\s+bucket\s+delete|d1\s+delete|kv\s+namespace\s+delete|queues\s+delete)\b"},
    {"tool": "*", "why": "deletes a DigitalOcean resource",
     "command": r"\bdoctl\s+(\S+\s+){1,3}(delete|rm)\b"},
    {"tool": "*", "why": "destroys infrastructure or deletes its state",
     "command": r"\bterraform\s+apply\b[^;&|]*\s-destroy\b"
                r"|\bterraform\s+(state\s+rm|workspace\s+delete)\b|\btofu\s+destroy\b"
                r"|\bpulumi\s+stack\s+(rm|remove|delete)\b"},
    {"tool": "*", "why": "rewrites history, deletes a remote branch or drops stashed work",
     "command": r"\bgit\s+(filter-branch|filter-repo)\b|\bgit\s+update-ref\s+-d\b"
                r"|\bgit\s+stash\s+clear\b|\bgit\s+push\s[^;&|]*\s(:[\w./-]+|\+[\w./:-]+)(\s|$)"},
    {"tool": "*", "why": "deletes a secret, release or repository, or makes a repository public",
     "command": r"\bgh\s+(secret\s+delete|release\s+delete|repo\s+archive)\b"
                r"|\bgh\s+repo\s+edit\b[^;&|]*--visibility[\s=]+public"
                r"|\bgh\s+api\b[^;&|]*(-X|--method)[\s=]*DELETE\b|\bglab\s+repo\s+delete\b"},
    {"tool": "*", "why": "deletes files in cloud storage in bulk",
     "command": r"\baws\s+s3\s+sync\b[^;&|]*--delete\b|\bgsutil\s+(-m\s+)?(rm\s+-\w*r|rb)\b"
                r"|\bgcloud\s+storage\s+rm\b|\brclone\s+(purge|delete)\b"},
    {"tool": "*", "why": "moves money or deletes Stripe customers, products or subscriptions",
     "command": r"\bstripe\s+((refunds|payouts|transfers)\s+create|(customers|products|coupons)\s+delete|subscriptions\s+cancel)\b"},
    {"tool": "*", "why": "deletes OpenShift resources, drains a node or scales a workload to zero",
     "command": r"\boc\s+delete\b|\bkubectl\s+drain\b|\bkubectl\s+scale\b[^;&|]*--replicas[=\s]+0\b"},
    {"tool": "*", "why": "destroys secrets in Vault for good",
     "command": r"\bvault\s+(kv\s+(destroy|metadata\s+delete)|secrets\s+disable)\b"},
    {"tool": "*", "why": "deletes files across a whole disk or home directory, or wipes a disk",
     "command": r"\bfind\s+(/|~|\$HOME)\s[^;&|]*-delete\b|\b(shred|wipefs)\s"},
]}

BUILT_IN["http"] = [
    {"id": "railway.volume", "host": "backboard.railway.*", "method": ["POST"],
     "path": "^/graphql/v2$",
     "graphql": ["volumeDelete", "volumeInstanceBackupDelete", "volumeInstanceBackupScheduleUpdate", "volumeInstanceBackupRestore"],
     "why": "deletes a Railway volume or its backups, or changes or restores backups"},
    {"id": "railway.service", "host": "backboard.railway.*", "method": ["POST"],
     "path": "^/graphql/v2$",
     "graphql": ["serviceDelete", "environmentDelete", "deploymentRemove"],
     "why": "deletes a Railway service, environment or deployment"},
    {"id": "railway.project", "host": "backboard.railway.*", "method": ["POST"],
     "path": "^/graphql/v2$",
     "graphql": ["projectDelete", "projectScheduleDelete", "projectScheduleDeleteForce", "workspaceDelete"],
     "why": "deletes a Railway project or workspace"},
    {"id": "railway.config", "host": "backboard.railway.*", "method": ["POST"],
     "path": "^/graphql/v2$",
     "graphql": ["customDomainDelete", "variableDelete", "pluginDelete"],
     "why": "deletes a Railway domain, variable or plugin"},
    {"id": "railway.variables-replace", "host": "backboard.railway.*", "method": ["POST"],
     "path": "^/graphql/v2$",
     "body": r"\breplace\W{0,3}:\s*true\b",
     "graphql": ["variableCollectionUpsert"],
     "why": "replaces every Railway variable in a service"},
    {"id": "railway.staged-delete", "host": "backboard.railway.*", "method": ["POST"],
     "path": "^/graphql/v2$",
     "body": r"\bisDeleted\W{0,3}:\s*true\b",
     "graphql": ["environmentPatchCommit", "environmentStageChanges"],
     "why": "commits a Railway environment change that deletes a service, volume or bucket"},
    {"id": "vercel.project", "host": "api.vercel.com", "method": ["DELETE"],
     "path": r"^/v\d+/projects/[^/]+$",
     "why": "deletes a Vercel project"},
    {"id": "vercel.deployment", "host": "api.vercel.com", "method": ["DELETE"],
     "path": r"^/v\d+/deployments(/[^/]+)?$",
     "why": "deletes a Vercel deployment"},
    {"id": "vercel.domain-env", "host": "api.vercel.com", "method": ["DELETE"],
     "path": r"^/v\d+/(domains/[^/]+|projects/[^/]+/env/[^/]+)$",
     "why": "removes a Vercel domain or environment variable"},
    {"id": "render.delete", "host": "api.render.com", "method": ["DELETE"],
     "path": "^/v1/(services|postgres|key-value|redis|disks|env-groups)/[^/]+$",
     "why": "deletes a Render service, database, key value store, disk or environment group"},
    {"id": "render.suspend", "host": "api.render.com", "method": ["POST"],
     "path": "^/v1/(services|postgres)/[^/]+/suspend$",
     "why": "suspends a Render service or database"},
    {"id": "fly.delete", "host": "api.machines.dev", "method": ["DELETE"],
     "path": "^/v1/apps/[^/]+(/(machines|volumes)/[^/]+)?$",
     "why": "deletes a Fly app, machine or volume"},
    {"id": "heroku.app", "host": "api.heroku.com", "method": ["DELETE"],
     "path": "^/(apps/[^/]+(/addons/[^/]+)?|spaces/[^/]+|pipelines/[^/]+|teams/[^/]+)$",
     "why": "deletes a Heroku app, add-on (such as its database), space, pipeline or team"},
    {"id": "netlify.site", "host": "api.netlify.com", "method": ["DELETE"],
     "path": "^/api/v1/(sites/[^/]+(/database(/.*)?)?|(sites/[^/]+/)?deploys/[^/]+|dns_zones/[^/]+)$",
     "why": "deletes a Netlify site, deploy, database or DNS zone"},
    {"id": "netlify.env", "host": "api.netlify.com", "method": ["DELETE"],
     "path": "^/api/v1/accounts/[^/]+/env/[^/]+$",
     "why": "deletes a Netlify environment variable"},
    {"id": "supabase.project", "host": "api.supabase.com", "method": ["DELETE"],
     "path": "^/v1/(projects/[^/]+(/branches)?|branches/[^/]+)$",
     "why": "deletes a Supabase project or branch, or turns branching off"},
    {"id": "supabase.reset", "host": "api.supabase.com", "method": ["POST"],
     "path": r"^/v1/(projects/[^/]+/(pause|database/backups/restore[\w-]*)|branches/[^/]+/reset)$",
     "why": "pauses a Supabase project, resets a branch or restores a backup over the database"},
    {"id": "supabase.sql", "host": "api.supabase.com", "method": ["POST"],
     "path": "^/v1/projects/[^/]+/database/query$",
     "body": r"\b(drop\s+(database|schema|table|warehouse)\s|truncate\s+(table\s+)?[\w.\x22]+)|\bdelete\s+from\s+[\w.\x22]+\s*(;|\\?\x22|$)",
     "why": "runs SQL that drops or empties a table or deletes every row"},
    {"id": "supabase.storage", "host": "*.supabase.co", "method": ["DELETE", "POST"],
     "path": "^/storage/v1/bucket/[^/]+(/empty)?$",
     "why": "deletes or empties a Supabase storage bucket"},
    {"id": "neon.delete", "host": "console.neon.tech", "method": ["DELETE"],
     "path": "^/api/v2/projects/[^/]+(/branches/[^/]+(/databases/[^/]+)?|/snapshots/[^/]+)?$",
     "why": "deletes a Neon project, branch, database or snapshot"},
    {"id": "neon.restore", "host": "console.neon.tech", "method": ["POST"],
     "path": "^/api/v2/projects/[^/]+/(branches|snapshots)/[^/]+/restore$",
     "why": "restores a Neon branch over its current data"},
    {"id": "planetscale.delete", "host": "api.planetscale.com", "method": ["DELETE"],
     "path": "^/v1/organizations/[^/]+/databases/[^/]+(/branches/[^/]+(/backups/[^/]+)?)?$",
     "why": "deletes a PlanetScale database, branch or backup"},
    {"id": "atlas.cluster", "host": "cloud.mongodb.com", "method": ["DELETE"],
     "path": "^/api/atlas/v2/(groups/[^/]+(/(clusters|flexClusters)/[^/]+)?|orgs/[^/]+)$",
     "why": "deletes an Atlas cluster, project or organization"},
    {"id": "atlas.backup", "host": "cloud.mongodb.com", "method": ["DELETE"],
     "path": "^/api/atlas/v2/groups/[^/]+/clusters/[^/]+/backup/(snapshots(/shardedCluster)?/[^/]+|schedule)$",
     "why": "deletes an Atlas backup snapshot or backup schedule"},
    {"id": "snowflake.sql", "host": "*.snowflakecomputing.com", "method": ["POST"],
     "path": "^/api/v2/statements/?$",
     "body": r"\b(drop\s+(database|schema|table|warehouse)\s|truncate\s+(table\s+)?[\w.\x22]+)|\bdelete\s+from\s+[\w.\x22]+\s*(;|\\?\x22|$)",
     "why": "runs SQL that drops or empties a table, schema, database or warehouse"},
    {"id": "aws.query-action", "host": "*.amazonaws.com", "method": ["POST", "GET"],
     "path": "^/?$",
     "body": r"(^|&)Action=(Terminate\w*|Delete(DB\w+|Volume|Snapshot|Vpc|Subnet|Stack|User|Role|AccessKey|LoadBalancer|SecurityGroup|KeyPair|Queue|Topic|CacheCluster|ReplicationGroup|HostedZone|NatGateway|LaunchTemplate)|DeregisterImage)(&|$)",
     "why": "terminates instances or deletes databases, volumes, snapshots, stacks or IAM identities"},
    {"id": "aws.query-action-url", "host": "*.amazonaws.com", "method": ["POST", "GET"],
     "path": "^/?$",
     "query": r"(^|&)Action=(Terminate\w*|Delete(DB\w+|Volume|Snapshot|Vpc|Subnet|Stack|User|Role|AccessKey|LoadBalancer|SecurityGroup|KeyPair|Queue|Topic|CacheCluster|ReplicationGroup|HostedZone|NatGateway|LaunchTemplate)|DeregisterImage)(&|$)",
     "why": "terminates instances or deletes databases, volumes, snapshots, stacks or IAM identities"},
    {"id": "aws.s3-bucket", "host": ["*.s3.amazonaws.com", "*.s3.*.amazonaws.com", "*.s3-*.amazonaws.com"], "method": ["DELETE"],
     "path": "^/?$",
     "why": "deletes an S3 bucket"},
    {"id": "aws.s3-bucket-path", "host": ["s3.amazonaws.com", "s3.*.amazonaws.com", "s3-*.amazonaws.com"], "method": ["DELETE"],
     "path": "^/[^/]+/?$",
     "why": "deletes an S3 bucket"},
    {"id": "aws.s3-objects", "host": ["*.amazonaws.com"], "method": ["POST"],
     "path": "^/[^/]*/?$",
     "query": "(^|&)delete(=|&|$)",
     "why": "deletes many S3 objects at once"},
    {"id": "gcp.project", "host": "cloudresourcemanager.googleapis.com", "method": ["DELETE"],
     "path": "^/v[13]/projects/[^/]+$",
     "why": "deletes a Google Cloud project"},
    {"id": "gcp.sql", "host": "sqladmin.googleapis.com", "method": ["DELETE"],
     "path": "^(/sql)?/v1(beta4)?/projects/[^/]+/instances/[^/]+(/(databases|backupRuns)/[^/]+)?$",
     "why": "deletes a Cloud SQL instance, database or backup"},
    {"id": "gcp.storage", "host": ["storage.googleapis.com", "www.googleapis.com"], "method": ["DELETE"],
     "path": "^/storage/v1/b/[^/]+$",
     "why": "deletes a Cloud Storage bucket"},
    {"id": "gcp.compute", "host": ["compute.googleapis.com", "www.googleapis.com"], "method": ["DELETE"],
     "path": "^/compute/(v1|beta)/projects/[^/]+/((zones|regions)/[^/]+/(instances|disks|instanceGroupManagers)|global/(snapshots|images|networks))/[^/]+$",
     "why": "deletes a Compute Engine instance, disk, snapshot, image or network"},
    {"id": "gcp.gke", "host": "container.googleapis.com", "method": ["DELETE"],
     "path": "^/v1(beta1)?/projects/[^/]+/(locations|zones)/[^/]+/clusters/[^/]+$",
     "why": "deletes a GKE cluster"},
    {"id": "gcp.firestore", "host": "firestore.googleapis.com", "method": ["DELETE", "POST"],
     "path": "^/v1/projects/[^/]+/databases/[^/:]+(:bulkDeleteDocuments)?$",
     "why": "deletes a Firestore database or bulk-deletes its documents"},
    {"id": "gcp.bigquery", "host": "bigquery.googleapis.com", "method": ["DELETE"],
     "path": "^/bigquery/v2/projects/[^/]+/datasets/[^/]+(/tables/[^/]+)?$",
     "why": "deletes a BigQuery dataset or table"},
    {"id": "gcp.bigquery-sql", "host": "bigquery.googleapis.com", "method": ["POST"],
     "path": "^/bigquery/v2/projects/[^/]+/(queries|jobs)$",
     "body": r"\b(drop\s+(database|schema|table|warehouse)\s|truncate\s+(table\s+)?[\w.\x22]+)|\bdelete\s+from\s+[\w.\x22]+\s*(;|\\?\x22|$)",
     "why": "runs SQL that drops or empties a table or deletes every row"},
    {"id": "azure.resource-group", "host": "management.azure.com", "method": ["DELETE"],
     "path": "^/subscriptions/[^/]+/resourcegroups/[^/]+$",
     "why": "deletes an Azure resource group and everything in it"},
    {"id": "azure.resource", "host": "management.azure.com", "method": ["DELETE"],
     "path": "^/subscriptions/[^/]+/resourcegroups/[^/]+/providers/.+$",
     "why": "deletes an Azure resource"},
    {"id": "cloudflare.zone", "host": "api.cloudflare.com", "method": ["DELETE"],
     "path": "^/client/v4/zones/[^/]+(/dns_records/[^/]+)?$",
     "why": "deletes a Cloudflare zone or DNS record"},
    {"id": "cloudflare.storage", "host": "api.cloudflare.com", "method": ["DELETE"],
     "path": "^/client/v4/accounts/[^/]+/(workers/scripts|r2/buckets|d1/database|storage/kv/namespaces)/[^/]+$",
     "why": "deletes a Worker, R2 bucket, D1 database or KV namespace"},
    {"id": "cloudflare.d1-sql", "host": "api.cloudflare.com", "method": ["POST"],
     "path": "^/client/v4/accounts/[^/]+/d1/database/[^/]+/(query|raw)$",
     "body": r"\b(drop\s+(database|schema|table|warehouse)\s|truncate\s+(table\s+)?[\w.\x22]+)|\bdelete\s+from\s+[\w.\x22]+\s*(;|\\?\x22|$)",
     "why": "runs SQL on D1 that drops or empties a table or deletes every row"},
    {"id": "cloudflare.purge", "host": "api.cloudflare.com", "method": ["POST"],
     "path": "^/client/v4/zones/[^/]+/purge_cache$",
     "body": r"\x22purge_everything\x22\s*:\s*true",
     "why": "purges a zone's whole cache"},
    {"id": "digitalocean.delete", "host": "api.digitalocean.com", "method": ["DELETE"],
     "path": "^/v2/((droplets|databases|volumes|apps|projects|snapshots|domains|images)(/[^/]+)?|kubernetes/clusters/[^/]+|databases/[^/]+/dbs/[^/]+|(droplets|kubernetes/clusters)/[^/]+/destroy_with_associated_resources(/.*)?)$",
     "why": "deletes DigitalOcean droplets, databases, volumes, apps, clusters, snapshots or domains"},
    {"id": "kubernetes.namespace", "host": ["*"], "method": ["DELETE"],
     "path": "^/api/v1/(namespaces/[^/]+|persistentvolumes(/[^/]+)?|namespaces/[^/]+/persistentvolumeclaims(/[^/]+)?)$",
     "why": "deletes a Kubernetes namespace or persistent volume (and its data)"},
    {"id": "kubernetes.workloads", "host": ["*"], "method": ["DELETE"],
     "path": "^/apis/apps/v1/namespaces/[^/]+/(deployments|statefulsets|daemonsets)(/[^/]+)?$|^/api/v1/namespaces/[^/]+/(pods|services|secrets|configmaps)$",
     "why": "deletes a Kubernetes workload, or every pod, service, secret or config map in a namespace"},
    {"id": "kubernetes.crd", "host": ["*"], "method": ["DELETE"],
     "path": r"^/apis/apiextensions\.k8s\.io/v1/customresourcedefinitions(/[^/]+)?$",
     "why": "deletes a custom resource definition and every resource of that kind"},
    {"id": "terraform-cloud.destroy-run", "host": "app.terraform.io", "method": ["POST"],
     "path": "^/api/v2/runs$",
     "body": r"\x22is-destroy\x22\s*:\s*true",
     "why": "starts a destroy run"},
    {"id": "terraform-cloud.workspace", "host": "app.terraform.io", "method": ["DELETE"],
     "path": "^/api/v2/(workspaces/[^/]+|organizations/[^/]+(/workspaces/[^/]+)?)$",
     "why": "deletes a Terraform Cloud workspace or organization"},
    {"id": "terraform-cloud.safe-delete", "host": "app.terraform.io", "method": ["POST"],
     "path": "^/api/v2/(workspaces/[^/]+|organizations/[^/]+/workspaces/[^/]+)/actions/safe-delete$",
     "why": "deletes a Terraform Cloud workspace that manages no resources"},
    {"id": "github.repo", "host": "api.github.com", "method": ["DELETE"],
     "path": "^/(repos/[^/]+/[^/]+|orgs/[^/]+)$",
     "why": "deletes a GitHub repository or organization"},
    {"id": "github.force-ref", "host": "api.github.com", "method": ["PATCH"],
     "path": "^/repos/[^/]+/[^/]+/git/refs/.+$",
     "body": r"\x22force\x22\s*:\s*true",
     "why": "force-moves a branch or tag, which can drop commits"},
    {"id": "github.delete-ref", "host": "api.github.com", "method": ["DELETE"],
     "path": "^/repos/[^/]+/[^/]+/git/refs/.+$",
     "why": "deletes a branch or tag"},
    {"id": "github.protection", "host": "api.github.com", "method": ["DELETE"],
     "path": r"^/repos/[^/]+/[^/]+/branches/.+/protection(/.*)?$|^/(repos/[^/]+/[^/]+|orgs/[^/]+)/rulesets/\d+$",
     "why": "removes branch protection or a ruleset"},
    {"id": "github.secrets", "host": "api.github.com", "method": ["DELETE"],
     "path": "^/((repos/[^/]+/[^/]+|orgs/[^/]+)/(actions|dependabot|codespaces|agents)/secrets/[^/]+|repos/[^/]+/[^/]+/environments/[^/]+/secrets/[^/]+|user/codespaces/secrets/[^/]+)$",
     "why": "deletes a GitHub secret"},
    {"id": "github.keys", "host": "api.github.com", "method": ["DELETE"],
     "path": r"^/(repos/[^/]+/[^/]+/keys|user/(gpg_)?keys)/\d+$",
     "why": "deletes a deploy key or SSH key"},
    {"id": "github.members", "host": "api.github.com", "method": ["DELETE"],
     "path": "^/(orgs/[^/]+/(members|memberships|outside_collaborators)/[^/]+|orgs/[^/]+/teams/[^/]+/memberships/[^/]+|repos/[^/]+/[^/]+/collaborators/[^/]+)$",
     "why": "removes a person from an organization, team or repository"},
    {"id": "github.transfer", "host": "api.github.com", "method": ["POST"],
     "path": "^/repos/[^/]+/[^/]+/transfer$",
     "why": "transfers a repository to another owner"},
    {"id": "github.visibility", "host": "api.github.com", "method": ["PATCH"],
     "path": "^/repos/[^/]+/[^/]+$",
     "body": r"\x22visibility\x22\s*:\s*\x22public\x22|\x22private\x22\s*:\s*false",
     "why": "makes a repository public"},
    {"id": "github.environment", "host": "api.github.com", "method": ["DELETE"],
     "path": "^/repos/[^/]+/[^/]+/environments/[^/]+$",
     "why": "deletes a deployment environment and its secrets"},
    {"id": "github.graphql", "host": "api.github.com", "method": ["POST"],
     "path": "^/graphql$",
     "graphql": ["deleteRef", "deleteBranchProtectionRule", "deleteRepositoryRuleset", "deleteEnvironment", "archiveRepository"],
     "why": "deletes a branch, branch protection, ruleset or environment, or archives a repository"},
    {"id": "github.graphql-force", "host": "api.github.com", "method": ["POST"],
     "path": "^/graphql$",
     "body": r"\bforce\W{0,3}:\s*true\b",
     "graphql": ["updateRef", "updateRefs"],
     "why": "force-moves a branch or tag, which can drop commits"},
    {"id": "gitlab.project", "host": "gitlab.com", "method": ["DELETE"],
     "path": "^/api/v4/(projects|groups)/(?!.*/(members|variables|repository|protected_branches|hooks|issues|merge_requests|pipelines|jobs|deploy_keys|labels|milestones|environments|badges|share|fork|push_rule|access_requests|registry|packages|releases|snippets|wikis|boards|runners|integrations|services|deployments|uploads|avatar|pages|triggers|clusters)(/|$))[^/]+(/[^/]+)*$",
     "why": "deletes a GitLab project or group"},
    {"id": "gitlab.branches", "host": "gitlab.com", "method": ["DELETE"],
     "path": "^/api/v4/projects/.+/(protected_branches/[^/]+|repository/(branches/.+|merged_branches))$",
     "why": "deletes a branch or removes branch protection"},
    {"id": "gitlab.variables", "host": "gitlab.com", "method": ["DELETE"],
     "path": "^/api/v4/(projects|groups)/.+/variables/[^/]+$",
     "why": "deletes a CI/CD variable"},
    {"id": "gitlab.members", "host": "gitlab.com", "method": ["DELETE"],
     "path": r"^/api/v4/((projects|groups)/.+/members/\d+|users/\d+)$",
     "why": "removes a member, or deletes a user"},
    {"id": "gitlab.visibility", "host": "gitlab.com", "method": ["PUT"],
     "path": "^/api/v4/projects/[^/]+(/[^/]+)*$",
     "body": r"visibility\x22?\s*[:=]\s*\x22?public\b",
     "why": "makes a project public"},
    {"id": "stripe.refund", "host": "api.stripe.com", "method": ["POST"],
     "path": "^/v1/(refunds|charges/[^/]+/refunds?)$",
     "why": "refunds a payment"},
    {"id": "stripe.payout", "host": "api.stripe.com", "method": ["POST"],
     "path": "^/v1/(payouts|transfers)$",
     "why": "sends a payout or a transfer"},
    {"id": "stripe.delete", "host": "api.stripe.com", "method": ["DELETE"],
     "path": "^/v1/(customers|products|accounts|coupons|webhook_endpoints)/[^/]+$",
     "why": "deletes a Stripe customer, product, connected account, coupon or webhook"},
    {"id": "stripe.cancel", "host": "api.stripe.com", "method": ["DELETE"],
     "path": "^/v1/subscriptions/[^/]+$",
     "why": "cancels a subscription"},
    {"id": "stripe.void", "host": "api.stripe.com", "method": ["POST"],
     "path": "^/v1/(invoices/[^/]+/void|credit_notes)$",
     "why": "voids an invoice or issues a credit note"},
    {"id": "shopify.delete", "host": "*.myshopify.com", "method": ["POST"],
     "path": r"^/admin/api/[^/]+/graphql\.json$",
     "graphql": ["productDelete", "customerDelete", "orderDelete", "collectionDelete", "themeDelete"],
     "why": "deletes a product, customer, order, collection or theme"},
    {"id": "shopify.refund", "host": "*.myshopify.com", "method": ["POST"],
     "path": r"^/admin/api/[^/]+/graphql\.json$",
     "graphql": ["refundCreate", "orderCancel"],
     "why": "refunds or cancels an order"},
    {"id": "shopify.bulk", "host": "*.myshopify.com", "method": ["POST"],
     "path": r"^/admin/api/[^/]+/graphql\.json$",
     "body": r"\b(productDelete|customerDelete|orderDelete|collectionDelete|refundCreate|orderCancel)\b",
     "graphql": ["bulkOperationRunMutation"],
     "why": "runs a bulk operation that deletes, refunds or cancels"},
    {"id": "shopify.rest", "host": "*.myshopify.com", "method": ["DELETE", "POST"],
     "path": r"^/admin/(api/[^/]+/)?((products|customers|orders|custom_collections|smart_collections|themes)/\d+|orders/\d+/(refunds|cancel))\.json$",
     "why": "deletes a product, customer, order, collection or theme, or refunds or cancels an order"},
    {"id": "twilio.delete", "host": "api.twilio.com", "method": ["DELETE"],
     "path": r"^/2010-04-01/Accounts/[^/]+/(IncomingPhoneNumbers|Keys|Recordings)/[^/]+\.json$",
     "why": "releases a phone number, or deletes an API key or recording"},
    {"id": "twilio.close", "host": "api.twilio.com", "method": ["POST"],
     "path": r"^/2010-04-01/Accounts/[^/]+\.json$",
     "body": "(^|&)Status=(closed|suspended)(&|$)",
     "why": "closes a Twilio account"},
    {"id": "sendgrid.contacts", "host": "api.sendgrid.com", "method": ["DELETE"],
     "path": "^/v3/marketing/contacts$",
     "query": "(^|&)delete_all_contacts=true",
     "why": "deletes every contact"},
    {"id": "sendgrid.delete", "host": "api.sendgrid.com", "method": ["DELETE"],
     "path": "^/v3/(api_keys/[^/]+|marketing/lists/[^/]+|asm/suppressions/global/[^/]+)$",
     "why": "deletes an API key or contact list, or lets mail reach someone who unsubscribed"},
    {"id": "sendgrid.send", "host": "api.sendgrid.com", "method": ["PUT"],
     "path": "^/v3/marketing/singlesends/[^/]+/schedule$",
     "why": "schedules a marketing email to a whole list"},
    {"id": "slack.channel", "host": "slack.com", "method": ["*"],
     "path": r"^/api/(admin\.conversations\.(delete|archive)|conversations\.archive)$",
     "why": "archives or deletes a Slack channel"},
    {"id": "slack.user", "host": ["slack.com", "api.slack.com"], "method": ["*"],
     "path": r"^/api/(admin\.users\.remove|conversations\.kick)$|^/scim/v[12]/Users/[^/]+$",
     "why": "removes a person from a channel or the workspace"},
    {"id": "slack.files", "host": "slack.com", "method": ["*"],
     "path": r"^/api/files\.delete$",
     "why": "deletes a Slack file"},
    {"id": "linear.delete", "host": "api.linear.app", "method": ["POST"],
     "path": "^/graphql$",
     "graphql": ["issueDelete", "projectDelete", "teamDelete", "documentDelete", "initiativeDelete", "fileUploadDangerouslyDelete"],
     "why": "deletes a Linear issue, project, team, document, initiative or file"},
    {"id": "linear.org", "host": "api.linear.app", "method": ["POST"],
     "path": "^/graphql$",
     "graphql": ["organizationDelete", "userSuspend", "integrationDelete", "webhookDelete"],
     "why": "suspends a user, removes an integration or webhook, or deletes the organization"},
    {"id": "jira.project", "host": "*.atlassian.net", "method": ["DELETE"],
     "path": "^/rest/api/[23]/project/[^/]+$",
     "why": "deletes a Jira project"},
    {"id": "jira.project-async", "host": "*.atlassian.net", "method": ["POST"],
     "path": "^/rest/api/[23]/project/[^/]+/delete$",
     "why": "deletes a Jira project"},
    {"id": "jira.issue", "host": "*.atlassian.net", "method": ["DELETE"],
     "path": "^/rest/api/[23]/issue/[^/]+$",
     "why": "deletes a Jira issue"},
    {"id": "jira.bulk-delete", "host": "*.atlassian.net", "method": ["POST"],
     "path": "^/rest/api/3/bulk/issues/delete$",
     "why": "deletes up to 1,000 Jira issues at once"},
    {"id": "jira.user", "host": "*.atlassian.net", "method": ["DELETE"],
     "path": "^/rest/api/[23]/user$",
     "why": "deletes a Jira user"},
    {"id": "confluence.space", "host": "*.atlassian.net", "method": ["DELETE"],
     "path": "^/wiki/rest/api/space/[^/]+$",
     "why": "deletes a Confluence space"},
    {"id": "confluence.purge", "host": "*.atlassian.net", "method": ["DELETE"],
     "path": "^/wiki/api/v2/(pages|blogposts)/[^/]+$",
     "query": "(^|&)purge=true",
     "why": "deletes a Confluence page for good"},
    {"id": "notion.trash", "host": "api.notion.com", "method": ["PATCH"],
     "path": "^/v1/(pages|databases|data_sources)/[^/]+$",
     "body": r"\x22(in_trash|archived)\x22\s*:\s*true",
     "why": "moves a Notion page or database to the trash"},
    {"id": "google.drive-delete", "host": ["www.googleapis.com", "content.googleapis.com"], "method": ["DELETE"],
     "path": "^/drive/v[23]/files/[^/]+$",
     "why": "deletes a Drive file for good, skipping the trash, or empties the trash"},
    {"id": "google.drive-public", "host": ["www.googleapis.com", "content.googleapis.com"], "method": ["POST"],
     "path": "^/drive/v3/files/[^/]+/permissions$",
     "body": r"\x22type\x22\s*:\s*\x22anyone\x22",
     "why": "shares a Drive file with anyone who has the link"},
    {"id": "google.gmail-delete", "host": "gmail.googleapis.com", "method": ["DELETE"],
     "path": "^/gmail/v1/users/[^/]+/(messages|threads)/[^/]+$",
     "why": "deletes email for good, skipping the trash"},
    {"id": "google.gmail-batch-delete", "host": "gmail.googleapis.com", "method": ["POST"],
     "path": "^/gmail/v1/users/[^/]+/messages/batchDelete$",
     "why": "deletes many emails for good, skipping the trash"},
    {"id": "google.gmail-forward", "host": "gmail.googleapis.com", "method": ["POST", "PUT"],
     "path": "^/gmail/v1/users/[^/]+/settings/(forwardingAddresses|autoForwarding)$",
     "why": "forwards a mailbox to another address"},
    {"id": "google.gmail-filter", "host": "gmail.googleapis.com", "method": ["POST"],
     "path": "^/gmail/v1/users/[^/]+/settings/filters$",
     "body": r"\x22forward\x22\s*:",
     "why": "adds a Gmail filter that forwards mail"},
    {"id": "google.admin", "host": "admin.googleapis.com", "method": ["DELETE", "POST"],
     "path": "^/admin/directory/v1/((users|groups)/[^/]+|users/[^/]+/makeAdmin)$",
     "why": "deletes a Workspace user or group, or makes someone an admin"},
    {"id": "salesforce.delete", "host": ["*.my.salesforce.com", "*.salesforce.com"], "method": ["DELETE"],
     "path": r"^/services/data/v[\d.]+/(sobjects/[^/]+/[^/]+|composite/sobjects)$",
     "why": "deletes Salesforce records"},
    {"id": "salesforce.bulk-delete", "host": ["*.my.salesforce.com", "*.salesforce.com"], "method": ["POST"],
     "path": r"^/services/data/v[\d.]+/jobs/ingest/?$",
     "body": r"\x22operation\x22\s*:\s*\x22(delete|hardDelete)\x22",
     "why": "starts a bulk job that deletes records"},
    {"id": "hubspot.delete", "host": "api.hubapi.com", "method": ["DELETE"],
     "path": "^/crm/v3/objects/[^/]+/[^/]+$",
     "why": "deletes a CRM record"},
    {"id": "hubspot.bulk-delete", "host": "api.hubapi.com", "method": ["POST"],
     "path": "^/crm/v3/objects/[^/]+/(batch/archive|gdpr-delete)$",
     "why": "deletes CRM records in bulk, or erases a contact for good"},
    {"id": "datadog.delete", "host": ["api.datadoghq.com", "api.*.datadoghq.com", "api.datadoghq.eu", "api.ddog-gov.com"], "method": ["DELETE"],
     "path": "^/api/(v1/(monitor|dashboard)/[^/]+|v2/(api_keys|application_keys)/[^/]+)$",
     "why": "deletes a monitor, dashboard or key"},
    {"id": "datadog.mute", "host": ["api.datadoghq.com", "api.*.datadoghq.com", "api.datadoghq.eu", "api.ddog-gov.com"], "method": ["POST"],
     "path": "^/api/(v2/downtime|v1/monitor/[^/]+/mute)$",
     "why": "mutes alerts"},
    {"id": "pagerduty.delete", "host": "api.pagerduty.com", "method": ["DELETE"],
     "path": "^/(services|escalation_policies|schedules|users)/[^/]+$",
     "why": "deletes a service, escalation policy, schedule or user"},
    {"id": "pagerduty.bulk-resolve", "host": "api.pagerduty.com", "method": ["PUT"],
     "path": "^/incidents$",
     "why": "changes many incidents at once, such as resolving them all"},
    {"id": "pagerduty.maintenance", "host": "api.pagerduty.com", "method": ["POST"],
     "path": "^/maintenance_windows$",
     "why": "starts a maintenance window, which silences alerts"},
    {"id": "pinecone.index", "host": "api.pinecone.io", "method": ["DELETE"],
     "path": "^/(indexes|collections)/[^/]+$",
     "why": "deletes a Pinecone index or collection"},
    {"id": "pinecone.vectors", "host": "*.pinecone.io", "method": ["POST"],
     "path": "^/vectors/delete$",
     "body": r"\x22deleteAll\x22\s*:\s*true",
     "why": "deletes every vector in a namespace"},
    {"id": "algolia.index", "host": ["*.algolia.net", "*.algolianet.com"], "method": ["DELETE"],
     "path": "^/1/indexes/[^/]+$",
     "why": "deletes an Algolia index"},
    {"id": "algolia.clear", "host": ["*.algolia.net", "*.algolianet.com"], "method": ["POST"],
     "path": "^/1/indexes/[^/]+/(clear|deleteByQuery)$",
     "why": "empties an Algolia index, or deletes records by query"},
    {"id": "auth0.delete", "host": "*.auth0.com", "method": ["DELETE"],
     "path": "^/api/v2/(users|clients|connections)/[^/]+$",
     "why": "deletes an Auth0 user, application or connection"},
    {"id": "okta.delete", "host": ["*.okta.com", "*.oktapreview.com", "*.okta-emea.com"], "method": ["DELETE"],
     "path": "^/api/v1/(users|groups|apps)/[^/]+$",
     "why": "deactivates or deletes an Okta user, or deletes a group or app"},
    {"id": "okta.deactivate", "host": ["*.okta.com", "*.oktapreview.com", "*.okta-emea.com"], "method": ["POST"],
     "path": "^/api/v1/users/[^/]+/lifecycle/deactivate$",
     "why": "deactivates an Okta user"},
    {"id": "sentry.delete", "host": ["sentry.io", "*.sentry.io"], "method": ["DELETE"],
     "path": "^/api/0/(projects/[^/]+/[^/]+|organizations/[^/]+)/?$",
     "why": "deletes a Sentry project or organization"},
    {"id": "elasticsearch.index", "host": ["*.elastic-cloud.com", "*.cloud.es.io", "*.es.amazonaws.com", "*.aws.found.io"], "method": ["DELETE"],
     "path": "^/((?!_)[^/]+|_all)/?$",
     "why": "deletes an index"},
    {"id": "elasticsearch.bulk", "host": ["*"], "method": ["DELETE", "POST"],
     "path": "^/[^/]+/_delete_by_query$|^/_snapshot/[^/]+/[^/]+$|^/_data_stream/[^/]+$",
     "why": "deletes documents by query, a snapshot or a data stream"},
]


# Ed25519 verification (RFC 8032), the reference algorithm.
_p = 2**255 - 19
_q = 2**252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _add(P, Q):
    x1, y1, z1, t1 = P
    x2, y2, z2, t2 = Q
    a, b = (y1 - x1) * (y2 - x2) % _p, (y1 + x1) * (y2 + x2) % _p
    c, d = 2 * t1 * t2 * _d % _p, 2 * z1 * z2 % _p
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _p, g * h % _p, f * g % _p, e * h % _p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s:
        if s & 1:
            Q = _add(Q, P)
        P, s = _add(P, P), s >> 1
    return Q


def _x(y, sign):
    if y >= _p:
        return None
    x2 = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p) % _p
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p:
        x = x * _I % _p
    if (x * x - x2) % _p:
        return None
    return _p - x if x & 1 != sign else x


def _point(data):
    y = int.from_bytes(data, "little")
    x = _x(y & ((1 << 255) - 1), y >> 255)
    return None if x is None else (x, y & ((1 << 255) - 1), 1, x * (y & ((1 << 255) - 1)) % _p)


_gy = 4 * pow(5, _p - 2, _p) % _p
_G = (_x(_gy, 0), _gy, 1, _x(_gy, 0) * _gy % _p)


def verify(public: bytes, msg: bytes, sig: bytes) -> bool:
    if len(public) != 32 or len(sig) != 64:
        return False
    A, R, s = _point(public), _point(sig[:32]), int.from_bytes(sig[32:], "little")
    if A is None or R is None or s >= _q:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + public + msg).digest(), "little") % _q
    P, Q = _mul(s, _G), _add(R, _mul(k, A))
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def verified(envelope, key: str):
    """The feed body if it is signed with key, else None."""
    try:
        body = envelope["feed"]
        msg = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        public, sig = bytes.fromhex(key.removeprefix("ed25519-pub:")), bytes.fromhex(envelope["signature"])
        return body if isinstance(body, dict) and verify(public, msg, sig) else None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def feed_rules() -> dict:
    """The newest rules we can trust: a verified feed if newer than the built-in ones."""
    if not FEED_KEY:
        return BUILT_IN
    try:
        fresh = CACHE.exists() and time.time() - CACHE.stat().st_mtime < DAY
        if not fresh:
            with urllib.request.urlopen(FEED, timeout=3) as resp:
                raw = resp.read(1_000_000)
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_bytes(raw)
        body = verified(json.loads(CACHE.read_bytes()), FEED_KEY)
    except (OSError, ValueError):
        body = None
    newer = body and isinstance(body.get("version"), int) and body["version"] > BUILT_IN["version"]
    return body if newer and isinstance(body.get("rules"), list) else BUILT_IN


def text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = list(value.values())
    return " ".join(text(v) for v in value) if isinstance(value, list) else ""


# HTTP rules: FORMAT.md, "HTTP rule". The guard reads them for web calls that an agent makes
# from the shell (curl, wget, HTTPie, gh api) or through an MCP tool that fetches a URL.

HTTP_FIELDS = {"id", "service", "host", "method", "path", "graphql", "body", "query", "action", "why", "source"}
METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"}


def globs(value) -> list[str]:
    return [value] if isinstance(value, str) else value


def http_matches(rule: dict, call: dict) -> bool:
    """FORMAT.md, HTTP rule: every field the rule has must match the call."""
    def glob(text, patterns):
        return any(fnmatchcase(text.lower(), p.lower()) for p in globs(patterns))

    def search(field, text):
        return field not in rule or re.search(rule[field], text, re.IGNORECASE) is not None

    fields = call.get("graphql") or []
    return (glob(call["host"], rule["host"])
            and ("*" in globs(rule["method"]) or call["method"] in globs(rule["method"]))
            and search("path", call["path"])
            and search("query", call.get("query", ""))
            and search("body", call.get("body", ""))
            and ("graphql" not in rule or any(glob(f, rule["graphql"]) for f in fields)))


def http_check(call: dict, feed: dict) -> str | None:
    """Why an HTTP rule asks about this call, or None."""
    shown = f"{call['method']} {call['host']}{call['path']}"
    for rule in feed.get("http") or []:
        try:
            if not isinstance(rule, dict) or not set(rule) <= HTTP_FIELDS or rule.get("action", "approve") != "approve":
                continue  # a field we do not know may narrow the rule, so skip it (FORMAT.md)
            if http_matches(rule, call):
                return f"Quarter feed rule {rule.get('id')}: {rule.get('why')} ({shown})"
            # FORMAT.md: a reader that cannot read the body of a call a graphql rule would
            # otherwise match asks a person.
            if call.get("unread") and "graphql" in rule and http_matches(
                    {k: v for k, v in rule.items() if k not in ("graphql", "body")}, call):
                return (f"Quarter feed rule {rule.get('id')}: {rule.get('why')} ({shown}). "
                        "The guard could not read this call's GraphQL query, so it cannot tell.")
        except (KeyError, TypeError, AttributeError, re.error):
            continue
    return None


_GQL = re.compile(r'"""(?:\\"""|[^"]|"(?!""))*"""|"(?:\\.|[^"\\\n])*"|#[^\n]*|[\s,]+|\.\.\.'
                  r'|[_A-Za-z]\w*|-?\d[\w.+-]*|.', re.S)
_NAME = re.compile(r"[_A-Za-z]\w*")


def graphql_roots(doc: str) -> list[str] | None:
    """The root fields every operation in a GraphQL document runs, or None if it does not parse."""
    toks = [t for t in _GQL.findall(doc) if not (t[0] in " \t\r\n," or t[0] == "#")]

    def name(i):
        if not _NAME.fullmatch(toks[i]):
            raise ValueError(toks[i])
        return i + 1

    def group(i):  # toks[i] opens ( { or [; the index after its match
        depth = 0
        for j in range(i, len(toks)):
            depth += (toks[j] in "({[") - (toks[j] in ")}]")
            if depth == 0:
                return j + 1
        raise ValueError("unclosed")

    def directives(i):
        while toks[i] == "@":
            i = name(i + 1)
            if toks[i] == "(":
                i = group(i)
        return i

    def definitions():
        i = 0
        while i < len(toks):
            if toks[i] == "{":
                ops.append(i)
            elif toks[i] in ("query", "mutation", "subscription"):
                i += 1
                if _NAME.fullmatch(toks[i]):
                    i += 1
                if toks[i] == "(":
                    i = group(i)
                i = directives(i)
                ops.append(i)
            elif toks[i] == "fragment":
                frag, i = toks[i + 1], i + 2
                if toks[i] != "on":
                    raise ValueError("fragment")
                i = directives(name(i + 1))
                frags[frag] = i
            else:
                raise ValueError(toks[i])
            if toks[i] != "{":
                raise ValueError("selection")
            i = group(i)

    def roots(i, seen):
        fields, i = [], i + 1
        while toks[i] != "}":
            if toks[i] == "...":
                i += 1
                if toks[i] == "on":
                    i = name(i + 1)
                if toks[i] in ("{", "@"):
                    i = directives(i)
                    fields += roots(i, seen)
                    i = group(i)
                else:
                    spread, i = toks[i], directives(name(i))
                    if spread not in seen:
                        fields += roots(frags[spread], seen | {spread})
                continue
            if toks[i + 1] == ":":
                i += 2
            fields.append(toks[i])
            i = name(i)
            if toks[i] == "(":
                i = group(i)
            i = directives(i)
            if toks[i] == "{":
                i = group(i)
        return fields

    ops, frags = [], {}
    try:
        definitions()
        return [f for op in ops for f in roots(op, frozenset())]
    except (IndexError, KeyError, ValueError):
        return None


def graphql_fields(body: str, query: str) -> list[str] | None:
    """Root fields of the GraphQL a request carries: [] if none, None if it carries some we cannot read."""
    docs = []
    try:
        data = json.loads(body)
    except ValueError:
        data = None
        if re.match(r"\s*(\{|query\b|mutation\b|subscription\b|fragment\b)", body):
            docs.append(body)  # application/graphql
    for item in data if isinstance(data, list) else [data]:
        if isinstance(item, dict) and isinstance(item.get("query"), str):
            docs.append(item["query"])
    docs += urllib.parse.parse_qs(query).get("query", [])
    fields = [graphql_roots(d) for d in docs]
    return None if None in fields else [f for found in fields for f in found]


def http_call(method: str, url: str, body: str = "", unread: bool = False, scheme: str = "http") -> dict | None:
    """The call as FORMAT.md reads it, or None when its host is not known (a $VAR, say)."""
    if not re.match(r"[a-z][\w+.-]*://", url, re.I):
        url = f"{scheme}://{url}"
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not host or re.search(r"[$`{}*()]", parts.netloc):
        return None
    graphql = graphql_fields(body, parts.query)
    return {"method": method.upper(), "host": host.rstrip("."), "path": urllib.parse.unquote(parts.path) or "/",
            "query": parts.query, "body": body, "graphql": graphql or [], "unread": unread or graphql is None}


# Reading a shell command line, enough to find the web calls in it. It splits on | || && ; &
# and newlines outside quotes, follows $(...), `...`, bash -c and eval, and keeps what a
# command reads on stdin when the line says (echo/printf into a pipe, a here-document, < file).

def _close(s: str, i: int) -> int:
    """Index of the ) that closes a $( opened just before i."""
    depth = 1
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 1
        elif c == "'":
            i = s.find("'", i + 1) % (len(s) + 1)
        elif c == '"':
            i += 1
            while i < len(s) and s[i] != '"':
                i += 2 if s[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if not depth:
                return i
        i += 1
    return len(s)


def shell_commands(line: str, depth: int = 0) -> list[dict]:
    """Simple commands in a shell line: {"words", "stdin" (text or None), "stdin_file", "prev"}."""
    out, nested, heredocs = [], [], []
    cmd = {"words": [], "stdin": None, "stdin_file": None, "prev": None}
    word, has, redirect = [], False, None
    i, n = 0, len(line)

    def end_word():
        nonlocal word, has, redirect
        if has:
            w = "".join(word)
            if redirect in ("<<", "<<-"):
                heredocs.append((cmd, w, redirect == "<<-"))
            elif redirect == "<<<":
                cmd["stdin"] = w + "\n"
            elif redirect == "<":
                cmd["stdin_file"] = w
            elif not redirect:
                cmd["words"].append(w)
            redirect = None
        word, has = [], False

    def end_cmd(piped=False):
        nonlocal cmd
        end_word()
        if cmd["words"]:
            out.append(cmd)
        cmd = {"words": [], "stdin": None, "stdin_file": None, "prev": out[-1] if piped and out else None}

    while i < n:
        c = line[i]
        if c in " \t":
            end_word()
        elif c == "\n":
            end_cmd()
            for target, delim, tabs in heredocs:
                lines, j = [], i + 1
                while j <= n:
                    k = line.find("\n", j)
                    k = n if k < 0 else k
                    row = line[j:k].lstrip("\t") if tabs else line[j:k]
                    j = k + 1
                    if row == delim:
                        break
                    lines.append(row + "\n")
                target["stdin"], i = "".join(lines), j - 1
            heredocs.clear()
        elif c == "\\":
            if line[i + 1:i + 2] != "\n":
                word.append(line[i + 1:i + 2])
                has = True
            i += 1
        elif c == "'":
            j = line.find("'", i + 1)
            j = n if j < 0 else j
            word.append(line[i + 1:j])
            has, i = True, j
        elif c == '"':
            has, i = True, i + 1
            while i < n and line[i] != '"':
                if line[i] == "\\" and line[i + 1:i + 2] in ('"', "\\", "$", "`", "\n"):
                    word.append(line[i + 1].replace("\n", ""))
                    i += 2
                elif line.startswith("$(", i):
                    k = _close(line, i + 2)
                    nested.append(line[i + 2:k])
                    word.append(line[i:k + 1])
                    i = k + 1
                else:
                    word.append(line[i])
                    i += 1
        elif line.startswith("$(", i) or c == "`":
            k = _close(line, i + 2) if c == "$" else line.find("`", i + 1) % (n + 1)
            nested.append(line[i + 2:k] if c == "$" else line[i + 1:k])
            word.append(line[i:k + 1])
            has, i = True, k
        elif c == "#" and not has:
            while i + 1 < n and line[i + 1] != "\n":
                i += 1
        elif c in "|&;()":
            two = line[i:i + 2]
            if two == "&>":  # &> and &>> send output to a file
                end_word()
                redirect, i = ">", i + (3 if line[i + 2:i + 3] == ">" else 2)
            else:
                end_cmd(piped=c == "|" and two != "||")
                i += 2 if two in ("&&", "||", "|&", ";;") else 1
            continue
        elif c in "<>":
            if has and "".join(word).isdigit():
                word, has = [], False  # a file descriptor, as in 2>&1
            end_word()
            if line[i + 1:i + 2] == "(":  # process substitution <( ) or >( )
                k = _close(line, i + 2)
                nested.append(line[i + 2:k])
                i = k + 1
                continue
            op = re.match(r"<<<|<<-|<<|<>|<&|>>|>&|>\||<|>", line[i:]).group()
            redirect, i = op if op in ("<<<", "<<-", "<<", "<") else ">", i + len(op)
            continue
        else:
            word.append(c)
            has = True
        i += 1
    end_cmd()
    if depth < 3:
        for inner in nested:
            out += shell_commands(inner, depth + 1)
    return out


WRAPPERS = {"sudo": "ugCDhprtU", "env": "uCS", "command": "", "exec": "a", "nohup": "", "time": "", "nice": "n",
            "timeout": "sk", "doas": "uC", "builtin": "", "stdbuf": "ioe", "caffeinate": "tw", "xargs": "IEnPLdsa"}
KEYWORDS = {"!", "{", "}", "then", "do", "else", "elif", "if", "while", "until"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}


def program(words: list[str]) -> tuple[str | None, list[str]]:
    """The program a simple command runs, past assignments, keywords and wrappers like sudo, and its arguments."""
    i = 0
    while i < len(words):
        w = words[i]
        name = os.path.basename(w)
        if w in KEYWORDS or re.match(r"[A-Za-z_]\w*=", w):
            i += 1
        elif name in WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-") and words[i] != "-":
                i += 2 if len(words[i]) == 2 and words[i][1] in WRAPPERS[name] else 1
            if name == "timeout":
                i += 1  # the duration
        else:
            return name, words[i + 1:]
    return None, []


def scan(args: list[str], short_values: str = "", long_values=(), equals: bool = True) -> list[tuple]:
    """A getopt reading of args: (option, value or None) pairs, and (None, word) for each positional."""
    out, i = [], 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--":
            return out + [(None, w) for w in args[i:]]
        if a.startswith("--"):
            name, eq, value = a.partition("=") if equals else (a, "", "")
            if eq:
                out.append((name, value))
            elif name in long_values:
                out.append((name, args[i] if i < len(args) else ""))
                i += 1
            else:
                out.append((name, None))
        elif a.startswith("-") and len(a) > 1:
            for j in range(1, len(a)):
                if a[j] in short_values:
                    value = a[j + 1:]
                    if not value:
                        value, i = (args[i] if i < len(args) else ""), i + 1
                    out.append(("-" + a[j], value))
                    break
                out.append(("-" + a[j], None))
        else:
            out.append((None, a))
    return out


def unknown(word: str) -> bool:
    """A word that is only an expansion, such as "$BODY": what the shell passes is not known here."""
    return bool(re.fullmatch(r"\$(\w+|\{[^}]*\}|\(.*\))|`.*`", word, re.S))


def read_file(name: str, cwd: str | None, stdin: str | None) -> str | None:
    if name == "-":
        return stdin
    try:
        path = Path(os.path.expanduser(name))
        with open(path if path.is_absolute() else Path(cwd or ".") / path, "rb") as f:
            return f.read(1_000_000).decode("utf-8", "replace")
    except (OSError, ValueError):
        return None


def looks_like_url(word: str) -> bool:
    return bool(re.match(r"https?://|(localhost|[\w-]+(\.[\w-]+)*\.[a-z]{2,}|\d+(\.\d+){3}|\[[\da-f:.]+\])(:\d+)?(/|\?|$)",
                         word, re.I))


def with_query(url: str, query: list[str]) -> str:
    query = [q for q in query if q]
    if not query:
        return url
    base, hash_, frag = url.partition("#")
    return base + ("&" if "?" in base else "?") + "&".join(query) + hash_ + frag


CURL_SHORT = "AbcCdDeEFHKmoPQrtTuUwxXyYz"
CURL_LONG = {
    "--request", "--data", "--data-ascii", "--data-binary", "--data-raw", "--data-urlencode", "--json", "--form",
    "--form-string", "--url", "--url-query", "--header", "--user-agent", "--user", "--output", "--cookie",
    "--cookie-jar", "--config", "--max-time", "--connect-timeout", "--retry", "--retry-delay", "--retry-max-time",
    "--proxy", "--proxy-user", "--referer", "--cacert", "--capath", "--cert", "--key", "--cert-type", "--key-type",
    "--pass", "--upload-file", "--write-out", "--resolve", "--connect-to", "--range", "--limit-rate",
    "--oauth2-bearer", "--aws-sigv4", "--variable", "--output-dir", "--dump-header", "--trace", "--trace-ascii",
    "--stderr", "--interface", "--dns-servers", "--unix-socket", "--abstract-unix-socket", "--proto",
    "--proto-redir", "--max-redirs", "--max-filesize", "--keepalive-time", "--time-cond", "--ciphers",
    "--request-target", "--continue-at", "--quote", "--expect100-timeout", "--happy-eyeballs-timeout-ms",
    "--local-port", "--noproxy", "--preproxy", "--proxy-header", "--rate", "--parallel-max", "--etag-save",
    "--etag-compare", "--hsts", "--alt-svc", "--login-options", "--sasl-authzid", "--mail-from", "--mail-rcpt",
    "--ftp-port", "--speed-limit", "--speed-time", "--tls-max", "--pinnedpubkey", "--crlfile", "--engine",
    "--netrc-file", "--socks5", "--socks5-hostname", "--socks4", "--socks4a", "--doh-url", "--ip-tos"}
CURL_DATA = {"-d": "data", "--data": "data", "--data-ascii": "data", "--data-binary": "binary",
             "--data-raw": "raw", "--data-urlencode": "urlencode", "--json": "json"}


def curl_calls(args, stdin, cwd) -> list[dict]:
    calls, groups, group = [], [], []
    for a in args:  # --next starts a new set of options for the URLs after it
        if a in ("--next", "-:"):
            groups.append(group)
            group = []
        else:
            group.append(a)
    for group in groups + [group]:
        method, urls, query, data, form, unread = None, [], [], [], [], False
        get = head = upload = False
        for opt, value in scan(group, CURL_SHORT, CURL_LONG | set(CURL_DATA), equals=False):
            if opt is None:
                if looks_like_url(value):
                    urls.append(value)
            elif opt in ("-X", "--request"):
                method = value
            elif opt in ("--url",):
                urls.append(value)
            elif opt == "--url-query":
                query.append(value)
            elif opt in CURL_DATA:
                piece = curl_data(CURL_DATA[opt], value, stdin, cwd)
                unread |= piece is None
                data.append((CURL_DATA[opt], piece or ""))
            elif opt in ("-F", "--form", "--form-string"):
                form.append((opt, value))
            elif opt in ("-G", "--get"):
                get = True
            elif opt in ("-I", "--head"):
                head = True
            elif opt in ("-T", "--upload-file"):
                upload = True
        body = ""
        for kind, piece in data:
            body += piece if not body or kind == "json" else "&" + piece
        if form:
            fields = {}
            for opt, spec in form:
                key, _, value = spec.partition("=")
                if opt != "--form-string" and value.startswith("<"):
                    value = read_file(value[1:].split(";")[0], cwd, stdin)
                elif opt != "--form-string" and value.startswith("@"):
                    value = ""  # an uploaded file, not text
                unread |= value is None
                fields[key] = value or ""
            body = fields.get("operations") or "&".join(f"{k}={v}" for k, v in fields.items())
        if get:
            query, body = query + [body], ""
        method = method or ("HEAD" if head else "GET" if get else "PUT" if upload
                            else "POST" if data or form else "GET")
        for url in urls:
            call = http_call(method, with_query(url, query), body, unread)
            if call:
                calls.append(call)
    return calls


def curl_data(kind, value, stdin, cwd) -> str | None:
    """What one -d family option adds to the body, or None if it is not known here."""
    if unknown(value):
        return None
    if kind == "urlencode":
        key, eq, content = value.partition("=")
        if not eq:
            key, at, name = value.partition("@")
            content = read_file(name, cwd, stdin) if at else value
            key = key if at else ""
            if content is None:
                return None
        return (key + "=" if key else "") + urllib.parse.quote(content, safe="")
    if kind == "raw" or not value.startswith("@"):
        return value
    content = read_file(value[1:], cwd, stdin)
    return content.replace("\r", "").replace("\n", "") if content is not None and kind == "data" else content


WGET_SHORT = "OoaePtTwUlARDIXiBQ"
WGET_LONG = {
    "--method", "--body-data", "--body-file", "--post-data", "--post-file", "--header", "--output-document",
    "--output-file", "--append-output", "--user-agent", "--user", "--password", "--http-user", "--http-password",
    "--directory-prefix", "--tries", "--timeout", "--wait", "--level", "--input-file", "--referer",
    "--load-cookies", "--save-cookies", "--execute", "--base", "--ca-certificate", "--certificate",
    "--private-key", "--dns-timeout", "--connect-timeout", "--read-timeout", "--limit-rate", "--quota",
    "--accept", "--reject", "--domains", "--exclude-domains", "--include-directories", "--exclude-directories",
    "--proxy-user", "--proxy-password", "--bind-address", "--default-page", "--restrict-file-names"}


def wget_calls(args, stdin, cwd) -> list[dict]:
    method, urls, body, unread = None, [], None, False
    args = [a for a in args if not re.fullmatch(r"-n[a-zA-Z]+", a)]  # -nv, -nc and the like
    for opt, value in scan(args, WGET_SHORT, WGET_LONG):
        if opt is None and looks_like_url(value):
            urls.append(value)
        elif opt == "--method":
            method = value
        elif opt in ("--body-data", "--post-data"):
            body = None if unknown(value) else value
            unread |= body is None
            method = method or ("POST" if opt == "--post-data" else None)
        elif opt in ("--body-file", "--post-file"):
            body = read_file(value, cwd, stdin)
            unread |= body is None
            method = method or ("POST" if opt == "--post-file" else None)
    return [c for url in urls if (c := http_call(method or "GET", url, body or "", unread))]


HTTPIE_SHORT = "aAopPs"
HTTPIE_LONG = {
    "--auth", "--auth-type", "--output", "--print", "--history-print", "--style", "--session",
    "--session-read-only", "--verify", "--cert", "--cert-key", "--cert-key-pass", "--ssl", "--ciphers", "--proxy",
    "--timeout", "--max-redirects", "--pretty", "--format-options", "--response-charset", "--response-mime",
    "--raw", "--boundary", "--default-scheme", "--max-headers", "--bearer"}
HTTPIE_SEPS = (":=@", "=@", "==", ":=", "@", "=", ":")


def httpie_calls(args, stdin, piped, cwd, scheme) -> list[dict]:
    words, form, raw, ignore_stdin = [], False, None, False
    for opt, value in scan(args, HTTPIE_SHORT, HTTPIE_LONG):
        if opt is None:
            words.append(value)
        elif opt in ("-f", "--form", "--multipart"):
            form = True
        elif opt == "--raw":
            raw = value
        elif opt in ("-I", "--ignore-stdin"):
            ignore_stdin = True
        elif opt == "--offline":
            return []  # builds the request without sending it
    method = words.pop(0).upper() if len(words) > 1 and words[0].upper() in METHODS else None
    if not words:
        return []
    url, items = words[0], words[1:]
    if url.startswith(":"):
        url = "localhost" + url  # :3000/x is localhost:3000/x
    data, query, unread = {}, [], False
    for item in items:
        seps = [(item.find(s), -len(s), s) for s in HTTPIE_SEPS if item.find(s) > 0]
        if not seps:
            continue
        at, _, sep = min(seps)
        key, value = item[:at], item[at + len(sep):]
        if sep in ("=@", ":=@"):
            value = read_file(value, cwd, stdin)
            unread |= value is None
            value = value or ""
        if sep == "==":
            query.append(urllib.parse.urlencode({key: value}))
        elif sep in ("=", "=@"):
            data[key] = value
        elif sep in (":=", ":=@"):
            try:
                data[key] = json.loads(value)
            except ValueError:
                data[key] = value
        elif sep == "@":
            form, data[key] = True, ""  # a file upload
    if raw is not None:
        body = raw
    elif data:
        body = urllib.parse.urlencode({k: v if isinstance(v, str) else json.dumps(v) for k, v in data.items()}) \
            if form else json.dumps(data)
    elif piped and not ignore_stdin:
        body, unread = stdin or "", unread or stdin is None
    else:
        body = ""
    call = http_call(method or ("POST" if body or unread else "GET"), with_query(url, query), body, unread, scheme)
    return [call] if call else []


GH_SHORT = "XfFHqtp"
GH_LONG = {"--method", "--raw-field", "--field", "--header", "--jq", "--template", "--input", "--hostname",
           "--cache", "--preview"}


def gh_put(obj: dict, key: str, value) -> None:
    """Set key in obj the way gh api reads field names: a[b]=x nests, a[]=x appends."""
    m = re.fullmatch(r"([^\[\]]+)((?:\[[^\[\]]*\])*)", key)
    keys = [m.group(1)] + re.findall(r"\[([^\[\]]*)\]", m.group(2)) if m else [key]
    cur = obj
    for k, nxt in zip(keys, keys[1:] + [None]):
        new = value if nxt is None else [] if nxt == "" else {}
        if isinstance(cur, list):
            cur.append(new)
        elif isinstance(cur, dict):
            new = cur[k] = value if nxt is None else cur.get(k, new)
        cur = new


def gh_calls(args, stdin, cwd) -> list[dict]:
    if not args or args[0] != "api":
        return []
    endpoint, method, host, fields, body, unread = None, None, "api.github.com", {}, None, False
    for opt, value in scan(args[1:], GH_SHORT, GH_LONG):
        if opt is None:
            endpoint = endpoint or value
        elif opt in ("-X", "--method"):
            method = value
        elif opt == "--hostname":
            host = "api.github.com" if value.lower() == "github.com" else value
        elif opt in ("-f", "--raw-field", "-F", "--field"):
            key, _, raw = value.partition("=")
            if opt in ("-F", "--field"):  # typed: true, false, null, numbers and @file
                if raw.startswith("@"):
                    raw = read_file(raw[1:], cwd, stdin)
                    unread, raw = unread or raw is None, raw or ""
                elif raw in ("true", "false", "null") or re.fullmatch(r"-?\d+", raw):
                    raw = json.loads(raw)
            if isinstance(raw, str) and unknown(raw):
                unread, raw = True, ""
            gh_put(fields, key, raw)
        elif opt == "--input":
            body = read_file(value, cwd, stdin)
            unread |= body is None
    if not endpoint:
        return []
    url = endpoint if re.match(r"https?://", endpoint) else f"https://{host}/" + (
        "api/v3/" if host != "api.github.com" else "") + endpoint.lstrip("/")
    query = []
    if endpoint == "graphql":
        url = f"https://{host}/" + ("api/graphql" if host != "api.github.com" else "graphql")
        payload = {k: fields.pop(k) for k in ("query", "operationName") if k in fields}
        body = json.dumps({**payload, "variables": fields})
        method = method or "POST"
    else:
        method = (method or ("POST" if fields or body is not None else "GET")).upper()
        if fields and method == "GET":
            query.append(urllib.parse.urlencode({k: v if isinstance(v, str) else json.dumps(v)
                                                 for k, v in fields.items()}))
        elif fields:
            body = json.dumps(fields)
    call = http_call(method, with_query(url, query), body or "", unread, "https")
    return [call] if call else []


def stdin_of(cmd: dict, cwd) -> tuple[str | None, bool]:
    """What a command reads on stdin, if the line says, and whether it reads from a pipe."""
    if cmd["stdin"] is not None:
        return cmd["stdin"], False
    if cmd["stdin_file"]:
        return read_file(cmd["stdin_file"], cwd, None), False
    prev = cmd["prev"]
    if not prev:
        return None, False
    name, args = program(prev["words"])
    if name == "echo":
        args = args[1:] if args[:1] == ["-n"] else args
        return (None if any("$" in a for a in args) else " ".join(args) + "\n"), True
    if name == "printf" and args and "$" not in args[0] and "%" not in args[0]:
        return args[0].encode().decode("unicode_escape", "replace"), True
    if name == "cat":
        if not args:
            return stdin_of(prev, cwd)[0], True
        return (read_file(args[0], cwd, None) if len(args) == 1 else None), True
    return None, True


def shell_calls(line: str, cwd: str | None = None, depth: int = 0) -> list[dict]:
    """The HTTP calls a shell command line makes with curl, wget, HTTPie or gh api, as far as it says."""
    calls = []
    for cmd in shell_commands(line):
        name, args = program(cmd["words"])
        stdin, piped = stdin_of(cmd, cwd)
        if name in SHELLS and depth < 3:
            script = next((args[k + 1] for k, a in enumerate(args[:-1])
                           if re.fullmatch(r"-[a-z]*c[a-z]*", a)), None)
            calls += shell_calls(script, cwd, depth + 1) if script else []
        elif name == "eval" and depth < 3:
            calls += shell_calls(" ".join(args), cwd, depth + 1)
        elif name == "curl":
            calls += curl_calls(args, stdin, cwd)
        elif name == "wget":
            calls += wget_calls(args, stdin, cwd)
        elif name in ("http", "https", "xh", "xhs"):
            calls += httpie_calls(args, stdin, piped or stdin is not None, cwd, "https" if name in ("https", "xhs") else "http")
        elif name == "gh":
            calls += gh_calls(args, stdin, cwd)
    return calls


def mcp_calls(tool_input) -> list[dict]:
    """An MCP tool call that plainly names an absolute URL and an HTTP method, such as a generic fetch tool."""
    if not isinstance(tool_input, dict):
        return []
    given = {k.lower(): v for k, v in tool_input.items() if isinstance(k, str)}
    url = next((given[k] for k in ("url", "uri", "endpoint") if isinstance(given.get(k), str)), "")
    method = next((given[k] for k in ("method", "http_method", "httpmethod", "verb")
                   if isinstance(given.get(k), str)), "")
    if method.upper() not in METHODS or not re.match(r"https?://", url, re.I):
        return []
    body = next((given[k] for k in ("body", "data", "json", "payload") if given.get(k) is not None), "")
    params = given.get("params") if isinstance(given.get("params"), dict) else {}
    call = http_call(method, with_query(url, [urllib.parse.urlencode(params)]),
                     body if isinstance(body, str) else json.dumps(body))
    return [call] if call else []


def check(tool: str, tool_input, cwd: str | None = None) -> str | None:
    """Why a rule asks about this call, or None."""
    feed, said = feed_rules(), text(tool_input)
    for n, rule in enumerate(feed["rules"], 1):
        if rule.get("action", "approve") != "approve" or not isinstance(rule.get("tool"), str):
            continue  # the guard only ever asks
        try:
            if fnmatchcase(tool.lower(), rule["tool"].lower()) and (
                    not rule.get("command") or re.search(rule["command"], said, re.IGNORECASE)):
                return f"Quarter feed rule {n}: {rule.get('why') or 'matches ' + rule.get('command', '')}"
        except re.error:
            continue
    try:
        if tool.lower() == "bash" and isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
            calls = shell_calls(tool_input["command"], cwd)
        else:
            calls = mcp_calls(tool_input) if tool.lower().startswith("mcp__") else []
        return next((why for call in calls if (why := http_check(call, feed))), None)
    except Exception:  # a reading this guard gets wrong must never stand in the agent's way
        return None


def claude_reply(call: dict) -> dict | None:
    """Claude Code PreToolUse. Codex sends the same input but does not act on "ask" yet."""
    why = check(str(call.get("tool_name", "")), call.get("tool_input"), call.get("cwd"))
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                   "permissionDecisionReason": why}} if why else None


def cursor_reply(call: dict) -> dict | None:
    """Cursor beforeShellExecution and beforeMCPExecution: https://cursor.com/docs/agent/hooks"""
    roots = call.get("workspace_roots") or [None]
    cwd = call.get("cwd") or roots[0]
    event = call.get("hook_event_name")
    if event == "beforeMCPExecution" or event is None and "tool_name" in call:
        tool_input = call.get("tool_input")
        try:
            tool_input = json.loads(tool_input) if isinstance(tool_input, str) else tool_input
        except ValueError:
            pass
        tool = f"mcp__{call.get('mcp_server_name', '')}__{call.get('tool_name', '')}"
        why = check(tool, tool_input, cwd)
    elif isinstance(call.get("command"), str):
        why = check("Bash", {"command": call["command"]}, cwd)
    else:
        why = None
    # No match prints nothing: Cursor then lets the call through to its normal flow.
    return {"permission": "ask", "user_message": why, "agent_message": why} if why else None


HOSTS = {"claude": claude_reply, "cursor": cursor_reply}
SETTINGS = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
    {"type": "command", "command": "python3", "args": [str(Path(__file__).resolve())], "timeout": 10}]}]}}


def settings(host: str) -> dict:
    if host == "cursor":
        hook = {"command": f"python3 {shlex.quote(str(Path(__file__).resolve()))} --host cursor", "timeout": 10}
        return {"version": 1, "hooks": {"beforeShellExecution": [hook], "beforeMCPExecution": [hook]}}
    return SETTINGS


def main() -> None:
    args, host = sys.argv[1:], "claude"
    if "--host" in args:
        k = args.index("--host")
        host = args[k + 1] if k + 1 < len(args) else ""
        del args[k:k + 2]
    if host not in HOSTS:
        sys.exit(f"guard.py: unknown host {host!r}. Hosts: {', '.join(HOSTS)}")
    if args == ["--settings"]:
        print(json.dumps(settings(host), indent=2))
        return
    try:
        call = json.load(sys.stdin)
    except ValueError:
        return  # not a hook call we understand: the normal permission flow applies
    reply = HOSTS[host](call) if isinstance(call, dict) else None
    if reply:
        print(json.dumps(reply))


if __name__ == "__main__":
    main()

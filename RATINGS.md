# Quarter ratings of MCP server tools

Feed version 4, issued 2026-11-03. 27 servers, 112 tools rated `ask` and 461 rated `watch`.

An MCP server labels its own tools as read-only or destructive. The MCP specification says a client must not trust those labels from a server it does not trust. These ratings are Quarter's own, read from each server's published tool list.

- `ask`: the tool deletes, pays, refunds, sends to customers, revokes or rotates, or cannot be undone. `guard.py` asks you before it runs.
- `watch`: the tool writes, and the write can be undone. Nothing asks. A gateway may record it.
- Tools that only read have no rating.

A rating applies when the tool name matches and the server name matches one of the names listed. You choose the server's name when you add it, so the names cover the usual ones. Claude Code shows a tool as `mcp__<server>__<tool>`. Where a rating has an input pattern, it asks only when the call's input matches it. Each `ask` rating has a call it must catch and a close call on the same server it must let through, in `cases.json`.

Shell rules still apply inside MCP calls. A SQL tool that runs `DROP TABLE` asks because of the SQL rule, so SQL tools are rated `watch`.

## MCP reference filesystem server

From `@modelcontextprotocol/server-filesystem`. Server names: `filesystem`, `*filesystem*`, `fs`, so tools show as `mcp__filesystem__<tool>`. Tool list: https://github.com/modelcontextprotocol/servers/blob/main/src/filesystem/README.md

Watch: `write_file`, `edit_file`, `move_file`, `create_directory`.

## MCP reference git server

From `mcp-server-git`. Server names: `git`, `*mcp-server-git*`, `*mcp_server_git*`, so tools show as `mcp__git__<tool>`. Tool list: https://github.com/modelcontextprotocol/servers/blob/main/src/git/README.md

Watch: `git_commit`, `git_add`, `git_reset`, `git_create_branch`, `git_checkout`.

## GitHub

From `github/github-mcp-server`, `https://api.githubcopilot.com/mcp/`. Server names: `github`, `*github*`, so tools show as `mcp__github__<tool>`. Tool list: https://github.com/github/github-mcp-server/blob/main/README.md

Ask:

- `delete_repository`: deletes a GitHub repository with its issues, pull requests and wiki.

Watch: `delete_file`, `merge_pull_request`, `push_files`, `create_or_update_file`, `create_branch`, `create_repository`, `fork_repository`, `create_gist`, `update_gist`, `actions_run_trigger`, `create_pull_request`, `create_pull_request_with_copilot`, `update_pull_request`, `update_pull_request_branch`, `pull_request_review_write`, `add_comment_to_pending_review`, `add_reply_to_pull_request_comment`, `add_issue_comment`, `update_issue_comment`, `issue_write`, `sub_issue_write`, `label_write`, `discussion_comment_write`, `projects_write`, `create_repository_ruleset`, `custom_properties_write`, `assign_copilot_to_issue`, `assign_copilot_to_issue_with_intent`, `request_copilot_review`, `dismiss_notification`, `mark_all_notifications_read`, `manage_notification_subscription`, `manage_repository_notification_subscription`, `star_repository`, `unstar_repository`.

## Stripe

From `https://mcp.stripe.com`, `@stripe/mcp`. Server names: `stripe`, `*stripe*`, so tools show as `mcp__stripe__<tool>`. Tool list: https://docs.stripe.com/mcp#tools

Ask:

- `send_money`: sends money from a Treasury account to a recipient.
- `transfer_money`: moves money between Stripe balances.
- `convert_currency`: converts funds between currencies.
- `stripe_api_write`: runs any Stripe write, including refunds, cancellations and deletes.

Watch: `setup_recipient`, `atlas_company_formation`, `send_stripe_feedback`.

## Supabase

From `@supabase/mcp-server-supabase`, `https://mcp.supabase.com/mcp`. Server names: `supabase`, `*supabase*`, so tools show as `mcp__supabase__<tool>`. Tool list: https://github.com/supabase-community/supabase-mcp/blob/main/packages/mcp-server-supabase/src/tools/branching-tools.ts

Ask:

- `delete_branch`: deletes a development branch and its data.
- `reset_branch`: resets a branch's migrations; untracked data and schema changes are lost.
- `merge_branch`: applies a branch's migrations and Edge Functions to production.
- `pause_project`: pauses a project, taking its database and APIs offline.

Watch: `rebase_branch`, `create_branch`, `create_project`, `confirm_cost`, `restore_project`, `apply_migration`, `execute_sql`, `deploy_edge_function`, `create_edge_function_secret`, `update_storage_config`, `create_notebook`, `run_notebook`, `delete_notebook`, `submit_feedback`, `delete_feedback`.

## Cloudflare API (code mode)

From `https://mcp.cloudflare.com/mcp`, `cloudflare/mcp`. Server names: `cloudflare*`, `*cloudflare*`, so tools show as `mcp__cloudflare__<tool>`. Tool list: https://github.com/cloudflare/mcp/blob/main/README.md

Ask:

- `execute`: runs code that sends a DELETE to the Cloudflare API. Only when the input matches its pattern.

## Cloudflare Workers Bindings (deprecated)

From `cloudflare/mcp-server-cloudflare`, `https://bindings.mcp.cloudflare.com/mcp`. Server names: `cloudflare*`, `*cloudflare*`, `*bindings*`, so tools show as `mcp__cloudflare__<tool>`. Tool list: https://github.com/cloudflare/mcp-server-cloudflare/blob/main/apps/workers-bindings/README.md

Ask:

- `d1_database_delete`: deletes a D1 database and its data.
- `r2_bucket_delete`: deletes an R2 bucket.
- `kv_namespace_delete`: deletes a KV namespace and its keys.
- `hyperdrive_config_delete`: deletes a Hyperdrive configuration.

Watch: `d1_database_query`, `d1_database_create`, `r2_bucket_create`, `kv_namespace_create`, `kv_namespace_update`, `hyperdrive_config_create`, `hyperdrive_config_edit`.

## Notion (hosted)

From `https://mcp.notion.com/mcp`. Server names: `notion`, `*notion*`, so tools show as `mcp__notion__<tool>`. Tool list: https://developers.notion.com/guides/mcp/tools-calendars-reference

Ask:

- `notion-calendar-cancel-events`: cancels calendar events, which may notify every guest.

Watch: `notion-calendar-create-events`, `notion-calendar-update-events`, `notion-delete-pages`, `notion-create-pages`, `notion-update-page`, `notion-move-pages`, `notion-duplicate-page`, `notion-delete-databases`, `notion-create-database`, `notion-update-data-source`, `notion-create-view`, `notion-update-view`, `notion-restore-version`, `notion-restore-pages`, `notion-create-comment`, `notion-update-comment`, `notion-delete-comment`, `notion-set-comment-reaction`, `notion-set-discussion-resolved`, `notion-create-suggested-edit`, `notion-resolve-suggested-edit`, `notion-create-file-upload`, `notion-create-attachment`, `notion-create-folder`, `notion-update-folder`, `notion-spawn-session`, `notion-send-message-to-session`, `notion-stop-session`, `notion-upload-skill`, `notion-convert-page-to-skill`, `notion-update-enabled-skills`.

## Notion (local, API-derived)

From `@notionhq/notion-mcp-server`. Server names: `notion`, `*notion*`, so tools show as `mcp__notion__<tool>`. Tool list: https://github.com/makenotion/notion-mcp-server/blob/main/scripts/notion-openapi.json

Watch: `API-delete-a-block`, `API-update-a-block`, `API-patch-block-children`, `API-patch-page`, `API-post-page`, `API-update-page-markdown`, `API-move-page`, `API-create-a-comment`, `API-create-a-data-source`, `API-update-a-data-source`.

## Sentry

From `@sentry/mcp-server`, `https://mcp.sentry.dev/mcp`. Server names: `sentry`, `*sentry*`, so tools show as `mcp__sentry__<tool>`. Tool list: https://github.com/getsentry/sentry-mcp/blob/main/packages/mcp-core/src/tools/catalog/index.ts

Ask:

- `delete_alert_rule`: deletes an alert for good, with its notifications for every connected project.
- `delete_metric_monitor`: deletes a metric monitor for good, with its incident history.
- `delete_uptime_monitor`: deletes an uptime monitor for good.
- `delete_monitor_environment`: deletes a cron monitor's environment.
- `execute_sentry_tool`: runs one of Sentry's delete tools. Only when the input matches its pattern.

Watch: `update_alert_rule`, `update_metric_monitor`, `update_uptime_monitor`, `create_alert_rule`, `create_metric_monitor`, `create_uptime_monitor`, `update_issue`, `update_project`, `update_dsn`, `create_dsn`, `create_project`, `create_team`, `add_team_to_project`, `remove_team_from_project`, `link_issue`, `unlink_issue`, `add_issue_note`, `analyze_issue_with_seer`, `onboarding_status_update`, `submit_feedback_to_sentry_team`.

## Neon

From `neondatabase/mcp-server-neon`, `https://mcp.neon.tech/mcp`. Server names: `neon`, `*neon*`, so tools show as `mcp__neon__<tool>`. Tool list: https://github.com/neondatabase/mcp-server-neon/blob/main/mcp/tools/generated/names.ts

Ask:

- `delete_project`: deletes a Neon project with all its branches and data.
- `delete_branch`: deletes a branch and its data.
- `reset_from_parent`: resets a branch to its parent, discarding its changes.
- `delete_postgres_database`: deletes a database.
- `delete_postgres_role`: deletes a database role.
- `reset_postgres_role_password`: resets a role's password, which breaks apps using the old one.
- `delete_postgres_endpoint`: deletes a compute endpoint.
- `suspend_postgres_endpoint`: suspends a compute endpoint, taking it offline.
- `delete_snapshot`: deletes a snapshot.
- `restore_snapshot`: restores a snapshot onto a branch.
- `finalize_branch_restore`: finishes a branch restore.
- `disable_auth`: turns Neon Auth off for a branch.
- `delete_auth_user`: deletes a Neon Auth user.
- `delete_auth_oauth_client`: deletes an OAuth client.
- `rotate_auth_oauth_client_secret`: rotates an OAuth client secret, which breaks apps using the old one.
- `delete_data_api`: deletes the Data API for a database.
- `delete_function`: deletes a function.
- `revoke_credential`: revokes a credential.
- `rotate_credential`: rotates a credential, which breaks apps using the old one.
- `delete_storage_bucket`: deletes a storage bucket.
- `delete_storage_object`: deletes a stored object.
- `delete_storage_objects_by_prefix`: deletes every stored object under a prefix.
- `rotate_realtime_secret`: rotates the realtime secret, which breaks clients using the old one.

Watch: `run_sql`, `run_sql_transaction`, `prepare_database_migration`, `complete_database_migration`, `prepare_query_tuning`, `complete_query_tuning`, `explain_sql_statement`, `send_feedback`, `create_project`, `update_project`, `recover_project`, `create_branch`, `update_branch`, `set_default_branch`, `create_postgres_role`, `create_postgres_database`, `update_postgres_database`, `create_postgres_endpoint`, `update_postgres_endpoint`, `start_postgres_endpoint`, `restart_postgres_endpoint`, `set_snapshot_schedule`, `create_snapshot`, `update_snapshot`, `provision_neon_auth`, `update_auth_config`, `add_auth_oauth_provider`, `update_auth_oauth_provider`, `delete_auth_oauth_provider`, `add_auth_trusted_domain`, `delete_auth_trusted_domain`, `create_auth_user`, `update_auth_user_role`, `update_auth_oauth_server`, `create_auth_oauth_client`, `update_auth_oauth_client`, `provision_neon_data_api`, `update_data_api`, `update_function`, `deploy_function`, `register_functions_custom_domain`, `delete_functions_custom_domain`, `create_trigger`, `update_trigger`, `delete_trigger`, `create_credential`, `create_storage_bucket`, `presign_storage_object`, `enable_realtime`, `disable_realtime`.

## MongoDB

From `mongodb-mcp-server`, `mongodb-js/mongodb-mcp-server`. Server names: `mongo*`, `*mongodb*`, so tools show as `mcp__mongo__<tool>`. Tool list: https://github.com/mongodb-js/mongodb-mcp-server/blob/main/README.md

Ask:

- `delete-many`: deletes every document that matches the filter.
- `drop-collection`: drops a collection with its indexes.
- `drop-database`: drops a database and its data files.
- `atlas-pause-resume-cluster`: pauses or resumes an Atlas cluster.
- `atlas-streams-teardown`: deletes Atlas Stream Processing workspaces, connections or processors.
- `atlas-local-delete-deployment`: deletes a local Atlas deployment and its data.

Watch: `update-many`, `insert-many`, `create-collection`, `create-index`, `drop-index`, `rename-collection`, `atlas-create-access-list`, `atlas-create-cluster`, `atlas-create-free-cluster`, `atlas-create-db-user`, `atlas-create-project`, `atlas-upgrade-cluster`, `atlas-load-sample-dataset`, `atlas-streams-build`, `atlas-streams-manage`, `atlas-local-create-deployment`.

## Railway

From `railway mcp (Railway CLI)`, `@railway/mcp-server`. Server names: `railway`, `*railway*`, so tools show as `mcp__railway__<tool>`. Tool list: https://github.com/railwayapp/cli/blob/master/src/commands/mcp/handler.rs

Ask:

- `remove_service`: removes a service from a project; Railway says this is irreversible.
- `remove_volume`: removes a volume and its data; Railway says this is irreversible.
- `remove_bucket`: removes a storage bucket; Railway says this is irreversible.
- `delete_domain`: deletes a domain; Railway says this is irreversible.
- `remove_tcp_proxy`: removes a public TCP proxy; Railway says this is irreversible.

Watch: `deploy`, `deploy_template`, `create_project`, `create_environment`, `create_service`, `update_service`, `scale_service`, `connect_service_source`, `disconnect_service_source`, `set_variables`, `add_reference_variable`, `generate_domain`, `update_domain`, `retry_domain_certificate`, `create_tcp_proxy`, `private_network_update`, `create_bucket`, `create_volume`, `update_volume`, `link_service`, `link_environment`.

## Heroku

From `@heroku/mcp-server`, `heroku mcp:start`. Server names: `heroku`, `*heroku*`, so tools show as `mcp__heroku__<tool>`. Tool list: https://github.com/heroku/heroku-mcp-server/blob/main/README.md

Ask:

- `transfer_app`: gives ownership of an app to another user or team.
- `maintenance_on`: puts an app in maintenance mode, taking it offline.
- `pg_upgrade`: upgrades Postgres to a newer version, which cannot be rolled back.

Watch: `pg_psql`, `pg_kill`, `pg_credentials`, `pg_backups`, `create_app`, `rename_app`, `deploy_to_heroku`, `deploy_one_off_dyno`, `ps_scale`, `ps_restart`, `create_addon`, `maintenance_off`, `pipelines_create`, `pipelines_promote`.

## Netlify

From `@netlify/mcp`, `netlify/netlify-mcp`. Server names: `netlify`, `*netlify*`, so tools show as `mcp__netlify__<tool>`. Tool list: https://github.com/netlify/netlify-mcp/blob/main/src/tools/index.ts

Ask:

- `netlify-project-services-updater`: deletes a form submission or an environment variable. Only when the input matches its pattern.
- `netlify-project-manage-form-submissions`: deletes a form submission. Only when the input matches its pattern.
- `netlify-project-manage-env-vars`: deletes an environment variable. Only when the input matches its pattern.

Watch: `netlify-deploy-services-updater`, `netlify-deploy-site`, `netlify-extension-services-updater`, `netlify-extension-change-extension-installation`, `netlify-project-create-new-project`, `netlify-project-update-forms`, `netlify-project-update-project-name`, `netlify-project-update-visitor-access-controls`, `netlify-feedback-services-updater`, `netlify-submit-feedback`.

## Vercel

From `https://mcp.vercel.com`. Server names: `vercel`, `*vercel*`, so tools show as `mcp__vercel__<tool>`. Tool list: https://vercel.com/docs/agent-resources/vercel-mcp/tools

Ask:

- `buy_domain`: buys a domain with the team's payment method.
- `replace_domain_dns_records`: replaces a domain's DNS records.
- `revoke_kms_signing_key`: revokes a signing key.
- `pause_project`: pauses a project, taking its deployments offline.

Watch: `cancel_deployment`, `create_deployment`, `deploy_to_vercel`, `upload_file`, `unpause_project`, `update_project`, `create_project`, `create_git_project`, `add_project_domain`, `verify_project_domain`, `update_project_deployment_protection`, `update_project_protection_bypass`, `accept_project_transfer_request`, `request_promote`, `request_rollback`, `start_rolling_release`, `approve_rolling_release_stage`, `complete_rolling_release`, `update_rolling_release_config`, `create_or_transfer_domain`, `create_record`, `update_record`, `issue_cert`, `create_project_env`, `edit_project_env`, `put_firewall_config`, `update_firewall_config`, `update_attack_challenge_mode`, `invalidate_by_tags`, `invalidate_by_src_images`, `create_edge_config`, `update_edge_config`, `patch_edge_config_items`, `restore_edge_config_backup`, `create_edge_config_token`, `create_kms_signing_key`, `activate_kms_signing_key`, `create_kms_issuer`, `update_kms_issuer`, `create_kms_issuer_policy`, `update_kms_issuer_policy`, `add_route`, `edit_route`, `assign_alias`, `stage_routes`, `stage_redirects`, `restore_redirects`, `update_route_versions`, `update_bulk_redirect_version`, `run_session_command`, `write_session_files`, `stop_session`, `kill_session_command`, `update_sandbox`, `update_session_network_policy`.

## PlanetScale

From `https://mcp.pscale.dev/mcp/planetscale`. Server names: `planetscale`, `*planetscale*`, `pscale`, so tools show as `mcp__planetscale__<tool>`. Tool list: https://planetscale.com/docs/connect/mcp#available-tools

Watch: `planetscale_execute_write_query`, `planetscale_update_payment_method`.

## Atlassian (Jira, Confluence, Bitbucket)

From `https://mcp.atlassian.com/v2/mcp`. Server names: `atlassian`, `*atlassian*`, `*jira*`, `*confluence*`, so tools show as `mcp__atlassian__<tool>`. Tool list: https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/

Ask:

- `executeDestructive`: runs an Atlassian tool its server marks destructive, such as deleting a Jira issue.
- `executeWrite`: deletes Jira content or makes a Confluence page public. Only when the input matches its pattern.
- `deleteJiraIssue`: deletes a Jira issue for good.
- `deleteJiraComment`: deletes a Jira comment for good.
- `deleteJiraIssueAttachment`: deletes a Jira attachment for good.
- `enableConfluencePublicLink`: makes a Confluence page readable by anyone with the link.

Watch: `mergeBitbucketRepoPullRequest`, `archiveConfluenceContent`, `removeConfluenceContentPermissions`, `replaceConfluenceContentPermissions`, `shareLoomObject`, `updateLoomObjectVisibility`, `decideJsmRequestApproval`, `runBitbucketRepoPipeline`, `createJiraIssue`, `editJiraIssue`, `transitionJiraIssue`, `addOrEditJiraIssueComment`, `createConfluenceContent`, `updateConfluenceContent`, `moveConfluenceContent`, `createBitbucketRepoPullRequest`, `createBitbucketRepoCommit`, `createBitbucketRepoBranch`, `createJiraProject`, `updateJiraProject`, `createJsmRequest`, `transitionJsmRequest`.

## Slack

From `https://mcp.slack.com/mcp`, `@modelcontextprotocol/server-slack (archived)`. Server names: `slack`, `*slack*`, so tools show as `mcp__slack__<tool>`. Tool list: https://docs.slack.dev/ai/slack-mcp-server

Watch: `slack_send_message`, `slack_schedule_message`, `slack_add_reaction`, `slack_complete_file_upload`, `slack_post_message`, `slack_reply_to_thread`.

## Resend

From `resend-mcp`, `resend/mcp-send-email`. Server names: `resend`, `*resend*`, so tools show as `mcp__resend__<tool>`. Tool list: https://github.com/resend/mcp-send-email/blob/main/src/tools/emails.ts

Ask:

- `send-email`: sends an email, which cannot be unsent.
- `send-batch-emails`: sends a batch of emails, which cannot be unsent.
- `send-broadcast`: sends a broadcast to a whole audience.
- `send-new-inbox-email`: sends an email from an inbox.
- `send-inbox-draft`: sends a draft.
- `reply-to-inbox-thread-email`: sends a reply.
- `forward-inbox-thread-email`: forwards an email.
- `send-event`: sends an event that can start automations which email a contact.
- `remove-api-key`: deletes an API key, which breaks apps using it.
- `remove-domain`: deletes a sending domain.
- `remove-contact`: deletes a contact.
- `remove-segment`: deletes a segment.
- `remove-inbox`: deletes an inbox.
- `remove-inbox-thread`: deletes an email thread.
- `remove-broadcast`: deletes a broadcast.
- `remove-template`: deletes a template.
- `remove-automation`: deletes an automation.
- `remove-webhook`: deletes a webhook.
- `rotate-webhook-signing-secret`: rotates a webhook secret, which breaks receivers using the old one.
- `revoke-oauth-grant`: revokes an app's access.

Watch: `cancel-email`, `update-email`, `share-email`, `create-broadcast`, `update-broadcast`, `cancel-broadcast`, `duplicate-broadcast`, `compose-broadcast`, `create-contact`, `update-contact`, `add-contact-to-segment`, `remove-contact-from-segment`, `update-contact-topics`, `create-contact-import`, `create-segment`, `update-segment`, `create-template`, `update-template`, `publish-template`, `duplicate-template`, `compose-template`, `create-automation`, `update-automation`, `duplicate-automation`, `manage-events`, `create-domain`, `update-domain`, `verify-domain`, `create-api-key`, `update-api-key`, `create-webhook`, `update-webhook`, `replay-webhook-event`, `add-suppression`, `remove-suppression`, `batch-add-suppressions`, `batch-remove-suppressions`, `create-topic`, `update-topic`, `remove-topic`, `create-contact-property`, `update-contact-property`, `remove-contact-property`, `create-inbox`, `update-inbox`, `create-inbox-draft`, `update-inbox-draft`, `remove-inbox-draft`, `update-inbox-agent`.

## PayPal

From `paypal/agent-toolkit (its MCP toolkit)`. Server names: `paypal`, `*paypal*`, so tools show as `mcp__paypal__<tool>`. Tool list: https://github.com/paypal/agent-toolkit/blob/main/README.md

Ask:

- `pay_order`: takes payment for an order.
- `create_refund`: refunds a captured payment.
- `accept_dispute_claim`: accepts a dispute, refunding the buyer.
- `send_invoice`: sends an invoice to a customer.
- `send_invoice_reminder`: sends a reminder to a customer.
- `activate_recurring_series`: starts sending invoices on a schedule.
- `cancel_sent_invoice`: cancels an invoice a customer already has.
- `delete_invoice`: deletes a draft or scheduled invoice for good.
- `cancel_subscription`: cancels a customer's subscription.
- `cancel_recurring_series`: cancels a recurring invoice series.
- `delete_recurring_series`: deletes a draft recurring invoice series.

Watch: `create_invoice`, `update_invoicing`, `cancel_invoice_auto_reminder`, `record_payment_for_invoice`, `record_refund_for_invoice`, `create_conditional_rules_for_invoice`, `create_recurring_series`, `create_order`, `create_shipment_tracking`, `update_shipment_tracking`, `create_product`, `create_subscription_plan`, `create_subscription`, `update_subscription`, `generate_invoice_qr_code`, `generate_invoice_number`.

## Square

From `square-mcp-server`, `https://mcp.squareup.com/mcp`. Server names: `square`, `*square*`, so tools show as `mcp__square__<tool>`. Tool list: https://github.com/square/square-mcp-server/blob/main/README.md

Ask:

- `make_api_request`: charges, refunds, cancels, publishes an invoice to a customer, or deletes in Square. Only when the input matches its pattern.

## HubSpot

From `https://mcp.hubspot.com`. Server names: `hubspot`, `*hubspot*`, so tools show as `mcp__hubspot__<tool>`. Tool list: https://developers.hubspot.com/docs/apps/developer-platform/build-apps/integrate-with-the-remote-hubspot-mcp-server

Watch: `manage_crm_objects`, `manage_segment`, `manage_custom_properties`, `manage_custom_pipelines`, `manage_campaign_objects`, `manage_marketing_email`, `manage_landing_page`, `manage_website_page`, `manage_blog_post`, `manage_aeo_prompts`, `manage_aeo_recommendations`, `manage_onboarding`, `submit_feedback`.

## AWS API (awslabs)

From `awslabs.aws-api-mcp-server`. Server names: `*aws-api*`, `*aws_api*`, `awslabs*aws-api*`, `aws`, so tools show as `mcp__aws-api__<tool>`. Tool list: https://github.com/awslabs/mcp/blob/main/src/aws-api-mcp-server/README.md

Ask:

- `call_aws`: runs an AWS CLI command that deletes, terminates, revokes or turns something off. Only when the input matches its pattern.

## HCP Terraform and Terraform Enterprise

From `hashicorp/terraform-mcp-server`. Server names: `terraform`, `*terraform*`, so tools show as `mcp__terraform__<tool>`. Tool list: https://github.com/hashicorp/terraform-mcp-server/blob/main/pkg/tools/tfe/action_run.go

Ask:

- `action_run`: approves and applies a Terraform run. Only when the input matches its pattern.
- `create_run`: starts a destroy run, or a run that applies without review. Only when the input matches its pattern.
- `delete_workspace_safely`: deletes a workspace.
- `delete_project`: deletes a project.
- `delete_team`: deletes a team with its memberships and access.

Watch: `force_unlock_workspace`, `create_workspace`, `create_no_code_workspace`, `update_workspace`, `create_project`, `create_team`, `add_team_member`, `grant_team_access`, `attach_policy_set_to_workspaces`, `create_variable_set`, `create_variable_in_variable_set`, `delete_variable_in_variable_set`, `attach_variable_set_to_workspaces`, `detach_variable_set_from_workspaces`, `create_workspace_variable`, `update_workspace_variable`, `create_workspace_tags`.

## Redis

From `redis/mcp-redis`, `redis-mcp-server`. Server names: `redis`, `*redis*`, so tools show as `mcp__redis__<tool>`. Tool list: https://github.com/redis/mcp-redis/blob/main/src/tools/misc.py

Ask:

- `delete`: deletes a key.
- `json_del`: deletes a JSON value, the whole document by default.
- `xgroup_destroy`: destroys a stream consumer group.

Watch: `expire`, `rename`, `set`, `hset`, `hdel`, `json_set`, `lpush`, `rpush`, `lpop`, `rpop`, `lrem`, `sadd`, `srem`, `zadd`, `zrem`, `xadd`, `xdel`, `xgroup_create`, `xack`, `set_vector_in_hash`, `create_vector_index_hash`, `publish`.

## Grafana

From `grafana/mcp-grafana`. Server names: `grafana`, `*grafana*`, so tools show as `mcp__grafana__<tool>`. Tool list: https://github.com/grafana/mcp-grafana/blob/main/README.md

Ask:

- `delete_snapshot`: deletes a dashboard snapshot, so its shared link stops working.

Watch: `delete_annotation`, `alerting_rules_write`, `alerting_silences_write`, `alerting_manage_routing`, `alerting_routing_write`, `update_alert_group`, `grafana_api_request`, `update_dashboard`, `create_folder`, `create_datasource`, `update_datasource`, `create_incident`, `update_incident`, `add_activity_to_incident`, `create_annotation`, `update_annotation`, `create_snapshot`, `install_plugin`.

## Read only, nothing to rate

- MCP reference Postgres server (`@modelcontextprotocol/server-postgres`, archived). Its one tool, `query`, runs in a read-only transaction. https://github.com/modelcontextprotocol/servers-archived/blob/main/src/postgres/README.md
- MCP reference Google Drive server (`@modelcontextprotocol/server-gdrive`, archived). Its one tool, `search`, only reads. https://github.com/modelcontextprotocol/servers-archived/blob/main/src/gdrive/README.md

## Not covered

These servers have no ratings, because their exact tool names could not be read.

- Linear (`https://mcp.linear.app/mcp`). The docs explain setup but publish no tool list, and the server lists its tools only after sign-in.
- Shopify. The Dev MCP repository named in its docs was not found, and each store's Storefront MCP lists its own tools.
- Slack's official server, for canvases, channels and lists. Slack's docs name those tools in words only. Its message tools are rated, from Slack's own plugin repository.
- Cloudflare's API server with code mode off. It makes one tool for each of about 2,500 API endpoints, generated at run time.
- PlanetScale's tools generated from its API specification. Only the curated tools in its docs are rated.
- AWS servers other than the AWS API server. awslabs publishes dozens; none of the others were read for this version.
- HubSpot's publish actions. `manage_landing_page`, `manage_website_page` and `manage_blog_post` can publish, but the input field that chooses it is not documented, so they are rated `watch`.
- Grafana's `grafana_api_request`, `alerting_rules_write` and `alerting_silences_write` can delete rules or mute alerts, but their input fields are not documented, so they are rated `watch`.

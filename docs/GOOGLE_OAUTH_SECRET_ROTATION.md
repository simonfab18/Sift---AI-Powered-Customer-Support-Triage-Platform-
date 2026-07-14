# Google OAuth Client Secret Rotation

The Gmail OAuth web client used by the app is the standard Google Cloud OAuth client under **APIs & Services > Credentials**. It is not exposed through the installed `gcloud iam oauth-clients` commands, which manage a newer IAM OAuth client type with limited Google Cloud identity scopes. Because this app requires Gmail scopes, the client secret reset must be initiated in Google Cloud Console.

Current staging OAuth client ID:

```text
1019789305707-7j85gebr9dd6o16iiqphddijk4k2mqnh.apps.googleusercontent.com
```

Current staging redirect URI:

```text
https://sift-api-staging-1019789305707.asia-southeast1.run.app/v1/gmail/oauth/callback
```

## Console Step

1. Open Google Cloud Console for project `customer-support-triage-501408`.
2. Go to **APIs & Services > Credentials**.
3. Open the OAuth 2.0 Client ID matching the staging client ID above.
4. Reset or create a new client secret for that OAuth client.
5. Save the new secret into a temporary local file at `C:\tmp\sift-google-client-secret-rotation.txt`.

Do not paste the secret into chat or commit it to the repository.

## Operator Commands After Console Reset

Run these from PowerShell after the new secret is in the temporary file:

```powershell
$secretFile = 'C:\tmp\sift-google-client-secret-rotation.txt'
& 'C:\Users\stanl\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' secrets versions add sift-staging-google-client-secret --project customer-support-triage-501408 --data-file=$secretFile
Remove-Item -LiteralPath $secretFile -Force

& 'C:\Users\stanl\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' run deploy sift-api-staging --project customer-support-triage-501408 --region asia-southeast1 --image asia-southeast1-docker.pkg.dev/customer-support-triage-501408/cloud-run-source-deploy/sift-api-staging@sha256:13e2ba700d012d84440393900a66cf4c929e50cef82e5d35c84bed7ccb287df1 --allow-unauthenticated

Invoke-WebRequest -Uri 'https://sift-api-staging-1019789305707.asia-southeast1.run.app/health/ready' -UseBasicParsing
```

## Verification

After the Cloud Run restart:

1. Start Gmail OAuth from the Vercel app.
2. Complete Google consent with a test inbox.
3. Confirm the app returns to the Gmail settings page with the connection active.
4. Confirm Gmail watch status becomes active.
5. Run a manual import or history sync for the test inbox.

Only after this passes, disable the older Secret Manager version:

```powershell
& 'C:\Users\stanl\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' secrets versions list sift-staging-google-client-secret --project customer-support-triage-501408
& 'C:\Users\stanl\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' secrets versions disable <OLD_VERSION_NUMBER> --secret sift-staging-google-client-secret --project customer-support-triage-501408 --quiet
```

## Current Status

As of 2026-07-13, staging Cloud Run reads `GOOGLE_CLIENT_SECRET` from `sift-staging-google-client-secret:latest`. Secret Manager version `2` contains the new OAuth client secret, Gmail OAuth reconnect has succeeded, and version `1` is disabled. The old OAuth client secret `****7Xgv` has been disabled in Google Cloud Console.

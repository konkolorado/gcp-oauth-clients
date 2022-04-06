Class based OAuth2 Clients for Google Cloud Platform

## Installation

```console
pip install gcp-oauth-clients
```

## 3 legged OAuth2 / Native Clients

For convenient 3-legged OAuth, you can create a client which will automatically
receive the GCP redirect containing its response code and automatically exchange
that for tokens on your behalf:

```python
import requests

from gcp_oauth_clients import GcpNativeClient

# Instantiate a new client in server mode to automatically 
# handle redirects
gcpc = GcpNativeClient(
    "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "YOUR_CLIENT_SECRET",
    redirect_method="server",
)

# Begin a new login, supplying the desired scope or scopes
with gcpc.new_login("openid"):
    print(f"Please visit this url in a browser: {gcpc.authentication_url}")
    tokens = gcpc.exchange_authorization_code_for_tokens()

# Use the tokens to access the GCP APIs
r = requests.get(
    "https://www.googleapis.com/oauth2/v2/userinfo",
    headers={"Authorization": f"Bearer {tokens.access_token}"},
)
print(r.status_code, r.json())
```

If you are unable to (or don't want to) receive local network connections, you
can perform a manual copy-paste of the GCP code in order to exchange that for tokens:

```python
import requests

from gcp_oauth_clients import GcpNativeClient

# Instantiate a new client
gcpc = GcpNativeClient(
    "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "YOUR_CLIENT_SECRET",
)

# Begin a new login, supplying the desired scope or scopes
with gcpc.new_login("openid"):
    print(f"Please visit this url in a browser: {gcpc.authentication_url}")
    code = input("Give code here: ")
    tokens = gcpc.exchange_authorization_code_for_tokens(code)

# Use the tokens to access the GCP APIs
r = requests.get(
    "https://www.googleapis.com/oauth2/v2/userinfo",
    headers={"Authorization": f"Bearer {tokens.access_token}"},
)
print(r.status_code, r.json())
```

## 2 legged OAuth2 / Confidential Clients

A Confidential Client class is provided to facilitate server-to-server
communication via a service account. Use this method for non-interactive applications:

```python
import requests

from gcp_oauth_clients import GcpConfidentialClient

# Instantiate a new client
gcpcc = GcpConfidentialClient(
    "service-account-name@ogcp-project.iam.gserviceaccount.com",
    "-----BEGIN PRIVATE ...-----END PRIVATE KEY-----\n",
)

# Begin a new login, supplying the desired scope or scopes
with gcpcc.new_login("https://www.googleapis.com/auth/drive"):
    tokens = gcpcc.get_tokens()

# Use the tokens to access the GCP APIs
r = requests.get(
    "https://www.googleapis.com/drive/v2/files",
    headers={"Authorization": f"Bearer {tokens.access_token}"},
)
print(r.status_code, r.json())
```

## IAP Protected Resources

There are two clients available to facilitate access to IAP protected APIs, the
`IapServiceAccountClient` and the `IapNativeClient`. The difference between the
two is that the `IapNativeClient` facilitates interactively authenticating a 
user on a laptop whereas the `IapServiceAccountClient` non-interactively
authenticates a service account using its client secret.

The `IapNativeClient` requires the ability to start a local server that can
receive a redirect request from Google. Google does not support the copy-paste
method available on the GcpNativeClient:

```python
import requests

from gcp_oauth_clients import IapNativeClient

# Instantiate a new client using an OAuth client with IAP access
iapnc = IapNativeClient(
    "iap-enabled-native-oauth-client-id",
    "iap-enabled-mative-oauth-client-secret",
)

# Begin a new login, note that no scopes are supplied
with iapnc.new_login():
    print(f"Go here: {iapnc.authentication_url}")
    oauth_tokens = iapnc.exchange_authorization_code_for_tokens()
    assert oauth_tokens.refresh_token

# After logging in, exchange the refresh token for an OIDC token specifying 
# the IAP-secured resource's OAuth client ID
oidc_tokens = iapnc.oidc_token_for_iap_client(
    oauth_tokens.refresh_token,
    "iap-secured-resources-oauth-client_id",
)

# Use the OIDC token to access the IAP-secured resource
resp = requests.get(
    "https://iap-resource-url/",
    headers={"Authorization": f"Bearer {oidc_tokens.id_token}"},
)
print(resp.status_code, resp.json())
```

To use the `IapServiceAccountClient` class, you need access to the service
account's id, email, private key id, and its private key. There's a class method
to help parse this information from the downloaded key file:

```python
import requests

from gcp_oauth_clients import IapServiceAccountClient

# Instantiate a new client using an OAuth client with IAP access
iapsc = IapServiceAccountClient.from_key_file("/path/to/keyfile.json")

# Request an OIDC token for the IAP-secured resource's OAuth client
oidc_tokens = iapnc.oidc_token_for_iap_client(
    "iap-secured-resources-oauth-client_id",
)

# Use the OIDC token to access the IAP-secured resource
resp = requests.get(
    "https://iap-resource-url/",
    headers={"Authorization": f"Bearer {oidc_tokens.id_token}"},
)
print(resp.status_code, resp.json())
```

## Resources
- https://cloud.google.com/iap/docs/authentication-howto
- https://developers.google.com/identity/protocols/oauth2
- https://developers.google.com/identity/protocols/oauth2/scopes
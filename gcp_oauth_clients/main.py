import logging

import requests

from gcp_oauth_clients import GcpNativeClient

# logging.basicConfig(level=logging.DEBUG)


def server_mode():
    gcpc = GcpNativeClient(
        "490256184949-toaq9ulppmgkai74g0amrandlrb6ts7v.apps.googleusercontent.com",
        "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",
        redirect_method="server",
    )
    with gcpc.new_login("openid"):
        url = gcpc.get_authentication_url()
        print(url)
        tokens = gcpc.exchange_authorization_code_for_tokens()
        print(tokens)

    r = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )
    print(r.status_code, r.json())

    r = requests.get(
        "https://www.googleapis.com/userinfo/v2/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )
    print(r.status_code, r.json())


def cli_mode():
    gcpc = GcpNativeClient(
        "490256184949-toaq9ulppmgkai74g0amrandlrb6ts7v.apps.googleusercontent.com",
        "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",
    )
    with gcpc.new_login("openid"):
        url = gcpc.get_authentication_url()
        print(url)
        code = input("Give code here: ")
        tokens = gcpc.exchange_authorization_code_for_tokens(code)
        print(tokens)

    r = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )
    print(r.status_code, r.json())

    r = requests.get(
        "https://www.googleapis.com/userinfo/v2/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )
    print(r.status_code, r.json())


server_mode()

from __future__ import annotations

import os
from collections.abc import Sequence

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account

import config


def get_credentials(scopes: Sequence[str]):
    service_account_file = getattr(config, "SERVICE_ACCOUNT_FILE", "")

    try:
        credentials, _ = google.auth.default(scopes=list(scopes))
        return credentials
    except DefaultCredentialsError as exc:
        if service_account_file and os.path.exists(service_account_file):
            return service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=list(scopes),
            )
        raise RuntimeError(
            "Google 인증 정보를 찾을 수 없습니다. "
            "`gcloud auth application-default login`으로 로그인했는지 확인해주세요."
        ) from exc

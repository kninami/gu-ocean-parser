from __future__ import annotations

import os
from collections.abc import Sequence
from contextvars import ContextVar

import google.auth
from google.auth import identity_pool
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account

import settings

_request_oidc_token: ContextVar[str | None] = ContextVar(
    "request_oidc_token",
    default=None,
)


def set_request_oidc_token(token: str | None) -> None:
    _request_oidc_token.set(token.strip() if token else None)


def _get_current_oidc_token() -> str | None:
    return _request_oidc_token.get() or os.getenv("VERCEL_OIDC_TOKEN")


class _VercelOIDCTokenSupplier(identity_pool.SubjectTokenSupplier):
    def get_subject_token(self, context, request):
        token = _get_current_oidc_token()
        if not token:
            raise DefaultCredentialsError(
                "Vercel OIDC 토큰을 찾을 수 없습니다. "
                "`x-vercel-oidc-token` 헤더 또는 `VERCEL_OIDC_TOKEN` 환경변수를 확인해주세요."
            )
        return token


def _get_vercel_wif_credentials(scopes: Sequence[str]):
    project_number = os.getenv("GCP_PROJECT_NUMBER")
    service_account_email = os.getenv("GCP_SERVICE_ACCOUNT_EMAIL")
    pool_id = os.getenv("GCP_WORKLOAD_IDENTITY_POOL_ID")
    provider_id = os.getenv("GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID")
    oidc_token = _get_current_oidc_token()

    if not all([project_number, service_account_email, pool_id, provider_id, oidc_token]):
        return None

    audience = (
        f"//iam.googleapis.com/projects/{project_number}"
        f"/locations/global/workloadIdentityPools/{pool_id}/providers/{provider_id}"
    )
    impersonation_url = (
        "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
        f"{service_account_email}:generateAccessToken"
    )

    return identity_pool.Credentials(
        audience=audience,
        subject_token_type="urn:ietf:params:oauth:token-type:jwt",
        token_url="https://sts.googleapis.com/v1/token",
        subject_token_supplier=_VercelOIDCTokenSupplier(),
        service_account_impersonation_url=impersonation_url,
        quota_project_id=os.getenv("GCP_PROJECT_ID"),
        scopes=list(scopes),
    )


def get_credentials(scopes: Sequence[str]):
    service_account_file = getattr(settings, "SERVICE_ACCOUNT_FILE", "")
    vercel_credentials = _get_vercel_wif_credentials(scopes)

    if vercel_credentials is not None:
        return vercel_credentials

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
            "`gcloud auth application-default login`으로 로그인했는지 확인하거나 "
            "Vercel OIDC Workload Identity Federation 환경변수를 설정해주세요."
        ) from exc

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class JsonResponse:
    status: int
    body: Any


def post_json(url, payload, *, service_key, request_id):
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Mesa-Service-Key": service_key,
            "X-Request-ID": request_id,
        },
    )

    try:
        with build_opener(NoRedirect).open(request, timeout=2) as response:
            return JsonResponse(response.status, json.load(response))
    except HTTPError as error:
        with error:
            try:
                body = json.load(error)
            except ValueError:
                body = None

            return JsonResponse(error.code, body)

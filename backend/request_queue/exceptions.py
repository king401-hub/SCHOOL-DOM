"""Exceptions a request_type handler can raise to control queue behavior.

Anything else the handler raises is treated as a non-retriable failure.
"""


class RetriableRequestError(Exception):
    """Transient failure (timeout, network error, 5xx from a provider) -
    the queue will retry this request with exponential backoff."""


class RequestRejectedError(Exception):
    """Permanent business-rule failure (invalid account, insufficient
    balance, etc.) - the queue marks the request rejected and never retries."""

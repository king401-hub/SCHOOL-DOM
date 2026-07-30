"""Maps a request_type string to the handler that processes it.

A handler is `handler(queued_request) -> JSON-serializable result`. It must
raise request_queue.exceptions.RetriableRequestError for transient failures
(will be retried with backoff) or RequestRejectedError for permanent
business-rule failures (never retried). Any other exception is treated as a
non-retriable failure too, but is logged as an unexpected error.

Imported lazily (dotted path, resolved on first use) so this module never
has to import finance/hr/users at Django app-loading time.
"""

REQUEST_TYPE_REGISTRY = {
    "wallet_withdrawal": {
        "handler": "finance.queue_handlers.handle_wallet_withdrawal",
        "max_retries": 5,
        "expiry_hours": 24,
    },
}


def get_defaults(request_type):
    return REQUEST_TYPE_REGISTRY.get(request_type, {})


def get_handler(request_type):
    import importlib

    config = REQUEST_TYPE_REGISTRY.get(request_type)
    if not config:
        raise KeyError(f"No handler registered for request_type '{request_type}'.")
    module_path, func_name = config["handler"].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)

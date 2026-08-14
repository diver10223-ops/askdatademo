import os


# Credential-free test value; production code has no fallback token.
os.environ["ASKDATA_INTERNAL_SERVICE_TOKEN"] = "askdata-test-service-token-32-bytes-minimum"

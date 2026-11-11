BUSINESS_REJECTIONS = {
    "feature_disabled": 403,
    "configuration_changed": 409,
    "catalog_changed": 409,
    "price_changed": 409,
    "product_unavailable": 409,
    "idempotency_conflict": 409,
}


def is_business_rejection(error):
    return BUSINESS_REJECTIONS.get(error.code) == error.status

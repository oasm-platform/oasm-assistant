from uuid import UUID

# OASM System Model Configurations
OASM_MODELS = [
    {
        "id": "cyber-1.0-flash",
        "name": "Cyber 1.0 Flash",
        "provider": "oasm",
        "description": "Built-in OASM security specialized model (Gemini 1.5 Flash).",
        "is_active": True,
        "is_recommended": True,
        "api_key": "built-in",
        "internal_model": "gemini-1.5-flash"
    },
    {
        "id": "cyber-1.0-pro",
        "name": "Cyber 1.0 Pro",
        "provider": "oasm",
        "description": "High-performance OASM security reasoning model (Gemini 1.5 Pro).",
        "is_active": True,
        "is_recommended": False,
        "api_key": "built-in",
        "internal_model": "gemini-1.5-pro"
    }
]

# System-level ID prefix for OASM models to distinguish them from user-created ones
# This helps in preventing deletion/editing of system models on the frontend
SYSTEM_CONFIG_ID_PREFIX = "00000000-0000-0000-0000-"

from .configs import Configs, EmbeddingConfigs, LlmConfigs, PostgresConfigs, AppConfigs

configs = Configs()

__doc__ = "Configs for the application"

__all__ = ["configs", "EmbeddingConfigs", "LlmConfigs", "PostgresConfigs", "AppConfigs"]
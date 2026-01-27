from .configs import Configs, EmbeddingConfigs, LlmConfigs, PostgresConfigs

configs = Configs()

__doc__ = "Configs for the application"

__all__ = ["configs", "EmbeddingConfigs", "LlmConfigs", "PostgresConfigs"]
"""
Assess embedding quality based on statistical and semantic metrics.
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import euclidean


class EmbeddingQualityAssessor:
    """
    Class to assess the quality of embeddings.
    """

    @staticmethod
    def compute_cosine_similarity(embeddings: np.ndarray) -> float:
        """
        Compute the average pairwise cosine similarity between embeddings.

        Args:
            embeddings (np.ndarray): 2D array of shape (n_samples, embedding_dim).

        Returns:
            float: Average cosine similarity.
        """
        if embeddings.shape[0] < 2:
            raise ValueError("At least two embeddings are required for similarity computation.")

        # Compute pairwise cosine similarity
        similarity_matrix = cosine_similarity(embeddings)
        # Exclude diagonal (self-similarity)
        upper_triangle = similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)]
        return np.mean(upper_triangle)

    @staticmethod
    def compute_embedding_variance(embeddings: np.ndarray) -> float:
        """
        Compute the variance of the embeddings.

        Args:
            embeddings (np.ndarray): 2D array of shape (n_samples, embedding_dim).

        Returns:
            float: Variance of the embeddings.
        """
        return np.var(embeddings, axis=0).mean()

    @staticmethod
    def compute_nearest_neighbor_distance(embeddings: np.ndarray) -> float:
        """
        Compute the average distance to the nearest neighbor for each embedding.

        Args:
            embeddings (np.ndarray): 2D array of shape (n_samples, embedding_dim).

        Returns:
            float: Average nearest neighbor distance.
        """
        if embeddings.shape[0] < 2:
            raise ValueError("At least two embeddings are required for nearest neighbor computation.")

        distances = []
        for i, emb in enumerate(embeddings):
            other_embeddings = np.delete(embeddings, i, axis=0)
            nearest_distance = min(euclidean(emb, other) for other in other_embeddings)
            distances.append(nearest_distance)
        return np.mean(distances)

    def assess(self, embeddings: np.ndarray) -> dict:
        """
        Assess the quality of embeddings using multiple metrics.

        Args:
            embeddings (np.ndarray): 2D array of shape (n_samples, embedding_dim).

        Returns:
            dict: Dictionary containing quality metrics.
        """
        return {
            "average_cosine_similarity": self.compute_cosine_similarity(embeddings),
            "embedding_variance": self.compute_embedding_variance(embeddings),
            "average_nearest_neighbor_distance": self.compute_nearest_neighbor_distance(embeddings),
        }


# Example usage
if __name__ == "__main__":
    # Example embeddings (replace with actual embeddings)
    example_embeddings = np.array([
        [0.1, 0.2, 0.3],
        [0.2, 0.1, 0.4],
        [0.3, 0.3, 0.3],
    ])

    assessor = EmbeddingQualityAssessor()
    metrics = assessor.assess(example_embeddings)
    print("Embedding Quality Metrics:")
    for metric, value in metrics.items():
        print(f"{metric}: {value:.4f}")
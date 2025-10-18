"""
Utilities for score normalization and manipulation
"""
from typing import List


def normalize_scores(scores: List[float]) -> List[float]:
    """
    Normalize scores to [0, 1] range using min-max normalization

    Args:
        scores: List of scores to normalize

    Returns:
        List of normalized scores
    """
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [1.0] * len(scores)

    return [(s - min_score) / (max_score - min_score) for s in scores]


def combine_scores(
    score1: float,
    score2: float,
    weight1: float = 0.5,
    weight2: float = 0.5
) -> float:
    """
    Combine two scores with given weights

    Args:
        score1: First score
        score2: Second score
        weight1: Weight for first score (default: 0.5)
        weight2: Weight for second score (default: 0.5)

    Returns:
        Combined score
    """
    return weight1 * score1 + weight2 * score2

"""
Coffee Flavor Categories
========================

Reference flavor hierarchy structure based on the SCA Coffee Taster's Flavor Wheel.

This module contains the standard 9-category inner layer classification system
used for coffee flavor profiling and sensory analysis.
"""

from typing import Dict, List


# Inner layer: 9 broad flavor categories
INNER_CATEGORIES: List[str] = [
    "floral",
    "fruity",
    "sour/fermented",
    "green/vegetable",
    "defected",
    "roasted",
    "spices",
    "nutty/cocoa",
    "sweet",
]

# Example sub-categories for reference
# These represent common flavor descriptors under each main category
CATEGORY_EXAMPLES: Dict[str, List[str]] = {
    "floral": [
        "jasmine",
        "rose",
        "chamomile",
        "lavender",
        "tea-like",
        "black tea",
    ],
    "fruity": [
        "berry",
        "blueberry",
        "strawberry",
        "raspberry",
        "blackberry",
        "citrus fruit",
        "lemon",
        "orange",
        "grapefruit",
        "stone fruit",
        "peach",
        "apricot",
        "plum",
        "cherry",
        "tropical fruit",
        "mango",
        "pineapple",
        "papaya",
        "dried fruit",
        "raisin",
        "prune",
    ],
    "sour/fermented": [
        "sour",
        "acetic acid",
        "lactic acid",
        "citric acid",
        "malic acid",
        "alcohol",
        "fermented",
        "winey",
    ],
    "green/vegetable": [
        "olive oil",
        "raw",
        "green",
        "beany",
        "fresh vegetable",
        "cucumber",
        "celery",
        "dried vegetable",
        "hay",
    ],
    "defected": [
        "papery",
        "musty",
        "dusty",
        "earthy",
        "moldy",
        "chemical",
        "medicinal",
        "petroleum",
        "rubber",
    ],
    "roasted": [
        "pipe tobacco",
        "tobacco",
        "burnt",
        "acrid",
        "ashy",
        "smoky",
        "cereal",
        "grain",
        "malt",
    ],
    "spices": [
        "pungent",
        "pepper",
        "black pepper",
        "white pepper",
        "brown spice",
        "clove",
        "cinnamon",
        "nutmeg",
        "anise",
    ],
    "nutty/cocoa": [
        "nutty",
        "almond",
        "hazelnut",
        "walnut",
        "peanut",
        "cocoa",
        "chocolate",
        "dark chocolate",
    ],
    "sweet": [
        "brown sugar",
        "molasses",
        "maple syrup",
        "caramel",
        "vanilla",
        "vanillin",
        "honey",
        "butterscotch",
        "sweet aromatics",
        "butter",
        "milky",
        "cream",
    ],
}


def get_category_for_descriptor(descriptor: str) -> str:
    """
    Find which main category a flavor descriptor belongs to.

    Args:
        descriptor: Flavor descriptor name

    Returns:
        Category name, or "unknown" if not found

    Example:
        >>> get_category_for_descriptor("jasmine")
        'floral'
        >>> get_category_for_descriptor("berry")
        'fruity'
    """
    descriptor_lower = descriptor.lower()
    for category, examples in CATEGORY_EXAMPLES.items():
        if descriptor_lower in [ex.lower() for ex in examples]:
            return category
    return "unknown"


def list_all_descriptors() -> List[str]:
    """
    Get a flat list of all example flavor descriptors.

    Returns:
        List of all descriptor names across all categories

    Example:
        >>> descriptors = list_all_descriptors()
        >>> len(descriptors)
        110+
    """
    all_descriptors = []
    for examples in CATEGORY_EXAMPLES.values():
        all_descriptors.extend(examples)
    return sorted(set(all_descriptors))

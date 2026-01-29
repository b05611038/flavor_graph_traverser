"""Setup configuration for FlavorGraphTraverser package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="FlavorGraphTraverser",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool for traversing coffee flavor hierarchies as directed acyclic graphs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/flavor_graph_traverser",
    packages=find_packages(exclude=["tests", "reference_code"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.19.0,<2.0.0",
        "python-igraph>=0.10.0,<1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
    },
)

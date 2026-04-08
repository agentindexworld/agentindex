from setuptools import setup, find_packages

setup(
    name="agentindex-trust",
    version="1.0.0",
    description="Save 30% on API costs. Earn $TRUST. Get a Bitcoin passport. All automatically.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="AgentIndex",
    author_email="comallagency@gmail.com",
    url="https://agentindex.world",
    packages=find_packages(),
    install_requires=["requests>=2.28.0"],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="ai agent trust reputation bitcoin verification cache",
    entry_points={
        "console_scripts": [
            "agentindex=agentindex_trust.cli:main",
        ],
    },
)

from setuptools import setup, find_packages

setup(
    name="entigram-ai",
    version="0.2.1",
    description="Schema-first semantic governance layer for enterprise agents",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Entigram Authors",
    author_email="dickens.nyabuti@gmail.com",
    url="https://api.entigram.ai",
    project_urls={
        "Source": "https://github.com/nyabutid/entigram",
        "Documentation": "https://api.entigram.ai",
        "Tracker": "https://github.com/nyabutid/entigram/issues",
    },
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "streamlit>=1.35.0",
        "pysqlite3",
        "pyyaml",
        "networkx",
        "inflect",
        "protobuf>=5.26.1",
        "requests"
    ],
    entry_points={
        "console_scripts": [
            "entigram=entigram.cli_runner.etg_cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)

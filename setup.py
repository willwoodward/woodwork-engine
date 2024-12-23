from setuptools import setup, find_packages

setup(
    packages=find_packages(where="."),
    package_dir={"": "."},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "woodwork=woodwork.__main__:main",
        ],
    },
    python_requires=">=3.10",
)

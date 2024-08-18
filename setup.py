from setuptools import setup, find_packages

setup(
    name='woodwork',
    version='0.0.1',
    packages=find_packages(where='.'),
    package_dir={'': '.'},
    entry_points={
        'console_scripts': [
            'woodwork=woodwork.__main__:main',
        ],
    },
)
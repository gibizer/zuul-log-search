from setuptools import setup

with open("requirements.txt") as f:
    requirements = f.read().splitlines()


setup(
    name="zuul-log-search",
    version="0.1",
    description="Search the logs of a Zuul deployment",
    url="https://github.com/gibizer/zuul-log-search",
    author="Balazs Gibizer",
    author_email="gibizer@gmail.com",
    license="Apache License 2.0",
    packages=['logsearch'],
    zip_safe=False,
    install_requires=requirements,
    entry_points={
        'console_scripts': ['logsearch=logsearch.main:main'],
    }
)

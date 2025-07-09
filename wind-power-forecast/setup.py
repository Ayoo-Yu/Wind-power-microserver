from setuptools import setup, find_packages

setup(
    name="wind_power_forecast",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'flask',
        'minio',
        'sqlalchemy'
    ]
) 
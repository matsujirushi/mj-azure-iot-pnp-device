from setuptools import setup, find_packages

setup(
    name='mj-azure-iot-pnp-device',
    version='0.5',
    description='Assist IoT Plug and Play Library for the Azure IoT Device SDK for Python',
    license='MIT License',
    url='https://github.com/matsujirushi/mj-azure-iot-pnp-device',
    author='Takashi Matsuoka (matsujirushi)',
    author_email='matsujirushi@live.jp',
    classifiers=[
        "Programming Language :: Python :: 3.8",
    ],
    install_requires=[
        "azure-iot-device>=2.5.1"
    ],
    packages=find_packages(
        exclude=[
            "samples",
            "samples.*",
        ]
    ),
)

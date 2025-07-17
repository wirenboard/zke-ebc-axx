from setuptools import find_packages, setup

setup(
    name="zke_ebc_axx",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyserial>=3.4",
    ],
    author="Board Developer",
    author_email="developer@example.com",
    description="Python package for ZKE EBC-Axx electronic loads and battery testers",
    keywords="electronic load, battery tester, ZKE, EBC-Axx",
    url="https://github.com/yourusername/zke_ebc_axx",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering",
    ],
    python_requires=">=3.6",
)

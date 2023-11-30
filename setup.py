# setup.py

from setuptools import setup, find_packages

setup(
    name='prompt_block',
    version='0.1',
    packages=find_packages(),
    description='Faster way to write long prompts.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Contentify AI',
    author_email='hi@contentify.app',
    url='https://github.com/alphatrait/prompt-block',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)

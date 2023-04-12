# LoST Protocol Reimagined

The Location-to-Service Translation (LoST) protocol [RFC 5222](https://www.rfc-editor.org/rfc/rfc5222.html) has been originally designed for emergency (911) calling services. The protocol provides a mapping service that translates the client's location, represented with a longitude and latitude pair, to a public safety answering point (PSAP), i.e., a call center, that provides emergency services at the client's location. The protocol was developed as part of the next-generation IP-based emergency calling architecture and has been standardized by the IETF.

Mapping geographic information to related services is a more general problem with applicability beyond emergency calling. For example, geographically-dispersed cyber-physical systems often need to discover services appropriate for a particular area, location, or geographic feature. The goal of this project is to evolve the LoST protocol framework to support applications beyond emergency calling.

## Installation

Please make sure you have a recent version of Python 3, preferably Python 3.9 or newer. Clone the repository into a local folder and enter the folder:
```
git clone https://github.com/irtlab/lost
cd lost
```
Create a Python virtual environment in the folder `.venv` and activate it:
```
python -m venv .venv
. .venv/bin/activate
```
Install the lost package in editable mode:
```
pip install -e .
```

# LoST Protocol Reimagined

The Location-to-Service Translation (LoST) protocol [[RFC 5222]](https://www.rfc-editor.org/rfc/rfc5222.html) has been originally designed for emergency (911) calling services. The protocol provides a mapping service that translates the client's location, represented with a longitude and latitude pair, to a public safety answering point (PSAP) that provides emergency services at the client's location. The protocol was developed as part of the next-generation IP-based emergency calling architecture and has been standardized by the IETF. Mapping geographic information to related services is a more general problem with applicability beyond emergency calling. For example, geographically-dispersed cyber-physical systems often need to discover services appropriate for a particular area, location, or geographic feature. This project aims to evolve and generalize the LoST protocol framework for applications beyond emergency calling.

This repository contains the software used to prototype various LoST protocol entities.

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
Set the connection string for your PostgreSQL database in an environment variable DB_URL:
```
export DB_URL="host=<host> user=lostsrv password=<password> sslmode=require dbname=lost"
```
Run the LoST server. The server will listen on the loopback interface (127.0.0.1) and port 5000 by default:
```
lost-server
```
Use the lost-seeker program to send a LoST request to the server. To send a point use:
```
lost-seeker find-service -- lost -73.96094 40.80965
```
To send a polygon from a GeoJSON file use:
```
lost-seeker find-service -- lost data/cepsr-intersect.geojson
```

import sys
import click
from .. import db
from .. import osm
from . import LoSTResolver, create_app, resolver
from flask import request, Response, Flask
import requests
from lxml import etree, objectify
import os
from ..  import LOST_MIME_TYPE, LOST_NAMESPACE, NAMESPACE_MAP

app = Flask(__name__)

@app.route('/', methods=['POST'])
def handler():
    server_url = 'http://localhost:5000'
    xml_data = request.data
    
    while True:
        response = requests.post(server_url, data=xml_data, headers={'Content-Type': LOST_MIME_TYPE})
        
        if response.status_code == 200:
            tree = etree.fromstring(response.content)
            ns = {'lost2': 'urn:ietf:params:xml:ns:lost2'}
            redirect_element = tree.xpath('//lost2:redirect', namespaces=ns)

            if redirect_element:
                server_url = redirect_element[0].get('target')
                print(f"Redirect found, redirected to {server_url}")
            else:
                print("Leaf node.")
                break
        else:
            print(f"Error: Received status code {response.status_code}")
            break

    return Response(response.content, mimetype=LOST_MIME_TYPE)

if __name__ == '__main__':
    app.run(debug=True)

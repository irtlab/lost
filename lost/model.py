from __future__ import annotations
import sys
import click
import json
import os.path
import osm2geojson
from jinja2 import Environment
from .osm import search_overpass_by_id, extract_boundary


DATA_DIR=os.path.realpath(os.path.join(os.path.dirname(__file__), '../data'))


class PortGenerator:
    current: int
    def __init__(self, base=1024):
        self.current = base

    def next(self):
        self.current = self.current + 1
        return self.current

    def setBase(self, base):
        self.current = base


def build_path(comps):
    return os.path.relpath(os.path.abspath(os.path.join(*comps)), start='/')


def traverse(name: str, node: dict, ports: PortGenerator | None = None, path=['/'], parent={}):
    node = node.copy()
    path = path.copy()
    attrs = parent.copy()
    attrs.update(node)
    parent = parent.copy()

    if ports is not None:
        if node.get('$port') is not None:
            ports.setBase(node['$port'])
        else:
            attrs['$port'] = ports.next()

    if node.get('$path') is not None:
        path.append(node['$path'])

    attrs['$path'] = build_path(path)

    yield name, node, attrs

    if node.get('children') is not None:
        for k, n in node['children'].items():
            for s in traverse(k, n, ports, path, attrs):
                yield s



@click.group(help='LoST model')
@click.pass_context
@click.option('--model', '-m', envvar='MODEL', default=f'{DATA_DIR}/model.json', help='JSON model file')
@click.option('--url-prefix', '-u', envvar='URL_PREFIX', default='https://www.openstreetmap.org')
def cli(ctx, model, url_prefix):
    click.echo(f'Loading model file {model}...')
    with open(model, 'r') as f:
        data = json.load(f)

    ctx.ensure_object(dict)
    ctx.obj['model'] = data
    ctx.obj['url_prefix'] = url_prefix


@cli.command(help='Generate Docker compose file')
@click.option('--template', '-t', envvar='TEMPLATE', default=f'{DATA_DIR}/compose.yml.jinja2', help='Compose YAML template')
@click.option('--output', '-o', envvar='OUTPUT', default=f'{DATA_DIR}/compose.yml', help='Compose YAML file')
@click.pass_obj
def compose(obj, template, output):
    ports = PortGenerator()
    env = Environment(autoescape=False, trim_blocks=True)

    def servers(name='World', current=obj['model'], path=['/'], parent={}):
        for name, node, attrs in traverse(name, current, ports, path, parent):
            if node.get('server'):
                yield name, node, attrs

    click.echo(f"Reading template {template}...")
    with open(template, "rt") as inp:
        tpl = env.from_string(inp.read())
        click.echo(f"Writing output to {output}...")
        with open(output, "wt") as out:
            out.write(tpl.render(url_prefix=obj['url_prefix'], ports=ports, servers=servers))


@cli.command(help='Fetch all OSM objects from the model')
@click.option('--dir', '-d', envvar='OUTPUT_DIR', default=f'{DATA_DIR}/world', help='Output directory')
@click.pass_obj
def fetchall(obj, dir):
    os.makedirs(dir, exist_ok=True)

    for name, node, attrs in traverse('World', obj['model']):
        osm_id = node.get('osmId')
        if osm_id is None: continue

        print(f"Downloading {name}...", end='')
        sys.stdout.flush()
        gjsn = osm2geojson.json2geojson(search_overpass_by_id(osm_id))

        filename = f'{attrs["$path"]}.geojson'
        path = os.path.join(dir, filename)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wt') as f:
           f.write(json.dumps(gjsn, indent=4))

        print(f"{path}")


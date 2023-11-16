import click
import os
import json

@click.command(help='<geojson_folder> <output_directory>')
@click.argument('geojson_folder')
@click.argument('output_directory')
def main(geojson_folder, output_directory):
    all_file_data = {}
    
    for root, dirpath, files in os.walk(geojson_folder):
        for filename in files:
            if filename.endswith('.geojson'):
                file_path = os.path.join(root, filename)
                
                #Retrieve shortended state abbreviation from geojson file (ie New York = NY)
                with open(file_path, 'r') as file:
                    data = json.load(file)   
                for feature in data['features']:
                    if feature['properties'].get('type') == 'relation':
                        abbrev_state = feature['properties']['tags'].get('ISO3166-2')
                        if abbrev_state:
                            abbrev_state = abbrev_state.lower()

                #Sometimes the state abbreviation is NULL, such as for cases with countries (ie Italy, Germany, etc)    
                if abbrev_state:
                    url = f"http://lost-server-{abbrev_state}:5000"
                else:
                    url = f"http://lost-server-{os.path.splitext(filename)[0]}:5000"
                
                #Build the dictionary with file path as the key and the associated url as the value
                all_file_data[file_path] = url


    #write the file the the output directory specified by the user
    output_file_path = os.path.join(output_directory, "mapping.json")

    with open(output_file_path, 'w') as json_file:
        json.dump(all_file_data, json_file, indent=4)

    click.echo(f"JSON file created with mapping data: {output_file_path}")
    
if __name__ == "__main__":
    main()

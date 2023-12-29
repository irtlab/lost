import ResolverAPI from './resolver';
import { RasterImage } from '../state/image';
import { resolverApi } from '../config';
import { loadHTMLImage } from '../utils/image';


// Load the contents of the given file and return it in the form determined by
// the value of the method argument.
function readFile(file: File, method = 'readAsArrayBuffer') {
    return new Promise<ArrayBuffer>((resolve, reject) => {
        const f = new FileReader();
        f.onabort = reject;
        f.onerror = event => {
            f.abort();
            reject(new Error(`Error while reading file ${file.name}: ${event}`));
        };
        f.onload = event => {
            if (event.target === null) {
                reject(new Error(`Error while reading file ${file.name}`));
                return;
            }

            if (event.target.result === null) {
                reject(new Error(`Got null result while reading file ${file.name}`));
                return;
            }

            resolve(event.target.result as ArrayBuffer);
        };
        (f[method] as ((blob: Blob) => void)).apply(f, [file]);
    });
}


async function readImageFile(file: File, method = 'readAsDataURL') {
    // Try to re-create an Image from the file to make sure that the file really
    // is an image. The following step will fail if the file is not an image.
    const dataURL = await readFile(file, method);
    try {
        await loadHTMLImage(dataURL);
    } catch(e) {
        throw new Error(`Error while loading file ${file.name}, not an image file?`);
    }

    return dataURL;
}


export default class RasterImageAPI extends ResolverAPI {
    async getAllImages(): Promise<RasterImage[]> {
        return this.invoke('image', null, 'GET');
    };

    async deleteAllImages() {
        await this.invoke('image', null, 'DELETE');
    };

    async createImages(fileList: FileList): Promise<RasterImage[]> {
        const p: Promise<File>[] = [];

        for(let i = 0; i < fileList.length; i++)
            p.push((async () => {
                const file = fileList.item(i) as File;
                // Try to load all images with readImageFile to ensure they
                // really are image files.
                await readImageFile(file);
                return file;
            })());
        const files = await Promise.all(p);

        const body = new FormData();
        for(const file of files)
            body.append('file', file);

        const res = await fetch(`${resolverApi}/image`, {
            method: 'POST', body
        });
        const rv = await res.json();

        if (!res.ok) throw new Error(rv.message || res.statusText);
        return rv;
    };

    async deleteImage(id: string) {
        await this.invoke(`image/${id}`, null, 'DELETE');
    };
 
    async getImage(id: string): Promise<RasterImage> {
        return this.invoke(`image/${id}`, null, 'GET');
    };

    async updateImage(data: RasterImage): Promise<RasterImage> {
        return this.invoke(`image/${data.id}`, data, 'PUT');
    };

    async updateImages(data: RasterImage[]): Promise<RasterImage[]> {
        return this.invoke(`image`, data, 'PUT');
    };
}

import { resolverApi } from '../config';


export default class ResolverAPI {
    async invoke(endpoint: string, body: any = null, method = 'POST') {
        const headers = {};
        const params: any = { method, headers };

        if (body !== null) {
            headers['Content-Type'] = 'application/json';
            params.body = JSON.stringify(body);
        }

        const res = await fetch(`${resolverApi}/${endpoint}`, params);
        const data = await res.json();

        if (!res.ok) throw new Error(data.message || res.statusText);

        return data;
    }

    async sql(query: string) {
        return this.invoke('sql', query, 'POST');
    }
};



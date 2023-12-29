import ResolverAPI from './resolver';
import type { CoordinateTransform, TransformMatrix } from '../state/transform';
import type { Coordinates } from '../utils/coordinates';
import { ControlPointState } from '../state/control';


export default class TransformAPI extends ResolverAPI {
    private invokeWithControlLinks(transform: CoordinateTransform, points: ControlPointState, endpoint: string, body: any = {}, method = 'POST') {
        const links = Object.values(transform.controlLinks);

        return this.invoke(endpoint, {
            controlLinks: links.map(({ wgs84Point, imagePoint }) => {
                const ip = points[imagePoint].coordinates;
                const wp = points[wgs84Point].coordinates;
                return [ ip, wp ];
            }),
            ...body
        }, method);
    }

    async estimate(transform: CoordinateTransform, points: ControlPointState) {
        const data = await this.invokeWithControlLinks(transform, points, 'estimate');

        if (!('forward' in data) || !('backward' in data))
            throw new Error('Invalid response received from server');

        return {
            forward: data.forward as TransformMatrix,
            backward: data.backward as TransformMatrix
        }
    }

    async reproject(transform: CoordinateTransform, points: ControlPointState, url: string) {
        const data = await this.invokeWithControlLinks(transform, points, 'reproject', { url });

        if (!('bounds' in data) || !('url' in data))
            throw new Error('Invalid response received from server');

        return { bounds: data.bounds, url: data.url as string };
    }

    private transform(m: TransformMatrix, [ a, b ]: Coordinates): Coordinates {
        // floating point number to avoid division by zero.
        const d = (m[2][0] * a + m[2][1] * b + m[2][2]) || Number.MIN_VALUE,
            X = (m[0][0] * a + m[0][1] * b + m[0][2]) / d,
            Y = (m[1][0] * a + m[1][1] * b + m[1][2]) / d;

        return [ X, Y ];
    }

    toWGS84(m: TransformMatrix, p: Coordinates): Coordinates {
        return this.transform(m, p);
    }

    fromWGS84(m: TransformMatrix, p: Coordinates): Coordinates {
        return this.transform(m, p);
    }
}

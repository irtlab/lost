import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import API from '../api/image';
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';


export interface RasterImage {
    id         : string;
    name       : string | null;
    fileName   : string;
    width      : number;
    height     : number;
    size       : number;
    storageRef : string;
    src?       : string;
    created    : string;
    updated    : string;
}


export type ImageState = Record<string, RasterImage>;


export const image = createSlice({
    name: 'image',
    initialState: {} as ImageState,
    reducers: {
        create(state, { payload }: PayloadAction<RasterImage>) {
            state[payload.id] = payload;
        },
        setName(state, { payload: { id, name } }: PayloadAction<{ id: string, name: string }>) {
            const i = state[id];
            if (!i) throw Error('Invalid image ID');
            i.name = name;
        },
        delete(state, { payload: ids }: PayloadAction<string[]>) {
            ids.forEach(id => { delete state[id]; });
        }
    }
});


export const {
    setName: setImageName
} = image.actions;


export function uploadImages(fileList: FileList) {
    return async dispatch => {
        const api = new API();
        const rasterImages = await api.createImages(fileList);
        rasterImages.forEach(v => dispatch(image.actions.create(v)));
    };
}


export function update(state: ImageState) {
    const api = new API();
    return api.updateImages(Object.values(state));
}


export const imageApi = createApi({
    // The cache reducer expects to be added at `state.api` (already default - this is optional)
    reducerPath: 'image',
    baseQuery: fetchBaseQuery({ baseUrl: '/api/image' }),
    endpoints: builder => ({
        getImages: builder.query<ImageState, void>({
            query: () => '',
            transformResponse: (images: RasterImage[]): ImageState => {
                const rv = {};
                for(const image of images) rv[image.id] = image;
                return rv;
            }
        })
    })
});

// Export the auto-generated hook for the `getPosts` query endpoint
export const { useGetImagesQuery } = imageApi;
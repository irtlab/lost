import { configureStore } from '@reduxjs/toolkit';
import busy from './busy';
import { alert } from './alert';
import { controlPoint } from './control';
import { feature } from './feature';
import { shape } from './shape';
import { coordinateTransform } from './transform';
import { imageApi } from './image';


export const store = configureStore({
    reducer: {
        alert                  : alert.reducer,
        busy                   : busy.reducer,
        [imageApi.reducerPath] : imageApi.reducer
    },
    middleware: getDefaultMiddleware => getDefaultMiddleware().concat(imageApi.middleware)
});


// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
// Inferred type: {posts: PostsState, comments: CommentsState, users: UsersState}
export type AppDispatch = typeof store.dispatch;

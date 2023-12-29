// eslint-disable-next-line no-undef
module.exports = {
    resolverApi  : '/api',
    nominatimApi : 'https://nominatim.openstreetmap.org',
    overpassApi  : 'https://overpass-api.de/api/interpreter',

    defaultMapCenter: {
        lng : -73.96082,
        lat : 40.80963
    },

    defaultMapZoom : 20,
    maxNativeZoom: 19,
    maxZoom : 25,

    borderStyle: {
        borderRadius: '4px',
        border: '2px solid rgba(0,0,0,0.2)',
        backgroundClip: 'padding-box'
    }
};
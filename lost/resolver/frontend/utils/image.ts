export function loadHTMLImage(data) {
    return new Promise<HTMLImageElement>((resolve, reject) => {
        const i = new Image();

        i.onabort = reject;
        i.onerror = reject;
        i.onload = () => resolve(i);
        i.src = data;
    });
}

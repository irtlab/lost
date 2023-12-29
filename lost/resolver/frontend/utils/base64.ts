export function toBase64url(base64: string) {
    return base64.replace(/[+/]/g, c => {
        return {
            '+': '-',
            '/': '_'
        }[c] as string;
    });
}


export function toBase64(base64url: string) {
    return base64url.replace(/[-_]/g, c => {
        return {
            '-': '+',
            '_': '/'
        }[c] as string;
    });
}

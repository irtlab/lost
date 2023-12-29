import React from 'react';


interface ImageProps extends Omit<React.SVGProps<SVGSVGElement>, 'width'|'height'|'xmlns'|'ref'> {
    url: string;
    viewWidth: number;
    viewHeight: number;
}


/**
 * Show the selected plan enlarged to fit within the view port defined by
 * viewWidth and viewHeight and display the children on top of the plan.
 */
const Image = React.forwardRef<SVGSVGElement,ImageProps>(({
    url,
    viewWidth,
    viewHeight,
    children,
    ...props
}: ImageProps, ref) => {
    return (
        <svg {...props} ref={ref} width={viewWidth} height={viewHeight}
            xmlns='http://www.w3.org/2000/svg'
        >
            <image width={viewWidth} height={viewHeight} href={url} />
            {children}
        </svg>
    );
});

Image.displayName = 'Image';

export default Image;

import React, { forwardRef, Component, Children } from 'react';
import PropTypes from 'prop-types';
import ReactDOM from 'react-dom';
import elementResizeDetectorMaker from 'element-resize-detector';
import invariant from 'invariant';


//type DivProps = React.DetailedHTMLProps<React.HTMLAttributes<HTMLDivElement>, HTMLDivElement>;
type DivProps = React.HTMLAttributes<HTMLDivElement>;


export const Center = ({ children, style, ...props }: DivProps) => (
    <div style={{...style, width: '100%', height: '100%', position: 'relative'}} {...props}>
        <div style={{
            top: '50%',
            left: '50%',
            position: 'absolute',
            transform: 'translateY(-50%) translateX(-50%)'
        }}>
            {children}
        </div>
    </div>
);

export type StackProps = DivProps;

export const Stack = forwardRef<HTMLDivElement, StackProps>(({ children, style, ...props}: DivProps, ref) => (
    <div ref={ref} style={{ ...style, position: 'relative' }} {...props}>
        {children}
    </div>
));

Stack.displayName = 'Stack';


export interface OverlayProps extends Omit<DivProps,'ref'> {
    top?: number;
    left?: number;
}

export const Overlay = forwardRef<HTMLDivElement, OverlayProps>(({
    children,
    style,
    top = 0,
    left = 0,
    ...props
}: OverlayProps, ref) => (
    <div ref={ref} style={{ ...style, position: 'absolute', top, left }} {...props}>
        {children}
    </div>
));

Overlay.displayName = 'Overlay';


export function ErrorMessage({ children }: { children: any }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%', userSelect: 'none' }}>
            <Center style={{ flexGrow: 1 }}>
                <em>{children}</em>
            </Center>
        </div>
    );
}


export class ContainerDimensions extends Component {
    parentNode: any;
    elementResizeDetector: any;
    componentIsMounted: any;

    static propTypes = {
        children: PropTypes.oneOfType([PropTypes.element, PropTypes.func]).isRequired
    };

    static getDomNodeDimensions(node) {
        const { top, right, bottom, left, width, height } = node.getBoundingClientRect();
        return { top, right, bottom, left, width, height };
    }

    constructor(props) {
        super(props);

        this.state = {
            initiated: false
        };
        this.onResize = this.onResize.bind(this);
    }

    componentDidMount() {
        if (this === null) return;
        ReactDOM.findDOMNode(this);
        this.parentNode = ReactDOM.findDOMNode(this)!.parentNode;
        this.elementResizeDetector = elementResizeDetectorMaker({
            strategy: 'scroll',
            callOnAdd: false
        });
        this.elementResizeDetector.listenTo(this.parentNode, this.onResize);
        this.componentIsMounted = true;
        this.onResize();
    }

    componentWillUnmount() {
        this.componentIsMounted = false;
        this.elementResizeDetector.uninstall(this.parentNode);
    }

    onResize() {
        const clientRect = ContainerDimensions.getDomNodeDimensions(this.parentNode);
        if (this.componentIsMounted) {
            this.setState({
                initiated: true,
            ...clientRect
            });
        }
    }

    render() {
        invariant((this.props as any).children, 'Expected children to be one of function or React.Element');

        if (!(this.state as any).initiated) {
            return <div />;
        }

        if (typeof (this.props as any).children === 'function') {
            const renderedChildren = (this.props as any).children(this.state);
            return renderedChildren && Children.only(renderedChildren);
        }
        return Children.only(React.cloneElement((this.props as any).children, this.state));
    }
}
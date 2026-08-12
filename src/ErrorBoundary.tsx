import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Catches rendering errors anywhere below it in the tree and shows a
 * friendly fallback instead of an unstyled blank page.
 *
 * React error boundaries only catch errors thrown during rendering, in
 * lifecycle methods, and in constructors of the tree below them -- not
 * errors inside event handlers or async callbacks (those are already
 * handled locally in App.tsx via try/catch + toast). The two mechanisms are
 * complementary, not redundant: this one is the last line of defense for
 * anything neither of those paths caught.
 */
class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In a production deployment this is where you'd forward to an error
    // tracking service (Sentry, etc.); logging keeps this dependency-free.
    console.error('Unhandled error in component tree:', error, info.componentStack);
  }

  private handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 via-pink-50 to-purple-50 px-4">
          <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center border border-orange-100">
            <div className="w-14 h-14 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
              <AlertTriangle className="w-7 h-7 text-red-500" />
            </div>
            <h1 className="text-2xl font-bold text-gray-800 mb-2">Something went wrong</h1>
            <p className="text-gray-600 mb-6">
              An unexpected error interrupted the app. Nothing was uploaded or lost outside
              this page -- reloading will start you back at step one.
            </p>
            {this.state.error && (
              <pre className="text-xs text-left text-red-600 bg-red-50 rounded-lg p-3 mb-6 overflow-auto max-h-32">
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={this.handleReload}
              className="inline-flex items-center space-x-2 bg-gradient-to-r from-orange-500 to-pink-500 text-white px-6 py-3 rounded-lg font-semibold hover:from-orange-600 hover:to-pink-600 transition-all duration-300"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Reload the app</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

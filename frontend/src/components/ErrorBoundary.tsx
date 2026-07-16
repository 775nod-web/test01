import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label: string;
}

interface State {
  hasError: boolean;
}

/**
 * 各パネルの描画中に予期しないエラーが発生しても、画面全体をクラッシュさせず
 * この領域だけを日本語のフォールバック表示に切り替える。
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error(`[${this.props.label}] 表示中にエラーが発生しました`, error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <p className="panel__status panel__status--error">
          {this.props.label}の表示中にエラーが発生しました。他の操作は引き続き行えます。
        </p>
      );
    }
    return this.props.children;
  }
}

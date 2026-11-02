"""Start the local customer app: uv run python main.py."""
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description='ResolveGuard local customer app')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run('resolveguard.web:create_app', factory=True, host='127.0.0.1',
                port=args.port, workers=1)


if __name__ == '__main__':
    main()

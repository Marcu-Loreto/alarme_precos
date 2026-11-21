"""Alarme de Preços: monitor de passagens aéreas com SerpApi (Google Flights)."""

import logging
import os


def main() -> None:
    # Telemetria do Gradio desligada por padrão (precisa ser definida antes de importar o gradio).
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

    from .app import create_interface
    from .config import get_settings

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = get_settings()
    if settings.share and not settings.auth:
        raise SystemExit(
            "GRADIO_SHARE=true exige APP_AUTH_USER e APP_AUTH_PASSWORD no .env "
            "(o link público ficaria aberto para qualquer pessoa)."
        )
    if not settings.has_api_key:
        logging.getLogger(__name__).warning("SERPAPI_API_KEY ausente: rodando em MODO DEMONSTRAÇÃO.")
    demo, monitor = create_interface()
    monitor.start()
    try:
        demo.launch(
            share=settings.share,
            auth=settings.auth,
            server_name=settings.server_name,
            server_port=settings.server_port,
            debug=False,
            show_error=False,
        )
    finally:
        monitor.shutdown()

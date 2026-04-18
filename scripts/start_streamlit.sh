#!/usr/bin/env bash
set -euo pipefail
exec uv run streamlit run streamlit_app/app.py --server.port 8501

# Railway Procfile
# web: Service principal Streamlit
# worker: Scheduler pour les scans automatiques

web: streamlit run src/presentation/streamlit/dashboard.py --server.port=${PORT:-8501} --server.address=0.0.0.0
worker: python scheduler.py
